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


def fallback_tone_hz(x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float | None:
    """Đỉnh phổ trong dải tone, dùng khi `estimate_tone` không đủ tự tin để báo có tín hiệu.

    `estimate_tone` đòi đỉnh nhô lên `MIN_PEAK_DB` so với nền; ở 0 dB SNR kèm fading QSB thì
    ngưỡng đó không đạt và cả clip bị trả rỗng (CER 1,0). Đoán theo đỉnh phổ kém chắc chắn hơn
    nhiều, nhưng đo trên T1 cho 74,8 % thay vì 100 % trên đúng nhóm clip đó, nên vẫn hơn bỏ cuộc.
    Trả `None` khi clip quá ngắn để dựng phổ.
    """
    if len(x) < N_FFT * 2:
        return None
    power, freqs = stft_power(x, sample_rate=sample_rate)
    band = (freqs >= TONE_MIN_HZ) & (freqs <= TONE_MAX_HZ)
    if not band.any():
        return None
    p90 = np.percentile(power, 90, axis=1)
    idx = np.flatnonzero(band)
    return float(freqs[idx[int(np.argmax(p90[band]))]])


# Ước lượng tone không cần cả clip: một tone CW ổn định lộ ra sau vài chục giây. Đo ngày 22/09,
# clip 20 phút (38 MB dữ liệu) làm hàm này chiếm 1 805 MB vì STFT chạy trên toàn bộ, và cả lượt
# giải mã file 60 phút chạm 5,4 GB — quá nhiều cho máy air-gap, và là thứ chặn CP-14.
MAX_ANALYSIS_SECONDS = 60.0
N_ANALYSIS_SLICES = 6        # rải đều để không bị lừa bởi một đoạn im lặng hay một đoạn nhiễu


def analysis_slice(x: np.ndarray, sample_rate: int = SAMPLE_RATE,
                   max_seconds: float = MAX_ANALYSIS_SECONDS,
                   n_slices: int = N_ANALYSIS_SLICES) -> np.ndarray:
    """Phần clip đủ để ước lượng tone: nguyên clip nếu ngắn, hoặc vài đoạn rải đều nếu dài.

    Ghép các đoạn rời tạo ra chỗ nối không liên tục, nhưng STFT lấy phân vị 90 theo thời gian
    nên vài khung ở chỗ nối không đổi được đỉnh phổ.
    """
    limit = int(max_seconds * sample_rate)
    if len(x) <= limit:
        return x
    per = limit // n_slices
    step = (len(x) - per) // (n_slices - 1)
    return np.concatenate([x[i * step: i * step + per] for i in range(n_slices)])


def estimate_tone(x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> ToneEstimate:
    if len(x) < N_FFT * 2:
        return ToneEstimate(None, 0.0, False, None)
    x = analysis_slice(x, sample_rate)
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
