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


def _tone(sr: int = 8000, seconds: float = 4.0, hz: float = 700.0):
    import numpy as np

    t = np.arange(int(sr * seconds)) / sr
    return (0.5 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def _pull(pb, blocks: int, n: int = 1024):
    import numpy as np

    out = np.zeros((n, 1), dtype=np.float32)
    got = []
    for _ in range(blocks):
        pb._callback(out, n, None, None)
        got.append(out[:, 0].copy())
    return np.concatenate(got)


@pytest.mark.parametrize("rate", [0.5, 0.75, 1.25, 1.5, 2.0])
def test_speed_changes_time_but_keeps_the_pitch(rate):
    """Tốc độ nghe lại chỉ đụng tới tiếng phát: tone 700 Hz vẫn là 700 Hz, vị trí trong FILE
    GỐC (thứ karaoke dùng để tô chữ) tiến đúng tốc độ x thời gian phát."""
    import numpy as np

    from morsedesk.audio.playback import AudioPlayback

    sr = 8000
    pb = AudioPlayback(sr, 1024)
    pb.load(_tone(sr), sr)
    pb.set_speed(rate)
    y = _pull(pb, 12)[2048:]
    played_s = 12 * 1024 / sr
    assert abs(pb.position_s - played_s * rate) < 0.05
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    assert abs(np.argmax(spec) * sr / len(y) - 700.0) < 5.0
    env = np.maximum.reduceat(np.abs(y), np.arange(0, len(y), 40))
    assert env.min() > 0.45                 # không phập phồng ở chỗ nối khung


def test_volume_scales_the_output_and_speed_one_is_bit_exact():
    import numpy as np

    from morsedesk.audio.playback import AudioPlayback

    x = _tone()
    pb = AudioPlayback(8000, 1024)
    pb.load(x, 8000)
    assert np.array_equal(_pull(pb, 1), x[:1024])       # 1× = phát nguyên bản, không xử lý gì
    pb.set_volume(0.5)
    assert np.allclose(_pull(pb, 1), 0.5 * x[1024:2048])
    pb.set_volume(0.0)
    assert not _pull(pb, 1).any()


def test_seek_while_stretched_and_finish_at_the_end():
    from morsedesk.audio.playback import _StopPlayback

    pb = AudioPlayback(8000, 1024)
    pb.load(_tone(seconds=2.0), 8000)
    pb.set_speed(2.0)
    pb.seek(1.5)
    _pull(pb, 1)
    assert 1.5 <= pb.position_s <= 1.8
    with pytest.raises(_StopPlayback):          # "phát nốt khối này rồi dừng" khi đã hết
        _pull(pb, 4)
    assert pb.finished and pb.position_s == pb.duration_s


def _pumped(fake, p, blocks: int, t0: float = 10.0):
    """Bơm `blocks` khối 0,1 s (sr 1000, block 100); khối k tới loa lúc t0 + 0,1 k."""
    stream = fake.OutputStream.instances[-1]
    for k in range(blocks):
        stream.pump(100, dac=t0 + 0.1 * k)
    return stream


@pytest.mark.parametrize("rate", [1.0, 2.0, 0.5])
def test_position_is_what_is_heard_not_what_was_sent(fake_sounddevice, rate):
    """Đo 24/09: đếm theo khung đã gửi làm karaoke/vệt quét 3D đi trước tiếng 315 ms ở 1×, 628 ms
    ở 2×. Nay vị trí là giây của file đang ra loa theo mốc thời gian của thiết bị, nội suy mượt."""
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(5000))
    p.set_speed(rate)
    p.play()
    stream = _pumped(fake_sounddevice, p, 4)          # đã gửi 0,4 s tiếng, loa mới tới đâu tùy lúc
    stream.time = 10.0 - 0.05
    assert p.position_s == pytest.approx(0.0)         # khối đầu chưa tới loa
    for now in (10.05, 10.15, 10.25):
        stream.time = now
        assert p.position_s == pytest.approx((now - 10.0) * rate, abs=0.012 * max(rate, 1.0))


def test_pause_stops_at_what_was_heard_and_resumes_there(fake_sounddevice):
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(1000))
    p.play()
    stream = _pumped(fake_sounddevice, p, 4)          # gửi 0,4 s, nhưng mới nghe tới 0,15 s
    stream.time = 10.15
    p.pause()
    assert p.position_s == pytest.approx(0.15, abs=0.001) and not p.playing
    p.play()
    out = fake_sounddevice.OutputStream.instances[-1].pump(100)
    assert np.allclose(out, _ramp(1000)[150:250])     # nghe tiếp đúng chỗ vừa dừng


def test_finished_only_when_the_last_sample_has_played(fake_sounddevice):
    """Khối cuối đã gửi nhưng loa còn đang phát phần đệm: chưa được coi là "hết" (nếu không, hình
    dừng sớm hơn tiếng ~0,3 s)."""
    p = AudioPlayback(sample_rate=1000, block=100)
    p.load(_ramp(250))
    p._callback(np.zeros((100, 1), np.float32), 100, None, None)
    p._finished = True                                # như vừa gửi khối cuối
    p._stream = object()                              # stream vẫn còn đang xả đệm
    assert p.playing and not p.finished
    p._on_stream_finished()
    assert p.finished and not p.playing
