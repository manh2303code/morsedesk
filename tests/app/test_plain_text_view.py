"""Ô văn bản thuần dưới các chip từ.

Các chip tô màu theo độ tin cậy rất tiện để soi từng từ, nhưng người vận hành còn cần đọc cả
bản tin liền mạch và chọn một đoạn để sao chép. Ảnh chụp giao diện cho thấy vùng dưới chip bỏ
trống hẳn với bản tin ngắn, nên chỗ đó là nơi hợp lý cho ô văn bản.
"""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from morsedesk.api import DecodeResult, Word
from morsedesk.app.decode_page import DecodePage
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import DecoderWorker


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def page(qtbot, tmp_path):
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=None)
    p = DecodePage(worker, settings)
    qtbot.addWidget(p)
    # `on_result` cố ý bỏ qua kết quả không khớp file đang mở (kết quả trễ của file đã bị thay).
    p._path = tmp_path / "x.wav"
    return p


def result_with(text: str) -> DecodeResult:
    words = [Word(t, i * 1.0, i * 1.0 + 0.5, 0.9) for i, t in enumerate(text.split())]
    return DecodeResult(text, words, 20.0, 700.0, 12.0, "en", {}, [], "baseline")


def test_text_view_shows_the_whole_message(page):
    page.on_result(result_with("CQ CQ DE R1ABC K"), None, str(page._path))
    assert page.text_view.toPlainText() == "CQ CQ DE R1ABC K"


def test_text_view_is_read_only_but_selectable(page):
    assert page.text_view.isReadOnly()
    page.on_result(result_with("CQ DE K"), None, str(page._path))
    page.text_view.selectAll()
    assert page.text_view.textCursor().selectedText() == "CQ DE K"


def test_text_view_clears_on_failure(page):
    page.on_result(result_with("CQ DE K"), None, str(page._path))
    page.on_failed("unsupported", "hỏng", str(page._path))
    assert page.text_view.toPlainText() == ""


def test_copy_uses_the_same_text(page):
    page.on_result(result_with("CQ CQ DE K"), None, str(page._path))
    page._copy()
    assert QApplication.clipboard().text() == "CQ CQ DE K"
