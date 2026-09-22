"""Những lỗi bố cục chỉ thấy bằng mắt trên ảnh chụp thật.

Ba cái đầu lộ ra từ ảnh chụp GUI chạy trên Ubuntu qua Xvfb:
- nhãn trên cùng của trục tần số (2000) bị cắt mất nửa vì `padding=0` ghim đúng mép;
- ô chuỗi chấm gạch cao 90 px trong khi ô nhập văn bản chiếm hơn 400 px, dù chuỗi Morse luôn
  dài gấp năm sáu lần văn bản;
- chuỗi chấm gạch vẽ bằng font tỉ lệ nên dấu chấm và gạch khó phân biệt ở cỡ chữ thường.
"""

import pytest
from PySide6.QtWidgets import QApplication

from morsedesk.app.widgets.spectrogram import MAX_FREQ_HZ, SpectrogramView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_frequency_axis_leaves_room_for_the_top_label(app):
    """Trục phải cao hơn tần số lớn nhất một chút, nếu không nhãn trên cùng bị cắt."""
    view = SpectrogramView()
    lo, hi = view.getViewBox().viewRange()[1]
    assert lo <= 0.0
    assert hi > MAX_FREQ_HZ, (lo, hi)
    assert hi <= MAX_FREQ_HZ * 1.15, "chừa quá nhiều thì biểu đồ tụt xuống"


def test_morse_view_is_monospaced_and_readable(qtbot, tmp_path):
    from PySide6.QtCore import QSettings

    from morsedesk.app.encode_page import EncodePage
    from morsedesk.app.settings import AppSettings
    from morsedesk.app.worker import Player

    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = EncodePage(Player(), settings)
    qtbot.addWidget(page)

    font = page.morse_view.font()
    assert font.styleHint() == font.StyleHint.Monospace or font.fixedPitch(), font.family()
    assert font.pointSize() >= 11 or font.pixelSize() >= 14, font.pointSize()

    # Ô Morse phải cao ít nhất bằng một phần ba ô nhập, vì nội dung của nó luôn dài hơn.
    page.text_edit.setPlainText("CQ CQ DE R1ABC R1ABC K")
    assert page.morse_view.maximumHeight() >= 150, page.morse_view.maximumHeight()
