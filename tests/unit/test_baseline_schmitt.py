"""Trễ Schmitt và xóa run ngắn cho bộ giải mã DSP.

Vì sao cần: bộ DSP là thứ GUI hiện ra cho người dùng khi model kém tin cậy. Với một ngưỡng
cứng, mỗi lần envelope rung qua ngưỡng lại sinh thêm một run, và bộ giải mã sinh một ký tự cho
mọi run nên chèn thừa tràn lan — đo được 306,84 % CER trên 152 clip `en` của T1. Cơ chế lấy từ
HamFist (`cw_dsp.cpp`): bật khi vượt ngưỡng cao, chỉ tắt khi rơi dưới ngưỡng thấp, rồi xóa những
run ngắn hơn 0,4 dit.
"""

import numpy as np

from morsedesk.dsp.baseline import (
    HYSTERESIS_RATIO,
    BaselineDecoder,
    despeckle,
    run_lengths,
    schmitt_mask,
)
from morsedesk.lm.profile import load_profile


def test_schmitt_keeps_wobbling_mark_as_one_run():
    """Dấu rung quanh ngưỡng: ngưỡng cứng cắt thành ba run, trễ Schmitt giữ nguyên một."""
    env = np.array([0.0, 0.0, 0.9, 0.42, 0.9, 0.42, 0.9, 0.0, 0.0])
    hard = [r for r in run_lengths(env > 0.45) if r[0]]
    soft = [r for r in run_lengths(schmitt_mask(env, 0.45)) if r[0]]
    assert len(hard) == 3
    assert len(soft) == 1 and soft[0][1:] == (2, 7)


def test_schmitt_does_not_latch_on_noise_below_high_threshold():
    """Nhiễu không bao giờ vượt ngưỡng cao thì không được bật, dù trên ngưỡng thấp."""
    env = np.full(20, 0.45 * HYSTERESIS_RATIO + 0.01, dtype=float)
    assert not schmitt_mask(env, 0.45).any()


def test_despeckle_removes_short_runs_both_polarities():
    mask = np.array([0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1], dtype=bool)
    out = despeckle(mask, 3)
    assert not out[1]                     # gai bật 1 khung -> tắt
    assert out[4:13].all()                # khe tắt 1 khung giữa hai dấu -> nối liền
    assert despeckle(np.ones(4, dtype=bool), 10).all()   # toàn bật: không được xóa sạch


def test_despeckle_keeps_runs_at_exactly_min_len():
    mask = np.array([0, 0, 0, 1, 1, 1, 0, 0, 0], dtype=bool)
    assert (despeckle(mask, 3) == mask).all()


def test_decoder_survives_speckled_envelope():
    """Envelope của 'SOS' 20 WPM kèm gai nhiễu một khung: bản có Schmitt phải đọc đúng."""
    unit = 12                              # khung/dit tại 20 WPM, FRAME_RATE 200
    env = np.zeros(unit * 60)
    pos = 0

    def put(n_units: int, on: bool) -> None:
        nonlocal pos
        if on:
            env[pos:pos + n_units * unit] = 1.0
        pos += n_units * unit

    for pattern in ("...", "---", "..."):
        for i, sym in enumerate(pattern):
            if i:
                put(1, False)
            put(1 if sym == "." else 3, True)
        put(3, False)
    for gai in (unit * 2 + 3, unit * 7 + 1, unit * 25 + 5):
        env[gai] = 0.95                    # gai đơn lẻ trong khoảng lặng

    res = BaselineDecoder().decode_envelope(env)
    assert load_profile("en").render(res.tokens) == "SOS"
