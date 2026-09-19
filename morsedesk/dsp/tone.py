"""Ước lượng tần số tone Morse, SNR trong băng 500 Hz, có tín hiệu hay không."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.constants import N_FFT, SAMPLE_RATE, TONE_MAX_HZ, TONE_MIN_HZ
from morsedesk.dsp.stft import stft_power

MIN_PEAK_DB = 6.0          # độ nhọn tối thiểu để coi là có tín hiệu
HANN_SPREAD_DB = 1.76      # bù công suất tone trải sang bin lân cận do cửa sổ Hann
BAND_BINS_DB = 12.04       # 10*log10(16 bin) = băng 500 Hz với bin 31.25 Hz


@dataclass
class ToneEstimate:
    f0_hz: float | None
    snr_db: float
    has_signal: bool
    second_peak_hz: float | None


def _parabolic_peak_hz(p90: np.ndarray, k: int, freqs: np.ndarray) -> float:
    if k <= 0 or k >= len(p90) - 1:
        return float(freqs[k])
    a, b, c = (np.log(p90[k - 1] + 1e-20), np.log(p90[k] + 1e-20), np.log(p90[k + 1] + 1e-20))
    denom = a - 2.0 * b + c
    delta = 0.0 if denom == 0 else float(np.clip(0.5 * (a - c) / denom, -1.0, 1.0))
    return float(freqs[k] + delta * (freqs[1] - freqs[0]))


def _noise_bin_power(power: np.ndarray, k: int, band: np.ndarray) -> float:
    """Trung vị theo thời gian của công suất các bin cách tone 4..8 bin, trong băng."""
    idx = [j for j in list(range(k - 8, k - 3)) + list(range(k + 4, k + 9))
           if 0 <= j < power.shape[0] and band[j]]
    if not idx:
        idx = [j for j in range(power.shape[0]) if band[j] and abs(j - k) > 3]
    return float(np.median(power[idx, :])) + 1e-20


def estimate_tone(x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> ToneEstimate:
    if len(x) < N_FFT * 2:
        return ToneEstimate(None, 0.0, False, None)
    power, freqs = stft_power(x, sample_rate=sample_rate)
    band = (freqs >= TONE_MIN_HZ) & (freqs <= TONE_MAX_HZ)
    p90 = np.percentile(power, 90, axis=1) + 1e-20
    floor = float(np.median(p90[band]))
    if floor <= 1e-18:
        return ToneEstimate(None, 0.0, False, None)
    peakiness = np.where(band, 10.0 * np.log10(p90 / floor), -np.inf)

    k = int(np.argmax(peakiness))
    if not np.isfinite(peakiness[k]) or peakiness[k] < MIN_PEAK_DB:
        return ToneEstimate(None, 0.0, False, None)

    f0 = _parabolic_peak_hz(p90, k, freqs)
    noise_bin = _noise_bin_power(power, k, band)
    sig_bin = max(float(p90[k]) - noise_bin, 1e-20)
    snr_db = 10.0 * np.log10(sig_bin / noise_bin) + HANN_SPREAD_DB - BAND_BINS_DB

    masked = peakiness.copy()
    masked[max(0, k - 2): k + 3] = -np.inf
    k2 = int(np.argmax(masked))
    second = None
    if np.isfinite(masked[k2]) and masked[k2] >= MIN_PEAK_DB and p90[k2] >= 0.5 * p90[k]:
        second = float(freqs[k2])
    return ToneEstimate(f0, float(snr_db), True, second)
