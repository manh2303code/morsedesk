"""Đọc/ghi file âm thanh và đưa về định dạng nội bộ: mono float32 8 kHz."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from morsedesk.constants import SAMPLE_RATE

SUPPORTED_EXT = (".wav", ".flac", ".ogg", ".mp3", ".aiff", ".aif", ".oga")


class UnsupportedAudio(ValueError):
    pass


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    fr = Fraction(sr_out, sr_in).limit_denominator(1000)
    y = resample_poly(x.astype(np.float64), fr.numerator, fr.denominator)
    return y.astype(np.float32)


def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    x = x.astype(np.float32) - np.float32(np.mean(x))
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    if m > 0:
        x = x * np.float32(peak / m)
    return x


def load_audio(path: str | Path, target_sr: int = SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """Đọc file bất kỳ libsndfile hỗ trợ (WAV/FLAC/OGG/MP3), trả (mono float32 8 kHz, 8000)."""
    path = Path(path)
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except sf.LibsndfileError as e:
        raise UnsupportedAudio(
            f"không đọc được {path.name}: {e}. Định dạng hỗ trợ: {', '.join(SUPPORTED_EXT)}"
        ) from e
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    mono = resample(mono, int(sr), target_sr)
    return normalize(mono), target_sr


def save_audio(path: str | Path, x: np.ndarray, sample_rate: int) -> None:
    sf.write(str(path), np.clip(x, -1.0, 1.0), sample_rate, subtype="PCM_16")


def audio_info(path: str | Path) -> tuple[int, int, float]:
    info = sf.info(str(path))
    return int(info.samplerate), int(info.channels), float(info.duration)
