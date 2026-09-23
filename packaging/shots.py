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
    from morsedesk.app.live_worker import LiveWorker
    from morsedesk.app.main import I18N_DIR, set_app_identity
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.settings import AppSettings
    from morsedesk.app.theme import apply_theme
    from morsedesk.app.worker import DecoderWorker, Player

    QApplication(sys.argv[:1])      # giữ sống qua vòng đời hàm; không cần tham chiếu
    set_app_identity()
    print("font:", apply_application_font(), flush=True)
    # Cùng theme với ứng dụng thật (create_app): thiếu dòng này ảnh chụp ra kiểu Qt mặc định —
    # nút xanh dương, nền xám — và không còn soi được giao diện người dùng thấy.
    apply_theme(QApplication.instance())

    worker = DecoderWorker(engine="onnx", model_path=None, lm_dir=None)
    worker.start()
    live = LiveWorker(engine="onnx", model_path=None, lm_dir=None)
    live.start()
    win = MainWindow(worker, Player(), AppSettings(), I18N_DIR, live=live)

    def show(page) -> None:
        """Chuyển tab theo WIDGET, không theo chỉ số.

        Chỉ số tab đổi mỗi lần thêm trang (tab Nghe vừa chèn vào giữa), và script chụp thì
        không có test nào canh nên lỗi kiểu đó chỉ lộ ra khi nhìn ảnh sai trang.
        """
        win.tabs.setCurrentIndex(win.tabs.indexOf(page))
    win.resize(1180, 760)
    win.show()

    def pump(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    pump(800)
    grab(win, "01-decode-rong")

    # Tạo mã: gõ văn bản ba thứ tiếng
    show(win.encode_page)
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
        show(win.decode_page)
        pump(200)
        win.decode_page.load_file(clip)
        for _ in range(40):
            pump(500)
            if win.decode_page.result is not None:
                break
        pump(600)
        grab(win, "05-decode-ketqua")

    # Nghe trực tiếp: chụp cả trạng thái rỗng và trạng thái có chữ hai tầng
    if win.live_page is not None:
        show(win.live_page)
        pump(400)
        grab(win, "06-nghe-rong")
        # Nạp dữ liệu THẬT vào thác nước và chip từ, không chỉ đặt chữ: ảnh phải cho thấy
        # trang lúc đang làm việc, vì đó là lúc lỗi bố cục lộ ra.

        from morsedesk.api import Encoder, Word
        from morsedesk.model.stream import StreamUpdate

        audio = Encoder("en").to_audio("CQ CQ DE R1ABC R1A", wpm=20, snr_db=12, seed=5)
        for i in range(0, len(audio), 1600):
            win.live_page.waterfall.push(audio[i:i + 1600])
        win.live_page.on_text("CQ CQ DE R1ABC", " R1A")
        win.live_page.on_stats(StreamUpdate(
            "CQ CQ DE R1ABC", " R1A", True, 14.0,
            [Word("R1A", 12.1, 12.9, 0.52)], 20.3, 700.0, 12.4, "en"))
        win.live_page.on_level(0.02)
        pump(300)
        grab(win, "07-nghe-haitang")

    # Cài đặt
    show(win.settings_page)
    pump(400)
    grab(win, "08-caidat")

    # Đổi ngôn ngữ giao diện
    for code, name in (("ru", "09-giaodien-ru"), ("kk", "10-giaodien-kk")):
        btn = win.language_bar.buttons.get(code)
        if btn is not None:
            btn.click()
        pump(500)
        show(win.decode_page)
        pump(300)
        grab(win, name)

    # Giới thiệu và tài liệu kỹ thuật, cả ba ngôn ngữ: tài liệu mở đúng ngôn ngữ giao diện.
    for code in ("en", "ru", "kk"):
        btn = win.language_bar.buttons.get(code)
        if btn is not None:
            btn.click()
        pump(400)
        show(win.about_page)
        win.about_page.strip.finish()           # ảnh chụp: đèn đã sáng hết
        pump(300)
        grab(win, f"11-gioithieu-{code}")
        doc = win.open_docs()
        doc.resize(1080, 760)
        pump(500)
        grab(doc, f"12-tailieu-{code}")
        doc.view.scrollToAnchor("tables")
        pump(300)
        grab(doc, f"13-tailieu-bangma-{code}")
    if win.doc_window is not None:
        win.doc_window.close()

    live.shutdown()
    live.wait(3000)
    worker.stop()
    QCoreApplication.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
