import math

import numpy as np

from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.timing import Element, TimingParams, tokens_to_elements, total_seconds
from tests.helpers import make_morse


def test_length_matches_total_duration():
    els = tokens_to_elements(["-.-.", "--.-"], TimingParams(wpm=20))
    x = elements_to_audio(els)
    assert x.dtype == np.float32
    assert abs(len(x) - round(total_seconds(els) * 8000)) <= 1


def test_tone_rms_and_silence():
    els = [Element(True, 1.0), Element(False, 0.5)]
    x = elements_to_audio(els, tone_hz=700.0, amplitude=0.8)
    on = x[400:7600]                      # bỏ sườn lên xuống
    assert math.isclose(np.sqrt(np.mean(on**2)), 0.8 / math.sqrt(2), rel_tol=0.02)
    # Sườn xuống cưỡi lên ranh giới nên lấn sang khoảng lặng nửa sườn (5 ms / 2 = 20 mẫu);
    # phần còn lại của khoảng lặng phải im tuyệt đối.
    assert np.all(x[8000 + 20:] == 0)


def test_ramps_avoid_clicks():
    els = [Element(True, 0.2)]
    x = elements_to_audio(els, tone_hz=700.0, amplitude=0.8, ramp_ms=5.0)
    assert np.max(np.abs(x[:5])) < 0.15
    assert np.max(np.abs(x[-5:])) < 0.15
    assert np.max(np.abs(x)) > 0.7


def test_tone_array_drift_changes_phase_rate():
    els = [Element(True, 1.0)]
    n = 8000
    x_lo = elements_to_audio(els, tone_hz=np.full(n, 600.0))
    x_hi = elements_to_audio(els, tone_hz=np.full(n, 900.0))
    zc_lo = np.sum(np.diff(np.sign(x_lo)) != 0)
    zc_hi = np.sum(np.diff(np.sign(x_hi)) != 0)
    assert 1150 < zc_lo < 1250      # ~2 zero crossing mỗi chu kỳ
    assert 1750 < zc_hi < 1850


def test_tone_power():
    assert math.isclose(tone_power(0.8), 0.32)


def test_add_noise_variance_matches_inband_snr():
    x = np.zeros(80000, dtype=np.float32)
    rng = np.random.default_rng(1)
    y = add_noise(x, snr_db=10.0, signal_power=0.32, rng=rng)
    # công suất nhiễu trong băng 500 Hz = 0.32/10; nhiễu trắng trải 4000 Hz -> phương sai = 0.032 * 8
    assert math.isclose(float(np.var(y)), 0.032 * 8, rel_tol=0.05)
    assert y.dtype == np.float32


def test_make_morse_helper():
    x, toks = make_morse("CQ", wpm=20, snr_db=20)
    assert len(toks) == 2
    assert len(x) > 8000 * 0.6
