"""Đọc/ghi file âm thanh và đưa về định dạng nội bộ: mono float32 8 kHz."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
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
    if not path.exists():
        raise FileNotFoundError(f"không tìm thấy file: {path}")
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except sf.LibsndfileError as e:
        raise UnsupportedAudio(
            f"không đọc được {path.name}: {e}. Định dạng hỗ trợ: {', '.join(SUPPORTED_EXT)}"
        ) from e
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    mono = resample(mono, int(sr), target_sr)
    return normalize(mono), target_sr


# libsndfile gọi định dạng theo TÊN, không theo đuôi file, và hai đuôi hợp lệ không trùng tên:
# `.aif` thuộc `AIFF`, `.oga` thuộc `OGG`. Viết hoa đuôi file để suy tên thì hai đuôi này ném
# `TypeError: No format specified and unable to get format from file extension` (CP-07).
EXT_TO_FORMAT = {".aif": "AIFF", ".oga": "OGG"}


def _sndfile_writes_mp3() -> bool:
    """libsndfile có LAME hay không. Tách hàm riêng để test giả lập được máy thiếu LAME."""
    try:
        return "MP3" in sf.available_formats()
    except Exception:                                   # bản libsndfile quá cũ không có API này
        return False


def mp3_capability() -> str | None:
    """Đường xuất MP3 khả dụng: 'libsndfile', 'ffmpeg', hoặc None (CP-06).

    Trang Cài đặt hiện giá trị này để người dùng biết vì sao nút xuất MP3 mờ đi, thay vì bấm rồi
    mới nhận lỗi.
    """
    if _sndfile_writes_mp3():
        return "libsndfile"
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    return None


def _save_mp3_via_ffmpeg(path: Path, x: np.ndarray, sample_rate: int) -> None:
    """Ghi WAV tạm rồi để ffmpeg chuyển mã. Chỉ dùng khi libsndfile không có LAME."""
    tmp = Path(tempfile.mkdtemp(prefix="morsedesk-mp3-")) / "source.wav"
    try:
        sf.write(str(tmp), np.clip(x, -1.0, 1.0), sample_rate, format="WAV", subtype="PCM_16")
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp),
             "-codec:a", "libmp3lame", "-qscale:a", "4", str(path)],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise UnsupportedAudio(
                f"ffmpeg không chuyển mã được sang MP3: {proc.stderr.decode('utf-8', 'replace').strip()}"
            )
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


def save_audio(path: str | Path, x: np.ndarray, sample_rate: int) -> None:
    """Ghi audio theo phần mở rộng của `path`, biên độ clip về [-1, 1].

    Chỉ ép `PCM_16` cho container nhận subtype PCM (WAV, AIFF, FLAC). OGG không nhận PCM_16 —
    libsndfile ném `ValueError: Invalid combination of format, subtype and endian` — nên để
    `soundfile` tự chọn subtype mặc định (Vorbis).
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".mp3" and not _sndfile_writes_mp3():
        if not shutil.which("ffmpeg"):
            raise UnsupportedAudio(
                "không xuất được MP3: libsndfile trên máy này không có bộ mã hóa LAME và cũng "
                "không tìm thấy ffmpeg trong PATH. Cài ffmpeg, hoặc chọn định dạng khác "
                f"({', '.join(e for e in SUPPORTED_EXT if e != '.mp3')})."
            )
        _save_mp3_via_ffmpeg(path, x, sample_rate)
        return
    fmt = EXT_TO_FORMAT.get(ext, ext.lstrip(".").upper())   # WAV, FLAC, OGG, AIFF…
    subtype = "PCM_16" if sf.check_format(fmt, "PCM_16") else None
    sf.write(str(path), np.clip(x, -1.0, 1.0), sample_rate, format=fmt, subtype=subtype)


def audio_info(path: str | Path) -> tuple[int, int, float]:
    info = sf.info(str(path))
    return int(info.samplerate), int(info.channels), float(info.duration)
