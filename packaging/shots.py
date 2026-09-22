"""Chụp màn hình mọi trang của GUI để soi UI/UX (chạy trong container Ubuntu qua Xvfb).

Khác với test: ở đây nạp dữ liệu THẬT — giải mã một file, gõ văn bản ba thứ tiếng — để thấy
giao diện ở trạng thái làm việc chứ không phải trạng thái rỗng.
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/work/shots")


def grab(widget, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(OUT / f"{name}.png"))
    print(f"  {name}.png", flush=True)


def main() -> int:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from morsedesk.app.fonts import apply_application_font
    from morsedesk.app.main import I18N_DIR, set_app_identity
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.settings import AppSettings
    from morsedesk.app.worker import DecoderWorker, Player

    QApplication(sys.argv[:1])      # giữ sống qua vòng đời hàm; không cần tham chiếu
    set_app_identity()
    print("font:", apply_application_font(), flush=True)

    worker = DecoderWorker(engine="onnx", model_path=None, lm_dir=None)
    worker.start()
    win = MainWindow(worker, Player(), AppSettings(), I18N_DIR)
    win.resize(1180, 760)
    win.show()

    def pump(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    pump(800)
    grab(win, "01-decode-rong")

    # Tạo mã: gõ văn bản ba thứ tiếng
    win.tabs.setCurrentIndex(1)
    pump(300)
    # Để combo ở "Tự động": ảnh phải cho thấy bảng mã được nhận ra từ chính văn bản.
    for text, name in (
        ("CQ CQ DE R1ABC R1ABC K", "02-encode-en"),
        ("ВСЕМ ВСЕМ ДЕ Р1АБВ К", "03-encode-ru"),
        ("СӘЛЕМ ӘЛЕМ ҚҰРМЕТТІ ДОС", "04-encode-kk"),
        ("HELLO МИР", "04b-encode-tronhechu"),
    ):
        win.encode_page.text_edit.setPlainText(text)
        pump(500)
        grab(win, name)

    # Giải mã một file thật
    clip = OUT.parent / "sample.wav"
    if clip.is_file():
        win.tabs.setCurrentIndex(0)
        pump(200)
        win.decode_page.load_file(clip)
        for _ in range(40):
            pump(500)
            if win.decode_page.result is not None:
                break
        pump(600)
        grab(win, "05-decode-ketqua")

    # Cài đặt
    win.tabs.setCurrentIndex(2)
    pump(400)
    grab(win, "06-caidat")

    # Đổi ngôn ngữ giao diện
    for code, name in (("ru", "07-giaodien-ru"), ("kk", "08-giaodien-kk")):
        idx = win.language_combo.findData(code)
        if idx >= 0:
            win.language_combo.setCurrentIndex(idx)
        pump(500)
        win.tabs.setCurrentIndex(0)
        pump(300)
        grab(win, name)

    worker.stop()
    QCoreApplication.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
