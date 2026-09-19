import numpy as np
import pytest

from morsedesk.model.chunker import frame_windows, run_chunked


class FakeModel:
    """Trả one-hot của (chỉ số khung toàn cục) % 6, lấy chỉ số từ cột 0 của đặc trưng."""
    time_stride = 2
    meta = {"vocab": list(range(6))}

    def output_length(self, t):
        return (t - 1) // 2 + 1

    def __call__(self, feats):
        n_out = self.output_length(len(feats))
        out = np.full((n_out, 6), -10.0, dtype=np.float32)
        for j in range(n_out):
            out[j, int(feats[2 * j, 0]) % 6] = 0.0
        return out


def test_frame_windows_short_and_long():
    assert frame_windows(500) == [(0, 500)]
    w = frame_windows(2000, 800, 600)
    assert w == [(0, 800), (600, 1400), (1200, 2000)]
    w2 = frame_windows(2001, 800, 600)
    assert all(s % 2 == 0 for s, _ in w2)
    assert w2[-1][1] <= 2001 and w2[-1][1] >= 1999
    with pytest.raises(ValueError):
        frame_windows(100, 801, 600)


def test_run_chunked_maps_global_frames():
    n = 2001
    feats = np.zeros((n, 11), dtype=np.float32)
    feats[:, 0] = np.arange(n)
    out = run_chunked(FakeModel(), feats, window=800, step=600)
    assert out.shape == ((n - 1) // 2 + 1, 6)
    expected = (2 * np.arange(out.shape[0])) % 6
    assert np.array_equal(out.argmax(axis=1), expected)


def test_run_chunked_single_window():
    feats = np.zeros((300, 11), dtype=np.float32)
    feats[:, 0] = np.arange(300)
    out = run_chunked(FakeModel(), feats)
    assert out.shape == (150, 6)
