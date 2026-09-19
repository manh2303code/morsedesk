"""ARPA (từ lmplz) -> nhị phân numpy .bin theo bảng chữ của profile, kèm thống kê và perplexity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import load_arpa, save_bin
from morsedesk.lm.profile import load_profile
from morsedesk.textio import force_utf8_streams


def convert(
    arpa: Path,
    profile_id: str,
    out: Path,
    holdout: Path | None = None,
    holdout_lines: int = 1000,
) -> dict:
    alphabet = LMAlphabet.for_profile(load_profile(profile_id))
    lm = load_arpa(arpa, alphabet)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_bin(lm, out)
    stats = {
        "arpa": str(arpa), "out": str(out), "order": lm.order,
        "ngrams_per_order": [int(len(t.hashes)) for t in lm.tables],
        "size_mb": round(out.stat().st_size / 1e6, 2),
        "perplexity": None,
    }
    if holdout and Path(holdout).exists():
        lines = Path(holdout).read_text(encoding="utf-8").splitlines()[:holdout_lines]
        filtered = [ln for ln in lines if ln.strip()]
        stats["perplexity"] = round(lm.perplexity(filtered), 3) if filtered else None
    return stats


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="ARPA -> .bin")
    ap.add_argument("--arpa", type=Path, required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--holdout", type=Path, default=None)
    a = ap.parse_args(argv)
    print(json.dumps(convert(a.arpa, a.profile, a.out, a.holdout), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
