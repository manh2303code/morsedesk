"""Huấn luyện CTC on-the-fly bằng SynthGenerator; checkpoint tốt nhất theo token error rate.

Chế độ đặc trưng 'window' (mặc định) tính tone và chuẩn hóa theo cửa sổ 4 s như lúc suy luận;
'clip' là cách của tuần 1–2. Lịch LR: constant hoặc cosine, có warmup. --resume khôi phục optimizer
và bước nếu checkpoint có (checkpoint cũ chỉ nạp trọng số).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

from morsedesk.constants import HOP
from morsedesk.data.channel import HARD_QSB_SAMPLING, ChannelSampling
from morsedesk.data.synth import Example, SynthConfig, SynthGenerator
from morsedesk.dsp.frontend import (
    FrontendConfig,
    compute_features,
    compute_features_windowed,
    stitch_windows,
    window_cfg,
)
from morsedesk.dsp.tone import estimate_tone
from morsedesk.metrics import edit_distance
from morsedesk.model.ctc import greedy_decode
from morsedesk.model.vocab import VOCAB
from morsedesk.textio import force_utf8_streams
from tools.net_torch import CONFIG_DEFAULT, MorseNet, count_params, output_length

FEATURE_MODES = ("clip", "window")
DEFAULT_FEATURE_MODE = "window"
VAL_SEED_BASE = 2_000_000_000  # seed validation tách hẳn khỏi dải seed train (seed*1e6 + steps*batch)


def sampling_for(qsb_hard: bool) -> ChannelSampling | None:
    """None = phân bố mặc định tuần 1–4 (giữ nguyên hành vi cũ khi không truyền cờ)."""
    return HARD_QSB_SAMPLING if qsb_hard else None


def example_features(ex: Example, mode: str = DEFAULT_FEATURE_MODE, agc_tau_s: float = 1.0) -> np.ndarray:
    """Đặc trưng như lúc chạy thật. 'window': tone và chuẩn hóa theo cửa sổ, ghép theo khung, tone
    thật làm gợi ý khi cửa sổ không dò được; 'clip': tone toàn cục."""
    if mode == "window":
        n_frames = len(ex.audio) // HOP
        return stitch_windows(
            compute_features_windowed(ex.audio, f0_hint=ex.f0_hz, cfg=window_cfg(agc_tau_s)), n_frames)
    if mode != "clip":
        raise ValueError(f"feature_mode lạ: {mode}")
    est = estimate_tone(ex.audio)
    f0 = est.f0_hz if est.has_signal and est.f0_hz is not None else ex.f0_hz
    return compute_features(ex.audio, f0, cfg=FrontendConfig(agc_tau_s=agc_tau_s))


class SynthDataset(IterableDataset):
    def __init__(self, gen: SynthGenerator, seed_start: int, n_items: int,
                 feature_mode: str = DEFAULT_FEATURE_MODE, agc_tau_s: float = 1.0) -> None:
        self.gen, self.seed_start, self.n_items = gen, seed_start, n_items
        self.feature_mode, self.agc_tau_s = feature_mode, agc_tau_s

    def __iter__(self):
        info = get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        for k in range(wid, self.n_items, nw):
            ex = self.gen.generate(self.seed_start + k)
            yield (torch.from_numpy(example_features(ex, self.feature_mode, self.agc_tau_s)),
                   torch.tensor(ex.labels, dtype=torch.long), ex.tokens)


def collate(batch):
    feats = [b[0] for b in batch]
    t_max = max(f.shape[0] for f in feats)
    padded = torch.zeros(len(feats), t_max, feats[0].shape[1])
    for i, f in enumerate(feats):
        padded[i, : f.shape[0]] = f
    feat_lens = torch.tensor([output_length(f.shape[0]) for f in feats], dtype=torch.long)
    targets = torch.cat([b[1] for b in batch])
    target_lens = torch.tensor([len(b[1]) for b in batch], dtype=torch.long)
    return padded, feat_lens, targets, target_lens, [b[2] for b in batch]


@torch.no_grad()
def token_error_rate(model: nn.Module, items: list[tuple[torch.Tensor, list[str]]]) -> float:
    model.eval()
    errs = total = 0
    for feats, tokens in items:
        logp = model(feats[None])[0].cpu().numpy()
        hyp = [VOCAB.token(i) for i in greedy_decode(logp)]
        errs += edit_distance(tokens, hyp)
        total += len(tokens)
    model.train()
    return errs / max(1, total)


def lr_at(step: int, base_lr: float, total_steps: int, schedule: str = "constant", warmup: int = 0,
          min_ratio: float = 0.05) -> float:
    """LR tại bước step (1-based): warmup tuyến tính, rồi constant hoặc cosine xuống base_lr*min_ratio."""
    if schedule not in ("constant", "cosine"):
        raise ValueError(f"lịch LR lạ: {schedule}")
    if warmup > 0 and step <= warmup:
        return base_lr * step / warmup
    if schedule == "constant":
        return base_lr
    span = max(1, total_steps - warmup)
    progress = min(1.0, max(0.0, (step - warmup) / span))
    return base_lr * (min_ratio + (1.0 - min_ratio) * 0.5 * (1.0 + math.cos(math.pi * progress)))


def save_ckpt(path: Path, model: nn.Module, step: int, val_ter: float, config: dict, opt=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"state_dict": model.state_dict(), "step": step, "val_ter": val_ter, "config": dict(config)}
    if opt is not None:
        payload["optimizer"] = opt.state_dict()
    torch.save(payload, path)


def load_ckpt(path: Path) -> dict:
    return torch.load(path, map_location="cpu", weights_only=True)


def train_loop(model, loader, opt, ctc, steps, val_items, run_dir: Path, config: dict, log_every=50,
               val_every=500, start_step: int = 0, lr_fn=None, history: list[dict] | None = None) -> dict:
    history = list(history or [])
    best = min([h["val_ter"] for h in history], default=float("inf"))
    step = start_step
    t0 = time.time()
    for feats, feat_lens, targets, target_lens, _ in loader:
        step += 1
        if lr_fn is not None:
            lr = lr_fn(step)
            for g in opt.param_groups:
                g["lr"] = lr
        logp = model(feats)
        loss = ctc(logp.transpose(0, 1), targets, feat_lens, target_lens)
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % log_every == 0:
            print(f"step {step} loss {loss.item():.4f} lr {opt.param_groups[0]['lr']:.2e} ({time.time() - t0:.0f}s)",
                  flush=True)
        if step % val_every == 0 or step == steps:
            ter = token_error_rate(model, val_items)
            history.append({"step": step, "loss": loss.item(), "val_ter": ter,
                            "lr": opt.param_groups[0]["lr"], "elapsed_s": time.time() - t0})
            save_ckpt(run_dir / "last.pt", model, step, ter, config, opt)
            if ter < best:
                best = ter
                save_ckpt(run_dir / "best.pt", model, step, ter, config, opt)
            print(f"step {step} val TER {100 * ter:.2f}% (best {100 * best:.2f}%)", flush=True)
            (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        if step >= steps:
            break
    (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    return {"best_ter": best, "steps": step, "hours": (time.time() - t0) / 3600}


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Huấn luyện MorseNet bằng dữ liệu tổng hợp")
    ap.add_argument("--name", default="v1")
    ap.add_argument("--steps", type=int, default=20000, help="tổng số bước đích (kể cả bước đã có khi resume)")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--lr-schedule", choices=["constant", "cosine"], default="constant")
    ap.add_argument("--warmup", type=int, default=0, help="số bước warmup tuyến tính")
    ap.add_argument("--hidden", type=int, default=CONFIG_DEFAULT["hidden"])
    ap.add_argument("--feature-mode", choices=FEATURE_MODES, default=DEFAULT_FEATURE_MODE)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--val-clips", type=int, default=200)
    ap.add_argument("--val-every", type=int, default=500)
    ap.add_argument("--workers", type=int, default=0, help="DataLoader workers (0 an toàn trên Windows)")
    ap.add_argument("--no-mp3", action="store_true")
    ap.add_argument("--qsb-hard", action="store_true",
                    help="lấy mẫu QSB đúng độ khó ô qsb của T1 (E6): 60 %% clip, sâu 10–24 dB, chu kỳ 2–8 s")
    ap.add_argument("--agc-tau", type=float, default=1.0,
                    help="hằng số thời gian AGC (giây) dùng cả khi huấn luyện lẫn suy luận (E7)")
    ap.add_argument("--resume", type=Path, default=None,
                    help="checkpoint để tiếp tục; --lr/--lr-schedule/--warmup/--steps không lưu "
                         "trong checkpoint nên phải truyền lại đúng như lần chạy trước")
    a = ap.parse_args(argv)

    assert a.seed * 1_000_000 + a.steps * a.batch < VAL_SEED_BASE, "seed/steps quá lớn: trùng dải seed validation"

    torch.manual_seed(a.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    config = dict(CONFIG_DEFAULT, hidden=a.hidden, feature_mode=a.feature_mode,
                  qsb_hard=bool(a.qsb_hard), agc_tau_s=float(a.agc_tau))
    model = MorseNet(config["feat_dim"], config["n_classes"], config["hidden"])
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr)
    run_dir = Path("runs") / a.name
    start_step = 0
    history: list[dict] = []
    if a.resume:
        ckpt = load_ckpt(a.resume)
        ck_cfg = dict(CONFIG_DEFAULT, **ckpt.get("config", {}))
        if ck_cfg["hidden"] != a.hidden:
            raise SystemExit(f"--hidden {a.hidden} khác checkpoint ({ck_cfg['hidden']})")
        model.load_state_dict(ckpt["state_dict"])
        if "optimizer" in ckpt:
            opt.load_state_dict(ckpt["optimizer"])
            start_step = int(ckpt.get("step", 0))
            hist_path = Path(a.resume).resolve().parent / "history.json"
            if hist_path.exists() and Path(a.resume).resolve().parent == run_dir.resolve():
                history = json.loads(hist_path.read_text(encoding="utf-8"))
            print(f"tiếp tục từ bước {start_step} (optimizer khôi phục)")
        else:
            print("checkpoint cũ: chỉ nạp trọng số, bước bắt đầu 0")
        if ck_cfg.get("feature_mode", "clip") != a.feature_mode:
            print(f"cảnh báo: checkpoint feature_mode={ck_cfg.get('feature_mode', 'clip')}, đang train {a.feature_mode}")
    if start_step >= a.steps:
        raise SystemExit(f"--steps ({a.steps}) phải lớn hơn bước đã có trong checkpoint ({start_step})")
    print(f"tham số: {count_params(model):,} (hidden {a.hidden}, feature_mode {a.feature_mode})")

    gen = SynthGenerator(SynthConfig(mp3_enabled=not a.no_mp3, channel_sampling=sampling_for(a.qsb_hard)))
    val_items = []
    for i in range(a.val_clips):
        ex = gen.generate(VAL_SEED_BASE + i)
        val_items.append((torch.from_numpy(example_features(ex, a.feature_mode, a.agc_tau)), ex.tokens))

    ds = SynthDataset(gen, seed_start=a.seed * 1_000_000 + start_step * a.batch,
                      n_items=(a.steps - start_step) * a.batch, feature_mode=a.feature_mode,
                      agc_tau_s=a.agc_tau)
    loader = DataLoader(ds, batch_size=a.batch, collate_fn=collate, num_workers=a.workers)
    ctc = nn.CTCLoss(blank=VOCAB.blank_id, zero_infinity=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "args.json").write_text(json.dumps(vars(a), default=str, indent=2), encoding="utf-8")

    def lr_fn(step: int) -> float:
        return lr_at(step, a.lr, a.steps, a.lr_schedule, a.warmup)

    result = train_loop(model, loader, opt, ctc, a.steps, val_items, run_dir, config, val_every=a.val_every,
                        start_step=start_step, lr_fn=lr_fn, history=history)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
