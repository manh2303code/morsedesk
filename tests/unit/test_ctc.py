import numpy as np

from morsedesk.model.ctc import greedy_decode, greedy_decode_with_frames


def _logp(ids, n_classes=5):
    lp = np.full((len(ids), n_classes), -10.0, dtype=np.float32)
    for t, i in enumerate(ids):
        lp[t, i] = 0.0
    return lp


def test_greedy_collapses_repeats_and_blanks():
    assert greedy_decode(_logp([0, 3, 3, 0, 0, 4, 4, 4, 0, 3])) == [3, 4, 3]


def test_greedy_empty():
    assert greedy_decode(_logp([0, 0, 0])) == []
    assert greedy_decode(np.zeros((0, 5), dtype=np.float32)) == []


def test_greedy_with_frames():
    out = greedy_decode_with_frames(_logp([0, 3, 3, 0, 4]))
    assert [(i, f) for i, f, _ in out] == [(3, 1), (4, 4)]
    assert all(abs(p - 1.0) < 1e-3 for _, _, p in out)
