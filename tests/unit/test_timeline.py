"""Dòng thời gian của trang Tạo mã phải khớp ĐÚNG âm thanh đã dựng: mỗi dấu bắt đầu/kết thúc tại
chỗ tone bật/tắt trong mảng mẫu, ở mọi WPM, Farnsworth và trọng số gạch."""

from __future__ import annotations

import numpy as np
import pytest

from morsedesk.api import Encoder
from morsedesk.encode.timeline import Timeline, mark_timeline
from morsedesk.encode.timing import TimingParams

SR = 8000
PAD = 0.3


def _on_runs(x: np.ndarray) -> list[tuple[float, float]]:
    """(bắt đầu, kết thúc) các đoạn tone bật trong âm thanh sạch."""
    env = np.abs(x) > 1e-4
    runs, start = [], None
    for i, on in enumerate(env):
        if on and start is None:
            start = i
        elif not on and start is not None:
            # khe giữa hai nửa chu kỳ sin không phải là tắt tone
            if i + 40 < len(env) and env[i:i + 40].any():
                continue
            runs.append((start / SR, i / SR))
            start = None
    if start is not None:
        runs.append((start / SR, len(env) / SR))
    return runs


@pytest.mark.parametrize("params", [TimingParams(20), TimingParams(12, 6), TimingParams(30, weight=4.0)])
def test_marks_line_up_with_the_audio_tones(params):
    text = "CQ DE R1ABC ?"
    enc = Encoder("en")
    x = enc.to_audio(text, wpm=params.wpm, farnsworth_wpm=params.farnsworth_wpm, weight=params.weight,
                     pad_s=PAD)
    spans = mark_timeline(enc.to_tokens(text), params, offset_s=PAD)
    runs = _on_runs(x)
    assert len(spans) == len(runs)
    for s, (a, b) in zip(spans, runs, strict=True):
        assert abs(s.start - a) < 0.006 and abs(s.end - b) < 0.006, (s, a, b)


def test_letters_and_symbols_follow_the_patterns():
    enc = Encoder("ru")
    tokens = enc.to_tokens("ЩИ <AR>")
    spans = mark_timeline(tokens, TimingParams(20))
    letters = [t for t in tokens if t != " " and set(t) <= set(".-")]
    assert [s.letter for s in spans] == [i for i, t in enumerate(letters) for _ in t]
    assert "".join(s.symbol for s in spans) == "".join(letters)


def test_timeline_lookup_holds_the_letter_through_gaps():
    tl = Timeline(mark_timeline([".-", ".."], TimingParams(20)))       # A I, dit = 60 ms
    assert tl.at(-0.1).letter is None
    m = tl.at(0.03)
    assert (m.letter, m.element, m.symbol, m.on) == (0, 0, ".", True)
    gap = tl.at(0.09)                                                   # khe trong chữ A
    assert (gap.letter, gap.on) == (0, False)
    dah = tl.at(0.15)
    assert (dah.letter, dah.element, dah.symbol, dah.on) == (0, 1, "-", True)
    assert tl.at(0.35).letter == 0 and not tl.at(0.35).on              # khe giữa hai chữ: giữ A
    assert tl.at(0.45).letter == 0 and tl.at(0.50).letter == 1        # I bắt đầu ở 0,30 + 3 x 0,06
