"""`mix_envelope` phải chạy với bộ nhớ hằng số, không theo độ dài clip.

Đo ngày 22/09: clip 20 phút (38 MB dữ liệu) làm hàm này chiếm 768 MB, vì nó dựng liên tiếp
`t`, `lo` phức, `y` phức, hai nhánh I/Q và envelope — tất cả ở float64 và dài bằng cả clip.
Cùng với `estimate_tone`, đây là thứ đẩy một lượt giải mã file 60 phút lên 5,4 GB (CP-14).

Chia khối phải cho **đúng cùng kết quả**: pha của bộ trộn lấy theo chỉ số tuyệt đối, và mỗi
khối lọc kèm phần chồng lấn rồi chỉ giữ phần giữa.
"""

import tracemalloc

import numpy as np
import pytest

from morsedesk.constants import SAMPLE_RATE
from morsedesk.dsp.frontend import mix_envelope


def clip(seconds: float, f0: float = 700.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SAMPLE_RATE), dtype=np.float64) / SAMPLE_RATE
    keying = (np.sin(2 * np.pi * 3.0 * t) > 0).astype(np.float64)
    return (np.sin(2 * np.pi * f0 * t) * keying * 0.5 + rng.normal(scale=0.03, size=len(t))).astype(np.float32)


@pytest.mark.parametrize("seconds", [0.5, 3.0, 45.0, 130.0])
def test_chunked_result_matches_single_pass(seconds):
    """Kết quả phải khớp bản tính một lượt tới sai số máy, ở cả clip ngắn lẫn clip vượt một khối."""
    x = clip(seconds)
    got = mix_envelope(x, 700.0)
    want = mix_envelope(x, 700.0, chunk_seconds=0.0)     # 0 = tắt chia khối
    assert got.shape == want.shape
    assert np.allclose(got, want, rtol=1e-6, atol=1e-9), float(np.max(np.abs(got - want)))


@pytest.mark.slow
def test_memory_stays_flat_as_the_clip_grows():
    def peak_mb(seconds: float) -> float:
        x = clip(seconds)
        tracemalloc.start()
        mix_envelope(x, 700.0)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak / 1e6

    short = peak_mb(60.0)
    long = peak_mb(4 * 60.0)
    assert long < short * 2.0, f"{short:.0f} MB -> {long:.0f} MB"
