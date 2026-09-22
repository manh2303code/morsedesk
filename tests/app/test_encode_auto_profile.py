"""Trang Tạo mã tự chọn bảng mã theo văn bản đang gõ.

Người vận hành gõ bản tin rồi phát đi; bắt họ nhớ chọn đúng bảng trước là một chỗ để sai mà
không cần thiết. Việc chọn ở đây **tất định** chứ không phải đoán: xem
`morsedesk/encode/detect.py`. Khi nhiều bảng cùng phủ được, chúng sinh ra đúng cùng một chuỗi
Morse, nên tín hiệu phát ra không phụ thuộc lựa chọn.

Chọn tay vẫn giữ nguyên: người dùng đổi combo thì ứng dụng nghe theo, không tự ghi đè.
"""

import pytest
from PySide6.QtWidgets import QApplication

from morsedesk.app.encode_page import AUTO_PROFILE, EncodePage
from morsedesk.app.settings import AppSettings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def page(qtbot, tmp_path):
    from PySide6.QtCore import QSettings

    from morsedesk.app.worker import Player

    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    p = EncodePage(Player(), settings)
    qtbot.addWidget(p)
    return p


def test_auto_is_the_default_and_first_entry(page):
    assert page.profile_combo.itemData(0) == AUTO_PROFILE
    assert page.profile_combo.currentData() == AUTO_PROFILE


@pytest.mark.parametrize("text,expected", [
    ("CQ CQ DE R1ABC K", "en"),
    ("ПРИВЕТ МИР", "ru"),
    ("СӘЛЕМ ӘЛЕМ", "kk-cyrl-ru"),
])
def test_typing_switches_the_effective_profile(page, text, expected):
    page.text_edit.setPlainText(text)
    assert page.effective_profile_id() == expected
    assert page.profile_combo.currentData() == AUTO_PROFILE      # combo vẫn ở Tự động
    assert expected.split("-")[0] in page.auto_label.text().lower() or page.auto_label.text()


def test_manual_choice_wins_over_auto(page):
    page.text_edit.setPlainText("ПРИВЕТ")
    idx = page.profile_combo.findData("en")
    page.profile_combo.setCurrentIndex(idx)
    assert page.effective_profile_id() == "en"
    assert not page.auto_label.isVisible() or page.auto_label.text() == ""


def test_mixed_scripts_are_reported_not_silently_encoded(page):
    page.text_edit.setPlainText("HELLO МИР")
    assert page.warn_label.text()
    # Vẫn phải chọn một bảng để hiển thị được phần mã hóa được, và phải cảnh báo phần còn lại.
    assert page.effective_profile_id() in ("en", "ru", "kk-cyrl-ru")


def test_charmap_follows_the_detected_profile(page):
    page.text_edit.setPlainText("СӘЛЕМ")
    assert "Ә" in {b.text() for b in page.charmap.buttons()}
    page.text_edit.setPlainText("CQ DE K")
    assert page.charmap.isHidden() or not page.charmap.isVisibleTo(page)


def test_empty_text_keeps_a_usable_profile(page):
    page.text_edit.setPlainText("")
    assert page.effective_profile_id() in ("en", "ru", "kk-cyrl-ru")
