"""Giải mã greedy cho đầu ra CTC."""

from __future__ import annotations

import numpy as np


def greedy_decode(log_probs: np.ndarray, blank: int = 0) -> list[int]:
    if log_probs.shape[0] == 0:
        return []
    ids = log_probs.argmax(axis=-1)
    out: list[int] = []
    prev = -1
    for i in ids.tolist():
        if i != prev and i != blank:
            out.append(int(i))
        prev = i
    return out


def greedy_decode_with_frames(log_probs: np.ndarray, blank: int = 0) -> list[tuple[int, int, float]]:
    """(id, khung đầu tiên phát ra token, xác suất tại khung đó)."""
    if log_probs.shape[0] == 0:
        return []
    ids = log_probs.argmax(axis=-1)
    out: list[tuple[int, int, float]] = []
    prev = -1
    for t, i in enumerate(ids.tolist()):
        if i != prev and i != blank:
            out.append((int(i), t, float(np.exp(log_probs[t, i]))))
        prev = i
    return out
