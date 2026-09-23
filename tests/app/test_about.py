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
def test_face_reads_as_two_dits_and_a_dah_at_every_size(size):
    """Hai mắt và miệng là BA khối tách rời ở mọi cỡ, kể cả 16 px trên thanh tác vụ."""
    from scipy import ndimage

    img = make_icon.render(size).astype(float)
    lamp = np.array(make_icon.LAMP, dtype=float)
    dusk = np.array(make_icon.DUSK, dtype=float)
    closer_to_lamp = (np.linalg.norm(img[..., :3] - lamp, axis=2)
                      < np.linalg.norm(img[..., :3] - dusk, axis=2)) & (img[..., 3] > 128)
    _, n = ndimage.label(closer_to_lamp)
    assert n == 3


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
