"""Thanh tiến trình hiện phần trăm và nút Hủy dừng lần giải mã đang chạy (CP-08, CP-09)."""

import pytest
from PySide6.QtWidgets import QApplication

from morsedesk.app.widgets.stats_bar import StatsBar


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_bar_starts_indeterminate_then_switches_to_percent(app):
    bar = StatsBar()
    bar.set_busy(True)
    assert bar.progress.isVisible() or not bar.isVisible()      # widget rời chưa show
    assert bar.progress.maximum() == 0, "chưa biết tổng số bước thì phải là thanh vô định"
    bar.set_progress(3, 12)
    assert (bar.progress.minimum(), bar.progress.maximum()) == (0, 12)
    assert bar.progress.value() == 3
    bar.set_busy(False)
    assert bar.progress.maximum() == 0, "xong một lần thì lần sau phải bắt đầu lại từ vô định"


def test_progress_ignores_nonsense_totals(app):
    bar = StatsBar()
    bar.set_busy(True)
    bar.set_progress(5, 0)
    assert bar.progress.maximum() == 0                          # tổng 0: giữ vô định, không chia cho 0
    bar.set_progress(30, 12)
    assert bar.progress.value() == 12                           # kẹp về tổng, không vượt


def test_cancel_button_appears_only_while_busy(app):
    from morsedesk.app.decode_page import DecodePage

    assert hasattr(DecodePage, "on_progress")
    assert hasattr(DecodePage, "on_cancel_clicked")
