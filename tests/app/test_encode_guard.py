"""Không được phát hay lưu một bản tin đã bị cắt mất ký tự.

Trước đây ký tự ngoài bảng chỉ sinh một dải cảnh báo vàng, còn nút Nghe thử và Lưu vẫn bật —
nghĩa là người vận hành có thể phát đi bản tin thiếu chữ mà không nhận ra. Với bản tin nghiệp
vụ, phát thiếu nguy hiểm hơn nhiều so với việc phải sửa văn bản trước.

Cách xử lý giống hệt trường hợp audio quá thời lượng đã có từ tuần 4: chốt trong chính hàm dựng
audio, chứ không chỉ vô hiệu hóa nút — nút bị vô hiệu không phải là bất biến.
"""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from morsedesk.app.encode_page import EncodePage
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import Player


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def page(qtbot, tmp_path):
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    p = EncodePage(Player(), settings)
    qtbot.addWidget(p)
    return p


def test_clean_text_can_be_played_and_saved(page):
    page.text_edit.setPlainText("CQ CQ DE R1ABC K")
    assert page.play_button.isEnabled() and page.save_button.isEnabled()


def test_unsupported_characters_block_play_and_save(page):
    page.text_edit.setPlainText("HELLO МИР")
    assert not page.play_button.isEnabled()
    assert not page.save_button.isEnabled()
    assert page.warn_label.text()


def test_the_block_holds_even_when_calling_the_api_directly(page, tmp_path, monkeypatch):
    """Nút bị vô hiệu không phải bất biến: gọi thẳng API cũng không được dựng audio."""
    built = []
    monkeypatch.setattr(page, "build_audio", lambda: built.append(1))
    page.text_edit.setPlainText("HELLO МИР")
    page.play()
    page.save_to(tmp_path / "khong-duoc-ghi.wav")
    assert built == []
    assert not (tmp_path / "khong-duoc-ghi.wav").exists()


def test_fixing_the_text_unblocks_again(page):
    page.text_edit.setPlainText("HELLO МИР")
    assert not page.play_button.isEnabled()
    page.text_edit.setPlainText("HELLO WORLD")
    assert page.play_button.isEnabled() and page.save_button.isEnabled()
    assert not page.warn_label.text()
