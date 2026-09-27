"""Luồng thiết bị âm thanh (audio/engine.py): không bao giờ chặn bên gọi, độc quyền phát/thu, driver kẹt.

Người dùng 27/09: đang phát ở trang Tạo mã/Giải mã rồi bấm Nghe -> app đơ hẳn, phải giết trong Task
Manager. Dựng lại trên máy dev: mở micro lúc loa đang phát làm bộ máy âm thanh Windows treo (audiodg /
Audiosrv), và mọi lời gọi PortAudio — trước đây gọi ngay trên luồng giao diện — treo theo. Driver "treo"
ở đây được giả bằng stream giả chờ một Event.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from morsedesk.audio import capture as capture_mod
from morsedesk.audio import engine as engine_mod
from morsedesk.audio.capture import AudioCapture, CaptureError
from morsedesk.audio.engine import STUCK_TEXT, AudioEngine, AudioStuck
from morsedesk.audio.playback import AudioPlayback, PlaybackError


def _ramp(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float32) / n


def _wait(cond, timeout: float = 3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def test_stuck_driver_call_never_blocks_the_caller_and_is_reported():
    eng = AudioEngine()
    gate = threading.Event()
    t0 = time.monotonic()
    eng.submit(lambda: gate.wait(10), "open output", timeout=0.2)
    assert time.monotonic() - t0 < 0.1                      # xếp lệnh không bao giờ chờ driver
    assert _wait(lambda: eng.stuck() == "open output")
    # Đang kẹt: lệnh mở mới bị từ chối NGAY (không chồng chất sau lệnh kẹt) ...
    refused = eng.submit(lambda: 1, "open input", timeout=0.2)
    assert isinstance(refused.exception(timeout=0), AudioStuck)
    assert STUCK_TEXT in str(refused.exception(timeout=0))
    # ... còn lệnh đóng vẫn xếp hàng, để stream được đóng khi driver trả lời lại.
    closed = eng.submit(lambda: "closed", "close output", timeout=0.2, kind="close")
    assert not closed.done()
    gate.set()
    assert closed.result(timeout=3) == "closed"
    assert eng.stuck() is None
    assert eng._needs_reinit                # dịch vụ âm thanh vừa hồi lại: lần sau dò lại thiết bị
    assert eng.shutdown(2.0)


def test_shutdown_reports_a_stuck_engine_instead_of_hanging():
    eng = AudioEngine()
    gate = threading.Event()
    eng.submit(lambda: gate.wait(10), "abort output", timeout=0.1, kind="close")
    assert _wait(lambda: eng.stuck() is not None)
    t0 = time.monotonic()
    assert not eng.shutdown(0.3)            # main.finish sẽ thoát cứng thay vì chờ Pa_Terminate
    assert time.monotonic() - t0 < 1.0
    gate.set()


def test_listening_stops_playback_and_closes_it_before_the_microphone_opens(fake_sounddevice):
    """Không bao giờ có loa và micro mở cùng lúc: đó đúng là tổ hợp đã làm treo driver máy dev."""
    sd = fake_sounddevice
    events = []
    out_cls, in_cls = sd.OutputStream, sd.InputStream

    class Out(out_cls):
        def __init__(self, **kw):
            events.append("open output")
            super().__init__(**kw)

        def close(self):
            events.append("close output")
            super().close()

    class In(in_cls):
        def __init__(self, **kw):
            events.append("open input")
            super().__init__(**kw)

    sd.OutputStream, sd.InputStream = Out, In
    pb = AudioPlayback(sample_rate=1000, block=100)
    pb.load(_ramp(5000))
    pb.play()
    sd.OutputStream.instances[-1].pump(100)
    cap = AudioCapture()
    cap.start()
    assert events == ["open output", "close output", "open input"]
    assert not pb.playing and pb.preempted
    assert pb.position_s == pytest.approx(0.1)          # dừng tại chỗ đã phát, như tạm dừng
    with pytest.raises(PlaybackError) as e:             # đang nghe: không phát ra loa
        pb.play()
    assert e.value.kind == "busy"
    cap.stop()
    pb.play()                                           # thôi nghe: phát lại được, nghe tiếp chỗ cũ
    assert pb.playing and events[-1] == "open output"


def test_playing_on_one_page_stops_the_other(fake_sounddevice):
    a, b = AudioPlayback(1000, 100), AudioPlayback(1000, 100)
    a.load(_ramp(5000))
    b.load(_ramp(5000))
    a.play()
    first = fake_sounddevice.OutputStream.instances[-1]
    b.play()
    assert first.closed and not a.playing and a.preempted and b.playing


def test_a_stream_that_played_to_the_end_is_closed(fake_sounddevice):
    """Trước 27/09 stream phát hết chỉ bị bỏ quên (không close): còn mở tới lúc thoát, và
    `Pa_Terminate` của atexit đóng nó — đúng chỗ driver kẹt làm việc thoát app treo."""
    pb = AudioPlayback(1000, 100)
    pb.load(_ramp(150))
    pb.play()
    stream = fake_sounddevice.OutputStream.instances[-1]
    stream.pump(100)
    stream.pump(100)
    assert stream.stopped_by_callback and stream.closed and pb.finished


def test_play_and_pause_return_at_once_even_if_the_driver_hangs(fake_sounddevice):
    """Luồng giao diện gọi play/pause/position_s: phải trả về ngay dù driver không bao giờ trả lời."""
    sd = fake_sounddevice
    gate = threading.Event()
    base = sd.OutputStream

    class Hanging(base):
        def start(self):
            gate.wait(10)
            super().start()

    sd.OutputStream = Hanging
    eng = AudioEngine()
    pb = AudioPlayback(1000, 100, engine=eng)
    pb.load(_ramp(5000))
    t0 = time.monotonic()
    pb.play()
    assert pb.playing                                   # đúng từ lúc bấm, stream còn đang mở
    for _ in range(100):
        _ = pb.position_s                               # 100 nhịp hình: không gọi PortAudio
    pb.pause()
    pb.play()
    pb.stop()
    assert time.monotonic() - t0 < 0.2
    gate.set()
    assert eng.shutdown(3.0)
    assert all(s.closed for s in Hanging.instances)     # stream mở muộn vẫn được đóng, không mồ côi


def test_open_failure_arrives_later_as_an_error_not_an_exception(fake_sounddevice):
    sd = fake_sounddevice

    class Boom:
        def __init__(self, **kw):
            raise sd.PortAudioError("no device")

    sd.OutputStream = Boom
    eng = AudioEngine()
    pb = AudioPlayback(1000, 100, engine=eng)
    pb.load(_ramp(1000))
    pb.play()                                           # không ném trên luồng giao diện
    assert _wait(lambda: not pb.playing)
    assert pb.error is not None and "no device" in str(pb.error) and pb.error.kind == "device"
    assert eng.shutdown(2.0)


def test_capture_gives_up_on_a_hung_driver_and_closes_the_late_stream(fake_sounddevice, monkeypatch):
    """Luồng nghe chờ có hạn: driver kẹt -> CaptureError ("không phản hồi"); khi driver hồi lại, micro
    vừa mở muộn phải được đóng ngay, không để thu mồ côi."""
    sd = fake_sounddevice
    gate = threading.Event()
    base = sd.InputStream

    class Hanging(base):
        def start(self):
            gate.wait(10)
            super().start()

    sd.InputStream = Hanging
    monkeypatch.setattr(capture_mod, "OPEN_TIMEOUT_S", 0.2)
    monkeypatch.setattr(engine_mod, "CLOSE_TIMEOUT_S", 0.1)
    eng = AudioEngine()
    cap = AudioCapture(engine=eng)
    t0 = time.monotonic()
    with pytest.raises(CaptureError) as e:
        cap.start()
    assert STUCK_TEXT in str(e.value) and time.monotonic() - t0 < 1.0
    gate.set()
    assert _wait(lambda: Hanging.instances and Hanging.instances[-1].closed)
    assert _wait(lambda: not eng.capturing)
    assert eng.shutdown(2.0)


def test_stale_device_list_is_rescanned_once(fake_sounddevice):
    """Sau khi dịch vụ âm thanh khởi động lại, PortAudio còn giữ danh sách thiết bị cũ và mở stream ra
    paInvalidDevice (-9996, thấy thật trên máy dev 27/09): khởi tạo lại PortAudio rồi thử lại một lần."""
    sd = fake_sounddevice
    calls = []
    sd._terminate = lambda: calls.append("terminate")
    sd._initialize = lambda: calls.append("initialize")
    base = sd.OutputStream
    tries = []

    class Flaky(base):
        def __init__(self, **kw):
            tries.append(1)
            if len(tries) == 1:
                raise sd.PortAudioError("Error opening OutputStream: Invalid device [PaErrorCode -9996]", -9996)
            super().__init__(**kw)

    sd.OutputStream = Flaky
    pb = AudioPlayback(1000, 100)
    pb.load(_ramp(1000))
    pb.play()
    assert pb.playing and len(tries) == 2 and calls == ["terminate", "initialize"]


def test_pending_play_gives_up_when_the_device_thread_is_stuck(fake_sounddevice, monkeypatch):
    """Máy dev 27/09, âm thanh Windows kẹt thật: lệnh mở loa xếp hàng sau `Pa_Initialize` kẹt, trang
    Tạo mã đứng mãi ở "đang phát" với văn bản bị khóa. Nay: kẹt mà chưa ra tiếng nào -> bỏ cuộc, báo."""
    eng = AudioEngine()
    gate = threading.Event()
    eng.submit(lambda: gate.wait(10), "query devices", timeout=0.2, kind="query")
    pb = AudioPlayback(1000, 100, engine=eng)
    pb.load(_ramp(1000))
    pb.play()                                           # chưa kẹt (mới 0 s): xếp hàng
    assert pb.playing
    assert _wait(lambda: not pb.playing)                # quá hạn giờ -> tự bỏ cuộc
    assert pb.error is not None and pb.error.kind == "stuck"
    gate.set()
    assert eng.shutdown(3.0)
    assert not fake_sounddevice.OutputStream.instances  # lệnh mở cũ (đã hủy) không mở loa nữa
