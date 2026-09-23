"""Entry `morsedesk-gui`: tham số dòng lệnh, log, kiểm model, tạo QApplication, cửa sổ chính."""

from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLocale, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from morsedesk.app import gc_guard
from morsedesk.app.branding import install_app_identity, set_windows_app_id
from morsedesk.app.fonts import apply_application_font
from morsedesk.app.live_worker import LiveWorker
from morsedesk.app.main_window import MainWindow
from morsedesk.app.paths import log_directory
from morsedesk.app.settings import AppSettings, default_language
from morsedesk.app.startup import check_models, missing_models_message
from morsedesk.app.theme import apply_theme
from morsedesk.app.worker import DecoderWorker, Player
from morsedesk.textio import force_utf8_streams

I18N_DIR = Path(__file__).resolve().parent / "i18n"
ORG_NAME = "MorseDesk"
APP_NAME = "MorseDesk"
log = logging.getLogger("morsedesk.app")


def set_app_identity() -> None:
    """Đặt tên tổ chức/ứng dụng bằng setter tĩnh (chạy được khi chưa có QApplication).

    Phải gọi TRƯỚC `setup_logging()`: `QStandardPaths.AppDataLocation` chỉ trả về
    `.../MorseDesk/MorseDesk` khi đã có hai tên này; chưa có thì log rơi thẳng vào gốc
    `%APPDATA%` (Windows) hoặc `~/.local/share` (Linux).
    """
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setApplicationName(APP_NAME)


def build_parser() -> argparse.ArgumentParser:
    """Tham số CLI của GUI: --model, --lm-dir, --engine {onnx,baseline} (mặc định onnx), --lang."""
    p = argparse.ArgumentParser(prog="morsedesk-gui", description="MorseDesk GUI")
    p.add_argument("--model", type=Path, default=None, help="ONNX model (default models/acoustic.onnx)")
    p.add_argument("--lm-dir", type=Path, default=None, help="language model directory (default models/lm)")
    p.add_argument("--engine", choices=["onnx", "baseline"], default="onnx")
    p.add_argument("--lang", choices=["en", "ru", "kk"], default=None, help="UI language override")
    p.add_argument("--no-splash", action="store_true", help="skip the animated start screen")
    return p


def setup_logging() -> None:
    """Ghi log xoay vòng (1 MB x 3) vào thư mục log; rơi về basicConfig nếu không tạo được."""
    log_dir = log_directory()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "morsedesk.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
    except OSError:
        logging.basicConfig(level=logging.INFO)


def close_splash() -> None:
    """Đóng màn hình chờ của bản `.exe` một file, nếu đang chạy trong bản đó.

    Bản một file phải bung ~300 MB vào thư mục tạm trước khi Python chạy được dòng nào; lần đầu
    Defender quét từng file bung ra và việc đó từng mất 55 giây mà không có gì trên màn hình.
    Bootloader của PyInstaller hiện ảnh chờ trong lúc đó; đây là chỗ tắt nó. Module `pyi_splash`
    chỉ có trong bản đóng gói có splash, và nói chuyện với bootloader qua socket loopback
    127.0.0.1 — không ra mạng ngoài. Chạy từ mã nguồn, AppImage: không có module, không làm gì.
    """
    try:
        import pyi_splash  # type: ignore[import-not-found]
    except ImportError:
        return
    pyi_splash.close()


def show_missing_dialog(message: str) -> None:
    """Hộp thoại lỗi liệt kê file model/LM thiếu; tách riêng để test monkeypatch không mở hộp thoại thật."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    install_app_identity(app)
    QMessageBox.critical(None, "MorseDesk", message)
    _ = app


def load_settings() -> AppSettings:
    return AppSettings()


def create_app(args: argparse.Namespace) -> tuple[QApplication, MainWindow]:
    """Dựng QApplication (tái dùng nếu đã có) + MainWindow đã đặt ngôn ngữ giao diện; chưa show()."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    # GC vòng chỉ ở luồng giao diện: nếu để Python gom ở luồng giải mã/nghe/PortAudio, widget bị
    # hủy sai luồng -> timer mồ côi bắn vào vùng nhớ đã giải phóng (crash) hoặc kẹt khóa (treo).
    gc_guard.install(app)
    set_app_identity()              # idempotent: create_app có thể được gọi thẳng (script, test)
    install_app_identity(app)       # logo trên thanh tác vụ, Alt-Tab, dock
    # Font trong gói: máy air-gap tối giản có thể không có font nào phủ Ә Ғ Қ Ң Ө Ұ Ү Һ І, khi
    # đó Qt vẽ thành ô vuông. Không nạp được thì cứ chạy tiếp với font hệ thống (CP-11).
    family = apply_application_font()
    if family:
        log.info("font ứng dụng: %s", family)
    apply_theme(app)                # giao diện "thiết bị đo" nền đêm, sau khi đã nạp font
    settings = load_settings()
    worker = DecoderWorker(engine=args.engine, model_path=args.model, lm_dir=args.lm_dir)
    worker.start()
    # Vòng lặp sự kiện có thể kết thúc KHÔNG qua closeEvent (QCoreApplication.exit, đăng xuất
    # phiên, tín hiệu hệ thống). Thiếu chốt này, QThread bị hủy khi còn chạy -> abort 0xC0000409.
    app.aboutToQuit.connect(worker.stop)
    # Luồng THỨ HAI cho chế độ nghe: hai việc có nhịp khác hẳn nhau, nhồi chung một luồng thì
    # một bản tin 37 phút đang giải sẽ chặn đứng dòng chữ đang chạy.
    live = LiveWorker(engine=args.engine, model_path=args.model, lm_dir=args.lm_dir)
    live.start()
    app.aboutToQuit.connect(live.shutdown)
    window = MainWindow(worker, Player(), settings, I18N_DIR, live=live)
    window.decode_page.enable_samples()     # mở lên là có sẵn "Xin chào" đúng ngôn ngữ giao diện
    window.set_language(default_language(args.lang, settings.ui_language, QLocale.system().name()))
    return app, window


def main(argv: list[str] | None = None) -> int:
    """Điểm vào `morsedesk-gui`: thiếu model/LM -> hộp thoại lỗi + mã 2; đủ -> mở cửa sổ, chạy vòng lặp Qt."""
    force_utf8_streams()
    # Phải trước MỌI cửa sổ, kể cả hộp thoại thiếu model: Windows gán nhóm thanh tác vụ ngay khi
    # cửa sổ đầu tiên xuất hiện, và nếu lúc đó chưa có AppUserModelID thì logo Python sẽ hiện.
    set_windows_app_id()
    args = build_parser().parse_args(argv)
    set_app_identity()
    setup_logging()
    missing = check_models(args.model, args.lm_dir, args.engine)
    if missing:
        msg = missing_models_message(missing)
        log.error(msg)
        close_splash()                  # ảnh chờ nằm trên cùng sẽ che mất hộp thoại lỗi
        show_missing_dialog(msg)
        return 2

    def excepthook(exc_type, exc, tb):
        log.error("unhandled exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook
    if args.no_splash:
        app, window = create_app(args)
        window.show()
        close_splash()
        return int(app.exec())
    # Màn hình chờ động (phím Morse gõ ra logo): hiện NGAY, trước khi dựng cửa sổ chính. Khung đầu
    # của nó trùng ảnh tĩnh của màn hình chờ PyInstaller, nên chỗ nối giữa hai màn hình không giật.
    from morsedesk.app.splash import SplashScreen

    app = QApplication.instance() or QApplication(sys.argv[:1])
    install_app_identity(app)
    apply_application_font()
    splash = SplashScreen()
    # Hủy khởi động. Đi qua hàng đợi sự kiện: nếu bị đóng lúc create_app còn chạy (trước exec),
    # gọi quit() thẳng sẽ không có tác dụng vì vòng sự kiện chưa chạy.
    splash.cancelled.connect(lambda: QTimer.singleShot(0, QApplication.instance().quit))
    splash.center_on_screen()
    splash.show()
    app.processEvents()
    close_splash()                          # tắt ảnh tĩnh của bản .exe một file
    app, window = create_app(args)

    def reveal() -> None:
        window.show()
        splash.close()

    splash.finished.connect(reveal)
    splash.play()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
