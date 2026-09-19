"""STFT công suất dùng chung cho dò tone và đặc trưng phổ."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import HOP, N_FFT, SAMPLE_RATE


def stft_power(
    x: np.ndarray, sample_rate: int = SAMPLE_RATE, n_fft: int = N_FFT, hop: int = HOP
) -> tuple[np.ndarray, np.ndarray]:
    """Trả (power [n_bins, T], freqs [n_bins]).

    T = len(x)//hop, khung t căn giữa tại mẫu t*hop, cửa sổ Hann, pad hai đầu.
    """
    n = len(x)
    n_frames = n // hop
    pad = n_fft // 2
    xp = np.pad(np.asarray(x, dtype=np.float64), (pad, pad + n_fft))
    idx = np.arange(n_frames)[:, None] * hop + np.arange(n_fft)[None, :]
    frames = xp[idx] * np.hanning(n_fft)[None, :]
    spec = np.fft.rfft(frames, axis=1)
    power = (np.abs(spec) ** 2).T
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    return power, freqs
