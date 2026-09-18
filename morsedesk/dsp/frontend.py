"""Đặc trưng 11 chiều ở 200 khung/giây quanh tone đã dò.

Cột 0: log-envelope sau AGC; cột 1: đạo hàm cột 0; cột 2..10: 9 bin log-phổ quanh f0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi, sosfiltfilt

from morsedesk.constants import FEAT_DIM, FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.dsp.stft import stft_power


@dataclass(frozen=True)
class FrontendConfig:
    lowpass_hz: float = 200.0
    agc_tau_s: float = 1.0
    n_bins: int = 9


def mix_envelope(
    x: np.ndarray, f0_hz: float, sample_rate: int = SAMPLE_RATE, lowpass_hz: float = 200.0
) -> np.ndarray:
    """Trộn xuống băng gốc phức tại f0, lọc thấp, |I+jQ|, trung bình mỗi HOP mẫu.

    Khung t được căn giữa tại mẫu t*HOP, giống stft_power: pad env với HOP//2 mẫu 0
    ở đầu (và HOP mẫu 0 ở cuối để đủ cho khung cuối) rồi lấy trung bình từng khung
    HOP mẫu, sao cho khung t phủ [t*HOP - HOP//2, t*HOP + HOP//2).
    """
    n = len(x)
    n_frames = n // HOP
    if n_frames == 0:
        return np.zeros(0)
    t = np.arange(n) / sample_rate
    lo = np.exp(-2j * np.pi * f0_hz * t)
    y = x.astype(np.float64) * lo
    sos = butter(4, lowpass_hz, btype="low", fs=sample_rate, output="sos")
    yi = sosfiltfilt(sos, y.real)
    yq = sosfiltfilt(sos, y.imag)
    env = np.sqrt(yi * yi + yq * yq)
    env_p = np.pad(env, (HOP // 2, HOP))
    return env_p[: n_frames * HOP].reshape(n_frames, HOP).mean(axis=1)


def _ema(v: np.ndarray, alpha: float, init: float) -> np.ndarray:
    b = np.array([alpha])
    a = np.array([1.0, -(1.0 - alpha)])
    zi = lfilter_zi(b, a) * init
    out, _ = lfilter(b, a, v, zi=zi)
    return out


def agc_log(env: np.ndarray, frame_rate: int = FRAME_RATE, tau_s: float = 1.0) -> np.ndarray:
    """log(envelope) trừ mức nền trượt, chia độ lệch chuẩn trượt; kẹp về [-6, 6]."""
    if len(env) == 0:
        return np.zeros(0)
    log_env = np.log(env + 1e-6)
    alpha = 1.0 / (tau_s * frame_rate)
    head = log_env[: max(1, min(len(log_env), frame_rate))]
    mean = _ema(log_env, alpha, float(np.mean(head)))
    dev = log_env - mean
    var = _ema(dev * dev, alpha, float(np.mean(dev[: len(head)] ** 2)))
    out = dev / (np.sqrt(np.maximum(var, 0.0)) + 0.1)
    return np.clip(out, -6.0, 6.0)


def spectral_bins(
    x: np.ndarray, f0_hz: float, n_bins: int = 9, sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    n_frames = len(x) // HOP
    if n_frames == 0:
        return np.zeros((0, n_bins), dtype=np.float32)
    power, freqs = stft_power(x, sample_rate=sample_rate)
    bin_hz = float(freqs[1] - freqs[0])
    k0 = int(round(f0_hz / bin_hz))
    half = n_bins // 2
    ks = np.clip(np.arange(k0 - half, k0 - half + n_bins), 0, len(freqs) - 1)
    logp = np.log10(power[ks, :] + 1e-12).T            # [T, n_bins]
    med = float(np.median(logp))
    scale = float(np.percentile(logp, 95)) - med + 1e-3
    return ((logp - med) / scale).astype(np.float32)


def compute_features(
    x: np.ndarray,
    f0_hz: float,
    sample_rate: int = SAMPLE_RATE,
    cfg: FrontendConfig = FrontendConfig(),
) -> np.ndarray:
    n_frames = len(x) // HOP
    if n_frames == 0:
        return np.zeros((0, FEAT_DIM), dtype=np.float32)
    env = mix_envelope(x, f0_hz, sample_rate, cfg.lowpass_hz)
    a = agc_log(env, FRAME_RATE, cfg.agc_tau_s)
    d = np.diff(a, prepend=a[0] if len(a) else 0.0)
    bins = spectral_bins(x, f0_hz, cfg.n_bins, sample_rate)
    feats = np.concatenate([a[:, None], d[:, None], bins], axis=1).astype(np.float32)
    assert feats.shape == (n_frames, FEAT_DIM), feats.shape
    return feats
