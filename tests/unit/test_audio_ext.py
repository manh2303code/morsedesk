"""Mọi đuôi trong SUPPORTED_EXT phải ghi được và đọc lại được (CP-07).

libsndfile gọi định dạng theo TÊN, không theo đuôi file: `.aif` thuộc định dạng `AIFF` và `.oga`
thuộc `OGG`. Suy tên format bằng cách viết hoa đuôi file thì hai đuôi này ném
`ValueError: Invalid value for format`, dù chúng vẫn nằm trong danh sách mở file của GUI.
"""

import numpy as np
import pytest

from morsedesk.audio.io import SUPPORTED_EXT, audio_info, load_audio, save_audio

RATE = 8000


def tone(seconds: float = 0.25) -> np.ndarray:
    t = np.arange(int(RATE * seconds), dtype=np.float32) / RATE
    return (0.5 * np.sin(2 * np.pi * 600.0 * t)).astype(np.float32)


@pytest.mark.parametrize("ext", SUPPORTED_EXT)
def test_roundtrip_every_supported_extension(tmp_path, ext):
    if ext == ".mp3":
        pytest.skip("ghi MP3 là CP-06, có nhánh riêng và có thể thiếu bộ mã hóa")
    path = tmp_path / f"clip{ext}"
    x = tone()
    save_audio(path, x, RATE)
    assert path.is_file() and path.stat().st_size > 0
    rate, channels, duration = audio_info(path)
    assert rate == RATE and channels == 1
    assert duration == pytest.approx(len(x) / RATE, abs=0.02)
    y, sr = load_audio(path)
    assert sr == RATE
    # `load_audio` chuẩn hóa đỉnh về 0,9, nên so dạng sóng đã chuẩn hóa: nén có tổn hao
    # (ogg/oga) chỉ cần giữ đúng tỉ lệ RMS trên đỉnh, không cần giống từng mẫu.
    def shape(v: np.ndarray) -> float:
        peak = float(np.max(np.abs(v)))
        return float(np.sqrt(np.mean((v / peak) ** 2))) if peak else 0.0

    assert abs(shape(y) - shape(x)) < 0.05
