"""Logo, trang Giới thiệu và tài liệu kỹ thuật ba thứ tiếng."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

from morsedesk.app import branding
from morsedesk.app.about_page import AboutPage, MorseStrip, model_version
from morsedesk.app.doc_window import TechDocWindow, sections
from morsedesk.app.main import I18N_DIR
from morsedesk.app.main_window import MainWindow
from morsedesk.app.reading import DOC_LANGUAGES, doc_path, load_doc
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import DecoderWorker, Player

# `packaging/` của dự án trùng tên gói `packaging` của pip, nên nạp theo đường dẫn.
_spec = importlib.util.spec_from_file_location("make_icon", Path("packaging/make_icon.py"))
make_icon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_icon)

DEVELOPER = "Шабданбек Бақытжан Асанханұлы"


# ---- logo ----

def test_icon_set_is_complete_and_matches_the_generator():
    """File trong repo phải đúng là thứ bộ sinh vẽ ra — sửa tay một file PNG là lệch nhận diện."""
    for size in branding.ICON_SIZES:
        path = branding.ICON_DIR / f"morsedesk-{size}.png"
        assert path.is_file(), path
        assert path.read_bytes() == make_icon.png_bytes(make_icon.render(size)), size


@pytest.mark.parametrize("size", branding.ICON_SIZES)
def test_three_marks_stay_apart_at_every_size(size):
    """`· · –` phải là BA khối vàng tách rời ở mọi cỡ, kể cả 16 px trên thanh tác vụ, và phím trắng
    phải có mặt. Bản đầu của logo phím Morse dính ba dấu thành một khối ở 16–24 px."""
    from scipy import ndimage

    img = make_icon.render(size).astype(float)
    d_lamp = np.linalg.norm(img[..., :3] - np.array(make_icon.LAMP_RGB), axis=2)
    d_ink = np.linalg.norm(img[..., :3] - np.array(make_icon.INK_RGB), axis=2)
    d_tile = np.linalg.norm(img[..., :3] - np.array(make_icon.TOP_RGB), axis=2)
    opaque = img[..., 3] > 128
    lamp = (d_lamp < d_ink) & (d_lamp < d_tile) & (d_lamp < 90) & opaque
    ink = (d_ink < d_lamp) & (d_ink < 90) & opaque
    assert ndimage.label(lamp)[1] == 3
    assert ink.sum() >= size * size * 0.08


def test_ico_holds_every_size_as_png():
    pngs = [(s, make_icon.png_bytes(make_icon.render(s))) for s in (16, 32, 256)]
    ico = make_icon.ico_bytes(pngs)
    reserved, kind, count = np.frombuffer(ico[:6], dtype="<u2")
    assert (reserved, kind, count) == (0, 1, 3)
    assert ico.count(b"\x89PNG") == 3


def test_app_identity_sets_the_window_icon_and_desktop_name(qapp):
    branding.install_app_identity(qapp)
    icon = QApplication.windowIcon()
    assert not icon.isNull()
    assert {s.width() for s in icon.availableSizes()} >= {16, 32, 256}
    assert QApplication.desktopFileName() == branding.DESKTOP_FILE_NAME


def test_morse_strip_spells_the_name_in_real_morse():
    """Dải đèn trên trang Giới thiệu phải đọc ra đúng MORSEDESK, không phải hoa văn."""
    els = branding.morse_elements("MorseDesk")
    letters, cur, prev_end = [], "", None
    for start, length in els:
        if prev_end is not None and start - prev_end >= 3:
            letters.append(cur)
            cur = ""
        cur += "-" if length == 3 else "."
        prev_end = start + length
    letters.append(cur)
    assert letters == ["--", "---", ".-.", "...", ".", "-..", ".", "...", "-.-"]


def test_strip_lights_up_once_then_stays_lit(qtbot):
    strip = MorseStrip()
    qtbot.addWidget(strip)
    strip.play_once()
    assert strip.lit == 0
    qtbot.waitUntil(lambda: strip.lit == len(strip.elements), timeout=8000)
    strip.play_once()                     # lần hai: không chạy lại
    assert strip.lit == len(strip.elements)


# ---- tài liệu ----

@pytest.mark.parametrize("kind", ["about", "technical"])
@pytest.mark.parametrize("lang", DOC_LANGUAGES)
def test_every_language_has_its_own_finished_document(kind, lang):
    path = doc_path(kind, lang)
    assert path.name == f"{kind}_{lang}.html", "thiếu bản dịch, đang rơi về tiếng Anh"
    text = path.read_text(encoding="utf-8")
    assert "{{" not in text, "còn chỗ trống chưa điền số đo"
    assert "119" in text and "425" in text                   # 1 119 425 tham số (dấu tách tùy ngôn ngữ)


@pytest.mark.parametrize("lang", DOC_LANGUAGES)
def test_about_names_the_developer(lang):
    assert DEVELOPER in load_doc("about", lang)


def test_translations_keep_the_same_sections_order_and_layer_colours():
    """Mục lục dựng từ chính tài liệu: bản dịch thiếu hay đảo một mục là mục lục lệch ngay."""
    ref = [(s.anchor, s.layer) for s in sections(load_doc("technical", "en"))]
    assert len(ref) >= 10
    for lang in DOC_LANGUAGES:
        assert [(s.anchor, s.layer) for s in sections(load_doc("technical", lang))] == ref, lang


def test_translations_keep_every_table_and_kazakh_letter():
    en = load_doc("technical", "en")
    for lang in ("ru", "kk"):
        doc = load_doc("technical", lang)
        assert doc.count("<table") == en.count("<table"), lang
        assert doc.count("<tr") == en.count("<tr"), lang
        for letter in "ӘҒҚҢӨҰҮҺІ":
            assert letter in doc, (lang, letter)


def test_kazakh_code_table_matches_the_profile():
    """Bảng trong tài liệu phải khớp profile kk-cyrl-ru thật, không phải trí nhớ người viết."""
    from morsedesk.lm.profile import load_profile

    kk = load_profile("kk-cyrl-ru")
    rows = re.findall(r'<td class="morse">([·–]+)</td><td>(\w)</td><td class="kk">([^<]+)</td>',
                      load_doc("technical", "en"))
    assert len(rows) == 8
    for code, ru_letter, kk_letters in rows:
        pattern = code.replace("·", ".").replace("–", "-")
        options = kk.map[pattern]
        assert options[0] == ru_letter
        assert set(kk_letters.replace(",", " ").split()) == set(options[1:])


# ---- giao diện ----

def test_about_page_shows_versions_and_follows_the_language(qtbot):
    page = AboutPage()
    qtbot.addWidget(page)
    assert model_version() in page.version.text()
    page.set_language("kk")
    assert DEVELOPER in page.body.toPlainText()
    assert "Ә" in page.body.toPlainText()


def test_learn_more_opens_the_document_in_the_ui_language(qtbot, tiny_lm_dir, tmp_path):
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    win = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(win)
    try:
        assert win.tabs.tabText(win.tabs.indexOf(win.about_page)) == "About"
        assert win.set_language("ru")
        assert win.tabs.tabText(win.tabs.indexOf(win.about_page)) == "О программе"
        doc = win.open_docs()
        assert doc.language == "ru" and doc.windowTitle() == "Техническое описание MorseDesk"
        first = doc.toc.item(0).text()
        win.set_language("kk")              # đổi ngôn ngữ khi cửa sổ tài liệu đang mở
        assert doc.language == "kk" and doc.toc.item(0).text() != first
        assert win.open_docs() is doc       # mở lại thì dùng lại cửa sổ cũ
        doc.close()
    finally:
        win.set_language("en")
        QCoreApplication.processEvents()
        win.close()


def test_toc_jumps_and_pdf_export(qtbot, tmp_path):
    doc = TechDocWindow("en")
    qtbot.addWidget(doc)
    assert doc.toc.count() == len(sections(load_doc("technical", "en")))
    out = tmp_path / "ref.pdf"
    assert doc.save_pdf(str(out))
    assert out.read_bytes()[:5] == b"%PDF-" and out.stat().st_size > 20_000


@pytest.mark.parametrize("lang", ["en", "ru", "kk"])
def test_hero_tagline_is_never_clipped(qtbot, tiny_lm_dir, tmp_path, lang):
    """Bản Kazakh dài ba dòng từng bị cắt mất dòng cuối và bị dải đèn Morse đè lên."""
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    win = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(win)
    try:
        win.set_language(lang)
        win.tabs.setCurrentWidget(win.about_page)
        win.show()
        qtbot.waitExposed(win)
        tag = win.about_page.tagline
        assert tag.height() >= tag.heightForWidth(tag.width())
        assert win.about_page.strip.geometry().top() >= tag.geometry().bottom()
    finally:
        win.set_language("en")
        QCoreApplication.processEvents()
        win.close()


# ---- màn hình chờ động, vòng tiến trình, file mẫu ----

def test_splash_taps_out_the_logo_then_finishes(qtbot):
    from morsedesk.app import splash as sp

    assert sp.frame_state(0)[1] == (0.0, 0.0, 0.0)             # đứng yên: chưa dấu nào sáng
    lever, lit, spark = sp.frame_state(sp.PRE_MS + 0.5 * sp.UNIT_MS)
    assert lever > 0 and spark > 0 and lit[0] == 1.0             # đang nhấn dit đầu
    assert 0.0 < sp.frame_state(sp.PRE_MS + 5.5 * sp.UNIT_MS)[1][2] < 1.0   # dah đang dài dần
    assert sp.frame_state(sp.TOTAL_MS)[1] == (1.0, 1.0, 1.0)    # hết: đủ logo
    w = sp.SplashScreen()
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.finished, timeout=5000):
        w.play()
    img = sp.render_image(0.0)
    assert (img.width(), img.height()) == (sp.SIZE.width(), sp.SIZE.height())


def test_splash_names_the_author():
    from morsedesk.app.splash import COPYRIGHT

    assert DEVELOPER in COPYRIGHT and "©" in COPYRIGHT


def test_packaged_splash_image_is_the_first_frame():
    """Ảnh tĩnh của PyInstaller phải trùng khung đầu, nếu không chỗ nối hai màn hình sẽ giật."""
    from PySide6.QtGui import QImage

    img = QImage(str(Path("packaging/splash.png")))
    assert not img.isNull() and (img.width(), img.height()) == (520, 380)


def test_progress_ring_behaves_like_a_progress_bar(qtbot):
    from morsedesk.app.widgets.progress_ring import ProgressRing

    r = ProgressRing()
    qtbot.addWidget(r)
    r.setRange(0, 0)
    assert r.indeterminate() and r.maximum() == 0
    r.setRange(0, 1000)
    r.setValue(430)
    assert (r.minimum(), r.maximum(), r.value(), r.percent()) == (0, 1000, 430, 43)
    r.setValue(5000)
    assert r.value() == 1000                                    # kẹp, không vượt


@pytest.mark.parametrize("lang,text", [("en", "HELLO"), ("ru", "ЗДРАВСТВУЙТЕ"),
                                       ("kk", "СӘЛЕМЕТСІЗ БЕ")])
def test_hello_samples_decode_in_auto_mode(lang, text):
    """File mẫu phải được TỰ nhận đúng ngôn ngữ — đó là thứ người dùng thấy đầu tiên."""
    from morsedesk.api import DEFAULT_MODEL_PATH, Decoder
    from morsedesk.app.decode_page import SAMPLE_FILES, SAMPLES_DIR

    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip("cần models/acoustic.onnx")
    r = Decoder("auto", engine="onnx").decode_file(SAMPLES_DIR / SAMPLE_FILES[lang])
    assert r.text == text


def test_sample_follows_ui_language_until_the_user_opens_a_file(qtbot, tiny_lm_dir, tmp_path):
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    win = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(win)
    page = win.decode_page
    try:
        win.set_language("ru")
        assert page._path is None                  # trang trần (test): không tự nạp mẫu
        page.enable_samples()
        win.set_language("kk")
        assert page.showing_sample() and page._path.name == "hello_kk.wav"
        assert not page.sample_badge.isHidden()
        win.set_language("ru")
        assert page._path.name == "hello_ru.wav"
        own = tmp_path / "mine.wav"
        own.write_bytes((page._path).read_bytes())
        page.load_file(own)
        win.set_language("en")                     # file của người dùng: không bị thay
        assert page._path == own and not page.showing_sample() and page.sample_badge.isHidden()
    finally:
        win.set_language("en")
        QCoreApplication.processEvents()
        win.close()
