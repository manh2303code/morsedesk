"""Entry `morsedesk-gui`: tham số dòng lệnh, log, kiểm model, tạo QApplication, cửa sổ chính."""

from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QLocale, QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from morsedesk.app.main_window import MainWindow
from morsedesk.app.settings import AppSettings, default_language
from morsedesk.app.startup import check_models, missing_models_message
from morsedesk.app.worker import DecoderWorker
from morsedesk.textio import force_utf8_streams

I18N_DIR = Path(__file__).resolve().parent / "i18n"
log = logging.getLogger("morsedesk.app")


def build_parser() -> argparse.ArgumentParser:
    """Tham số CLI của GUI: --model, --lm-dir, --engine {onnx,baseline} (mặc định onnx), --lang."""
    p = argparse.ArgumentParser(prog="morsedesk-gui", description="MorseDesk GUI")
    p.add_argument("--model", type=Path, default=None, help="ONNX model (default models/acoustic.onnx)")
    p.add_argument("--lm-dir", type=Path, default=None, help="language model directory (default models/lm)")
    p.add_argument("--engine", choices=["onnx", "baseline"], default="onnx")
    p.add_argument("--lang", choices=["en", "ru", "kk"], default=None, help="UI language override")
    return p


def setup_logging() -> None:
    """Ghi log xoay vòng (1 MB x 3) vào thư mục dữ liệu ứng dụng; rơi về basicConfig nếu không tạo được."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    log_dir = Path(base) / "logs"
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


def show_missing_dialog(message: str) -> None:
    """Hộp thoại lỗi liệt kê file model/LM thiếu; tách riêng để test monkeypatch không mở hộp thoại thật."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    QMessageBox.critical(None, "MorseDesk", message)
    _ = app


def load_settings() -> AppSettings:
    return AppSettings()


def create_app(args: argparse.Namespace) -> tuple[QApplication, MainWindow]:
    """Dựng QApplication (tái dùng nếu đã có) + MainWindow đã đặt ngôn ngữ giao diện; chưa show()."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("MorseDesk")
    app.setOrganizationName("MorseDesk")
    settings = load_settings()
    worker = DecoderWorker(engine=args.engine, model_path=args.model, lm_dir=args.lm_dir)
    worker.start()
    window = MainWindow(worker, settings, I18N_DIR)
    window.set_language(default_language(args.lang, settings.ui_language, QLocale.system().name()))
    return app, window


def main(argv: list[str] | None = None) -> int:
    """Điểm vào `morsedesk-gui`: thiếu model/LM -> hộp thoại lỗi + mã 2; đủ -> mở cửa sổ, chạy vòng lặp Qt."""
    force_utf8_streams()
    args = build_parser().parse_args(argv)
    setup_logging()
    missing = check_models(args.model, args.lm_dir, args.engine)
    if missing:
        msg = missing_models_message(missing)
        log.error(msg)
        show_missing_dialog(msg)
        return 2

    def excepthook(exc_type, exc, tb):
        log.error("unhandled exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook
    app, window = create_app(args)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
