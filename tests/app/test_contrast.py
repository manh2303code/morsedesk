"""Chữ trên ảnh chụp THẬT phải đọc được — đo điểm ảnh, không tin màu ghi trong mã.

Ảnh chụp người dùng 24/09: banner cảnh báo ra chữ trắng trên nền vàng nhạt (1,05:1) vì nhãn con
ăn luật màu chữ của theme chứ không ăn màu đặt cho khung. Test đọc mã/stylesheet không bắt được;
đo trên ảnh chụp thì bắt được ngay (tools/contrast_audit.py).
"""

from PySide6.QtCore import QSettings

from morsedesk.app.main import I18N_DIR
from morsedesk.app.settings import AppSettings
from tools.contrast_audit import FAIL, audit_window


def test_every_text_is_readable_including_banners_and_disabled_controls(qtbot, tiny_lm_dir, tmp_path):
    from PySide6.QtWidgets import QApplication

    from morsedesk.app.live_worker import LiveWorker
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.theme import apply_theme
    from morsedesk.app.worker import DecoderWorker, Player

    apply_theme(QApplication.instance())
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    live = LiveWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)     # không start
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    win = MainWindow(worker, Player(), settings, I18N_DIR, live=live)
    qtbot.addWidget(win)
    win.resize(1300, 860)
    win.show()
    rows = []
    try:
        for page in (win.decode_page, win.live_page, win.encode_page):
            win.tabs.setCurrentIndex(win.tabs.indexOf(page))
            rows += audit_window(win, type(page).__name__)
            page.banner.show_warning("Tone not detected clearly; guessing from the spectral peak.")
            rows += audit_window(win, type(page).__name__ + " warning")
            page.banner.show_error("Cannot read this file.")
            rows += audit_window(win, type(page).__name__ + " error")
            page.banner.clear()
        for page in (win.settings_page, win.about_page):
            win.tabs.setCurrentIndex(win.tabs.indexOf(page))
            rows += audit_window(win, type(page).__name__)
    finally:
        win.close()
    assert len(rows) > 60, len(rows)
    bad = [(r["state"], r["widget"], r["text"], round(r["ratio"], 2)) for r in rows if r["ratio"] < FAIL]
    assert not bad, bad
    banners = [r for r in rows if r["state"].endswith(("warning", "error")) and "Tone" in r["text"] + "Cannot"]
    assert banners and all(r["ratio"] >= 4.5 for r in banners if r["widget"] == "QLabel")
