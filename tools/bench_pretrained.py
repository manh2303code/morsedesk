"""Đo model pretrain DeepCW trên bộ T1 để lấy mốc so sánh cho model tự huấn luyện (E3).

Chỉ là **thước đo**: DeepCW phát hành theo AGPL-3.0 nên model/mã của họ không được nhúng vào
MorseDesk. Script này chỉ nạp `model.onnx` + `model.onnx.json` từ một bản clone nằm ngoài repo.

Tiền xử lý bám đúng ví dụ tham chiếu `examples/python/decode_morse.py` của deepcw-engine:
resample về `sample_rate` trong metadata (3200 Hz), STFT `fft_length`=256 / `hop_length`=48,
cửa sổ Hann tuần hoàn, pad phản xạ `fft_length // 2`, lấy biên độ các bin trong 400–1200 Hz
(65 bin), chuẩn hóa `log1p`, rồi giải mã CTC greedy trên `log_probs`.

DeepCW chỉ xuất 41 lớp Latin (A–Z, 0–9, `,` `.` `/` `?`, khoảng trắng). Với profile Cyrillic
(ru, kk-cyrl-ru) kết quả được remap **chữ Latin -> mẫu chấm gạch -> chữ của profile đích** bằng
`morsedesk.data.text.translit_via_patterns`, đúng bảng mã của dự án.

Cách chạy (venv riêng trong scratchpad, KHÔNG dùng .venv của repo):

    uv venv <scratchpad>/venv-bench --python 3.11
    uv pip install --python <scratchpad>/venv-bench/Scripts/python.exe \
        "numpy>=1.24" "onnxruntime>=1.17" scipy pyyaml
    git clone https://github.com/e04/deepcw-engine <scratchpad>/deepcw-engine

    PYTHONUTF8=1 PYTHONPATH=<worktree> <scratchpad>/venv-bench/Scripts/python.exe \
        tools/bench_pretrained.py \
        --model <scratchpad>/deepcw-engine/model.onnx \
        --metadata <scratchpad>/deepcw-engine/model.onnx.json \
        --manifest C:/Users/Admin/morsedesk/testdata/generated/t1/manifest.jsonl \
        --out-dir runs/bench_deepcw

Kết quả: `<out-dir>/results.jsonl` (một dòng mỗi clip) và `<out-dir>/summary.json` với cùng cấu
trúc `by_profile/by_snr/by_wpm/by_channel/by_keying/pivot` như `runs/E3/t1_summary.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from morsedesk.bench import aggregate, gate, load_rows, pivot_snr_wpm
from morsedesk.metrics import cer, wer
from morsedesk.model.deepcw import (
    DEEPCW_MODEL_PATH,
    Remapper,
    audio_to_spectrogram,
    emissions_to_text,
    greedy_ctc_emissions,
    read_wav_mono,
    resample_to,
)
from morsedesk.textio import force_utf8_streams

# T1 sinh tone theo công thức của tools/make_t1.py: seed = 1000 + index.
T1_SEED_BASE = 1000


def tone_hz_for_seed(seed: int | None, seed_base: int = T1_SEED_BASE) -> float | None:
    """Tần số tone của clip T1 suy ra từ seed (xem `generate_matrix` trong tools/make_t1.py)."""
    if seed is None:
        return None
    return 500.0 + ((seed - seed_base) * 97) % 600


def resample_linear(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Nội suy tuyến tính — đúng như ví dụ tham chiếu (không chống chồng phổ)."""
    if src_rate == dst_rate or len(audio) == 0:
        return audio.astype(np.float32, copy=False)
    n = int(round(len(audio) * dst_rate / src_rate))
    pos = np.arange(n, dtype=np.float64) * src_rate / dst_rate
    left = np.floor(pos).astype(np.int64)
    right = np.minimum(left + 1, len(audio) - 1)
    frac = (pos - left).astype(np.float32)
    return (audio[left] * (1.0 - frac) + audio[right] * frac).astype(np.float32, copy=False)


def bandpass(audio: np.ndarray, rate: int, center_hz: float, width_hz: float, passes: int = 4) -> np.ndarray:
    """Biquad bandpass RBJ chạy `passes` lần — cùng công thức `applyBandpassFilter` của web app.

    Web app DeepCW cho người dùng khoanh tần số trên phổ trước khi giải mã; ví dụ dòng lệnh của
    deepcw-engine thì không, nên nó nghe cả dải 400–1200 Hz. Dùng cờ này để tách riêng ảnh hưởng
    của việc chọn băng (rõ nhất ở ô QRM) khỏi chất lượng model.
    """
    from scipy.signal import lfilter

    q = center_hz / width_hz
    omega = 2.0 * math.pi * center_hz / rate
    alpha = math.sin(omega) / (2.0 * q)
    b = np.array([alpha, 0.0, -alpha], dtype=np.float64) / (1.0 + alpha)
    a = np.array([1.0, -2.0 * math.cos(omega), 1.0 - alpha], dtype=np.float64) / (1.0 + alpha)
    out = audio.astype(np.float64, copy=False)
    for _ in range(passes):
        out = lfilter(b, a, out)
    return out.astype(np.float32, copy=False)


def unreachable_ratio(rows: list[dict], remap: Remapper, vocab: list[str]) -> dict[str, dict]:
    """Tỉ lệ ký tự tham chiếu nằm ngoài tập chữ DeepCW sinh được (sàn CER lý thuyết)."""
    per: dict[str, Counter] = {}
    for row in rows:
        per.setdefault(row.get("profile", "en"), Counter()).update(row["ref"].upper())
    out = {}
    for pid, counts in sorted(per.items()):
        ok = remap.reachable_chars(pid, vocab)
        bad = sum(n for ch, n in counts.items() if ch not in ok)
        total = sum(counts.values())
        out[pid] = {
            "n_chars": total,
            "n_unreachable": bad,
            "ratio": bad / max(1, total),
            "chars": "".join(sorted({ch for ch in counts if ch not in ok})),
        }
    return out


def decode_one(session, meta: dict, path: Path, resampler: str,
               band: tuple[float, float] | None = None) -> str:
    rate, audio = read_wav_mono(path)
    if band is not None:
        audio = bandpass(audio, rate, band[0], band[1])
    target = int(meta["sample_rate"])
    audio = resample_to(audio, rate, target) if resampler == "poly" else resample_linear(audio, rate, target)
    spec = audio_to_spectrogram(audio, meta)
    out = session.run([meta["onnx_output_name"]], {meta["onnx_input_name"]: spec})
    return emissions_to_text(greedy_ctc_emissions(out[0], list(meta["chars"]), int(meta["blank_index"])))


def evaluate(rows: list[dict], session, meta: dict, resampler: str, remap_cyrillic: bool,
             band_width_hz: float | None = None) -> list[dict]:
    remap = Remapper()
    results: list[dict] = []
    for i, row in enumerate(rows):
        pid = row.get("profile", "en")
        ref = row["text"]
        t0 = time.time()
        out = dict(row)
        out["ref"] = ref
        out["tone_hz"] = tone_hz_for_seed(row.get("seed"))
        band = (out["tone_hz"], band_width_hz) if band_width_hz and out["tone_hz"] else None
        try:
            latin = decode_one(session, meta, Path(row["path"]), resampler, band)
            hyp = remap(latin, pid) if remap_cyrillic else latin
            err = None
        except Exception as e:  # một clip hỏng không được làm mất cả lô
            latin, hyp, err = "", "", f"{type(e).__name__}: {e}"
        out.update({
            "hyp_latin": latin, "hyp": hyp, "cer": cer(ref, hyp), "wer": wer(ref, hyp),
            "seconds": time.time() - t0, "error": err,
        })
        results.append(out)
        if (i + 1) % 50 == 0:
            done = sum(r["cer"] for r in results) / len(results)
            print(f"  {i + 1}/{len(rows)} clip, CER trung bình {100 * done:.2f}%", flush=True)
    return results


def build_summary(results: list[dict], meta: dict, args: argparse.Namespace, elapsed: float) -> dict:
    ok, gate_cer, gate_n = gate(results, args.max_cer)
    in_band = [
        r for r in results
        if r["tone_hz"] is not None
        and float(meta["spectrogram_min_freq_hz"]) <= r["tone_hz"] <= float(meta["spectrogram_max_freq_hz"])
    ]
    remap = Remapper()
    return {
        "name": "deepcw",
        "model": str(args.model),
        "model_sha256": args.model_sha256,
        "engine_commit": args.engine_commit,
        "metadata": {k: v for k, v in meta.items() if k != "chars"},
        "resampler": args.resampler,
        "bandpass_width_hz": args.bandpass,
        "remap_cyrillic": not args.no_remap,
        "manifest": str(args.manifest),
        "n_rows": len(results),
        "mean_seconds": sum(r["seconds"] for r in results) / max(1, len(results)),
        "wall_seconds": elapsed,
        "errors": sum(1 for r in results if r.get("error")),
        "greedy": {
            "gate_ok": ok,
            "gate_cer": gate_cer,
            "n": gate_n,
            "mean_cer": sum(r["cer"] for r in results) / max(1, len(results)),
            "mean_wer": sum(r["wer"] for r in results) / max(1, len(results)),
            "by_profile": {k: v["cer"] for k, v in aggregate(results, "profile").items()},
            "by_channel": {k: v["cer"] for k, v in aggregate(results, "channel_actual").items()},
            "by_keying": {k: v["cer"] for k, v in aggregate(results, "keying").items()},
            "by_snr": {k: v["cer"] for k, v in aggregate(results, "snr").items()},
            "by_wpm": {k: v["cer"] for k, v in aggregate(results, "wpm").items()},
            "pivot": pivot_snr_wpm(results),
        },
        "tone_in_band": {
            "n": len(in_band),
            "n_total": len(results),
            "min_hz": min((r["tone_hz"] for r in results if r["tone_hz"] is not None), default=None),
            "max_hz": max((r["tone_hz"] for r in results if r["tone_hz"] is not None), default=None),
            "cer": sum(r["cer"] for r in in_band) / len(in_band) if in_band else None,
        },
        "unreachable": unreachable_ratio(results, remap, list(meta["chars"])),
    }


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Đo DeepCW pretrain trên T1 (thước đo, không nhúng)")
    ap.add_argument("--model", type=Path, default=DEEPCW_MODEL_PATH, help="mặc định models/deepcw/model.onnx")
    ap.add_argument("--metadata", type=Path, default=None, help="mặc định <model>.json")
    ap.add_argument("--manifest", type=Path, required=True, help="manifest.jsonl của T1")
    ap.add_argument("--out-dir", type=Path, default=Path("runs/bench_deepcw"))
    ap.add_argument("--limit", type=int, default=None, help="chỉ chạy N clip đầu")
    ap.add_argument("--resampler", choices=("poly", "linear"), default="poly",
                    help="poly = scipy resample_poly (chống chồng phổ); linear = như ví dụ gốc")
    ap.add_argument("--bandpass", type=float, default=None, metavar="HZ",
                    help="lọc dải quanh tone thật của clip (oracle, suy từ seed) trước khi giải mã")
    ap.add_argument("--no-remap", action="store_true", help="không remap Latin -> Cyrillic")
    ap.add_argument("--max-cer", type=float, default=0.02, help="ngưỡng gate để so với E3")
    ap.add_argument("--engine-commit", default="", help="commit của bản clone deepcw-engine")
    ap.add_argument("--model-sha256", default="", help="sha256 của model.onnx")
    args = ap.parse_args(argv)
    if args.metadata is None:
        args.metadata = Path(str(args.model) + ".json")

    import onnxruntime as ort

    meta = json.loads(args.metadata.read_text(encoding="utf-8"))
    rows = load_rows(args.manifest)
    if args.limit:
        rows = rows[: args.limit]
    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])

    t0 = time.time()
    results = evaluate(rows, session, meta, args.resampler, not args.no_remap, args.bandpass)
    elapsed = time.time() - t0
    summary = build_summary(results, meta, args, elapsed)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with open(args.out_dir / "results.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    g = summary["greedy"]
    print(g["pivot"])
    for key in ("by_profile", "by_channel", "by_keying", "by_snr", "by_wpm"):
        print(f"{key}: " + ", ".join(f"{k}={100 * v:.2f}%" for k, v in g[key].items()))
    for pid, info in summary["unreachable"].items():
        print(f"ngoài bảng Latin {pid}: {100 * info['ratio']:.2f}% ký tự ({info['chars']})")
    print(f"n={len(results)} CER={100 * g['mean_cer']:.2f}% WER={100 * g['mean_wer']:.2f}% "
          f"lỗi={summary['errors']} {summary['mean_seconds']:.3f}s/clip -> {args.out_dir}")
    print(f"gate (SNR>=0, 10-35 WPM, n={g['n']}): CER={100 * g['gate_cer']:.2f}% "
          f"{'ĐẠT' if g['gate_ok'] else 'TRƯỢT'} (ngưỡng {100 * args.max_cer:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
