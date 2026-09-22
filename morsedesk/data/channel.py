"""Kênh truyền: QSB, QRM, QRN, AWGN, lọc băng, mức, clipping, DC, codec MP3 (tùy chọn, cần ffmpeg)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.synth import add_noise

QrmFactory = Callable[[int, float, np.random.Generator], np.ndarray]


@dataclass(frozen=True)
class ChannelParams:
    tone_hz: float
    tone_drift_hz_per_s: float
    snr_db: float
    qsb_depth_db: float          # 0 = không QSB
    qsb_period_s: float
    qrm_offset_hz: float
    qrm_level_db: float          # QRM thấp hơn tín hiệu bao nhiêu dB
    qrm_kind: str                # "none" | "morse" | "carrier"
    qrn_rate_per_s: float        # 0 = không xung
    bandpass: bool
    gain: float
    clip: bool
    dc_offset: float
    mp3_kbps: int | None
    name: str = "random"


def clean(snr_db: float = 30.0, tone_hz: float = 700.0, name: str = "clean") -> ChannelParams:
    return ChannelParams(tone_hz, 0.0, snr_db, 0.0, 10.0, 0.0, 0.0, "none", 0.0, True, 1.0, False, 0.0, None, name)


@dataclass(frozen=True)
class ChannelSampling:
    """Tham số lấy mẫu kênh khi sinh dữ liệu huấn luyện. Mặc định = phân bố tuần 1–4."""

    qsb_prob: float = 0.4
    qsb_depth_db: tuple[float, float] = (5.0, 30.0)
    qsb_period_s: tuple[float, float] = (2.0, 20.0)
    # Vùng khó: nơi CER được quyết định, giữ nguyên phân bố tuần 1-4.
    snr_db: tuple[float, float] = (-6.0, 25.0)
    # Đuôi sạch (SNR 25-65 dB như bản ghi thật của ARRL). MẶC ĐỊNH TẮT sau thí nghiệm E11:
    # bật 20 % làm CER trên T1 xấu đi 6,6 điểm (26,80 % so với 20,21 % của E3, cùng seed 13,
    # cùng 30 000 bước, chỉ khác dữ liệu), vì một phần năm dung lượng huấn luyện dồn vào vùng mà
    # T1 không hề đo. Đổi lại KHÔNG được gì trên T2: trên bản ghi thật, `dsp/selection.py` lấy
    # kết quả bộ DSP nên cả hai model cho số liệu giống hệt nhau tới từng chữ số.
    # Giữ tham số để thử lại với tỉ lệ nhỏ hơn; xem docs/research/03-model-experiments.md.
    clean_tail_db: tuple[float, float] = (25.0, 65.0)
    clean_tail_prob: float = 0.0


DEFAULT_SAMPLING = ChannelSampling()
CLEAN_TAIL_PROB = DEFAULT_SAMPLING.clean_tail_prob
# Ô qsb của T1 là depth đúng 20 dB, chu kỳ đúng 4 s (tools/make_t1.py). Phân bố mặc định hiếm khi
# rơi vào vùng đó (chu kỳ rải đều 2–20 s), nên E6 kéo phân bố về đúng độ khó của T1 và tăng tỉ lệ
# lấy mẫu QSB từ 40 % lên 60 %.
HARD_QSB_SAMPLING = ChannelSampling(qsb_prob=0.6, qsb_depth_db=(10.0, 24.0), qsb_period_s=(2.0, 8.0))


def _sample_snr(rng: np.random.Generator, s: ChannelSampling) -> float:
    """SNR huấn luyện: phần lớn ở vùng khó, một phần nhỏ ở vùng sạch như bản ghi thật.

    Lấy mẫu hai đoạn rời chứ không nới rộng một `uniform`: nới rộng sẽ làm loãng chính vùng
    quyết định CER, còn ở đây tỉ lệ đuôi sạch là tham số riêng.
    """
    if s.clean_tail_prob > 0.0 and rng.random() < s.clean_tail_prob:
        return float(rng.uniform(*s.clean_tail_db))
    return float(rng.uniform(*s.snr_db))


def sample_channel_params(rng: np.random.Generator,
                          sampling: ChannelSampling | None = None) -> ChannelParams:
    s = sampling or DEFAULT_SAMPLING
    qsb = rng.random() < s.qsb_prob
    qrm = rng.random() < 0.25
    return ChannelParams(
        tone_hz=float(rng.uniform(400.0, 1200.0)),
        tone_drift_hz_per_s=float(rng.uniform(-2.0, 2.0)),
        snr_db=_sample_snr(rng, s),
        qsb_depth_db=float(rng.uniform(*s.qsb_depth_db)) if qsb else 0.0,
        qsb_period_s=float(rng.uniform(*s.qsb_period_s)),
        qrm_offset_hz=float(rng.choice([-1.0, 1.0]) * rng.uniform(150.0, 600.0)) if qrm else 0.0,
        qrm_level_db=float(rng.uniform(3.0, 20.0)) if qrm else 0.0,
        qrm_kind=("morse" if rng.random() < 0.7 else "carrier") if qrm else "none",
        qrn_rate_per_s=float(rng.uniform(5.0, 50.0)) if rng.random() < 0.2 else 0.0,
        bandpass=True,
        gain=float(rng.uniform(0.1, 1.0)),
        clip=bool(rng.random() < 0.05),
        dc_offset=float(rng.uniform(-0.1, 0.1)) if rng.random() < 0.2 else 0.0,
        mp3_kbps=int(rng.choice([48, 64, 96, 128])) if rng.random() < 0.3 else None,
    )


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def mp3_roundtrip(x: np.ndarray, sample_rate: int, kbps: int) -> np.ndarray:
    """Mã hóa MP3 rồi giải mã lại bằng ffmpeg (tiến trình ngoài). Không có ffmpeg -> trả nguyên."""
    if not ffmpeg_available():
        return x
    scale = max(1.0, float(np.max(np.abs(x))) if len(x) else 1.0)
    with tempfile.TemporaryDirectory() as tmp:
        wav, mp3 = Path(tmp) / "in.wav", Path(tmp) / "out.mp3"
        sf.write(wav, x / scale, sample_rate, subtype="PCM_16")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame",
                 "-b:a", f"{kbps}k", str(mp3)],
                check=True, capture_output=True,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            logging.getLogger(__name__).warning(
                "ffmpeg thất bại, bỏ qua MP3: %s", (getattr(e, "stderr", b"") or b"")[-300:]
            )
            return x
        y, sr = sf.read(mp3, dtype="float32", always_2d=True)
    y = y.mean(axis=1) * scale
    if len(y) >= len(x):
        y = y[: len(x)]
    else:
        y = np.pad(y, (0, len(x) - len(y)))
    return y.astype(np.float32)


def apply_channel(
    x: np.ndarray,
    p: ChannelParams,
    rng: np.random.Generator,
    sample_rate: int = SAMPLE_RATE,
    signal_power: float = 0.32,
    qrm_factory: QrmFactory | None = None,
) -> np.ndarray:
    y = np.asarray(x, dtype=np.float64).copy()
    n = len(y)
    t = np.arange(n) / sample_rate

    if p.qsb_depth_db > 0:
        phase = rng.uniform(0.0, 2.0 * np.pi)
        g_db = -p.qsb_depth_db * 0.5 * (1.0 - np.cos(2.0 * np.pi * t / p.qsb_period_s + phase))
        y *= 10.0 ** (g_db / 20.0)

    if p.qrm_kind != "none":
        level = 10.0 ** (-p.qrm_level_db / 20.0)
        f_qrm = p.tone_hz + p.qrm_offset_hz
        if p.qrm_kind == "morse" and qrm_factory is not None:
            q = qrm_factory(n, f_qrm, rng)
        else:
            q = 0.8 * np.sin(2.0 * np.pi * f_qrm * t)
        y += level * q[:n]

    if p.qrn_rate_per_s > 0:
        n_imp = int(rng.poisson(p.qrn_rate_per_s * n / sample_rate))
        for pos in rng.integers(0, max(1, n - 32), size=n_imp):
            width = int(rng.integers(8, 24))
            amp = float(rng.uniform(2.0, 10.0)) * 0.8 * float(rng.choice([-1.0, 1.0]))
            y[pos:pos + width] += amp * np.exp(-3.0 * np.arange(width) / width)

    y = add_noise(y.astype(np.float32), p.snr_db, signal_power, sample_rate, rng=rng).astype(np.float64)

    if p.bandpass:
        sos = butter(4, [300.0, 3000.0], btype="band", fs=sample_rate, output="sos")
        y = sosfiltfilt(sos, y)

    y *= p.gain
    if p.clip:
        y = np.clip(y * 1.5, -1.0, 1.0)
    y += p.dc_offset
    y = y.astype(np.float32)
    if p.mp3_kbps:
        y = mp3_roundtrip(y, sample_rate, p.mp3_kbps)
    return y
