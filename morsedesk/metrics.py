"""CER và WER bằng khoảng cách Levenshtein."""

from __future__ import annotations

from collections.abc import Sequence


def edit_distance(a: Sequence, b: Sequence) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def normalize_text(s: str) -> str:
    return " ".join(s.upper().split())


def cer(ref: str, hyp: str) -> float:
    r, h = normalize_text(ref), normalize_text(hyp)
    return edit_distance(r, h) / max(1, len(r))


def wer(ref: str, hyp: str) -> float:
    r, h = normalize_text(ref).split(), normalize_text(hyp).split()
    return edit_distance(r, h) / max(1, len(r))
