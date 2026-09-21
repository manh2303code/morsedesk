import threading

from PySide6.QtCore import QSettings

import morsedesk.app.main as app_main
from morsedesk.app.main import I18N_DIR, build_parser, create_app, main
from morsedesk.app.main_window import MainWindow
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import DecodeRequest, DecoderWorker, Player


def test_parser_defaults():
    a = build_parser().parse_args([])
    assert a.engine == "onnx" and a.model is None and a.lm_dir is None and a.lang is None


def test_main_exits_2_when_models_missing(tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(app_main, "show_missing_dialog", lambda msg: shown.append(msg))
    rc = main(["--model", str(tmp_path / "none.onnx"), "--lm-dir", str(tmp_path)])
    assert rc == 2 and shown and "none.onnx" in shown[0] and "en.bin" in shown[0]


def test_create_app_builds_window_with_language(qtbot, tiny_lm_dir, tmp_path, monkeypatch):
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(app_main, "load_settings", lambda: settings)
    args = build_parser().parse_args(["--engine", "baseline", "--lm-dir", str(tiny_lm_dir), "--lang", "ru"])
    app, window = create_app(args)
    qtbot.addWidget(window)
    try:
        assert window.current_language == "ru" and settings.ui_language == "ru"
        assert window.tabs.count() == 2
        assert window.language_combo.currentData() == "ru"
        assert window.decode_page is not None and window.worker.isRunning()
        from morsedesk.app.encode_page import EncodePage

        assert isinstance(window.encode_page, EncodePage)
    finally:
        window.close()
    assert not window.worker.isRunning()


class _PausedWorker(DecoderWorker):
    """`DecoderWorker` thật (hàng đợi, vòng `run`, tín hiệu `busy`/`finished`); chỉ phần giải mã
    được thay bằng một chỗ chờ để test giữ worker ở trạng thái bận đúng lúc gọi `close()`."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.working = threading.Event()
        self.release = threading.Event()

    def _handle(self, req) -> None:
        self.working.set()
        assert self.release.wait(20.0), "test không thả worker kịp"


def test_close_while_worker_busy_defers_close_instead_of_killing_thread(
    qtbot, tiny_lm_dir, tmp_path, wav_cq
):
    """Đóng cửa sổ giữa lúc giải mã: cửa sổ phải chờ worker xong, không hủy QThread đang chạy."""
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    worker = _PausedWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    worker.start()
    window = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(window)
    window.show()
    try:
        worker.request(DecodeRequest(wav_cq, "en", False))
        assert worker.working.wait(5.0)
        window.close()
        assert window.isVisible()                       # hoãn đóng, không giết QThread
        assert worker.isRunning()
        assert window.banner.level == "warning" and window.banner.text()
        assert not window.tabs.isEnabled()
        worker.release.set()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=10000)
        assert worker.isFinished() and not worker.isRunning()
    finally:
        worker.release.set()
        worker.stop()


def test_close_with_idle_worker_closes_immediately(qtbot, tiny_lm_dir, tmp_path):
    """Worker rảnh: cửa sổ đóng ngay trong lần `close()` đầu, worker dừng hẳn."""
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    worker.start()
    window = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(window)
    window.show()
    window.close()
    assert not window.isVisible() and window.banner.level is None
    qtbot.waitUntil(lambda: worker.isFinished(), timeout=5000)
