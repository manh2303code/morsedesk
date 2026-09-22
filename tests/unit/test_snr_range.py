"""Dải SNR khi sinh dữ liệu huấn luyện phải phủ cả tín hiệu SẠCH.

Bản ghi thật của ARRL W1AW đo được **61,7 dB** SNR, trong khi phân bố huấn luyện cũ chỉ lấy mẫu
trong `uniform(-6, 25)`. Model vì vậy chưa bao giờ thấy tín hiệu sạch hơn 25 dB và trả về rác
trên chính loại bản ghi mà người dùng sẽ đưa vào — trong khi bộ giải mã DSP đơn giản đọc đúng.
Thêm nhiễu vào cho bẩn đi thì model đọc được ngay, nên đây đúng là lệch phân bố.
"""

import numpy as np

from morsedesk.data.channel import (
    CLEAN_TAIL_PROB,
    ChannelSampling,
    sample_channel_params,
)


def sample_snrs(n: int = 4000, sampling: ChannelSampling | None = None) -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.array([sample_channel_params(rng, sampling).snr_db for _ in range(n)])


def test_distribution_reaches_real_recording_levels():
    snrs = sample_snrs()
    assert snrs.max() >= 55.0, "phải chạm tới mức của bản ghi thật (ARRL đo 61,7 dB)"
    assert (snrs > 25.0).mean() > 0.1, "đuôi sạch không được hiếm tới mức model bỏ qua"


def test_hard_region_is_still_the_bulk():
    """Đuôi sạch không được làm loãng vùng khó, vì đó mới là chỗ quyết định CER."""
    snrs = sample_snrs()
    assert (snrs <= 25.0).mean() >= 1.0 - CLEAN_TAIL_PROB - 0.05
    assert snrs.min() <= -5.0
    assert -6.0 <= np.median(snrs[snrs <= 25.0]) <= 25.0


def test_clean_tail_probability_is_configurable():
    none_tail = sample_snrs(sampling=ChannelSampling(clean_tail_prob=0.0))
    assert none_tail.max() <= 25.0
    all_tail = sample_snrs(sampling=ChannelSampling(clean_tail_prob=1.0))
    assert all_tail.min() > 25.0
