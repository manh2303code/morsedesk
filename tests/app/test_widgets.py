from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from morsedesk.api import DecodeResult, Encoder, Word
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.charmap import CYRILLIC, KAZAKH_EXTRA, CharMap
from morsedesk.app.widgets.signal_panel import SignalPanel
from morsedesk.app.widgets.stats_bar import StatsBar
from morsedesk.app.widgets.word_view import (
    ACTIVE_BG,
    ACTIVE_TEXT,
    COLOR_GOOD,
    COLOR_LOW,
    COLOR_MID,
    FADE_COLOR,
    TEXT_COLOR,
    UPCOMING_COLOR,
    WORD_GOOD,
    WordView,
    confidence_color,
)


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
    # ngưỡng theo số đo hiệu chuẩn (word_view.WORD_GOOD/WORD_FAIR)
    assert WORD_GOOD == 0.97
    assert confidence_color(0.99) == COLOR_GOOD and confidence_color(0.97) == COLOR_GOOD
    assert confidence_color(0.9) == COLOR_MID and confidence_color(0.8) == COLOR_MID
    assert confidence_color(0.79) == COLOR_LOW
    assert len({COLOR_GOOD, COLOR_MID, COLOR_LOW}) == 3


def test_word_view_texts_tooltips_and_click(qtbot):
    v = WordView()
    qtbot.addWidget(v)
    v.resize(600, 200)
    v.show()
    words = [Word("CQ", 0.0, 0.5, 0.98), Word("DE", 0.6, 1.0, 0.85), Word("K", 1.1, 1.3, 0.2)]
    v.set_words(words)
    assert v.texts() == ["CQ", "DE", "K"]
    assert [confidence_color(w.confidence) for w in v.words()] == [COLOR_GOOD, COLOR_MID, COLOR_LOW]
    assert "0.98" in v.tooltip_for(0) and "0.60" in v.tooltip_for(1) and "1.00" in v.tooltip_for(1)
    # tooltip nói VÌ SAO có màu đó (người dùng yêu cầu 25/09)
    assert "No underline" in v.tooltip_for(0)
    assert "Yellow" in v.tooltip_for(1) and "Red" in v.tooltip_for(2)
    got = []
    v.word_clicked.connect(got.append)
    qtbot.mouseClick(v.canvas(), Qt.MouseButton.LeftButton, pos=v.word_rect(1).center())
    assert got == [0.6]
    v.clear()
    assert v.texts() == []


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


def test_signal_panel_2d_shows_image_tone_and_words(qtbot):
    """Phổ 2D của khối Tín hiệu: ảnh, vạch tone, tên từ trong khung; nguồn None thì trống."""
    from morsedesk.api import Word
    from morsedesk.app.widgets.signal_columns import FileColumns

    p = SignalPanel()
    qtbot.addWidget(p)
    p.resize(900, 300)
    p.show()
    p.view_2d_button.click()
    p.set_source(FileColumns(Encoder("en").to_audio("PARIS PARIS", wpm=20)), fit=True)
    p.set_tone(700.0)
    p.set_words([Word("PARIS", 0.3, 1.5, 0.9)])
    s = p.strip
    assert s.has_image() and s.tone_hz == 700.0 and [w for _, w in s.words] == ["PARIS"]
    p.set_source(None)
    assert not s.has_image() and not p.ridge.surface().size


def test_language_change_event_triggers_retranslate(qtbot):
    widgets = [WordView(), StatsBar(), SignalPanel()]
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
    assert calls == {"WordView": 1, "StatsBar": 1, "SignalPanel": 1}


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
    # Chữ thường, chữ "chưa nghe tới" (mờ hơn) và chữ trên vệt karaoke: đều đạt AA.
    assert _contrast(TEXT_COLOR, FADE_COLOR) >= 4.5
    assert _contrast(UPCOMING_COLOR, FADE_COLOR) >= 4.5
    assert _contrast(ACTIVE_TEXT, ACTIVE_BG) >= 4.5
    # Gạch chân độ tin cậy là đồ họa, không phải chữ: mức 3:1 (WCAG 1.4.11) trên nền khung.
    for mark in (COLOR_MID, COLOR_LOW):
        assert _contrast(mark, FADE_COLOR) >= 3.0, mark


def test_word_tooltip_gives_measured_accuracy_and_localised_numbers(qtbot, monkeypatch):
    """"Đúng khoảng X %" lấy từ bảng hiệu chuẩn ĐO (app/confidence.py), riêng cho file và nghe; số
    dùng dấu phẩy thập phân khi giao diện là tiếng Nga/Kazakh."""
    from PySide6.QtCore import QCoreApplication

    from morsedesk.app import confidence

    monkeypatch.setattr(confidence, "_table", lambda mode, path=None: (
        ((0.0, 0.5, 0.40), (0.5, 0.8, 0.83), (0.8, 1.0, 0.97)) if mode == "file"
        else ((0.0, 0.5, 0.30), (0.5, 0.8, 0.70), (0.8, 1.0, 0.95))))
    words = [Word("CQ", 0.0, 0.5, 0.9), Word("DE", 0.6, 1.25, 0.6)]      # bảng giả: 0,8 / 0,5
    f = WordView()
    live = WordView(live=True)
    for v in (f, live):
        qtbot.addWidget(v)
        v.set_words(words)
    assert "97 %" in f.tooltip_for(0) and "83 %" in f.tooltip_for(1)
    assert "95 %" in live.tooltip_for(0) and "70 %" in live.tooltip_for(1)
    app = QCoreApplication.instance()
    old = app.property("ui_language")
    try:
        app.setProperty("ui_language", "ru")
        assert "0,60" in f.tooltip_for(1) and "1,25" in f.tooltip_for(1)
        app.setProperty("ui_language", "en")
        assert "0.60" in f.tooltip_for(1)
    finally:
        app.setProperty("ui_language", old)


def test_word_tooltip_omits_percentage_without_calibration(qtbot, monkeypatch):
    """Bản dựng thiếu bảng hiệu chuẩn: bỏ dòng phần trăm chứ không bịa số."""
    from morsedesk.app import confidence

    monkeypatch.setattr(confidence, "_table", lambda mode, path=None: ())
    v = WordView()
    qtbot.addWidget(v)
    v.set_words([Word("CQ", 0.0, 0.5, 0.9)])
    assert "%" not in v.tooltip_for(0)
