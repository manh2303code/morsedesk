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
    # "Lối phím" (E21, 28/09 — ĐO trên 3 file điện văn mạng thật T7, docs/research/06 §5). File 351: MỌI xung
    # hụt ~0,4 đơn vị (chấm 0,6, gạch 2,65) và phần hụt dồn sang lặng sau (chấm->chấm vẫn 1,93 đơn vị); lặng
    # SAU GẠCH trong ký tự chỉ 0,87 (sau chấm 1,27): phần tử sau gạch tới sớm 0,5 đơn vị; lặng giữa chữ giãn
    # (trung vị 4,3), lặng giữa từ có khi NÉN lẫn vào lặng giữa chữ. (E20 dùng mô hình đoán sai: rút chấm sau
    # gạch — chấm sau gạch thật dài y như chấm khác.)
    mark_offset: float = 0.0     # đơn vị: cộng vào MỌI xung, trừ ở lặng ngay sau (nhịp giữ)
    dah_gap_cut: float = 0.0     # đơn vị: rút lặng sau gạch trong ký tự (không bù: phần tử sau tới sớm)
    char_stretch: float = 1.0    # nhân lặng giữa chữ
    word_stretch: float = 1.0    # nhân lặng giữa từ

    def timing(self) -> TimingParams:
        return TimingParams(self.wpm, self.farnsworth_wpm, self.weight)


def machine(wpm: float, name: str = "machine") -> KeyerParams:
    return KeyerParams(wpm, None, 3.0, 0.0, False, 0.0, 0.0, name)


def sample_keyer_params(rng: np.random.Generator, fist_p: float = 0.0) -> KeyerParams:
    """`fist_p` (E21): xác suất clip có "lối phím" như điện văn mạng thật (T7: 351 -0,4/0,5, 352 -0,25/0,3,
    347 ~chuẩn). 0 = KHÔNG rút thêm số ngẫu nhiên nào: T1/dev sinh lại y hệt."""
    wpm = float(np.exp(rng.uniform(np.log(5.0), np.log(60.0))))
    farnsworth = None
    if wpm < 18.0 and rng.random() < 0.5:
        farnsworth = float(rng.uniform(5.0, min(13.0, wpm)))
    fist = {}
    if fist_p > 0 and rng.random() < fist_p:
        fist = dict(mark_offset=float(rng.uniform(-0.5, 0.1)),
                    dah_gap_cut=float(rng.uniform(0.0, 0.6)) if rng.random() < 0.7 else 0.0,
                    char_stretch=float(rng.uniform(1.0, 1.5)),
                    word_stretch=float(rng.uniform(0.7, 1.4)))
    return KeyerParams(
        wpm=wpm,
        farnsworth_wpm=farnsworth,
        weight=float(rng.uniform(2.0, 4.5)),
        jitter=float(rng.uniform(0.03, 0.20)),
        bug=bool(rng.random() < 0.2),
        drift=float(rng.uniform(-0.15, 0.15)),
        spacing_error_rate=0.05,
        **fist,
    )


def apply_fist(elements: list[Element], params: KeyerParams, u: float) -> list[Element]:
    """Lối phím (xem KeyerParams): lặng trong ký tự (<= 2 đơn vị) / giữa chữ (<= 5) / giữa từ; rút lặng sau gạch
    trong ký tự, giãn lặng giữa chữ/từ, rồi cộng `mark_offset` vào mọi xung và trừ ở lặng ngay sau. Không đổi
    số phần tử."""
    if (params.mark_offset == 0.0 and params.dah_gap_cut == 0.0 and params.char_stretch == 1.0
            and params.word_stretch == 1.0):
        return elements
    out = list(elements)
    for i, e in enumerate(out):
        if e.on or i == 0:
            continue
        prev = out[i - 1]
        g = e.duration
        if g <= 2.0 * u:
            if prev.on and prev.duration > 2.0 * u:
                g -= params.dah_gap_cut * u
        elif g <= 5.0 * u:
            g *= params.char_stretch
        else:
            g *= params.word_stretch
        out[i] = Element(False, max(MIN_ELEMENT_S, g))
    for i, e in enumerate(out):
        if not e.on:
            continue
        new = max(MIN_ELEMENT_S, e.duration + params.mark_offset * u)
        out[i] = Element(True, new)
        if i + 1 < len(out) and not out[i + 1].on:
            out[i + 1] = Element(False, max(MIN_ELEMENT_S, out[i + 1].duration + e.duration - new))
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
