"""Bộ giải mã DSP thích nghi: thử nhiều cặp (ngưỡng, độ dài dit), chọn cặp khớp timing nhất.

Dùng làm baseline đo lường và fallback khi mô hình nơ-ron kém tin cậy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.constants import FRAME_RATE, SAMPLE_RATE
from morsedesk.dsp.frontend import mix_envelope
from morsedesk.dsp.tone import ToneEstimate, estimate_tone
from morsedesk.model.vocab import SPACE

THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55, 0.65)
IDEAL_ON = np.array([1.0, 3.0])
IDEAL_OFF = np.array([1.0, 3.0, 7.0])


@dataclass
class Symbol:
    token: str
    start_frame: int
    end_frame: int


@dataclass
class BaselineResult:
    symbols: list[Symbol]
    unit_frames: float
    threshold: float
    cost: float

    @property
    def tokens(self) -> list[str]:
        return [s.token for s in self.symbols]

    @property
    def wpm(self) -> float:
        return 1.2 * FRAME_RATE / self.unit_frames if self.unit_frames > 0 else 0.0


def run_lengths(mask: np.ndarray) -> list[tuple[bool, int, int]]:
    """Các đoạn liên tiếp (is_on, start, end)."""
    if len(mask) == 0:
        return []
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(mask)]])
    return [(bool(mask[s]), int(s), int(e)) for s, e in zip(starts, ends)]


def _two_means_log(values: np.ndarray) -> tuple[float, float]:
    """2-means trên log; trả (tâm thấp, tâm cao) theo thang tuyến tính."""
    logs = np.log(values.astype(float))
    c_lo, c_hi = float(logs.min()), float(logs.max())
    for _ in range(20):
        assign = np.abs(logs - c_lo) <= np.abs(logs - c_hi)
        if assign.all() or (~assign).all():
            break
        c_lo, c_hi = float(logs[assign].mean()), float(logs[~assign].mean())
    return float(np.exp(c_lo)), float(np.exp(c_hi))


def candidate_units(on_lengths: np.ndarray) -> list[float]:
    """Ứng viên độ dài dit (khung) từ các đoạn bật."""
    cands: set[float] = set()
    if len(on_lengths) >= 2:
        lo, hi = _two_means_log(on_lengths)
        cands.update([lo, hi / 3.0])
    med = float(np.median(on_lengths))
    cands.update([med, med / 3.0])
    return sorted(c for c in cands if c >= 1.0)


def timing_cost(runs: list[tuple[bool, int, int]], unit: float) -> float:
    """Trung bình bình phương log-tỉ lệ so với mốc lý tưởng gần nhất; bỏ đoạn tắt đầu/cuối."""
    inner = list(runs)
    if inner and not inner[0][0]:
        inner = inner[1:]
    if inner and not inner[-1][0]:
        inner = inner[:-1]
    costs = []
    for on, s, e in inner:
        r = (e - s) / unit
        if not on:
            r = min(r, 7.0)
        ideals = IDEAL_ON if on else IDEAL_OFF
        costs.append(float(np.min(np.abs(np.log(r) - np.log(ideals))) ** 2))
    return float(np.mean(costs)) if costs else float("inf")


def split_gap_threshold(gap_units: np.ndarray) -> float:
    """Ngưỡng (đơn vị dit) tách khoảng giữa chữ và giữa từ; thích nghi Farnsworth."""
    if len(gap_units) == 0:
        return 5.0
    if len(gap_units) < 2 or gap_units.max() / gap_units.min() < 1.8:
        return float(gap_units.max()) * 1.5
    lo, hi = _two_means_log(gap_units)
    return float(np.sqrt(lo * hi))


def runs_to_symbols(runs: list[tuple[bool, int, int]], unit: float) -> list[Symbol]:
    gaps = np.array([(e - s) / unit for on, s, e in runs[1:-1] if not on and (e - s) / unit >= 2.0])
    word_thr = split_gap_threshold(gaps)
    symbols: list[Symbol] = []
    cur = ""
    cur_start = 0

    def flush(end: int) -> None:
        nonlocal cur
        if cur:
            symbols.append(Symbol(cur, cur_start, end))
            cur = ""

    for on, s, e in runs:
        r = (e - s) / unit
        if on:
            if not cur:
                cur_start = s
            cur += "." if r < 2.0 else "-"
            continue
        if r < 2.0:
            continue
        flush(s)
        if r >= word_thr and symbols and symbols[-1].token != SPACE:
            symbols.append(Symbol(SPACE, s, e))
    flush(runs[-1][2] if runs else 0)
    while symbols and symbols[-1].token == SPACE:
        symbols.pop()
    return symbols


class BaselineDecoder:
    def __init__(self, thresholds: tuple[float, ...] = THRESHOLDS) -> None:
        self.thresholds = thresholds

    def decode_envelope(self, env: np.ndarray) -> BaselineResult:
        if len(env) < 3:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        env = env / (np.percentile(env, 98) + 1e-9)
        env = np.convolve(env, np.ones(3) / 3.0, mode="same")
        best: tuple[float, float, float, list[tuple[bool, int, int]]] | None = None
        for thr in self.thresholds:
            runs = run_lengths(env > thr)
            on_lengths = np.array([e - s for on, s, e in runs if on])
            if len(on_lengths) < 2:
                continue
            for unit in candidate_units(on_lengths):
                cost = timing_cost(runs, unit)
                if best is None or cost < best[0]:
                    best = (cost, thr, unit, runs)
        if best is None:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        cost, thr, unit, runs = best
        return BaselineResult(runs_to_symbols(runs, unit), unit, thr, cost)

    def decode_audio(
        self, x: np.ndarray, sample_rate: int = SAMPLE_RATE
    ) -> tuple[BaselineResult, ToneEstimate]:
        est = estimate_tone(x, sample_rate)
        if not est.has_signal or est.f0_hz is None:
            return BaselineResult([], 0.0, 0.0, float("inf")), est
        env = mix_envelope(x, est.f0_hz, sample_rate)
        return self.decode_envelope(env), est
