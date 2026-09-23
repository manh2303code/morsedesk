import threading

from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths

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
        assert window.tabs.count() == 4          # Giải mã, Nghe, Tạo mã, Cài đặt
        assert window.language_bar.buttons["ru"].isChecked()
        assert window.decode_page is not None and window.worker.isRunning()
        from morsedesk.app.encode_page import EncodePage

        assert isinstance(window.encode_page, EncodePage)
    finally:
        window.close()
    assert not window.worker.isRunning()


def test_about_to_quit_stops_worker(qtbot, tiny_lm_dir, tmp_path, monkeypatch):
    """Vòng lặp sự kiện kết thúc KHÔNG qua closeEvent (QCoreApplication.exit, đăng xuất phiên)
    vẫn phải dừng worker; nếu không, QThread bị hủy khi còn chạy -> tiến trình abort 0xC0000409."""
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(app_main, "load_settings", lambda: settings)
    args = build_parser().parse_args(["--engine", "baseline", "--lm-dir", str(tiny_lm_dir)])
    app, window = create_app(args)
    qtbot.addWidget(window)
    assert window.worker.isRunning()
    app.aboutToQuit.emit()          # đúng tín hiệu Qt phát khi vòng lặp sự kiện sắp kết thúc
    assert window.worker.isFinished()
    window.close()


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


def test_logging_is_set_up_after_the_app_identity(tmp_path, monkeypatch):
    """setup_logging() phải chạy SAU set_app_identity(), nếu không log rơi ra gốc %APPDATA%."""
    seen = []
    monkeypatch.setattr(
        app_main,
        "setup_logging",
        lambda: seen.append(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)),
    )
    monkeypatch.setattr(app_main, "show_missing_dialog", lambda msg: None)
    QCoreApplication.setOrganizationName("ZZTestOrg")       # xóa dấu vết của test khác
    QCoreApplication.setApplicationName("ZZTestApp")
    try:
        before = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        rc = main(["--model", str(tmp_path / "none.onnx"), "--lm-dir", str(tmp_path)])
    finally:
        app_main.set_app_identity()
    assert rc == 2 and len(seen) == 1
    assert not before.endswith("MorseDesk/MorseDesk")
    assert seen[0].endswith("MorseDesk/MorseDesk"), seen[0]


def test_close_splash_is_a_no_op_outside_the_one_file_build(monkeypatch):
    """Chạy từ mã nguồn hay AppImage thì không có `pyi_splash`; không được ném lỗi."""
    import sys

    monkeypatch.setitem(sys.modules, "pyi_splash", None)     # None trong sys.modules -> ImportError
    app_main.close_splash()


def test_splash_is_closed_before_the_missing_models_dialog(tmp_path, monkeypatch):
    """Ảnh chờ luôn nằm trên cùng: còn mở thì nó che hộp thoại báo thiếu model."""
    import sys
    import types

    events = []
    fake = types.ModuleType("pyi_splash")
    fake.close = lambda: events.append("close")
    monkeypatch.setitem(sys.modules, "pyi_splash", fake)
    monkeypatch.setattr(app_main, "show_missing_dialog", lambda msg: events.append("dialog"))
    assert main(["--model", str(tmp_path / "none.onnx"), "--lm-dir", str(tmp_path)]) == 2
    assert events == ["close", "dialog"]
