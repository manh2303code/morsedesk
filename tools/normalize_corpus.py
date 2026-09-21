"""Chuẩn hóa corpus theo profile: viết hoa, alias, chỉ giữ bảng chữ LM, một câu một dòng.

Xuất ba file: <lang>.txt (thuần), <lang>.chars.txt (token hóa ký tự cho lmplz, khoảng trắng = ▁),
<lang>.holdout.txt (mỗi dòng thứ holdout_every, không vào train, để đo perplexity).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from morsedesk.encode.text import normalize
from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.textio import force_utf8_streams

TYPO_MAP = {
    "’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"',
    "„": '"', "—": "-", "–": "-", "…": "...", " ": " ",
}
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(text) if s.strip()]


def _iter_sentences(paths: list[Path]) -> Iterator[str]:
    """Sinh câu từ mọi file, gộp cả ba vòng lặp thành một để max_lines dừng đúng chỗ."""
    for path in paths:
        for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            yield from split_sentences(raw)


def normalize_line(line: str, profile: Profile, alphabet: LMAlphabet,
                    max_unknown_ratio: float = 0.05, min_len: int = 3) -> str | None:
    for src, dst in TYPO_MAP.items():
        line = line.replace(src, dst)
    text = normalize(line, profile)  # viết hoa + alias + gộp khoảng trắng
    if not text:
        return None
    non_space = [ch for ch in text if ch != " "]
    unknown = sum(1 for ch in non_space if ch not in alphabet.index)
    if not non_space or unknown / len(non_space) > max_unknown_ratio:
        return None
    kept = "".join(ch for ch in text if ch == " " or ch in alphabet.index)
    kept = " ".join(kept.split())
    return kept if len(kept) >= min_len else None


def normalize_paths(paths: list[Path], profile_id: str, out_plain: Path, out_chars: Path,
                     out_holdout: Path, holdout_every: int = 500, max_lines: int | None = None) -> dict:
    profile = load_profile(profile_id)
    alphabet = LMAlphabet.for_profile(profile)
    stats = {"lines_in": 0, "lines_out": 0, "holdout": 0, "chars": 0}
    hist: Counter = Counter()
    for p in (out_plain, out_chars, out_holdout):
        p.parent.mkdir(parents=True, exist_ok=True)
    kept_index = 0
    with open(out_plain, "w", encoding="utf-8") as fp, open(out_chars, "w", encoding="utf-8") as fc, \
            open(out_holdout, "w", encoding="utf-8") as fh:
        for sent in _iter_sentences(paths):
            stats["lines_in"] += 1
            norm = normalize_line(sent, profile, alphabet)
            if norm is None:
                continue
            kept_index += 1
            if kept_index % holdout_every == 0:
                fh.write(norm + "\n")
                stats["holdout"] += 1
                continue
            fp.write(norm + "\n")
            fc.write(alphabet.to_tokens_line(norm) + "\n")
            stats["lines_out"] += 1
            stats["chars"] += len(norm)
            hist.update(norm)
            if max_lines and stats["lines_out"] >= max_lines:
                break
    stats["top_chars"] = hist.most_common(20)
    return stats


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Chuẩn hóa corpus theo profile")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--lang", required=True, help="tên ngắn cho file ra: en, ru, kk")
    ap.add_argument("--in", dest="inputs", nargs="+", type=Path, required=True, help="file hoặc thư mục")
    ap.add_argument("--out-dir", type=Path, default=Path("corpus"))
    ap.add_argument("--holdout-every", type=int, default=500)
    ap.add_argument("--max-lines", type=int, default=None)
    a = ap.parse_args(argv)
    paths: list[Path] = []
    for p in a.inputs:
        paths.extend(sorted(p.glob("*.txt")) if p.is_dir() else [p])
    stats = normalize_paths(paths, a.profile, a.out_dir / f"{a.lang}.txt", a.out_dir / f"{a.lang}.chars.txt",
                             a.out_dir / f"{a.lang}.holdout.txt", a.holdout_every, a.max_lines)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
