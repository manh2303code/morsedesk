"""Mô hình tay gõ: WPM ngẫu nhiên, Farnsworth, weight, jitter, kiểu bug, trôi tốc độ, lỗi khoảng cách."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.encode.timing import Element, TimingParams, gap_seconds, unit_seconds

MIN_ELEMENT_S = 0.004


@dataclass(frozen=True)
class KeyerParams:
    wpm: float
    farnsworth_wpm: float | None
    weight: float
    jitter: float               # độ lệch chuẩn log-normal của độ dài phần tử
    bug: bool                   # dit đều, dah lệch nhiều
    drift: float                # thay đổi tỉ lệ độ dài từ đầu đến cuối clip (+0.1 = chậm dần 10%)
    spacing_error_rate: float   # xác suất khoảng giữa chữ bị rút còn 1.5 dit hoặc kéo tới 5 dit
    name: str = "random"

    def timing(self) -> TimingParams:
        return TimingParams(self.wpm, self.farnsworth_wpm, self.weight)


def machine(wpm: float, name: str = "machine") -> KeyerParams:
    return KeyerParams(wpm, None, 3.0, 0.0, False, 0.0, 0.0, name)


def sample_keyer_params(rng: np.random.Generator) -> KeyerParams:
    wpm = float(np.exp(rng.uniform(np.log(5.0), np.log(60.0))))
    farnsworth = None
    if wpm < 18.0 and rng.random() < 0.5:
        farnsworth = float(rng.uniform(5.0, min(13.0, wpm)))
    return KeyerParams(
        wpm=wpm,
        farnsworth_wpm=farnsworth,
        weight=float(rng.uniform(2.0, 4.5)),
        jitter=float(rng.uniform(0.03, 0.20)),
        bug=bool(rng.random() < 0.2),
        drift=float(rng.uniform(-0.15, 0.15)),
        spacing_error_rate=0.05,
    )


def apply_keyer(elements: list[Element], params: KeyerParams, rng: np.random.Generator) -> list[Element]:
    """Làm méo timing lý tưởng theo tham số tay gõ. Không đổi số phần tử."""
    if not elements:
        return []
    u = unit_seconds(params.wpm)
    inter_char, _ = gap_seconds(params.timing())
    n = len(elements)
    out: list[Element] = []
    for i, e in enumerate(elements):
        progress = i / max(1, n - 1)
        dur = e.duration * (1.0 + params.drift * progress)
        if e.on:
            is_dot = e.duration <= 1.5 * u
            if params.bug:
                j = params.jitter / 3.0 if is_dot else params.jitter * 2.0
            else:
                j = params.jitter
        else:
            j = params.jitter
            if (params.spacing_error_rate > 0 and abs(e.duration - inter_char) < 1e-9
                    and rng.random() < params.spacing_error_rate):
                dur = (1.5 if rng.random() < 0.5 else 5.0) * u
        if j > 0:
            dur *= float(np.exp(rng.normal(0.0, j)))
        out.append(Element(e.on, max(dur, MIN_ELEMENT_S)))
    return out
