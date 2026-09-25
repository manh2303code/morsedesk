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


def grab_tooltip(view, index: int, name: str) -> None:
    """Hiện tooltip của từ thứ `index` trong một WordView rồi chụp chính cửa sổ tooltip (Qt vẽ nó
    thành cửa sổ riêng, grab() của trang không thấy)."""
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QToolTip

    canvas = view.canvas()
    r = view.word_rect(index)
    QToolTip.showText(canvas.mapToGlobal(r.center()), view.tooltip_for(index), canvas)
    loop = QEventLoop()
    QTimer.singleShot(400, loop.quit)
    loop.exec()
    tips = [w for w in QApplication.topLevelWidgets() if w.inherits("QTipLabel") and w.isVisible()]
    if tips:
        grab(tips[0], name)
    QToolTip.hideText()


def tallest_cell(ridge):
    """Điểm màn hình trên sườn dải cao nhất của cảnh 3D (để chụp ô số đo khi rê chuột)."""
    from PySide6.QtCore import QPoint

    z = ridge.surface()
    if z.ndim != 2 or z.shape[0] < 2 or z.shape[1] < 2:
        return None
    h = ridge.heights(z)
    r, c = divmod(int(h.argmax()), z.shape[1])
    left, width, base, amp = ridge._row_geometry(r / (z.shape[0] - 1))
    return QPoint(int(left + width * c / (z.shape[1] - 1)), int(base - h[r, c] * amp * 0.6))


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
        grab_tooltip(win.decode_page.word_view, 0, "05b-giaima-tooltip")

    # File mẫu "Xin chào" (sạch, không nhiễu — người dùng 25/09) + rê chuột trên cảnh 3D và phổ 2D.
    from morsedesk.app.decode_page import SAMPLE_FILES, SAMPLES_DIR

    show(win.decode_page)
    win.decode_page.load_file(SAMPLES_DIR / SAMPLE_FILES["en"])
    for _ in range(40):
        pump(500)
        if win.decode_page.result is not None:
            break
    pump(600)
    grab(win, "05c-mau-sach-3d")
    ridge = win.decode_page.ridge
    cell = tallest_cell(ridge)
    if cell is not None:
        ridge.hover_at(cell)
        pump(200)
        grab(win, "05d-mau-3d-rechuot")
        ridge.hover_at(None)
    win.decode_page.view_2d_button.click()
    pump(300)
    r = win.decode_page.result
    if r is not None and r.words:
        w = r.words[0]
        win.decode_page.spectrogram.hover_at((w.start_s + w.end_s) / 2, r.tone_hz or 700.0)
        pump(200)
        grab(win, "05e-mau-2d-rechuot")
        win.decode_page.spectrogram.hover_at(None)
    win.decode_page.view_3d_button.click()

    # Nghe trực tiếp: chụp cả trạng thái rỗng và trạng thái có chữ hai tầng
    if win.live_page is not None:
        show(win.live_page)
        pump(400)
        grab(win, "06-nghe-rong")
        # Nạp dữ liệu THẬT vào thác nước và chip từ, không chỉ đặt chữ: ảnh phải cho thấy
        # trang lúc đang làm việc, vì đó là lúc lỗi bố cục lộ ra.

        from morsedesk.api import Encoder, Word
        from morsedesk.model.stream import StreamUpdate

        audio = Encoder("en").to_audio("CQ CQ DE R1ABC QTH MOSCOW R1A", wpm=20, snr_db=12, seed=5)
        for i in range(0, len(audio), 800):          # như LiveWorker: khối 100 ms
            win.live_page._on_block(audio[i:i + 800])
        win.live_page.on_text("CQ CQ DE R1ABC QTH MOSCOW", " R1A")
        committed = [Word("CQ", 1.0, 1.9, 0.97), Word("CQ", 2.4, 3.3, 0.95), Word("DE", 3.8, 4.5, 0.93),
                     Word("R1ABC", 5.0, 7.6, 0.71), Word("QTH", 8.1, 9.3, 0.9), Word("MOSCOW", 9.8, 11.7, 0.42)]
        win.live_page.on_stats(StreamUpdate(
            committed="CQ CQ DE R1ABC QTH MOSCOW", tentative=" R1A", decoded=True, audio_s=14.0,
            words=[Word("R1A", 12.1, 12.9, 0.52)], wpm=20.3, tone_hz=700.0, snr_db=12.4, language="en",
            committed_words=committed))
        win.live_page.on_level(0.02)
        pump(300)
        grab(win, "07-nghe-haitang")
        grab_tooltip(win.live_page.word_view, 3, "07b-nghe-tooltip-vang")
        grab_tooltip(win.live_page.word_view, 6, "07c-nghe-tooltip-tam")
        # Rê chuột: trên cảnh 3D (thác nước hiện dấu nối), rồi trên thác nước (cảnh 3D hiện dấu).
        cell = tallest_cell(win.live_page.ridge)
        if cell is not None:
            win.live_page.ridge.hover_at(cell)
            pump(200)
            grab(win, "07d-nghe-3d-rechuot")
            win.live_page.ridge.hover_at(None)
        wf = win.live_page.waterfall
        from PySide6.QtCore import QPoint

        wf.hover_at(QPoint(int(wf.width() * 0.97), int(wf.height() * (1 - 700 / 2000))))
        pump(200)
        grab(win, "07e-nghe-2d-rechuot")
        wf.hover_at(None)

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
