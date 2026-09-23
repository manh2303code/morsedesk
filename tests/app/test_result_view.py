"""Khung kết quả kiểu "lời bài hát", nút biểu tượng, phần văn bản thuần ẩn được (24/09).

Bối cảnh: ảnh chụp người dùng với bản tin ARRL 13 phút — khung chip chỉ hiện hai dòng rưỡi, cắt
ngang dòng thứ ba, còn văn bản thuần và kết quả thay thế chiếm gần nửa trang.
"""

import time

from PySide6.QtCore import QCoreApplication, QPointF, QSettings

from morsedesk.api import Word
from morsedesk.app.main import I18N_DIR
from morsedesk.app.settings import AppSettings
from morsedesk.app.widgets.icons import KINDS, icon_center_of_mass, line_icon
from morsedesk.app.widgets.word_view import FOLLOW_AT, WordView


def _words(n: int, step: float = 1.0) -> list[Word]:
    return [Word(f"W{i}", i * step, i * step + 0.5, 0.9) for i in range(n)]


def _settings(tmp_path) -> AppSettings:
    return AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))


def test_karaoke_brings_the_current_line_to_the_upper_third(qtbot):
    v = WordView()
    qtbot.addWidget(v)
    v.resize(520, 220)
    v.show()
    v.set_words(_words(400))
    QCoreApplication.processEvents()
    v.set_playhead(250.2)
    target = v.follow_target()
    y = v.word_rect(250).top()
    assert target > 0
    assert abs((y - target) - v.viewport().height() * FOLLOW_AT) <= 2, (y, target)
    # Cùng dòng thì không cuộn thêm (không giật mỗi từ).
    v.set_playhead(250.9)
    assert v.follow_target() == target


def test_karaoke_stops_following_while_the_user_scrolls(qtbot):
    v = WordView()
    qtbot.addWidget(v)
    v.resize(520, 220)
    v.show()
    v.set_words(_words(400))
    QCoreApplication.processEvents()
    v.verticalScrollBar().setValue(0)
    v._mark_user_scroll()                   # như lăn chuột / kéo thanh cuộn
    v.set_playhead(300.2)
    assert v.verticalScrollBar().value() == 0 and v.follow_target() == 0
    assert v.active_index() == 300          # vẫn tô đúng từ, chỉ không kéo khung đi


def test_long_messages_build_and_play_fast(qtbot):
    """Đo 24/09: một nhãn mỗi từ mất 7,5 s cho 2 400 từ; vùng tự vẽ phải dưới 0,5 s."""
    v = WordView()
    qtbot.addWidget(v)
    v.resize(1200, 360)
    v.show()
    words = _words(2400, step=1.5)
    t0 = time.perf_counter()
    v.set_words(words)
    QCoreApplication.processEvents()
    assert time.perf_counter() - t0 < 0.5
    t0 = time.perf_counter()
    for k in range(100):
        v.set_playhead(k * 3.0)
        QCoreApplication.processEvents()
    assert (time.perf_counter() - t0) / 100 < 0.02       # dư sức cho nhịp 50 ms của thanh phát


def test_every_icon_renders_centred_ink():
    for kind in KINDS:
        assert not line_icon(kind).isNull()
        c = icon_center_of_mass(kind)
        assert 7 <= c.x() <= 17 and 7 <= c.y() <= 17, (kind, c)
    assert icon_center_of_mass("copy") != QPointF(0, 0)


def _decode_page(qtbot, settings):
    from morsedesk.app.decode_page import DecodePage
    from morsedesk.app.worker import DecoderWorker

    page = DecodePage(DecoderWorker(engine="baseline", model_path=None, lm_dir=None), settings)
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    return page


def test_plain_text_panel_hides_and_the_choice_is_remembered(qtbot, tmp_path):
    settings = _settings(tmp_path)
    page = _decode_page(qtbot, settings)
    assert page.details.isVisible() and page.details_button.isChecked()
    page.details_button.click()
    assert not page.details.isVisible() and settings.show_text_details is False
    again = _decode_page(qtbot, settings)
    assert not again.details.isVisible() and not again.details_button.isChecked()
    again.details_button.click()
    assert again.details.isVisible() and settings.show_text_details is True


def test_one_export_button_offers_text_and_json(qtbot, tmp_path):
    page = _decode_page(qtbot, _settings(tmp_path))
    actions = page.export_button.menu().actions()
    assert actions == [page.export_txt_action, page.export_json_action]
    assert ".txt" in actions[0].text() and ".json" in actions[1].text()
    for b in (page.open_button, page.copy_button, page.export_button):
        assert b.text() == "" and not b.icon().isNull() and b.toolTip()
    assert "Ctrl+O" in page.open_button.toolTip()


def test_icon_buttons_speak_every_ui_language(qtbot, tiny_lm_dir, tmp_path):
    """Nút chỉ có biểu tượng: tooltip và tên trợ năng phải đổi theo ngôn ngữ giao diện."""
    from morsedesk.app.live_worker import LiveWorker
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.worker import DecoderWorker, Player

    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    live = LiveWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)   # không start
    w = MainWindow(worker, Player(), _settings(tmp_path), I18N_DIR, live=live)
    qtbot.addWidget(w)
    try:
        page = w.decode_page

        def texts():
            return (page.open_button.toolTip(), page.copy_button.toolTip(),
                    page.export_button.toolTip(), page.export_txt_action.text(),
                    page.details_button.text(), page.result_title.text(),
                    w.live_page.copy_button.toolTip(), w.live_page.clear_button.toolTip())

        en = texts()
        for lang, probe in (("ru", "Открыть аудиофайл… (Ctrl+O)"), ("kk", "Аудиофайлды ашу… (Ctrl+O)")):
            assert w.set_language(lang)
            got = texts()
            assert got[0] == probe
            assert all(a != b for a, b in zip(en, got, strict=True)), (lang, got)
    finally:
        w.set_language("en")
        QCoreApplication.processEvents()
        w.close()


def test_the_kazakh_interface_is_not_labelled_a_draft():
    """Tác giả là người Kazakh; gắn nhãn "bản nháp" cho chính ngôn ngữ của họ là phi lý."""
    from morsedesk.app.main_window import LANGUAGE_NAMES
    from morsedesk.app.reading import doc_path

    assert LANGUAGE_NAMES["kk"] == "Қазақша"
    banned = ("draft", "native speaker", "черновой", "носител", "алдын ала нұсқа", "ана тілі ретінде")
    for kind in ("about", "technical"):
        for lang in ("en", "ru", "kk"):
            html = doc_path(kind, lang).read_text(encoding="utf-8").lower()
            for word in banned:
                assert word not in html, (kind, lang, word)
