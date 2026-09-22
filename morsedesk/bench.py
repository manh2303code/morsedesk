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


def reference_text(row: dict, engine: str, lm: bool) -> str:
    """Chuỗi tham chiếu: `text_original` (chữ gốc trước khi render qua profile — Ә, Ғ, Қ... của
    Kazakh, Ъ của Nga) khi engine onnx có LM, còn lại `text` đã render qua profile."""
    if engine == "onnx" and lm and row.get("text_original"):
        return row["text_original"]
    return row["text"]


def evaluate(rows: list[dict], engine: str = "baseline", model_path: Path | None = None,
             limit: int | None = None, profile_override: str | None = None, lm: bool = True,
             beam: int = 64, lm_dir: Path | None = None) -> list[dict]:
    decoders: dict[str, Decoder] = {}
    results = []
    for row in rows[:limit] if limit else rows:
        pid = profile_override or row.get("profile", "en")
        if pid not in decoders:
            decoders[pid] = Decoder(pid, engine=engine, model_path=model_path, lm=lm, beam=beam, lm_dir=lm_dir)
        ref = reference_text(row, engine, lm)
        truth = row.get("profile")
        t0 = time.time()
        out = dict(row)
        out["ref"] = ref
        try:
            r = decoders[pid].decode_file(row["path"])
        except Exception as e:  # một file hỏng không được làm mất cả lô
            out.update({
                "hyp": "", "cer": cer(ref, ""), "wer": wer(ref, ""), "wpm_est": None,
                "seconds": time.time() - t0, "warnings": [], "language": None,
                "language_correct": None, "error": f"{type(e).__name__}: {e}",
            })
            results.append(out)
            continue
        out.update({
            "hyp": r.text, "cer": cer(ref, r.text), "wer": wer(ref, r.text), "wpm_est": r.wpm,
            "seconds": time.time() - t0, "warnings": r.warnings, "language": r.language,
            # thiếu khóa "profile" (không rõ nhãn đúng) -> None, không phải False
            "language_correct": (r.language == truth) if (profile_override == "auto" and truth is not None)
            else None,
            "error": None,
        })
        results.append(out)
    return results


def language_accuracy(results: list[dict]) -> float | None:
    judged = [r["language_correct"] for r in results if r.get("language_correct") is not None]
    return sum(1 for j in judged if j) / len(judged) if judged else None


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


# Ngưỡng theo rà soát D4: ARRL < 2 %, QSO tay < 10 %. Manifest T2 không có cột `snr` nên
# `gate()` (lọc theo SNR/WPM) không dùng được cho T2; gate theo nguồn thay thế.
T2_MAX_CER = {"arrl": 0.02, "commons": 0.10, "sraa": 0.10, "qso": 0.10,
              "ebook2cw": 0.02, "ebook2cw_kk": 0.02}
DEFAULT_T2_MAX_CER = 0.10


def source_gate(results: list[dict], max_cer: dict[str, float] | None = None) -> dict[str, dict]:
    table = dict(T2_MAX_CER)
    table.update(max_cer or {})
    out: dict[str, dict] = {}
    for src, agg in aggregate(results, "source").items():
        limit = table.get(src, DEFAULT_T2_MAX_CER)
        out[src] = {"n": agg["n"], "cer": agg["cer"], "wer": agg["wer"],
                    "max_cer": limit, "ok": agg["cer"] <= limit}
    return out


def run(manifest: Path, engine: str, model_path: Path | None, out_dir: Path,
        limit: int | None, do_gate: bool, max_cer: float, profile_override: str | None = None,
        lm: bool = True, beam: int = 64, lm_dir: Path | None = None,
        t2_gate: bool = False) -> tuple[dict, bool]:
    results = evaluate(load_rows(manifest), engine, model_path, limit, profile_override, lm, beam, lm_dir)
    ok, gate_cer, gate_n = gate(results, max_cer)
    summary = {
        "engine": engine, "manifest": str(manifest), "n": len(results),
        "mean_cer": sum(r["cer"] for r in results) / max(1, len(results)),
        "mean_wer": sum(r["wer"] for r in results) / max(1, len(results)),
        "errors": sum(1 for r in results if r.get("error")),
        "gate": {"ok": ok, "cer": gate_cer, "n": gate_n, "max_cer": max_cer},
        "by_snr": aggregate(results, "snr"), "by_wpm": aggregate(results, "wpm"),
        "by_keying": aggregate(results, "keying"), "by_channel": aggregate(results, "channel_actual"),
        "by_profile": aggregate(results, "profile"),
        "by_source": aggregate(results, "source"),
        "source_gate": source_gate(results) if t2_gate else None,
        "rows": results,
        "profile_override": profile_override, "lm": lm, "beam": beam,
        "language_acc": language_accuracy(results),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = ("_lm" if lm and engine == "onnx" else "") + ("_auto" if profile_override == "auto" else "")
    out = out_dir / f"bench_{engine}{suffix}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(pivot_snr_wpm(results))
    for key in ("by_keying", "by_channel", "by_profile"):
        print(key + ": " + ", ".join(f"{k}={100 * v['cer']:.2f}%" for k, v in summary[key].items()))
    print(f"n={len(results)} CER={100 * summary['mean_cer']:.2f}% WER={100 * summary['mean_wer']:.2f}% lỗi={summary['errors']} -> {out}")
    if summary["language_acc"] is not None:
        print(f"language_acc={100 * summary['language_acc']:.1f}%")
    if do_gate:
        print(f"gate (SNR>=0, 10-35 WPM, n={gate_n}): CER={100 * gate_cer:.2f}% "
              f"{'ĐẠT' if ok else 'TRƯỢT'} (ngưỡng {100 * max_cer:.2f}%)")
    if t2_gate:
        for src, g in summary["source_gate"].items():
            print(f"T2 {src}: n={g['n']} CER={100 * g['cer']:.2f}% ngưỡng {100 * g['max_cer']:.2f}% "
                  f"{'ĐẠT' if g['ok'] else 'TRƯỢT'}")
        return summary, all(g["ok"] for g in summary["source_gate"].values())
    return summary, ok if do_gate else True
