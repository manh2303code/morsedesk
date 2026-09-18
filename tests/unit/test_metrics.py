import math

from morsedesk.metrics import cer, edit_distance, normalize_text, wer


def test_edit_distance_basic():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("", "abc") == 3
    assert edit_distance("abc", "abc") == 0
    assert edit_distance(["a", "b"], ["b"]) == 1


def test_normalize_text():
    assert normalize_text("  cq   de  k ") == "CQ DE K"


def test_cer():
    assert cer("CQ DE K", "CQ DE K") == 0.0
    assert math.isclose(cer("CQ DE K", "CQ DE"), 2 / 7)
    assert cer("", "ABC") == 3.0
    assert math.isclose(cer("cq  de", "CQ DE"), 0.0)


def test_wer():
    assert wer("CQ DE K", "CQ DE K") == 0.0
    assert math.isclose(wer("CQ DE K", "CQ DE"), 1 / 3)
    assert math.isclose(wer("CQ DE K", "CQ DX K"), 1 / 3)
