"""Luồng nghe trực tiếp chạy thật, với card âm thanh và bộ giải mã giả.

Chạy QThread thật chứ không gọi thẳng `run()`: những lỗi đáng sợ nhất của chế độ này là lỗi
luồng (treo khi thoát, tín hiệu phát từ luồng sai, thread bị hủy khi còn chạy -> abort
0xC0000409 như đã gặp ở tuần 4), mà gọi hàm trực tiếp thì không lộ ra.
"""

from __future__ import annotations

import numpy as np

from morsedesk.app import live_worker as lw_mod
from morsedesk.app.live_worker import LiveWorker
from morsedesk.audio.capture import CaptureError


class FakeCapture:
    """Card thu giả: trả sẵn một dãy khối rồi im lặng mãi."""

    instances: list[FakeCapture] = []

    def __init__(self, device=None, **kw):
        self.device = device
        self.started = False
        self.stopped = False
        self.blocks = [np.zeros(800, dtype=np.float32) for _ in range(30)]
        self.i = 0
        FakeCapture.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def get(self, timeout=0.2):
        if self.i < len(self.blocks):
            self.i += 1
            return self.blocks[self.i - 1]
        return None


class FakeStream:
    """StreamDecoder giả: mỗi lần push đủ 5 khối thì "giải mã" ra thêm một từ."""

    def __init__(self, *a, **kw):
        self.pushed = 0
        self.words: list[str] = []
        self.flushed = False
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1
        self.pushed = 0
        self.words = []

    def push(self, block):
        from morsedesk.model.stream import StreamUpdate

        self.pushed += 1
        if self.pushed % 5 == 0:
            self.words.append(f"W{len(self.words)}")
            return StreamUpdate(" ".join(self.words), "tam", True, self.pushed * 0.1)
        return StreamUpdate(" ".join(self.words), "tam", False, self.pushed * 0.1)

    def flush(self):
        from morsedesk.model.stream import StreamUpdate

        self.flushed = True
        return StreamUpdate(" ".join(self.words) or "CUOI", "", True, self.pushed * 0.1)


def _patch(monkeypatch, capture=FakeCapture):
    FakeCapture.instances = []
    monkeypatch.setattr(lw_mod, "AudioCapture", capture)
    monkeypatch.setattr(lw_mod, "Decoder", lambda *a, **kw: object())
    monkeypatch.setattr(lw_mod, "StreamDecoder", FakeStream)


def test_listen_emits_text_and_stops_cleanly(qtbot, monkeypatch):
    _patch(monkeypatch)
    w = LiveWorker()
    texts: list[tuple[str, str]] = []
    states: list[bool] = []
    w.text_ready.connect(lambda c, t: texts.append((c, t)))
    w.listening.connect(states.append)
    w.start()
    try:
        w.start_listening(device=3)
        qtbot.waitUntil(lambda: len(texts) >= 4, timeout=5000)
        assert states and states[0] is True
        assert FakeCapture.instances[-1].device == 3        # chọn đúng thiết bị người dùng chỉ
        assert any(c.startswith("W0") for c, _ in texts)
        w.stop_listening()
        qtbot.waitUntil(lambda: states[-1] is False, timeout=5000)
        assert FakeCapture.instances[-1].stopped            # luôn đóng thiết bị lại
    finally:
        w.shutdown()
        assert w.wait(5000)                                 # không treo khi thoát


def test_flush_runs_so_the_last_sentence_is_not_cut(qtbot, monkeypatch):
    _patch(monkeypatch)
    w = LiveWorker()
    texts: list[tuple[str, str]] = []
    w.text_ready.connect(lambda c, t: texts.append((c, t)))
    w.start()
    try:
        w.start_listening()
        qtbot.waitUntil(lambda: len(texts) >= 2, timeout=5000)
        w.stop_listening()
        qtbot.waitUntil(lambda: texts[-1][1] == "", timeout=5000)
        assert texts[-1][1] == ""                           # sau flush không còn phần tạm
    finally:
        w.shutdown()
        assert w.wait(5000)


def test_capture_error_is_reported_not_raised(qtbot, monkeypatch):
    """Máy thiếu PortAudio hay mic bị chiếm: báo một dòng, không kéo sập ứng dụng."""

    class Broken(FakeCapture):
        def start(self):
            raise CaptureError("cannot open input device 9")

    _patch(monkeypatch, Broken)
    w = LiveWorker()
    errors: list[str] = []
    w.failed.connect(errors.append)
    w.start()
    try:
        w.start_listening(device=9)
        qtbot.waitUntil(lambda: bool(errors), timeout=5000)
        assert "cannot open input device 9" in errors[0]
    finally:
        w.shutdown()
        assert w.wait(5000)


def test_shutdown_without_listening_terminates(qtbot, monkeypatch):
    """Đóng ứng dụng khi chưa từng bấm nghe cũng phải thoát ngay, không chờ timeout."""
    _patch(monkeypatch)
    w = LiveWorker()
    w.start()
    w.shutdown()
    assert w.wait(3000)


def test_stream_is_reset_between_sessions(qtbot, monkeypatch):
    """Bấm nghe lần hai phải bắt đầu từ trang trắng, không nối tiếp bản tin cũ."""
    _patch(monkeypatch)
    w = LiveWorker()
    states: list[bool] = []
    w.listening.connect(states.append)
    w.start()
    try:
        w.start_listening()
        qtbot.waitUntil(lambda: bool(states) and states[-1] is True, timeout=5000)
        w.stop_listening()
        qtbot.waitUntil(lambda: states[-1] is False, timeout=5000)
        w.start_listening()
        qtbot.waitUntil(lambda: states[-1] is True, timeout=5000)
        assert w._stream.reset_calls >= 2
    finally:
        w.shutdown()
        assert w.wait(5000)
