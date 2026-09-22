"""Ước lượng tone trên clip dài không được ngốn bộ nhớ theo độ dài clip.

Đo ngày 22/09: clip 20 phút (38 MB dữ liệu) làm `estimate_tone` chiếm **1 805 MB** vì nó tính
STFT trên toàn bộ. Với file 60 phút, cả lượt giải mã chạm 5,4 GB — quá nhiều cho một máy air-gap
thông thường, và là thứ chặn việc nâng trần thời lượng (CP-14).

Ước lượng tone không cần toàn bộ clip: một tone CW ổn định lộ ra sau vài chục giây, nên lấy mẫu
vài đoạn rải đều cho cùng câu trả lời với một phần nhỏ bộ nhớ.
"""

import tracemalloc

import numpy as np
import pytest

from morsedesk.constants import SAMPLE_RATE
from morsedesk.dsp.tone import MAX_ANALYSIS_SECONDS, estimate_tone


def tone_clip(seconds: float, f0: float = 700.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    keying = (np.sin(2 * np.pi * 2.0 * t) > 0).astype(np.float32)   # bật/tắt đều đặn
    return (np.sin(2 * np.pi * f0 * t) * keying * 0.5
            + rng.normal(scale=0.02, size=len(t))).astype(np.float32)


def test_long_and_short_clips_agree_on_the_tone():
    short = estimate_tone(tone_clip(20.0))
    long = estimate_tone(tone_clip(8 * 60.0))
    assert short.has_signal and long.has_signal
    assert abs(long.f0_hz - short.f0_hz) < 5.0, (short.f0_hz, long.f0_hz)
    assert abs(long.snr_db - short.snr_db) < 6.0, (short.snr_db, long.snr_db)


@pytest.mark.slow
def test_memory_does_not_grow_with_clip_length():
    """Clip dài gấp bốn không được tốn gấp bốn bộ nhớ."""
    def peak_mb(seconds: float) -> float:
        x = tone_clip(seconds)
        tracemalloc.start()
        estimate_tone(x)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak / 1e6

    short = peak_mb(60.0)
    long = peak_mb(4 * 60.0)
    assert long < short * 2.0, f"{short:.0f} MB -> {long:.0f} MB"


def test_analysis_window_is_a_documented_constant():
    assert 20.0 <= MAX_ANALYSIS_SECONDS <= 180.0
