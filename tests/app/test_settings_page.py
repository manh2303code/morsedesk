"""Trang Cài đặt: cho biết máy này làm được gì, thay vì để người dùng bấm rồi mới nhận lỗi.

CP-06 yêu cầu khả năng xuất MP3 hiện ở đây. Cùng chỗ đó cũng là nơi hợp lý để nêu engine đang
dùng, thư mục log và các định dạng ghi được — những thứ mà trên máy air-gap không tra cứu được
ở đâu khác.
"""

import pytest
from PySide6.QtWidgets import QApplication

from morsedesk.app.settings_page import SettingsPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_shows_mp3_capability(app, monkeypatch):
    monkeypatch.setattr("morsedesk.app.settings_page.mp3_capability", lambda: "libsndfile")
    page = SettingsPage(engine="onnx")
    text = page.report_text()
    assert "MP3" in text and "libsndfile" in text


def test_names_the_missing_encoder_when_mp3_unavailable(app, monkeypatch):
    monkeypatch.setattr("morsedesk.app.settings_page.mp3_capability", lambda: None)
    page = SettingsPage(engine="onnx")
    text = page.report_text()
    assert "MP3" in text and "ffmpeg" in text.lower()


def test_reports_engine_log_dir_and_formats(app):
    page = SettingsPage(engine="deepcw")
    text = page.report_text()
    assert "deepcw" in text
    assert "logs" in text
    assert ".flac" in text and ".oga" in text


def test_retranslate_keeps_the_report_fresh(app):
    page = SettingsPage(engine="onnx")
    before = page.report_text()
    page.retranslate()
    assert page.report_text() == before
