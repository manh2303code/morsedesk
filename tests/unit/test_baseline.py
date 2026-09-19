import numpy as np
import pytest

from morsedesk.dsp.baseline import (
    BaselineDecoder,
    candidate_units,
    run_lengths,
    split_gap_threshold,
)
from morsedesk.encode.synth import add_noise
from morsedesk.lm.profile import load_profile
from morsedesk.metrics import cer
from morsedesk.model.vocab import SPACE
from tests.helpers import make_morse


def _decode(text, profile_id="en", **kw):
    x, _ = make_morse(text, profile_id=profile_id, **kw)
    res, est = BaselineDecoder().decode_audio(x)
    return load_profile(profile_id).render(res.tokens), res, est


def test_run_lengths():
    mask = np.array([0, 0, 1, 1, 1, 0, 1, 0, 0], dtype=bool)
    assert run_lengths(mask) == [(False, 0, 2), (True, 2, 5), (False, 5, 6), (True, 6, 7), (False, 7, 9)]
    assert run_lengths(np.zeros(0, dtype=bool)) == []


def test_candidate_units_two_clusters():
    on = np.array([12, 11, 13, 36, 35, 37, 12])
    cands = candidate_units(on)
    assert any(abs(c - 12) < 1.5 for c in cands)


def test_split_gap_threshold_standard_and_farnsworth():
    gaps = np.array([3.0, 3.1, 2.9, 7.0, 7.2])
    thr = split_gap_threshold(gaps)
    assert 3.2 < thr < 6.8
    far = np.array([12.9, 13.0, 30.0, 29.5])
    thr2 = split_gap_threshold(far)
    assert 13.5 < thr2 < 29.0
    assert split_gap_threshold(np.array([3.0, 3.1, 3.0])) > 3.1   # một cụm -> tất cả là giữa chữ


def test_clean_20wpm_english():
    text = "CQ CQ DE R1ABC K"
    out, res, est = _decode(text, wpm=20)
    assert out == text
    assert abs(res.wpm - 20) < 2.0
    assert est.has_signal


def test_clean_russian_15wpm():
    text = "ПРИВЕТ МИР"
    out, _, _ = _decode(text, profile_id="ru", wpm=15)
    assert out == text


def test_fast_40wpm():
    text = "THE QUICK BROWN FOX"
    out, res, _ = _decode(text, wpm=40)
    assert out == text
    assert abs(res.wpm - 40) < 4.0


def test_slow_5wpm():
    text = "SOS SOS"
    out, _, _ = _decode(text, wpm=5)
    assert out == text


def test_farnsworth_18_8():
    text = "CQ DE K1ABC"
    out, _, _ = _decode(text, wpm=18, farnsworth_wpm=8)
    assert out == text


def test_noisy_25wpm_10db():
    text = "CQ CQ DE R1ABC R1ABC PSE K"
    out, _, _ = _decode(text, wpm=25, snr_db=10.0, seed=11)
    assert cer(text, out) <= 0.05


def test_noise_only_returns_nothing():
    rng = np.random.default_rng(3)
    x = add_noise(np.zeros(8000 * 4, dtype=np.float32), 0.0, 0.32, rng=rng)
    res, est = BaselineDecoder().decode_audio(x)
    assert not est.has_signal
    assert res.symbols == []


def test_symbols_have_frames_and_no_trailing_space():
    _, res, _ = _decode("AB CD", wpm=20)
    assert res.symbols[-1].token != SPACE
    for a, b in zip(res.symbols, res.symbols[1:], strict=False):
        assert a.end_frame <= b.start_frame


def test_timing_cost_scores_boundary_on_runs():
    from morsedesk.dsp.baseline import timing_cost

    # bắt đầu và kết thúc bằng đoạn bật: dot 1u, tắt 3u, dash 3u -> khớp lý tưởng, chi phí 0
    runs = [(True, 0, 10), (False, 10, 40), (True, 40, 70)]
    assert timing_cost(runs, 10.0) == 0.0
    # đoạn bật đầu dài 2u (không khớp 1 hay 3) phải làm chi phí > 0 vì không được bỏ qua
    runs_bad = [(True, 0, 20), (False, 20, 50), (True, 50, 80)]
    assert timing_cost(runs_bad, 10.0) > 0.0


def test_timing_cost_ignores_boundary_off_runs():
    from morsedesk.dsp.baseline import timing_cost

    # đoạn tắt đầu 10u và tắt cuối 2u đều bị bỏ qua -> chi phí 0
    runs = [(False, 0, 100), (True, 100, 110), (False, 110, 140), (True, 140, 170), (False, 170, 190)]
    assert timing_cost(runs, 10.0) == 0.0


@pytest.mark.parametrize("wpm", [5, 8, 12, 20, 35, 50])
def test_short_all_dit_message_across_speeds(wpm):
    for text in ("HI", "EE E", "SI"):
        out, res, _ = _decode(text, wpm=wpm)
        assert out == text, (wpm, text, out)
        assert abs(res.wpm - wpm) < 0.15 * wpm + 1.0, (wpm, res.wpm)


@pytest.mark.parametrize("wpm", [12, 20, 35])
def test_short_all_dash_message_mid_speeds(wpm):
    # "TTT" ở 60 WPM trùng hoàn toàn với "S" ở 20 WPM (không có manh mối), nên chỉ kiểm ở dải giữa
    out, res, _ = _decode("TTT", wpm=wpm)
    assert out == "TTT", (wpm, out)
    assert abs(res.wpm - wpm) < 0.15 * wpm + 1.0


@pytest.mark.xfail(reason="giới hạn đã biết: dit 4-6 khung ở tốc độ cao, mất manh mối 9 vs 7", strict=False)
@pytest.mark.parametrize("wpm,text", [(40, "SI"), (48, "HI"), (60, "HI"), (60, "SI")])
def test_short_low_contrast_high_speed_known_limitation(wpm, text):
    out, _, _ = _decode(text, wpm=wpm)
    assert out == text, (wpm, text, out)


def test_timing_cost_soft_cap_on_long_off_runs():
    from morsedesk.dsp.baseline import OFF_LONG_CAP_UNITS, timing_cost

    # bật 1u, tắt 9u, bật 1u: khoảng tắt 9u phải bị phạt (không còn kẹp về 7)
    runs = [(True, 0, 10), (False, 10, 100), (True, 100, 110)]
    assert timing_cost(runs, 10.0) > 0.0
    # tắt 30u và tắt 12u phải cho cùng chi phí (kẹp mềm tại OFF_LONG_CAP_UNITS)
    runs_30 = [(True, 0, 10), (False, 10, 310), (True, 310, 320)]
    runs_12 = [(True, 0, 10), (False, 10, 130), (True, 130, 140)]
    assert abs(timing_cost(runs_30, 10.0) - timing_cost(runs_12, 10.0)) < 1e-12
    assert OFF_LONG_CAP_UNITS == 12.0
