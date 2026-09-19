"""Bộ giải mã DSP thích nghi: thử nhiều cặp (ngưỡng, độ dài dit), chọn cặp khớp timing nhất.

Dùng làm baseline đo lường và fallback khi mô hình nơ-ron kém tin cậy. Khi timing mơ hồ
(bản tin ngắn không tương phản dot/dash), một prior tốc độ nhẹ quanh SPEED_PRIOR_WPM
phá thế hòa giữa các giả thuyết (ngưỡng, độ dài dit) có timing_cost gần bằng nhau.

Giới hạn đã biết: bản tin ngắn không có tương phản chấm/gạch (HI, SI, TTT) có thể bị
đọc thành alias 3× tại một số tốc độ cao khi một dit chỉ dài 4–6 khung (200 khung/s) và
độ lượng tử hóa át manh mối khoảng tắt 9 so với 7 dit. Đã quan sát lỗi ở 40 WPM (SI),
48 WPM (HI) và 60 WPM (HI, SI); dải 5–35 WPM và 50 WPM hiện đúng theo test. "TTT" ở
60 WPM trùng hoàn toàn với "S" ở 20 WPM nên không có manh mối. Engine ONNX là bộ giải
mã chính; baseline chỉ là đối chứng và dự phòng. Hướng cải tiến sau: nội suy ranh giới
dưới khung trong run_lengths để giảm nhiễu lượng tử.
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

SPEED_PRIOR_WPM = 20.0       # tốc độ tiên nghiệm khi timing mơ hồ
# Đo thực nghiệm: cửa sổ khả thi để "HI"/"SI" đúng ở 5-8 WPM (wpm giả thuyết đúng cách xa 20)
# và "SI" đúng ở 50 WPM (giả thuyết sai có cost thô thấp hơn chút) là khoảng [0.0015, 0.0025];
# 0.01 (giá trị cũ) đủ lớn để prior lấn át chênh lệch timing_cost thật ở tốc độ thấp.
SPEED_PRIOR_WEIGHT = 0.002   # nhỏ so với chi phí timing, chỉ phá thế hòa

OFF_LONG_CAP_UNITS = 12.0   # khoảng tắt dài hơn 12 dit coi như "12": chỉ phạt nhẹ, không loại giả thuyết


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
    return [(bool(mask[s]), int(s), int(e)) for s, e in zip(starts, ends, strict=True)]


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
    """Trung bình bình phương log-tỉ lệ so với mốc lý tưởng gần nhất (bật: 1/3; tắt <=7u: 1/3/7);
    đoạn tắt dài hơn 7u dùng kẹp mềm (so với OFF_LONG_CAP_UNITS) thay vì kẹp cứng về 7, để vẫn phạt
    khoảng tắt quá dài mà không loại hẳn giả thuyết; bỏ đoạn tắt đầu/cuối."""
    inner = list(runs)
    if inner and not inner[0][0]:
        inner = inner[1:]
    if inner and not inner[-1][0]:
        inner = inner[:-1]
    costs = []
    for on, s, e in inner:
        r = (e - s) / unit
        if on:
            costs.append(float(np.min(np.abs(np.log(r) - np.log(IDEAL_ON))) ** 2))
        elif r <= 7.0:
            costs.append(float(np.min(np.abs(np.log(r) - np.log(IDEAL_OFF))) ** 2))
        else:
            costs.append(float(np.log(min(r, OFF_LONG_CAP_UNITS) / 7.0) ** 2))
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
        best: tuple[float, float, float, float, list[tuple[bool, int, int]]] | None = None
        for thr in self.thresholds:
            runs = run_lengths(env > thr)
            on_lengths = np.array([e - s for on, s, e in runs if on])
            if len(on_lengths) < 2:
                continue
            for unit in candidate_units(on_lengths):
                cost = timing_cost(runs, unit)
                wpm = 1.2 * FRAME_RATE / unit
                total = cost + SPEED_PRIOR_WEIGHT * float(np.log(wpm / SPEED_PRIOR_WPM)) ** 2
                if best is None or total < best[0]:
                    best = (total, cost, thr, unit, runs)
        if best is None:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        _total, cost, thr, unit, runs = best
        return BaselineResult(runs_to_symbols(runs, unit), unit, thr, cost)

    def decode_audio(
        self, x: np.ndarray, sample_rate: int = SAMPLE_RATE
    ) -> tuple[BaselineResult, ToneEstimate]:
        est = estimate_tone(x, sample_rate)
        if not est.has_signal or est.f0_hz is None:
            return BaselineResult([], 0.0, 0.0, float("inf")), est
        env = mix_envelope(x, est.f0_hz, sample_rate)
        return self.decode_envelope(env), est
