"""Token mẫu -> danh sách phần tử bật/tắt theo chuẩn PARIS và Farnsworth (ARRL)."""

from __future__ import annotations

from dataclasses import dataclass

from morsedesk.model.vocab import SPACE


@dataclass(frozen=True)
class Element:
    on: bool
    duration: float  # giây


@dataclass(frozen=True)
class TimingParams:
    wpm: float = 20.0
    farnsworth_wpm: float | None = None  # tốc độ hiệu dụng, phải <= wpm
    weight: float = 3.0                  # dash = weight * dit

    def __post_init__(self) -> None:
        if self.wpm <= 0:
            raise ValueError("wpm phải > 0")
        if self.weight < 1.0:
            raise ValueError("weight phải >= 1")
        if self.farnsworth_wpm is not None and not (0 < self.farnsworth_wpm <= self.wpm):
            raise ValueError("farnsworth_wpm phải trong (0, wpm]")


def unit_seconds(wpm: float) -> float:
    """Độ dài một dit: từ PARIS = 50 dit, 1 phút / (50 * wpm)."""
    return 1.2 / wpm


def gap_seconds(params: TimingParams) -> tuple[float, float]:
    """(khoảng giữa chữ, khoảng giữa từ) theo giây.

    Chuẩn: 3 và 7 dit. Farnsworth theo ARRL: t_a = (60c - 37.2s)/(s*c),
    giữa chữ = 3*t_a/19, giữa từ = 7*t_a/19.
    """
    c = params.wpm
    u = unit_seconds(c)
    s = params.farnsworth_wpm
    if s is None or s >= c:
        return 3.0 * u, 7.0 * u
    t_a = (60.0 * c - 37.2 * s) / (s * c)
    return 3.0 * t_a / 19.0, 7.0 * t_a / 19.0


def tokens_to_elements(tokens: list[str], params: TimingParams | None = None) -> list[Element]:
    if params is None:
        params = TimingParams()
    u = unit_seconds(params.wpm)
    dash = params.weight * u
    inter_char, inter_word = gap_seconds(params)
    elements: list[Element] = []
    pending_gap: float | None = None
    for tok in tokens:
        if tok == SPACE:
            pending_gap = inter_word
            continue
        if elements:
            elements.append(Element(False, pending_gap if pending_gap is not None else inter_char))
        pending_gap = None
        for k, sym in enumerate(tok):
            if k > 0:
                elements.append(Element(False, u))
            elements.append(Element(True, u if sym == "." else dash))
    if pending_gap is not None and elements:
        elements.append(Element(False, pending_gap))
    return elements


def total_seconds(elements: list[Element]) -> float:
    return sum(e.duration for e in elements)


def elements_to_segments(elements: list[Element], sample_rate: int) -> list[tuple[bool, int, int]]:
    """Ranh giới mẫu chính xác: làm tròn thời điểm tích lũy, không tích lũy sai số."""
    segs: list[tuple[bool, int, int]] = []
    t = 0.0
    start = 0
    for e in elements:
        t += e.duration
        end = int(round(t * sample_rate))
        segs.append((e.on, start, end))
        start = end
    return segs
