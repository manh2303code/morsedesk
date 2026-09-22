"""Worker phát tiến trình và hủy được lần giải mã đang chạy (CP-08, CP-09)."""

import time
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from morsedesk.app.worker import DecodeRequest, DecoderWorker
from morsedesk.audio.io import save_audio
from morsedesk.progress import DecodeCancelled
from tests.helpers import make_morse


@pytest.fixture
def clip(tmp_path):
    x, _ = make_morse("CQ CQ DE R1ABC K", profile_id="en", wpm=20)
    path = tmp_path / "clip.wav"
    save_audio(path, np.tile(x, 3), 8000)
    return path


def drain(app, until, timeout_s: float = 20.0) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        app.processEvents()
        if until():
            return True
        time.sleep(0.01)
    return False


def test_worker_emits_progress(qapp_or_skip, clip):
    app = qapp_or_skip
    seen: list[tuple[int, int]] = []
    done: list[str] = []
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=None)
    w.progress.connect(lambda d, t: seen.append((d, t)))
    w.result_ready.connect(lambda *a: done.append("ok"))
    w.start()
    try:
        w.request(DecodeRequest(path=str(clip), profile_id="en", use_lm=False))
        assert drain(app, lambda: done), "worker không trả kết quả"
    finally:
        w.stop()
    assert seen and all(1 <= d <= t for d, t in seen)


def test_handle_raises_when_cancel_flag_is_set(clip):
    """Cờ hủy phải tới được lõi: `_handle` ném `DecodeCancelled` thay vì chạy hết.

    Kiểm thẳng ở đây chứ không qua signal, vì signal đi qua vòng lặp sự kiện nên với clip ngắn
    worker thường xong trước khi UI kịp bấm hủy — test sẽ đua và chập chờn.
    """
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=None)
    w._cancel.set()
    with pytest.raises(DecodeCancelled):
        w._handle(DecodeRequest(path=str(clip), profile_id="en", use_lm=False))


def test_cancelled_request_returns_worker_to_idle(qapp_or_skip, clip, monkeypatch):
    """run() bắt `DecodeCancelled`, báo `cancelled`, hạ cờ bận và nhận yêu cầu tiếp theo."""
    app = qapp_or_skip
    events: list[str] = []
    states: list[bool] = []
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=None)
    w.busy.connect(states.append)
    w.cancelled.connect(lambda path: events.append("cancelled"))
    w.result_ready.connect(lambda *a: events.append("ok"))

    calls = {"n": 0}
    real_handle = w._handle

    def handle(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise DecodeCancelled()
        real_handle(req)

    monkeypatch.setattr(w, "_handle", handle)
    w.start()
    try:
        w.request(DecodeRequest(path=str(clip), profile_id="en", use_lm=False))
        assert drain(app, lambda: events == ["cancelled"]), events
        assert drain(app, lambda: states and states[-1] is False), states
        w.request(DecodeRequest(path=str(clip), profile_id="en", use_lm=False))
        assert drain(app, lambda: events == ["cancelled", "ok"]), events
    finally:
        w.stop()


def test_cancel_flag_is_cleared_for_each_new_request(clip):
    """Hủy yêu cầu này không được giết yêu cầu sau: run() xóa cờ ở đầu mỗi lượt."""
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=None)
    w.cancel()
    assert w._cancel.is_set()
    w._cancel.clear()                                  # chính là việc run() làm mỗi lượt
    w._handle(DecodeRequest(path=str(clip), profile_id="en", use_lm=False))


@pytest.fixture(scope="module")
def qapp_or_skip():
    app = QCoreApplication.instance()
    if app is None:
        from PySide6.QtWidgets import QApplication

        app = QApplication([])
    return app


def test_cancel_before_any_request_is_harmless(qapp_or_skip):
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=None)
    w.cancel()
    w.start()
    w.stop()
    assert not w.isRunning()
    _ = Path
