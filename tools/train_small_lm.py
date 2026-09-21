"""Dựng LM nhỏ thuần Python từ corpus đã chuẩn hóa (dự phòng khi không có KenLM). Cắt còn max_mb đầu."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import save_bin, train_small
from morsedesk.lm.profile import load_profile
from morsedesk.textio import force_utf8_streams


def build(text: Path, profile_id: str, out: Path, order: int = 5, max_mb: float = 5.0) -> dict:
    lines: list[str] = []
    used = 0
    limit = int(max_mb * 1e6)
    with open(text, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            used += len(ln.encode("utf-8")) + 1
            if used > limit:
                break
            if ln.strip():
                lines.append(ln)
    lm = train_small(lines, LMAlphabet.for_profile(load_profile(profile_id)), order=order)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_bin(lm, out)
    return {"lines": len(lines), "order": order, "size_mb": round(out.stat().st_size / 1e6, 2), "out": str(out)}


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="LM nhỏ thuần Python")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--text", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--order", type=int, default=5)
    ap.add_argument("--max-mb", type=float, default=5.0)
    a = ap.parse_args(argv)
    print(json.dumps(build(a.text, a.profile, a.out, a.order, a.max_mb), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
