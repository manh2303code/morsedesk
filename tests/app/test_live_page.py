"""Trang Nghe trực tiếp: hai tầng chữ, danh sách thiết bị, và ứng xử khi máy không có mic.

Worker được thay bằng bản giả: test này kiểm GIAO DIỆN phản ứng đúng với tín hiệu, không kiểm
PortAudio (máy CI và máy Linux tối giản đều có thể không có thiết bị thu nào).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from morsedesk.app import live_page as live_page_mod
from morsedesk.app.live_page import TENTATIVE_COLOR, LivePage


class FakeLiveWorker(QObject):
    text_ready = Signal(str, str)
    stats_ready = Signal(object)
    block_ready = Signal(object)
    level = Signal(float)
    listening = Signal(bool)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.started_with: list = []
        self.stopped = 0

    def start_listening(self, device=None, profile=None) -> None:
        self.started_with.append((device, profile))

    def stop_listening(self) -> None:
        self.stopped += 1


def _page(qtbot, monkeypatch, devices=((1, "Mic giả"), (2, "Card thu"))):
    monkeypatch.setattr(live_page_mod, "input_devices", lambda: list(devices))
    worker = FakeLiveWorker()
    page = LivePage(worker)
    qtbot.addWidget(page)
    return page, worker


def test_lists_devices_and_starts_with_selected_one(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    assert [page.device_combo.itemText(i) for i in range(page.device_combo.count())] == \
        ["Mic giả", "Card thu"]
    page.device_combo.setCurrentIndex(1)
    page.listen_button.setChecked(True)
    page._on_listen_clicked()
    # gửi CHỈ SỐ thiết bị (không phải tên) kèm bảng mã đang chọn
    assert worker.started_with == [(2, "auto")]


def test_stop_asks_worker_to_stop(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    page.listen_button.setChecked(False)
    page._on_listen_clicked()
    assert worker.stopped == 1


def test_two_tier_text_marks_tentative_grey(qtbot, monkeypatch):
    """Chữ đã chốt in thường, chữ tạm in xám — đây là điểm cốt lõi của trang."""
    page, worker = _page(qtbot, monkeypatch)
    worker.text_ready.emit("CQ CQ DE", " R1AB")
    html = page.view.toHtml()
    assert "CQ CQ DE" in page.view.toPlainText()
    assert "R1AB" in page.view.toPlainText()
    assert TENTATIVE_COLOR.lstrip("#").lower() in html.lower()   # phần tạm có màu riêng


def test_committed_text_has_no_colour_when_nothing_tentative(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    worker.text_ready.emit("CQ DE K", "")
    assert page.view.toPlainText().strip() == "CQ DE K"
    assert TENTATIVE_COLOR.lstrip("#").lower() not in page.view.toHtml().lower()


def test_html_special_characters_are_escaped(qtbot, monkeypatch):
    """Bản tin Morse có `<` `>` (prosign viết dạng <AR>): không được để nó thành thẻ HTML."""
    page, worker = _page(qtbot, monkeypatch)
    worker.text_ready.emit("<AR> & <SK>", "")
    assert page.view.toPlainText().strip() == "<AR> & <SK>"


def test_level_bar_follows_rms(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    worker.level.emit(0.0)
    assert page.level_bar.value() == 0
    worker.level.emit(1.0)
    assert page.level_bar.value() == 100          # kẹp ở trần, không tràn
    worker.level.emit(0.01)
    assert 0 < page.level_bar.value() < 100


def test_listening_state_locks_device_choice(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    worker.listening.emit(True)
    assert page.listen_button.isChecked() and not page.device_combo.isEnabled()
    worker.listening.emit(False)
    assert not page.listen_button.isChecked() and page.device_combo.isEnabled()
    assert page.level_bar.value() == 0


def test_no_device_disables_listen_and_warns(qtbot, monkeypatch):
    page, _ = _page(qtbot, monkeypatch, devices=())
    assert not page.listen_button.isEnabled() and not page.device_combo.isEnabled()
    assert page.banner.isVisible() or page.banner.text()


def test_failure_message_reaches_banner(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    worker.failed.emit("cannot open input device 3")
    assert "cannot open input device 3" in page.banner.text()
    assert not page.listen_button.isChecked()


def test_clear_empties_both_tiers(qtbot, monkeypatch):
    page, worker = _page(qtbot, monkeypatch)
    worker.text_ready.emit("CQ", " DE")
    page.clear()
    assert page.view.toPlainText().strip() == ""


def test_alphabet_defaults_to_auto_and_is_passed_through(qtbot, monkeypatch):
    """Ghim cứng `en` là lý do bản tin tiếng Nga từng ra chữ tiếng Anh — phải mặc định `auto`."""
    page, worker = _page(qtbot, monkeypatch)
    assert page.profile_combo.currentData() == "auto"
    page.profile_combo.setCurrentIndex(page.profile_combo.findData("ru"))
    page.listen_button.setChecked(True)
    page._on_listen_clicked()
    assert worker.started_with[-1][1] == "ru"


def test_stats_populate_words_tone_and_labels(qtbot, monkeypatch):
    from morsedesk.api import Word
    from morsedesk.model.stream import StreamUpdate

    page, worker = _page(qtbot, monkeypatch)
    up = StreamUpdate("CQ DE", " R1A", True, 12.0,
                      [Word("R1A", 3.0, 3.8, 0.55)], 21.5, 712.0, 9.5, "ru")
    worker.stats_ready.emit(up)
    assert page.word_view.texts() == ["R1A"]
    assert page.waterfall._tone_hz == 712.0
    txt = page.stats_label.text()
    assert "21.5" in txt and "712" in txt and "9.5" in txt and "ru" in txt


def test_waterfall_receives_audio_blocks(qtbot, monkeypatch):
    import numpy as np

    page, worker = _page(qtbot, monkeypatch)
    before = float(page.waterfall._data.max())
    worker.block_ready.emit(np.sin(2 * np.pi * 700 * np.arange(8000) / 8000).astype(np.float32))
    assert float(page.waterfall._data.max()) > before
