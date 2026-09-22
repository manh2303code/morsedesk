"""Kéo tín hiệu quá sạch về dải mà mô hình âm thanh từng thấy.

Mô hình được huấn luyện trên SNR -6..25 dB (`morsedesk/data/channel.py`). Bản ghi thật của ARRL
W1AW đo được **61,7 dB**, tức nằm ngoài phân bố, và mô hình trả về rác trên chính loại bản ghi
mà người dùng sẽ đưa vào — trong khi bộ giải mã DSP đơn giản đọc đúng gần như hoàn hảo. Thêm
nhiễu trắng cho bẩn đi thì mô hình đọc được ngay: trên hai clip đầu của T2, CER 89,8 % -> 28,9 %
và 91,4 % -> 25,0 %.

Đây là bản vá ở khâu suy luận, dùng được ngay mà không cần huấn luyện lại. Cách sửa tận gốc là
đuôi SNR sạch trong `ChannelSampling.clean_tail_db`, áp dụng từ lượt huấn luyện sau.

Nhiễu sinh từ seed cố định nên hai lần giải mã cùng một file cho đúng một kết quả — bộ đo và
người dùng đều cần điều đó.
"""

from __future__ import annotations

import math

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.synth import add_noise

SNR_CEILING_DB = 25.0    # trần của dải huấn luyện; trên mức này mô hình chưa từng thấy
SNR_TARGET_DB = 20.0     # kéo về mức sạch nhất mà mô hình quen
_SEED = 20260922         # cố định để kết quả tái lập


def dither_to_ceiling(x: np.ndarray, snr_db: float | None,
                      ceiling_db: float = SNR_CEILING_DB,
                      target_db: float = SNR_TARGET_DB,
                      sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Trả lại chính `x` nếu đã nằm trong dải, hoặc bản đã trộn nhiễu nếu sạch hơn trần.

    `snr_db` là ước lượng của `estimate_tone`; None hoặc NaN nghĩa là không đo được, khi đó
    không đụng vào tín hiệu — đoán mò rồi làm bẩn một tín hiệu vốn yếu sẽ tệ hơn nhiều.
    """
    if snr_db is None or not math.isfinite(float(snr_db)) or float(snr_db) <= ceiling_db:
        return x
    power = float(np.mean(np.asarray(x, dtype=np.float64) ** 2))
    if power <= 0.0:
        return x
    return add_noise(np.asarray(x, dtype=np.float32), target_db, power, sample_rate,
                     rng=np.random.default_rng(_SEED))
