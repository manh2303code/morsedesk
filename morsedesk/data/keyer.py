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
    # "Lối phím" (E20, 28/09 — điện văn mạng CW thật, docs/research/06): chấm dài `dit_scale` lần bình
    # thường, chấm NGAY SAU gạch trong cùng ký tự thêm `after_dah` lần; phần bị rút cộng vào khoảng lặng sau
    # nên NHỊP (điểm bắt đầu phần tử) giữ nguyên. File thật: chấm 0,72, chấm sau gạch xuống 0,15.
    dit_scale: float = 1.0
    after_dah: float = 1.0

    def timing(self) -> TimingParams:
        return TimingParams(self.wpm, self.farnsworth_wpm, self.weight)


def machine(wpm: float, name: str = "machine") -> KeyerParams:
    return KeyerParams(wpm, None, 3.0, 0.0, False, 0.0, 0.0, name)


def sample_keyer_params(rng: np.random.Generator, fist_p: float = 0.0) -> KeyerParams:
    """`fist_p` (E20): xác suất clip có "lối phím" nhẹ/nặng + rút chấm sau gạch. 0 = KHÔNG rút thêm số
    ngẫu nhiên nào: T1/dev sinh lại y hệt."""
    wpm = float(np.exp(rng.uniform(np.log(5.0), np.log(60.0))))
    farnsworth = None
    if wpm < 18.0 and rng.random() < 0.5:
        farnsworth = float(rng.uniform(5.0, min(13.0, wpm)))
    dit_scale = after_dah = 1.0
    if fist_p > 0 and rng.random() < fist_p:
        dit_scale = float(rng.uniform(0.5, 1.15))
        if rng.random() < 0.5:
            after_dah = float(rng.uniform(0.15, 0.75))
    return KeyerParams(
        wpm=wpm,
        farnsworth_wpm=farnsworth,
        weight=float(rng.uniform(2.0, 4.5)),
        jitter=float(rng.uniform(0.03, 0.20)),
        bug=bool(rng.random() < 0.2),
        drift=float(rng.uniform(-0.15, 0.15)),
        spacing_error_rate=0.05,
        dit_scale=dit_scale,
        after_dah=after_dah,
    )


def apply_fist(elements: list[Element], params: KeyerParams, u: float) -> list[Element]:
    """Rút/giãn chấm theo `dit_scale`, chấm ngay sau gạch thêm `after_dah`; phần chênh dồn sang khoảng lặng
    kế tiếp (nhịp giữ nguyên). Không đổi số phần tử."""
    if params.dit_scale == 1.0 and params.after_dah == 1.0:
        return elements
    out = list(elements)
    prev_dah = False
    for i, e in enumerate(out):
        if not e.on:
            if e.duration > 2.0 * u:                # giữa chữ/từ: ký tự mới
                prev_dah = False
            continue
        is_dah = e.duration > 2.0 * u
        if not is_dah:
            k = params.dit_scale * (params.after_dah if prev_dah else 1.0)
            new = max(MIN_ELEMENT_S, e.duration * k)
            out[i] = Element(True, new)
            if i + 1 < len(out) and not out[i + 1].on:
                out[i + 1] = Element(False, max(MIN_ELEMENT_S, out[i + 1].duration + e.duration - new))
        prev_dah = is_dah
    return out


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
    return apply_fist(out, params, u)
