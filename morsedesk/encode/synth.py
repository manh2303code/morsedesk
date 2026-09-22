"""Phần tử bật/tắt -> sóng âm, và thêm nhiễu theo SNR trong băng."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.timing import Element, elements_to_segments


def tone_power(amplitude: float) -> float:
    """Công suất trung bình của sine biên độ A khi phím đang bật."""
    return amplitude * amplitude / 2.0


def elements_to_audio(
    elements: list[Element],
    tone_hz: float | np.ndarray = 700.0,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.8,
    ramp_ms: float = 5.0,
) -> np.ndarray:
    """Sine liên tục pha, cửa bật/tắt có sườn raised-cosine để không lách tách.

    tone_hz là số (tone cố định) hoặc mảng tần số tức thời; mảng khác độ dài sẽ
    được nội suy theo thời gian.
    """
    segs = elements_to_segments(elements, sample_rate)
    n = segs[-1][2] if segs else 0
    if n == 0:
        return np.zeros(0, dtype=np.float32)

    if np.isscalar(tone_hz):
        freq = np.full(n, float(tone_hz))
    else:
        f = np.asarray(tone_hz, dtype=np.float64)
        freq = f if len(f) == n else np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(f)), f)
    phase = 2.0 * np.pi * np.cumsum(freq) / sample_rate
    carrier = np.sin(phase)

    ramp = max(1, int(round(ramp_ms * 1e-3 * sample_rate)))
    gate = np.zeros(n)
    for i, (on, s, e) in enumerate(segs):
        if not on or e <= s:
            continue
        # Sườn CƯỠI LÊN ranh giới: nửa nằm trong khoảng lặng kề, nửa nằm trong dấu. Đặt cả sườn
        # bên trong dấu làm mọi dấu ngắn đi đúng một `ramp` khi đo ở 50 % biên độ và mọi khoảng
        # lặng dài thêm chừng ấy — ở 30 WPM điều đó đẩy tỉ lệ dah/dit từ 3,00 lên 3,29, đủ để
        # một máy thu đo tỉ lệ thấy lệch. Với sườn đối xứng, độ dài ở 50 % đúng bằng danh nghĩa.
        r = min(ramp, e - s)
        before = segs[i - 1] if i > 0 else None
        after = segs[i + 1] if i + 1 < len(segs) else None
        gap_before = (before[2] - before[1]) if before is not None and not before[0] else s
        gap_after = (after[2] - after[1]) if after is not None and not after[0] else n - e
        # Lấn tối đa NỬA khoảng lặng mỗi bên: nửa còn lại dành cho dấu bên kia, nếu không hai
        # dấu cách nhau đúng một dit sẽ dính vào nhau. Ở mép clip không có gì để lấn nên phần
        # sườn đó nằm trong dấu — chuyện đó không ảnh hưởng tỉ lệ giữa các dấu.
        head = min(r // 2, max(0, gap_before) // 2, s)
        tail = min(r - r // 2, max(0, gap_after) // 2, n - e)
        lo, hi = s - head, e + tail
        length = hi - lo
        env = np.ones(length)
        if r > 0 and length >= 2 * r:
            k = np.arange(r)
            rc = 0.5 * (1.0 - np.cos(np.pi * k / r))
            env[:r] = rc
            env[length - r:] = rc[::-1]
        gate[lo:hi] = np.maximum(gate[lo:hi], env)
    return (amplitude * carrier * gate).astype(np.float32)


def add_noise(
    x: np.ndarray,
    snr_db: float,
    signal_power: float,
    sample_rate: int = SAMPLE_RATE,
    band_hz: float = 500.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Thêm AWGN sao cho SNR đo trong băng band_hz quanh tone bằng snr_db.

    Nhiễu trắng trải đều 0..sample_rate/2, nên phương sai tổng =
    (công suất nhiễu trong băng) * (sample_rate/2) / band_hz.
    """
    rng = np.random.default_rng() if rng is None else rng
    p_noise_band = signal_power / (10.0 ** (snr_db / 10.0))
    sigma2 = p_noise_band * (sample_rate / 2.0) / band_hz
    noise = rng.normal(0.0, np.sqrt(sigma2), size=len(x))
    return (x.astype(np.float64) + noise).astype(np.float32)
