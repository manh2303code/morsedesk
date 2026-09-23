"""Lõi phát audio: vị trí, pause giữ chỗ, seek, kết thúc sạch.

Dùng `OutputStream` giả trong fixture `fake_sounddevice` thay vì thiết bị thật: máy CI và máy
Linux air-gap có thể không có card âm thanh nào, và dù có thì nhịp callback của thiết bị thật
không tất định nên test sẽ chập chờn.
"""

from __future__ import annotations

import numpy as np
import pytest

from morsedesk.audio.playback import AudioPlayback, PlaybackError


def _ramp(n: int) -> np.ndarray:
    """Mảng có giá trị khác nhau ở mọi vị trí, để biết chắc khối nào đã ra loa."""
    return np.arange(n, dtype=np.float32) / n


def test_position_follows_frames_pushed(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(1000))
    assert p.duration_s == pytest.approx(1.0) and p.position_s == 0.0
    p.play()
    stream = fake_sounddevice.OutputStream.instances[-1]
    assert stream.started and stream.kwargs["samplerate"] == 1000

    out = stream.pump(100)
    assert p.position_s == pytest.approx(0.1)
    assert np.allclose(out, _ramp(1000)[:100])      # đúng khối đầu, không lệch mẫu nào
    stream.pump(100)
    assert p.position_s == pytest.approx(0.2)


def test_pause_keeps_position_and_play_resumes(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(1000))
    p.play()
    fake_sounddevice.OutputStream.instances[-1].pump(300)
    p.pause()
    assert p.position_s == pytest.approx(0.3) and not p.playing
    assert fake_sounddevice.OutputStream.instances[-1].closed

    p.play()                                        # tiếp tục, KHÔNG quay về đầu
    assert p.position_s == pytest.approx(0.3)
    out = fake_sounddevice.OutputStream.instances[-1].pump(100)
    assert np.allclose(out, _ramp(1000)[300:400])


def test_stop_rewinds(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(1000))
    p.play()
    fake_sounddevice.OutputStream.instances[-1].pump(400)
    p.stop()
    assert p.position_s == 0.0 and not p.playing


def test_seek_clamps_and_survives_while_playing(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(1000))
    p.seek(-5.0)
    assert p.position_s == 0.0
    p.seek(99.0)
    assert p.position_s == pytest.approx(1.0)       # kẹp ở độ dài, không vượt
    p.seek(0.5)
    p.play()
    out = fake_sounddevice.OutputStream.instances[-1].pump(100)
    assert np.allclose(out, _ramp(1000)[500:600])


def test_last_block_is_padded_and_stream_finishes(fake_sounddevice):
    """Khối cuối ngắn hơn blocksize: phần dư phải là im lặng, và stream tự đóng."""
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(250))
    p.play()
    stream = fake_sounddevice.OutputStream.instances[-1]
    stream.pump(100)
    stream.pump(100)
    out = stream.pump(100)                          # chỉ còn 50 mẫu thật
    assert np.allclose(out[:50], _ramp(250)[200:250])
    assert np.all(out[50:] == 0.0)                  # không lặp lại tiếng cũ ở đuôi
    assert stream.stopped_by_callback and p.finished and not p.playing


def test_play_after_finish_starts_over(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(100))
    p.play()
    fake_sounddevice.OutputStream.instances[-1].pump(100)
    assert p.finished
    p.play()                                        # bấm Nghe lại khi đã hết -> về đầu
    assert p.position_s == 0.0 and not p.finished


def test_load_resets_and_empty_array_never_opens_device(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(1000))
    p.play()
    fake_sounddevice.OutputStream.instances[-1].pump(200)
    n_before = len(fake_sounddevice.OutputStream.instances)

    p.load(_ramp(500))                              # nạp file khác: về đầu, dừng cái cũ
    assert p.position_s == 0.0 and p.duration_s == pytest.approx(0.5)
    p.load([])
    p.play()
    assert len(fake_sounddevice.OutputStream.instances) == n_before  # rỗng -> không mở thiết bị


def test_missing_portaudio_raises_playback_error(monkeypatch):
    """Máy thiếu libportaudio2: phải ném PlaybackError chứ không để OSError lọt lên giao diện."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "sounddevice":
            raise OSError("PortAudio library not found")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    p = AudioPlayback()
    p.load(_ramp(100))
    with pytest.raises(PlaybackError):
        p.play()
