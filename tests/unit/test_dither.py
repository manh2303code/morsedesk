"""Tín hiệu sạch hơn dải huấn luyện phải được kéo về miền trước khi vào mô hình.

Bản ghi thật của ARRL W1AW đo 61,7 dB SNR; mô hình chỉ được huấn luyện tới 25 dB và trả về rác
trên đúng loại bản ghi đó. Thêm nhiễu cho bẩn đi thì nó đọc được ngay (89,8 % -> 28,9 % CER trên
clip đầu của T2), nên đây là lệch phân bố ở khâu suy luận, vá được mà không cần huấn luyện lại.
"""

import numpy as np
import pytest

from morsedesk.api import Decoder
from morsedesk.dsp.dither import SNR_CEILING_DB, SNR_TARGET_DB, dither_to_ceiling
from morsedesk.dsp.tone import estimate_tone
from tests.helpers import make_morse


def test_noisy_signal_is_left_untouched():
    x, _ = make_morse("CQ DE K", profile_id="en", wpm=20, snr_db=6.0)
    out = dither_to_ceiling(x, estimate_tone(x).snr_db)
    assert out is x


def test_clean_signal_is_brought_down_to_the_target():
    x, _ = make_morse("CQ DE K", profile_id="en", wpm=20)
    before = estimate_tone(x).snr_db
    assert before > SNR_CEILING_DB, "clip không nhiễu phải sạch hơn trần"
    out = dither_to_ceiling(x, before)
    assert out is not x and out.shape == x.shape
    after = estimate_tone(out).snr_db
    assert abs(after - SNR_TARGET_DB) < 8.0, (before, after)


def test_dither_is_deterministic():
    x, _ = make_morse("CQ DE K", profile_id="en", wpm=20)
    snr = estimate_tone(x).snr_db
    assert np.array_equal(dither_to_ceiling(x, snr), dither_to_ceiling(x, snr))


def test_unknown_snr_is_left_untouched():
    x, _ = make_morse("CQ DE K", profile_id="en", wpm=20)
    assert dither_to_ceiling(x, None) is x
    assert dither_to_ceiling(x, float("nan")) is x


@pytest.mark.slow
def test_model_reads_a_clean_clip_end_to_end():
    """Ca thật: clip không nhiễu, đúng loại tín hiệu mà bản ghi ARRL đưa tới."""
    from pathlib import Path

    if not Path("models/acoustic.onnx").is_file():
        pytest.skip("cần models/acoustic.onnx")
    text = "CQ CQ DE R1ABC K"
    x, _ = make_morse(text, profile_id="en", wpm=20)
    got = Decoder("en", engine="onnx", lm=True).decode_array(x).text
    assert got == text, got
