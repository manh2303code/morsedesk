"""Font đóng gói cùng ứng dụng, để chữ Kazakh hiện được trên máy Linux tối giản (CP-11).

Qt chạy trên máy không có font nào sẽ vẽ mọi ký tự thành ô vuông — đã gặp khi chụp màn hình
headless. Máy air-gap tối giản có rủi ro tương tự, đặc biệt với Ә Ғ Қ Ң Ө Ұ Ү Һ І.
"""

from pathlib import Path

import pytest
from PySide6.QtGui import QFontDatabase, QRawFont
from PySide6.QtWidgets import QApplication

from morsedesk.app.fonts import FONT_DIR, KAZAKH_LETTERS, bundled_fonts, load_bundled_fonts

pytestmark = pytest.mark.skipif(not FONT_DIR.is_dir(), reason="chưa tải font (tools/fetch_fonts.py)")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_fonts_are_present_in_the_package():
    files = bundled_fonts()
    assert files, "không có font nào trong gói"
    assert all(Path(f).suffix.lower() in (".ttf", ".otf") for f in files)
    assert any("DejaVu" in Path(f).name for f in files)
    assert any("Noto" in Path(f).name for f in files)


def test_loading_registers_at_least_one_family(app):
    families = load_bundled_fonts()
    assert families
    installed = set(QFontDatabase.families())
    assert any(f in installed for f in families), (families, len(installed))


def test_a_bundled_font_covers_every_kazakh_letter(app):
    load_bundled_fonts()
    missing_per_file: dict[str, list[str]] = {}
    for path in bundled_fonts():
        raw = QRawFont(str(path), 12.0)
        # Phải truyền codepoint: `supportsCharacter` với `str` trả False cho mọi ký tự ngoài
        # Latin-1, kể cả khi font có glyph — đã kiểm bằng tay trên DejaVu Sans.
        missing = [ch for ch in KAZAKH_LETTERS if not raw.supportsCharacter(ord(ch))]
        missing_per_file[Path(path).name] = missing
        if not missing:
            return
    pytest.fail(f"không font nào phủ đủ chữ Kazakh: {missing_per_file}")
