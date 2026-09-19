"""Đo CER/WER trên manifest JSONL theo ô SNR × WPM × kiểu gõ × kênh; gate vùng mục tiêu."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from morsedesk.api import Decoder
from morsedesk.metrics import cer, wer


def load_rows(manifest: Path) -> list[dict]:
    with open(manifest, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(rows: list[dict], engine: str = "baseline", model_path: Path | None = None,
             limit: int | None = None) -> list[dict]:
    decoders: dict[str, Decoder] = {}
    results = []
    for row in rows[:limit] if limit else rows:
        pid = row.get("profile", "en")
        if pid not in decoders:
            decoders[pid] = Decoder(pid, engine=engine, model_path=model_path)
        t0 = time.time()
        out = dict(row)
        try:
            r = decoders[pid].decode_file(row["path"])
        except Exception as e:  # một file hỏng không được làm mất cả lô
            out.update({
                "hyp": "", "cer": cer(row["text"], ""), "wer": wer(row["text"], ""),
                "wpm_est": None, "seconds": time.time() - t0, "warnings": [],
                "error": f"{type(e).__name__}: {e}",
            })
            results.append(out)
            continue
        out.update({
            "hyp": r.text, "cer": cer(row["text"], r.text), "wer": wer(row["text"], r.text),
            "wpm_est": r.wpm, "seconds": time.time() - t0, "warnings": r.warnings, "error": None,
        })
        results.append(out)
    return results


def _is_number(s: str) -> bool:
    try:
        float(s)
    except ValueError:
        return False
    return True


def aggregate(results: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[str(r.get(key, "n/a"))].append(r)
    return {
        k: {"n": len(v), "cer": sum(x["cer"] for x in v) / len(v), "wer": sum(x["wer"] for x in v) / len(v)}
        for k, v in sorted(
            groups.items(),
            key=lambda kv: (0, float(kv[0])) if _is_number(kv[0]) else (1, kv[0]),
        )
    }


def pivot_snr_wpm(results: list[dict]) -> str:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in results:
        cells[(str(r.get("snr", "n/a")), str(r.get("wpm", "n/a")))].append(r["cer"])
    snrs = sorted({k[0] for k in cells}, key=lambda s: float(s) if s != "n/a" else 1e9)
    wpms = sorted({k[1] for k in cells}, key=lambda s: float(s) if s != "n/a" else 1e9)
    lines = ["CER % theo SNR (hàng) x WPM (cột)", "SNR\\WPM " + " ".join(f"{w:>7}" for w in wpms)]
    for s in snrs:
        vals = []
        for w in wpms:
            v = cells.get((s, w))
            vals.append(f"{100 * sum(v) / len(v):7.2f}" if v else f"{'-':>7}")
        lines.append(f"{s:>7} " + " ".join(vals))
    return "\n".join(lines)


def gate(results: list[dict], max_cer: float = 0.02, snr_min: float = 0.0,
         wpm_min: float = 10.0, wpm_max: float = 35.0) -> tuple[bool, float, int]:
    sub = [r for r in results
           if isinstance(r.get("snr"), (int, float)) and isinstance(r.get("wpm"), (int, float))
           and r["snr"] >= snr_min and wpm_min <= r["wpm"] <= wpm_max]
    if not sub:
        return False, 1.0, 0
    mean = sum(r["cer"] for r in sub) / len(sub)
    return mean <= max_cer, mean, len(sub)


def run(manifest: Path, engine: str, model_path: Path | None, out_dir: Path,
        limit: int | None, do_gate: bool, max_cer: float) -> tuple[dict, bool]:
    results = evaluate(load_rows(manifest), engine, model_path, limit)
    ok, gate_cer, gate_n = gate(results, max_cer)
    summary = {
        "engine": engine, "manifest": str(manifest), "n": len(results),
        "mean_cer": sum(r["cer"] for r in results) / max(1, len(results)),
        "mean_wer": sum(r["wer"] for r in results) / max(1, len(results)),
        "errors": sum(1 for r in results if r.get("error")),
        "gate": {"ok": ok, "cer": gate_cer, "n": gate_n, "max_cer": max_cer},
        "by_snr": aggregate(results, "snr"), "by_wpm": aggregate(results, "wpm"),
        "by_keying": aggregate(results, "keying"), "by_channel": aggregate(results, "channel_actual"),
        "by_profile": aggregate(results, "profile"), "rows": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"bench_{engine}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(pivot_snr_wpm(results))
    for key in ("by_keying", "by_channel", "by_profile"):
        print(key + ": " + ", ".join(f"{k}={100 * v['cer']:.2f}%" for k, v in summary[key].items()))
    print(f"n={len(results)} CER={100 * summary['mean_cer']:.2f}% WER={100 * summary['mean_wer']:.2f}% lỗi={summary['errors']} -> {out}")
    if do_gate:
        print(f"gate (SNR>=0, 10-35 WPM, n={gate_n}): CER={100 * gate_cer:.2f}% "
              f"{'ĐẠT' if ok else 'TRƯỢT'} (ngưỡng {100 * max_cer:.2f}%)")
    return summary, ok if do_gate else True
