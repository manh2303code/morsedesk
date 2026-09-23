"""Trang Nghe trực tiếp: chữ hiện dần theo tín hiệu đang vào từ card âm thanh.

Hai tầng hiển thị, và đây là điểm quan trọng nhất của trang này chứ không phải trang trí: chữ
**đã chốt** in màu thường và sẽ không bao giờ đổi nữa; chữ **tạm** in xám và có thể bị viết lại
khi nghe thêm. Người vận hành chép tay theo phần màu thường thì không bao giờ phải tẩy — rủi ro
thật của một máy thu tự sửa chữ là người ta đã chép xuống giấy rồi mới thấy nó đổi.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.live_worker import LiveWorker, input_devices
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.waterfall import WaterfallView
from morsedesk.app.widgets.word_view import WordView

# Cùng danh sách với trang Giải mã. `auto` đứng đầu và là mặc định: bắt người dùng chọn bảng mã
# trước khi nghe là bắt họ đoán thứ mà chính bản tin sẽ nói ra.
PROFILE_CHOICES = ("auto", "en", "ru", "kk-cyrl-ru")

# Xám đủ nhạt để thấy ngay là "chưa chắc", vẫn đủ đậm để đọc trên cả nền sáng lẫn nền tối.
TENTATIVE_COLOR = "#8a8a8a"
LEVEL_SCALE = 3000      # RMS 0..~0,33 trải hết vạch: tín hiệu Morse điển hình rất nhỏ


class LivePage(QWidget):
    """Chọn thiết bị, bật/tắt nghe, xem chữ chạy."""

    def __init__(self, worker: LiveWorker, parent=None) -> None:
        super().__init__(parent)
        self.worker = worker
        self._committed = ""
        self._tentative = ""

        self.device_label = QLabel(self)
        self.device_combo = QComboBox(self)
        self.profile_label = QLabel(self)
        self.profile_combo = QComboBox(self)
        self.profile_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for pid in PROFILE_CHOICES:
            self.profile_combo.addItem(pid, pid)
        self.refresh_button = QPushButton(self)
        self.listen_button = QPushButton(self)
        self.listen_button.setCheckable(True)
        self.level_bar = QProgressBar(self)
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setMaximumWidth(120)

        top = QHBoxLayout()
        top.addWidget(self.device_label)
        top.addWidget(self.device_combo, 1)
        top.addWidget(self.profile_label)
        top.addWidget(self.profile_combo)
        top.addWidget(self.refresh_button)
        top.addWidget(self.level_bar)
        top.addWidget(self.listen_button)

        self.banner = Banner(self)
        self.waterfall = WaterfallView(parent=self)
        # Chip từng từ, nền theo độ tin cậy — đúng widget trang Giải mã dùng, nên hai trang đọc
        # giống nhau và người dùng không phải học hai cách nhìn.
        self.word_view = WordView(self)
        self.word_view.setMinimumHeight(56)
        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        self.view.setStyleSheet("QTextEdit { font-size: 16pt; }")
        self.stats_label = QLabel(self)
        self.stats_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.legend = QLabel(self)
        self.legend.setStyleSheet(f"color: {TENTATIVE_COLOR};")
        self.copy_button = QPushButton(self)
        self.clear_button = QPushButton(self)
        bottom = QHBoxLayout()
        bottom.addWidget(self.legend, 1)
        bottom.addWidget(self.copy_button)
        bottom.addWidget(self.clear_button)

        self.split = QSplitter(Qt.Orientation.Vertical, self)
        self.split.addWidget(self.waterfall)
        self.split.addWidget(self.word_view)
        self.split.addWidget(self.view)
        self.split.setSizes([260, 90, 200])

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.banner)
        lay.addWidget(self.split, 1)
        lay.addWidget(self.stats_label)
        lay.addLayout(bottom)

        self.listen_button.clicked.connect(self._on_listen_clicked)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.copy_button.clicked.connect(self._copy)
        self.clear_button.clicked.connect(self.clear)
        worker.text_ready.connect(self.on_text)
        worker.stats_ready.connect(self.on_stats)
        worker.block_ready.connect(self.waterfall.push)
        worker.level.connect(self.on_level)
        worker.listening.connect(self.on_listening)
        worker.failed.connect(self.on_failed)

        self.refresh_devices()
        self.retranslate()

    # ---- thiết bị ----
    def refresh_devices(self) -> None:
        """Nạp lại danh sách mic. Cần nút bấm vì người dùng hay cắm tai nghe SAU khi mở app."""
        current = self.device_combo.currentData()
        self.device_combo.clear()
        devices = input_devices()
        for index, name in devices:
            self.device_combo.addItem(name, index)
        if current is not None:
            i = self.device_combo.findData(current)
            if i >= 0:
                self.device_combo.setCurrentIndex(i)
        has = bool(devices)
        self.device_combo.setEnabled(has)
        self.listen_button.setEnabled(has)
        if not has:
            self.banner.show_warning(self.tr("No input device found. Plug in a sound card or "
                                             "check that PortAudio is installed."))

    # ---- slot của worker ----
    def on_text(self, committed: str, tentative: str) -> None:
        self._committed, self._tentative = committed, tentative
        self._render()

    def on_stats(self, update) -> None:
        """Thông số của lần giải mã gần nhất: chip từ, WPM, tone, SNR, ngôn ngữ nhận ra."""
        self.word_view.set_words(list(getattr(update, "words", []) or []))
        self.waterfall.set_tone(getattr(update, "tone_hz", None))
        self.stats_label.setText(self._stats_text(update))

    def _stats_text(self, u) -> str:
        parts = []
        wpm, tone, snr = getattr(u, "wpm", None), getattr(u, "tone_hz", None), getattr(u, "snr_db", None)
        if wpm:
            parts.append(self.tr("WPM {v:.1f}").format(v=wpm))
        if tone:
            parts.append(self.tr("Tone {v:.0f} Hz").format(v=tone))
        if snr is not None:
            parts.append(self.tr("SNR {v:.1f} dB").format(v=snr))
        lang = getattr(u, "language", "")
        if lang:
            parts.append(self.tr("Alphabet: {v}").format(v=lang))
        parts.append(self.tr("{v:.0f} s heard").format(v=getattr(u, "audio_s", 0.0)))
        return " · ".join(parts)

    def on_level(self, rms: float) -> None:
        self.level_bar.setValue(max(0, min(100, int(rms * LEVEL_SCALE))))

    def on_listening(self, flag: bool) -> None:
        self.listen_button.setChecked(flag)
        self.device_combo.setEnabled(not flag)
        self.refresh_button.setEnabled(not flag)
        if not flag:
            self.level_bar.setValue(0)
        self.retranslate()

    def on_failed(self, message: str) -> None:
        self.banner.show_warning(self.tr("Listening failed: {detail}").format(detail=message))
        self.listen_button.setChecked(False)

    # ---- hành động ----
    def _on_listen_clicked(self) -> None:
        if self.listen_button.isChecked():
            self.banner.hide()
            self.waterfall.clear()
            self.word_view.clear()
            self.worker.start_listening(self.device_combo.currentData(),
                                        self.profile_combo.currentData())
        else:
            self.worker.stop_listening()

    def clear(self) -> None:
        self._committed = self._tentative = ""
        self.word_view.clear()
        self.waterfall.clear()
        self.stats_label.clear()
        self._render()

    def _copy(self) -> None:
        """Chép cả phần tạm: người vận hành cần nguyên văn những gì đang thấy."""
        text = (self._committed + " " + self._tentative).strip()
        if text:
            QGuiApplication.clipboard().setText(text)

    def _render(self) -> None:
        import html

        parts = []
        if self._committed:
            parts.append(html.escape(self._committed))
        if self._tentative.strip():
            parts.append(f'<span style="color:{TENTATIVE_COLOR}">'
                         f"{html.escape(self._tentative.strip())}</span>")
        self.view.setHtml(" ".join(parts))
        # Luôn dán mắt vào cuối: chữ mới nằm ở đó, và phiên trực dài thì người dùng không muốn
        # phải tự kéo thanh cuộn mỗi vài giây.
        cur = self.view.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self.view.setTextCursor(cur)

    # ---- i18n ----
    def retranslate(self) -> None:
        listening = self.listen_button.isChecked()
        self.device_label.setText(self.tr("Input:"))
        self.profile_label.setText(self.tr("Alphabet:"))
        self.profile_combo.setToolTip(
            self.tr("Auto detects the alphabet from the message itself"))
        self.refresh_button.setText(self.tr("Refresh"))
        self.refresh_button.setToolTip(self.tr("Look for newly plugged devices"))
        self.listen_button.setText(self.tr("Stop") if listening else self.tr("Listen"))
        self.level_bar.setToolTip(self.tr("Input level"))
        self.view.setPlaceholderText(self.tr("Decoded text appears here as it is heard."))
        self.legend.setText(self.tr("Grey text may still change; plain text is final."))
        self.copy_button.setText(self.tr("Copy"))
        self.clear_button.setText(self.tr("Clear"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
