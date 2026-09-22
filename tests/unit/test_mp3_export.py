"""Xuất MP3 theo ba nhánh của CP-06: libsndfile -> ffmpeg ngoài -> báo lỗi rõ.

libsndfile 1.2.2 đã tự ghi được MP3 (`MPEG_LAYER_III`), nên nhánh một là đường chính trên máy
dev. Hai nhánh còn lại phải kiểm bằng cách giả lập, vì không dựng được máy thiếu LAME trong test.
"""

import numpy as np
import pytest

from morsedesk.audio.io import UnsupportedAudio, audio_info, mp3_capability, save_audio

RATE = 8000


def tone(seconds: float = 0.25) -> np.ndarray:
    t = np.arange(int(RATE * seconds), dtype=np.float32) / RATE
    return (0.5 * np.sin(2 * np.pi * 600.0 * t)).astype(np.float32)


def test_capability_reports_one_of_three_states():
    assert mp3_capability() in ("libsndfile", "ffmpeg", None)


def test_libsndfile_branch_writes_readable_mp3(tmp_path):
    if mp3_capability() != "libsndfile":
        pytest.skip("libsndfile bản này không ghi được MP3")
    path = tmp_path / "clip.mp3"
    save_audio(path, tone(), RATE)
    rate, channels, duration = audio_info(path)
    assert rate == RATE and channels == 1 and duration == pytest.approx(0.25, abs=0.05)


def test_ffmpeg_branch_used_when_libsndfile_cannot(tmp_path, monkeypatch):
    """Không có LAME trong libsndfile thì phải gọi ffmpeg ngoài, không được ném lỗi."""
    called = {}

    def fake_run(cmd, **kw):
        called["cmd"] = cmd
        dst = cmd[-1]
        with open(dst, "wb") as f:                      # ffmpeg giả: chỉ tạo file
            f.write(b"ID3")
        import subprocess

        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr("morsedesk.audio.io._sndfile_writes_mp3", lambda: False)
    monkeypatch.setattr("morsedesk.audio.io.shutil.which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr("morsedesk.audio.io.subprocess.run", fake_run)
    path = tmp_path / "clip.mp3"
    save_audio(path, tone(), RATE)
    assert path.is_file()
    assert "ffmpeg" in called["cmd"][0]
    assert str(path) == called["cmd"][-1]


def test_clear_error_when_no_encoder_available(tmp_path, monkeypatch):
    monkeypatch.setattr("morsedesk.audio.io._sndfile_writes_mp3", lambda: False)
    monkeypatch.setattr("morsedesk.audio.io.shutil.which", lambda name: None)
    with pytest.raises(UnsupportedAudio) as e:
        save_audio(tmp_path / "clip.mp3", tone(), RATE)
    msg = str(e.value)
    assert "mp3" in msg.lower() and "ffmpeg" in msg.lower()
    assert not (tmp_path / "clip.mp3").exists()         # không để lại file dở dang


def test_capability_follows_the_same_probes(monkeypatch):
    monkeypatch.setattr("morsedesk.audio.io._sndfile_writes_mp3", lambda: False)
    monkeypatch.setattr("morsedesk.audio.io.shutil.which", lambda name: "/usr/bin/ffmpeg")
    assert mp3_capability() == "ffmpeg"
    monkeypatch.setattr("morsedesk.audio.io.shutil.which", lambda name: None)
    assert mp3_capability() is None
