import numpy as np
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from morsedesk.api import DecodeResult, Encoder, Word
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.charmap import CYRILLIC, KAZAKH_EXTRA, CharMap
from morsedesk.app.widgets.spectrogram import SpectrogramView
from morsedesk.app.widgets.stats_bar import StatsBar
from morsedesk.app.widgets.word_view import (
    COLOR_GOOD,
    COLOR_LOW,
    COLOR_MID,
    TEXT_COLOR,
    WORD_GOOD,
    WordView,
    confidence_color,
)
from morsedesk.app.worker import Spectrogram


def test_banner_levels_and_close(qtbot):
    b = Banner()
    qtbot.addWidget(b)
    assert b.isHidden() and b.level is None
    b.show_error("boom")
    assert b.level == "error" and b.text() == "boom" and not b.isHidden()
    b.show_warning("careful")
    assert b.level == "warning" and b.text() == "careful"
    b.setToolTip("chi tiet")
    b.show_warning("again")
    assert b.toolTip() == ""            # tooltip của lần trước không được sót lại
    b.setToolTip("chi tiet")
    b.close_button.click()
    assert b.level is None and b.isHidden() and b.toolTip() == ""


def test_confidence_colors_thresholds():
    assert WORD_GOOD == 0.8
    assert confidence_color(0.95) == "#c8f0c8" and confidence_color(0.8) == "#c8f0c8"
    assert confidence_color(0.6) == "#fff2b3" and confidence_color(0.5) == "#fff2b3"
    assert confidence_color(0.49) == "#f7c6c6"


def test_word_view_labels_tooltips_and_click(qtbot):
    v = WordView()
    qtbot.addWidget(v)
    v.show()
    words = [Word("CQ", 0.0, 0.5, 0.9), Word("DE", 0.6, 1.0, 0.55), Word("K", 1.1, 1.3, 0.2)]
    v.set_words(words)
    labels = v.labels()
    assert [lb.text() for lb in labels] == ["CQ", "DE", "K"]
    assert "#c8f0c8" in labels[0].styleSheet() and "#fff2b3" in labels[1].styleSheet() and "#f7c6c6" in labels[2].styleSheet()
    assert "0.90" in labels[0].toolTip() and "0.60" in labels[1].toolTip() and "1.00" in labels[1].toolTip()
    got = []
    v.word_clicked.connect(got.append)
    qtbot.mouseClick(labels[1], Qt.MouseButton.LeftButton)
    assert got == [0.6]
    v.clear()
    assert v.labels() == []


def test_stats_bar_text_and_busy(qtbot):
    s = StatsBar()
    qtbot.addWidget(s)
    r = DecodeResult("CQ", [], 20.4, 700.0, 12.3, "ru", {"en": -3.0, "ru": -1.0, "kk-cyrl-ru": -2.0}, [], "onnx")
    s.set_result(r, 0.42)
    t = s.text()
    assert "20.4" in t and "700" in t and "12.3" in t and s.language_label("ru") in t and "0.42" in t
    assert "-1.0" in s.language_widget.toolTip()
    s.set_result(DecodeResult("", [], None, None, None, "", {}, [], "onnx"), None)
    assert s.language_label("") in s.text()
    s.set_busy(True)
    assert not s.progress.isHidden()
    s.set_busy(False)
    assert s.progress.isHidden()


def test_charmap_groups_and_click(qtbot):
    c = CharMap()
    qtbot.addWidget(c)
    c.show()
    got = []
    c.char_clicked.connect(got.append)
    c.set_profile("kk-cyrl-ru")
    texts = [b.text() for b in c.buttons() if b.isVisibleTo(c)]
    assert set(CYRILLIC) <= set(texts) and set(KAZAKH_EXTRA) <= set(texts)
    kk_btn = next(b for b in c.buttons() if b.text() == "Ә")
    kk_btn.click()
    assert got == ["Ә"]
    c.set_profile("ru")
    assert all(not b.isVisibleTo(c) for b in c.buttons() if b.text() in KAZAKH_EXTRA)
    assert any(b.isVisibleTo(c) for b in c.buttons() if b.text() in CYRILLIC)
    c.set_profile("en")
    assert c.isHidden()


def test_spectrogram_view_sets_image_tone_marks(qtbot):
    v = SpectrogramView()
    qtbot.addWidget(v)
    spec = Spectrogram.from_audio(Encoder("en").to_audio("PARIS", wpm=20))
    v.set_spectrogram(spec)
    assert v.image.image is not None and v.image.image.shape == (spec.power_db.shape[1], spec.power_db.shape[0])
    v.set_tone(700.0)
    assert v.tone_line.isVisible() and abs(v.tone_line.value() - 700.0) < 1e-6
    v.set_tone(None)
    assert not v.tone_line.isVisible()
    v.set_word_marks([0.5, 1.2])
    assert len(v.word_lines) == 2
    v.set_cursor(0.7)
    assert v.cursor_line.isVisible() and abs(v.cursor_line.value() - 0.7) < 1e-6
    v.clear()
    assert v.image.image is None and v.word_lines == [] and not v.cursor_line.isVisible()
    v.set_spectrogram(Spectrogram.from_audio(np.zeros(0, np.float32)))   # rỗng không lỗi


def test_language_change_event_triggers_retranslate(qtbot):
    widgets = [WordView(), StatsBar(), SpectrogramView()]
    calls: dict[str, int] = {}
    for w in widgets:
        qtbot.addWidget(w)
        name = type(w).__name__
        original = w.retranslate

        def counted(name=name, original=original):
            calls[name] = calls.get(name, 0) + 1
            original()

        w.retranslate = counted
        QApplication.sendEvent(w, QEvent(QEvent.Type.LanguageChange))
    assert calls == {"WordView": 1, "StatsBar": 1, "SpectrogramView": 1}
    view = widgets[2]
    assert view.getAxis("bottom").labelText == "s" and view.getAxis("left").labelText == "Hz"


def _relative_luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def channel(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_word_colors_are_readable_on_any_system_theme(qtbot):
    """Màu chữ phải được ghim tối, không lấy theo bảng màu hệ thống.

    Ảnh chụp thật ở giao diện tối của Windows cho chữ trắng trên nền #c8f0c8 = 1,25:1.
    Ngưỡng 4,5:1 là mức AA của WCAG cho chữ thường.
    """
    for bg in (COLOR_GOOD, COLOR_MID, COLOR_LOW):
        assert _contrast(bg, TEXT_COLOR) >= 4.5, f"{bg} trên {TEXT_COLOR}"
    w = WordView()
    qtbot.addWidget(w)
    w.set_words([Word("CQ", 0.0, 0.5, 0.95), Word("DE", 0.6, 0.9, 0.6), Word("K", 1.0, 1.2, 0.2)])
    for label in w.labels():
        css = label.styleSheet()
        assert f"color:{TEXT_COLOR}" in css, css
        assert confidence_color(label.word.confidence) in css
