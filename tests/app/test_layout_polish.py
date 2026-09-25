"""Những lỗi bố cục chỉ thấy bằng mắt trên ảnh chụp thật.

Ba cái đầu lộ ra từ ảnh chụp GUI chạy trên Ubuntu qua Xvfb:
- nhãn trên cùng của trục tần số (2000) bị cắt mất nửa vì `padding=0` ghim đúng mép;
- ô chuỗi chấm gạch cao 90 px trong khi ô nhập văn bản chiếm hơn 400 px, dù chuỗi Morse luôn
  dài gấp năm sáu lần văn bản;
- chuỗi chấm gạch vẽ bằng font tỉ lệ nên dấu chấm và gạch khó phân biệt ở cỡ chữ thường.
"""

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_time_labels_at_the_edges_are_not_cut(app):
    """Nhãn vạch thời gian sát mép khung (0 s, 12 s) căn vào trong — ảnh chụp 25/09 cho thấy "0 s"
    và "12 s" của phổ 2D bị cắt mất nửa khi căn giữa."""
    from PySide6.QtCore import Qt

    from morsedesk.app.widgets.signal_strip import EDGE_PX, edge_align, edge_label_rect

    assert edge_align(0.0, 0.0, 800.0) == Qt.AlignmentFlag.AlignLeft
    assert edge_align(800.0, 0.0, 800.0) == Qt.AlignmentFlag.AlignRight
    assert edge_align(400.0, 0.0, 800.0) == Qt.AlignmentFlag.AlignHCenter
    for x in (0.0, 10.0, 790.0, 800.0):
        r = edge_label_rect(x, 0.0, 14.0, 0.0, 800.0)
        assert r.left() >= 0.0 and r.right() <= 800.0 and r.width() == 2 * EDGE_PX


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


def test_decode_split_keeps_the_spectrogram_usable(qtbot, tmp_path):
    """Thêm ô văn bản không được bóp chết biểu đồ phổ.

    `setStretchFactor` của QSplitter chỉ chia phần dư khi co giãn, không quyết định kích thước
    ban đầu — ảnh chụp cho thấy spectrogram bị ép còn khoảng 60 px trong khi ô văn bản chiếm
    hơn 400. Phải đặt cả chiều cao tối thiểu lẫn kích thước ban đầu.
    """
    from PySide6.QtCore import QSettings

    from morsedesk.app.decode_page import DecodePage
    from morsedesk.app.settings import AppSettings
    from morsedesk.app.worker import DecoderWorker

    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = DecodePage(DecoderWorker(engine="baseline", model_path=None, lm_dir=None), settings)
    qtbot.addWidget(page)
    page.resize(1180, 760)

    assert page.spectrogram.minimumHeight() >= 180, page.spectrogram.minimumHeight()
    assert page.text_view.maximumHeight() <= 260, page.text_view.maximumHeight()
    sizes = page.split.sizes()
    # Khung kết quả là trọng tâm: không bao giờ nhỏ hơn vùng tín hiệu.
    assert len(sizes) == 2 and sizes[1] >= sizes[0], sizes
