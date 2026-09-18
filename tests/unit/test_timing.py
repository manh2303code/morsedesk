import math

import pytest

from morsedesk.encode.timing import (
    Element,
    TimingParams,
    elements_to_segments,
    gap_seconds,
    tokens_to_elements,
    total_seconds,
    unit_seconds,
)
from morsedesk.model.vocab import SPACE

PARIS = [".--.", ".-", ".-.", "..", "..."]


def test_unit_seconds():
    assert math.isclose(unit_seconds(20), 0.06)
    assert math.isclose(unit_seconds(12), 0.1)


def test_paris_is_50_units():
    els = tokens_to_elements(PARIS + [SPACE], TimingParams(wpm=20))
    assert math.isclose(total_seconds(els), 3.0, rel_tol=1e-9)
    assert math.isclose(total_seconds(els), 50 * unit_seconds(20), rel_tol=1e-9)


def test_elements_alternate_and_start_on():
    els = tokens_to_elements(["-.-.", "--.-"], TimingParams(wpm=25))
    assert els[0].on
    for a, b in zip(els, els[1:]):
        assert a.on != b.on


def test_weight_changes_dash_only():
    u = unit_seconds(20)
    els = tokens_to_elements(["-"], TimingParams(wpm=20, weight=4.0))
    assert els == [Element(True, 4 * u)]
    els = tokens_to_elements(["."], TimingParams(wpm=20, weight=4.0))
    assert els == [Element(True, u)]


def test_gap_seconds_standard():
    ic, iw = gap_seconds(TimingParams(wpm=20))
    assert math.isclose(ic, 3 * 0.06) and math.isclose(iw, 7 * 0.06)
    ic2, iw2 = gap_seconds(TimingParams(wpm=20, farnsworth_wpm=20))
    assert math.isclose(ic, ic2) and math.isclose(iw, iw2)


def test_farnsworth_18_5_gives_5_wpm():
    els = tokens_to_elements(PARIS + [SPACE], TimingParams(wpm=18, farnsworth_wpm=5))
    assert math.isclose(total_seconds(els), 12.0, rel_tol=1e-6)
    ic, iw = gap_seconds(TimingParams(wpm=18, farnsworth_wpm=5))
    assert iw > ic > 3 * unit_seconds(18)


def test_word_gap_between_words():
    els = tokens_to_elements(["-", SPACE, "-"], TimingParams(wpm=20))
    assert els == [Element(True, 0.18), Element(False, 0.42), Element(True, 0.18)]


def test_invalid_params():
    with pytest.raises(ValueError):
        TimingParams(wpm=0)
    with pytest.raises(ValueError):
        TimingParams(wpm=20, farnsworth_wpm=30)
    with pytest.raises(ValueError):
        TimingParams(wpm=20, weight=0.5)


def test_segments_no_drift():
    els = tokens_to_elements(PARIS + [SPACE] * 1, TimingParams(wpm=20)) * 40
    segs = elements_to_segments(els, 8000)
    assert segs[0][1] == 0
    for (_, s0, e0), (_, s1, _) in zip(segs, segs[1:]):
        assert e0 == s1
    assert abs(segs[-1][2] - round(total_seconds(els) * 8000)) <= 1
