"""Đánh giá một run huấn luyện trên T1: xuất ONNX tạm (models/eval_<name>.onnx), bench greedy và
beam+LM (nếu đủ models/lm/*.bin), ghi runs/<name>/t1_summary.json và in một dòng bảng markdown."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from morsedesk.bench import aggregate, evaluate, gate, load_rows, pivot_snr_wpm
from morsedesk.lm.store import LMStore
from morsedesk.textio import force_utf8_streams
from tools.export_onnx import export

PROFILE_IDS = ("en", "ru", "kk-cyrl-ru")


def lm_ready(lm_dir: Path | None = None) -> bool:
    store = LMStore(lm_dir)
    return all(store.available(pid) for pid in PROFILE_IDS)


def summarize(results: list[dict]) -> dict:
    ok, cer_gate, n = gate(results)

    def cer_by(key: str) -> dict[str, float]:
        return {k: v["cer"] for k, v in aggregate(results, key).items()}

    return {
        "gate_ok": ok, "gate_cer": cer_gate, "n": n,
        "mean_seconds": sum(r["seconds"] for r in results) / max(1, len(results)),
        "by_profile": cer_by("profile"), "by_channel": cer_by("channel_actual"), "by_keying": cer_by("keying"),
        "by_snr": cer_by("snr"), "by_wpm": cer_by("wpm"),
        "pivot": pivot_snr_wpm(results) if results else "",
    }


def evaluate_run(run_dir: Path, manifest: Path, name: str | None = None, with_lm: bool = True,
                 lm_dir: Path | None = None, models_dir: Path = Path("models"), limit: int | None = None,
                 checkpoint: str = "best.pt") -> dict:
    name = name or run_dir.name
    ckpt = run_dir / checkpoint
    onnx_path = models_dir / f"eval_{name}.onnx"
    export(ckpt, onnx_path, version=f"eval-{name}")
    meta = json.loads(onnx_path.with_suffix(".json").read_text(encoding="utf-8"))
    rows = load_rows(manifest)
    t0 = time.time()
    greedy = evaluate(rows, "onnx", onnx_path, limit, lm=False)
    out = {
        "name": name, "checkpoint": str(ckpt), "onnx": str(onnx_path), "train_step": meta.get("train_step"),
        "val_ter": meta.get("val_ter"), "config": meta.get("config"), "feature_mode": meta.get("feature_mode"),
        "manifest": str(manifest), "n_rows": len(greedy), "greedy": summarize(greedy), "lm": None,
        "eval_seconds": None,
    }
    if with_lm and lm_ready(lm_dir):
        out["lm"] = summarize(evaluate(rows, "onnx", onnx_path, limit, lm=True, lm_dir=lm_dir))
    out["eval_seconds"] = time.time() - t0
    (run_dir / "t1_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _pct(v: float | None) -> str:
    return "–" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{100 * v:.2f}%"


def markdown_row(s: dict) -> str:
    cfg = s.get("config") or {}
    lm = s.get("lm")
    prof = s["greedy"]["by_profile"]
    per_profile = " / ".join(_pct(prof.get(p)) for p in PROFILE_IDS)
    return (f"| {s['name']} | {cfg.get('hidden')} | {s.get('feature_mode')} | {s.get('train_step')} | "
            f"{_pct(s.get('val_ter'))} | {_pct(s['greedy']['gate_cer'])} | "
            f"{_pct(lm['gate_cer']) if lm else '–'} | {per_profile} |")


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Đánh giá run trên T1")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--manifest", type=Path, default=Path("testdata/generated/t1/manifest.jsonl"))
    ap.add_argument("--no-lm", action="store_true")
    ap.add_argument("--lm-dir", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--checkpoint", default="best.pt")
    a = ap.parse_args(argv)
    s = evaluate_run(a.run, a.manifest, a.name, not a.no_lm, a.lm_dir, limit=a.limit, checkpoint=a.checkpoint)
    print("greedy:\n" + s["greedy"]["pivot"])
    if s["lm"]:
        print("beam+LM:\n" + s["lm"]["pivot"])
    print(markdown_row(s))
    print(f"-> {a.run / 't1_summary.json'} ({s['eval_seconds']:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
