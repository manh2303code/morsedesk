import numpy as np

from morsedesk.constants import FEAT_DIM, HOP, SAMPLE_RATE
from morsedesk.dsp.frontend import agc_log, compute_features, mix_envelope, spectral_bins
from morsedesk.encode.timing import TimingParams, elements_to_segments, tokens_to_elements
from tests.helpers import make_morse

PAD_S = 0.3


def _on_off_frame_masks(tokens, wpm, n_frames):
    els = tokens_to_elements(tokens, TimingParams(wpm=wpm))
    segs = elements_to_segments(els, SAMPLE_RATE)
    offset = int(PAD_S * SAMPLE_RATE)
    on = np.zeros(n_frames, dtype=bool)
    for is_on, s, e in segs:
        if is_on:
            f0, f1 = (s + offset) // HOP + 1, (e + offset) // HOP - 1   # bỏ khung biên
            if f1 > f0:
                on[f0:f1] = True
    return on


def test_feature_shape_and_dtype():
    x, _ = make_morse("PARIS PARIS", wpm=20)
    feats = compute_features(x, 700.0)
    assert feats.shape == (len(x) // HOP, FEAT_DIM)
    assert feats.dtype == np.float32
    assert np.all(np.isfinite(feats))


def test_envelope_contrast_on_vs_off():
    x, toks = make_morse("PARIS PARIS", wpm=20)
    env = mix_envelope(x, 700.0)
    on = _on_off_frame_masks(toks, 20, len(env))
    off = ~on
    off[: int(PAD_S * 200)] = False
    assert env[on].mean() > 5 * env[off].mean()


def test_agc_contrast_and_bounds():
    x, toks = make_morse("PARIS PARIS PARIS", wpm=25, snr_db=10.0, seed=2)
    feats = compute_features(x, 700.0)
    a = feats[:, 0]
    on = _on_off_frame_masks(toks, 25, len(a))
    assert a[on].mean() - a[~on].mean() > 1.0
    assert a.min() >= -6.0 and a.max() <= 6.0


def test_agc_on_silence_is_finite_zero():
    env = np.zeros(1000)
    a = agc_log(env)
    assert np.all(np.isfinite(a))
    assert np.allclose(a, 0.0)


def test_spectral_bins_peak_in_center():
    x, _ = make_morse("EEEEEEEEEE", wpm=20, tone_hz=700.0)
    bins = spectral_bins(x, 700.0)
    assert bins.shape == (len(x) // HOP, 9)
    center_energy = bins[:, 4].mean()
    edge_energy = bins[:, [0, 8]].mean()
    assert center_energy > edge_energy


def test_derivative_column_is_diff_of_agc():
    x, _ = make_morse("SOS", wpm=20)
    feats = compute_features(x, 700.0)
    d = np.diff(feats[:, 0], prepend=feats[0, 0])
    assert np.allclose(feats[:, 1], d, atol=1e-5)
