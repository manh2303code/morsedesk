import numpy as np

from morsedesk.constants import HOP, N_FFT
from morsedesk.dsp.stft import stft_power
from morsedesk.dsp.tone import MIN_PEAK_DB, estimate_tone
from morsedesk.encode.synth import add_noise
from tests.helpers import make_morse

TEXT = "CQ CQ DE R1ABC R1ABC K"


def test_stft_shapes():
    x = np.zeros(8000, dtype=np.float32)
    power, freqs = stft_power(x)
    assert power.shape == (N_FFT // 2 + 1, 8000 // HOP)
    assert np.isclose(freqs[1] - freqs[0], 31.25)


def test_clean_tone_700():
    x, _ = make_morse(TEXT, wpm=20, tone_hz=700.0)
    est = estimate_tone(x)
    assert est.has_signal
    assert abs(est.f0_hz - 700.0) < 10.0
    assert est.second_peak_hz is None


def test_noisy_tone_and_snr_estimate():
    x, _ = make_morse(TEXT, wpm=25, tone_hz=850.0, snr_db=10.0, seed=3)
    est = estimate_tone(x)
    assert est.has_signal
    assert abs(est.f0_hz - 850.0) < 15.0
    assert abs(est.snr_db - 10.0) < 4.0


def test_low_snr_still_detected():
    x, _ = make_morse(TEXT, wpm=20, tone_hz=600.0, snr_db=0.0, seed=5)
    est = estimate_tone(x)
    assert est.has_signal
    assert abs(est.f0_hz - 600.0) < 20.0


def test_noise_only_no_signal():
    rng = np.random.default_rng(7)
    x = add_noise(np.zeros(8000 * 5, dtype=np.float32), 0.0, 0.32, rng=rng)
    est = estimate_tone(x)
    assert not est.has_signal
    assert est.f0_hz is None


def test_silence_no_signal():
    est = estimate_tone(np.zeros(8000 * 2, dtype=np.float32))
    assert not est.has_signal


def test_two_tones_reports_second_peak():
    a, _ = make_morse(TEXT, wpm=20, tone_hz=600.0)
    b, _ = make_morse("TEST TEST TEST TEST TEST", wpm=18, tone_hz=1000.0)
    n = min(len(a), len(b))
    x = a[:n] + 0.8 * b[:n]
    est = estimate_tone(x)
    assert est.has_signal
    assert est.second_peak_hz is not None
    other = 1000.0 if abs(est.f0_hz - 600.0) < 40 else 600.0
    assert abs(est.second_peak_hz - other) < 40.0


def test_too_short_input():
    est = estimate_tone(np.zeros(100, dtype=np.float32))
    assert not est.has_signal and est.snr_db == 0.0
    assert MIN_PEAK_DB == 6.0
