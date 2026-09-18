import numpy as np
import pytest
import soundfile as sf

from morsedesk.audio.io import UnsupportedAudio, audio_info, load_audio, normalize, resample, save_audio


def _sine(sr, seconds, hz, ch=1):
    t = np.arange(int(sr * seconds)) / sr
    x = 0.5 * np.sin(2 * np.pi * hz * t).astype(np.float32)
    return np.stack([x] * ch, axis=1) if ch > 1 else x


def test_load_resamples_stereo_44k_to_mono_8k(tmp_path):
    p = tmp_path / "a.wav"
    sf.write(p, _sine(44100, 1.0, 440, ch=2), 44100)
    x, sr = load_audio(p)
    assert sr == 8000
    assert x.dtype == np.float32
    assert x.ndim == 1
    assert abs(len(x) - 8000) <= 2
    assert np.isclose(np.max(np.abs(x)), 0.9, atol=0.01)


def test_load_removes_dc(tmp_path):
    p = tmp_path / "dc.wav"
    sf.write(p, (_sine(8000, 1.0, 700) + 0.2).astype(np.float32), 8000)
    x, _ = load_audio(p)
    assert abs(float(np.mean(x))) < 1e-3


def test_load_flac_and_ogg(tmp_path):
    for ext in ("flac", "ogg"):
        p = tmp_path / f"a.{ext}"
        sf.write(p, _sine(16000, 0.5, 700), 16000)
        x, sr = load_audio(p)
        assert sr == 8000 and abs(len(x) - 4000) <= 2


def test_unsupported_file(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_text("không phải audio", encoding="utf-8")
    with pytest.raises(UnsupportedAudio):
        load_audio(p)


def test_save_and_info(tmp_path):
    p = tmp_path / "o.wav"
    save_audio(p, _sine(8000, 2.0, 700) * 3.0, 8000)   # vượt 1.0 phải được clip
    sr, ch, dur = audio_info(p)
    assert (sr, ch) == (8000, 1)
    assert abs(dur - 2.0) < 1e-3
    y, _ = sf.read(p)
    assert np.max(np.abs(y)) <= 1.0


def test_resample_identity_and_ratio():
    x = _sine(8000, 1.0, 700)
    assert resample(x, 8000, 8000) is x
    y = resample(x, 8000, 16000)
    assert abs(len(y) - 16000) <= 2


def test_normalize_zero_signal():
    z = np.zeros(100, dtype=np.float32)
    assert np.all(normalize(z) == 0)
