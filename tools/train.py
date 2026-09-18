"""Huấn luyện CTC on-the-fly bằng SynthGenerator; checkpoint tốt nhất theo token error rate."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

from morsedesk.data.synth import Example, SynthConfig, SynthGenerator
from morsedesk.dsp.frontend import compute_features
from morsedesk.dsp.tone import estimate_tone
from morsedesk.metrics import edit_distance
from morsedesk.model.ctc import greedy_decode
from morsedesk.model.vocab import VOCAB
from morsedesk.textio import force_utf8_streams
from tools.net_torch import CONFIG_DEFAULT, MorseNet, count_params, output_length


def example_features(ex: Example) -> np.ndarray:
    """Đặc trưng như lúc chạy thật: dùng tone dò được, rơi về tone thật nếu dò thất bại."""
    est = estimate_tone(ex.audio)
    f0 = est.f0_hz if est.has_signal and est.f0_hz is not None else ex.f0_hz
    return compute_features(ex.audio, f0)


class SynthDataset(IterableDataset):
    def __init__(self, gen: SynthGenerator, seed_start: int, n_items: int) -> None:
        self.gen, self.seed_start, self.n_items = gen, seed_start, n_items

    def __iter__(self):
        info = get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        for k in range(wid, self.n_items, nw):
            ex = self.gen.generate(self.seed_start + k)
            yield torch.from_numpy(example_features(ex)), torch.tensor(ex.labels, dtype=torch.long), ex.tokens


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


def save_ckpt(path: Path, model: nn.Module, step: int, val_ter: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "step": step, "val_ter": val_ter,
                "config": CONFIG_DEFAULT}, path)


def train_loop(model, loader, opt, ctc, steps, val_items, run_dir: Path, log_every=50, val_every=500) -> dict:
    history = []
    best = float("inf")
    step = 0
    t0 = time.time()
    for feats, feat_lens, targets, target_lens, _ in loader:
        logp = model(feats)
        loss = ctc(logp.transpose(0, 1), targets, feat_lens, target_lens)
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        step += 1
        if step % log_every == 0:
            print(f"step {step} loss {loss.item():.4f} ({time.time() - t0:.0f}s)", flush=True)
        if step % val_every == 0 or step == steps:
            ter = token_error_rate(model, val_items)
            history.append({"step": step, "loss": loss.item(), "val_ter": ter})
            save_ckpt(run_dir / "last.pt", model, step, ter)
            if ter < best:
                best = ter
                save_ckpt(run_dir / "best.pt", model, step, ter)
            print(f"step {step} val TER {100 * ter:.2f}% (best {100 * best:.2f}%)", flush=True)
        if step >= steps:
            break
    (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    return {"best_ter": best, "steps": step}


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Huấn luyện MorseNet bằng dữ liệu tổng hợp")
    ap.add_argument("--name", default="v1")
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--val-clips", type=int, default=200)
    ap.add_argument("--val-every", type=int, default=500)
    ap.add_argument("--workers", type=int, default=0, help="DataLoader workers (0 an toàn trên Windows)")
    ap.add_argument("--no-mp3", action="store_true")
    ap.add_argument("--resume", type=Path, default=None)
    a = ap.parse_args(argv)

    torch.manual_seed(a.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    gen = SynthGenerator(SynthConfig(mp3_enabled=not a.no_mp3))
    model = MorseNet(**CONFIG_DEFAULT)
    if a.resume:
        model.load_state_dict(torch.load(a.resume, map_location="cpu", weights_only=True)["state_dict"])
    print(f"tham số: {count_params(model):,}")

    val_items = []
    for i in range(a.val_clips):
        ex = gen.generate(10_000_000 + i)
        val_items.append((torch.from_numpy(example_features(ex)), ex.tokens))

    ds = SynthDataset(gen, seed_start=a.seed * 1_000_000, n_items=a.steps * a.batch)
    loader = DataLoader(ds, batch_size=a.batch, collate_fn=collate, num_workers=a.workers)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr)
    ctc = nn.CTCLoss(blank=VOCAB.blank_id, zero_infinity=True)
    run_dir = Path("runs") / a.name
    result = train_loop(model, loader, opt, ctc, a.steps, val_items, run_dir, val_every=a.val_every)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
