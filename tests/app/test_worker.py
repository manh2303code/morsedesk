import threading
from pathlib import Path

import numpy as np
import pytest

from morsedesk.api import Encoder
from morsedesk.app.worker import (
    MAX_COLUMNS,
    MAX_SECONDS,
    DecodeRequest,
    DecoderWorker,
    Player,
    Spectrogram,
)
from morsedesk.audio.io import save_audio


def test_spectrogram_shape_range_and_pooling():
    x = Encoder("en").to_audio("PARIS PARIS", wpm=20)
    s = Spectrogram.from_audio(x)
    assert s.power_db.dtype == np.float32
    assert s.freqs_hz[0] == 0.0 and s.freqs_hz[-1] <= 2000.0 and len(s.freqs_hz) == s.power_db.shape[0]
    assert s.power_db.shape[1] == len(s.times_s) == len(x) // 40
    assert s.power_db.max() <= 0.0 + 1e-6 and s.power_db.min() >= -60.0 - 1e-6
    tone_bin = int(np.argmin(np.abs(s.freqs_hz - 700.0)))
    assert s.power_db[tone_bin].max() > -3.0                                 # tone nổi rõ
    long = np.tile(x, 40)                                                    # ~ 5 phút
    s2 = Spectrogram.from_audio(long, max_columns=MAX_COLUMNS)
    assert s2.power_db.shape[1] <= MAX_COLUMNS and len(s2.times_s) == s2.power_db.shape[1]
    assert s2.times_s[-1] > s.times_s[-1]
    empty = Spectrogram.from_audio(np.zeros(0, np.float32))
    assert empty.power_db.shape[1] == 0 and len(empty.times_s) == 0


def _run(worker, qtbot, req, timeout=60000):
    with qtbot.waitSignal(worker.result_ready, timeout=timeout) as blocker:
        worker.request(req)
    return blocker.args


def test_worker_decodes_auto_and_forced(qtbot, tiny_lm_dir, wav_cq, wav_ru):
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    w.start()
    try:
        result, spec, path = _run(w, qtbot, DecodeRequest(wav_cq, "auto", True))
        assert path == str(wav_cq) and result.text == "CQ DE K" and result.language == "en"
        assert isinstance(spec, Spectrogram) and spec.power_db.shape[1] > 0
        assert set(result.language_scores) == {"en", "ru", "kk-cyrl-ru"}
        result2, _, _ = _run(w, qtbot, DecodeRequest(wav_ru, "ru", False))
        assert result2.text == "ПРИВЕТ МИР" and result2.language == "ru" and result2.language_scores == {}
        assert len(w._decoders) == 2                                          # cache theo (profile, lm)
    finally:
        w.stop()
    assert not w.isRunning()


def test_worker_reports_errors_and_stays_alive(qtbot, tiny_lm_dir, tmp_path, wav_cq):
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    w.start()
    try:
        bad = tmp_path / "bad.wav"
        bad.write_text("không phải audio", encoding="utf-8")
        with qtbot.waitSignal(w.failed, timeout=30000) as blocker:
            w.request(DecodeRequest(bad, "en", False))
        assert blocker.args == ["unsupported", blocker.args[1], str(bad)]
        assert "bad.wav" in blocker.args[1]
        missing = tmp_path / "missing.wav"
        with qtbot.waitSignal(w.failed, timeout=30000) as blocker:
            w.request(DecodeRequest(missing, "en", False))
        assert blocker.args[0] == "not_found" and blocker.args[2] == str(missing)
        assert "missing.wav" in blocker.args[1]
        result, _, _ = _run(w, qtbot, DecodeRequest(wav_cq, "en", False))    # vẫn sống
        assert result.text == "CQ DE K"
    finally:
        w.stop()


def test_worker_rejects_files_longer_than_limit(qtbot, tiny_lm_dir, tmp_path, monkeypatch):
    import morsedesk.app.worker as wk

    long_wav = tmp_path / "long.wav"
    save_audio(long_wav, np.zeros(8000 * 2, np.float32), 8000)
    monkeypatch.setattr(wk, "audio_info", lambda p: (8000, 1, MAX_SECONDS + 1.0))
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    w.start()
    try:
        with qtbot.waitSignal(w.failed, timeout=30000) as blocker:
            w.request(DecodeRequest(long_wav, "en", False))
        # detail của too_long là số phút đã format; UI ghép thành câu qua tr()
        assert blocker.args[0] == "too_long" and blocker.args[1].startswith("20.")
        assert blocker.args[2] == str(long_wav)
    finally:
        w.stop()


def test_worker_busy_signal_brackets_each_request(qtbot, tiny_lm_dir, wav_cq):
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    states = []
    w.busy.connect(states.append)
    w.start()
    try:
        _run(w, qtbot, DecodeRequest(wav_cq, "en", False))
        qtbot.waitUntil(lambda: states[-1:] == [False], timeout=5000)
    finally:
        w.stop()
    assert states[0] is True and states[-1] is False


def test_player_wraps_sounddevice(monkeypatch):
    import sounddevice as sd

    calls = []
    monkeypatch.setattr(sd, "play", lambda x, sr, **kw: calls.append(("play", len(x), sr)))
    monkeypatch.setattr(sd, "stop", lambda: calls.append(("stop",)))
    p = Player()
    assert p.play(np.zeros(800, np.float32), 8000) is None       # play gọi stop() trước để phát lại từ đầu
    p.stop()
    assert calls == [("stop",), ("play", 800, 8000), ("stop",)]

    def boom(x, sr, **kw):
        raise sd.PortAudioError("no device")

    monkeypatch.setattr(sd, "play", boom)
    msg = p.play(np.zeros(8, np.float32), 8000)
    assert msg and "no device" in msg


@pytest.mark.parametrize("bad", ["auto", "en"])
def test_worker_without_lm_files_reports_failure_for_auto_only(qtbot, tmp_path, wav_cq, bad):
    w = DecoderWorker(engine="baseline", model_path=None, lm_dir=tmp_path)
    w.start()
    try:
        if bad == "auto":
            with qtbot.waitSignal(w.failed, timeout=30000) as blocker:
                w.request(DecodeRequest(wav_cq, "auto", True))
            assert blocker.args[0] == "config" and "en.bin" in blocker.args[1]
        else:
            result, _, _ = _run(w, qtbot, DecodeRequest(wav_cq, "en", False))
            assert result.text == "CQ DE K"
    finally:
        w.stop()


class _GatedWorker(DecoderWorker):
    """`DecoderWorker` thật (hàng đợi, vòng `run`, `stop_async`); chỉ phần giải mã được thay
    bằng một cổng chờ để test giữ worker ở trạng thái bận đúng lúc bắn thêm yêu cầu."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.handled: list[str] = []

    def _handle(self, req) -> None:
        self.entered.set()
        assert self.gate.wait(20.0), "test không mở cổng kịp"
        self.handled.append(Path(req.path).name)


def test_queue_keeps_only_the_last_request_while_busy(qtbot, tiny_lm_dir, tmp_path):
    """Bất biến trung tâm của thiết kế: hàng đợi độ dài 1 — bắn dồn thì chỉ yêu cầu cuối chạy."""
    w = _GatedWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    w.start()
    try:
        w.request(DecodeRequest(tmp_path / "a.wav", "en", False))
        assert w.entered.wait(5.0)                      # a đang chạy -> worker bận
        for name in ("b.wav", "c.wav", "d.wav"):        # ba yêu cầu dồn trong lúc bận
            w.request(DecodeRequest(tmp_path / name, "en", False))
        w.gate.set()
        qtbot.waitUntil(lambda: len(w.handled) == 2, timeout=10000)
        qtbot.wait(300)                                 # không có yêu cầu thứ ba nào nữa
        assert w.handled == ["a.wav", "d.wav"]          # b và c bị yêu cầu sau thay chỗ
    finally:
        w.gate.set()
        w.stop()
    assert w.isFinished()


def test_stop_midway_finishes_cleanly(qtbot, tiny_lm_dir, tmp_path):
    """Xin dừng lúc đang bận: yêu cầu đang chạy vẫn xong, rồi thread kết thúc sạch."""
    w = _GatedWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    w.start()
    try:
        w.request(DecodeRequest(tmp_path / "a.wav", "en", False))
        assert w.entered.wait(5.0)
        w.stop_async()                                  # không chờ -> worker vẫn đang chạy
        assert w.isRunning()
        w.gate.set()
        assert w.wait(10000)
    finally:
        w.gate.set()
        w.stop()
    assert w.isFinished() and not w.isRunning() and w.handled == ["a.wav"]
