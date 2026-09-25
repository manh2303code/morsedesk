"""Dòng thời gian của bản tin sắp phát: chấm/gạch nào kêu lúc nào, thuộc chữ thứ mấy.

Trang Tạo mã tô chữ đang phát và làm nổi đúng dấu đang kêu, phím Morse động nhấn xuống đúng lúc
tone vang (yêu cầu người dùng 25/09). Để hình khớp tiếng, thời điểm lấy từ CHÍNH `tokens_to_elements`
mà `Encoder.to_audio` dùng để dựng âm thanh — cùng WPM, Farnsworth, trọng số gạch — cộng phần đệm
im lặng đầu bản tin (`pad_s`). Không import Qt.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.model.vocab import SPACE


@dataclass(frozen=True)
class MarkSpan:
    start: float        # giây trong âm thanh đã dựng (tính cả đệm đầu)
    end: float
    letter: int         # chữ thứ mấy (không tính dấu cách) — đúng thứ tự ô trên băng Morse
    element: int        # dấu thứ mấy trong mẫu của chữ đó
    symbol: str         # "." hoặc "-"


@dataclass(frozen=True)
class Moment:
    letter: int | None  # None: chưa tới chữ đầu tiên
    element: int
    symbol: str
    on: bool            # tone đang kêu


def mark_timeline(tokens: list[str], params: TimingParams, offset_s: float = 0.0) -> list[MarkSpan]:
    """Mỗi dấu (chấm/gạch) của `tokens` một khoảng thời gian, theo đúng nhịp dựng âm thanh."""
    letters = [t for t in tokens if t != SPACE]
    spans: list[MarkSpan] = []
    t = offset_s
    li = ei = 0
    for e in tokens_to_elements(tokens, params):
        if e.on:
            spans.append(MarkSpan(t, t + e.duration, li, ei, letters[li][ei]))
            ei += 1
            if ei == len(letters[li]):
                li, ei = li + 1, 0
        t += e.duration
    return spans


class Timeline:
    """Tra nhanh (bisect) "lúc t giây đang ở chữ nào, dấu nào, tone có kêu không"."""

    def __init__(self, spans: list[MarkSpan]) -> None:
        self.spans = spans
        self._starts = [s.start for s in spans]

    def at(self, t: float) -> Moment:
        i = bisect_right(self._starts, t) - 1
        if i < 0:
            return Moment(None, 0, "", False)
        s = self.spans[i]
        # Khoảng lặng giữa hai dấu/hai chữ: giữ chữ vừa phát (khung tô không nhấp nháy).
        return Moment(s.letter, s.element, s.symbol, t < s.end)

    @property
    def end_s(self) -> float:
        return self.spans[-1].end if self.spans else 0.0
