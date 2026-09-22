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


def test_clean_tail_is_off_by_default():
    """Mặc định TẮT sau thí nghiệm E11.

    Bật 20 % làm CER trên T1 xấu đi 6,6 điểm (26,80 % so với 20,21 %, cùng seed, cùng số bước,
    chỉ khác dữ liệu) vì một phần năm dung lượng huấn luyện dồn vào vùng T1 không đo; đổi lại
    không được gì trên T2, nơi bộ giải mã DSP mới là đường được chọn. Vấn đề tín hiệu quá sạch
    đã xử lý ở khâu suy luận bằng `morsedesk/dsp/dither.py`.
    """
    assert CLEAN_TAIL_PROB == 0.0
    snrs = sample_snrs()
    assert snrs.max() <= 25.0
    assert snrs.min() <= -5.0


def test_hard_region_keeps_its_shape():
    snrs = sample_snrs()
    assert -6.0 <= np.median(snrs) <= 25.0


def test_clean_tail_probability_is_configurable():
    none_tail = sample_snrs(sampling=ChannelSampling(clean_tail_prob=0.0))
    assert none_tail.max() <= 25.0
    all_tail = sample_snrs(sampling=ChannelSampling(clean_tail_prob=1.0))
    assert all_tail.min() > 25.0
