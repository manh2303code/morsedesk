"""Trang Nghe trực tiếp: chữ hiện dần theo tín hiệu đang vào từ card âm thanh.

Hai tầng hiển thị, và đây là điểm quan trọng nhất của trang này chứ không phải trang trí: chữ
**đã chốt** in màu thường và sẽ không bao giờ đổi nữa; chữ **tạm** in xám và có thể bị viết lại
khi nghe thêm. Người vận hành chép tay theo phần màu thường thì không bao giờ phải tẩy — rủi ro
thật của một máy thu tự sửa chữ là người ta đã chép xuống giấy rồi mới thấy nó đổi.

Từ 25/09 bản chép dùng CHÍNH widget của trang Giải mã (WordView): từ đáng ngờ gạch chân vàng/đỏ,
rê chuột hiện độ tin cậy, vì sao có màu đó và tỉ lệ đúng đo được ở mức ấy (người dùng yêu cầu hai
trang đọc giống nhau). Chưa khóa được ngôn ngữ thì mọi chữ còn ở dạng tạm (model/stream.py).

Khối Tín hiệu (25/09, người dùng: "thiết kế tương tự như Decode — chọn 3D hay spectrogram, view chạy
theo con trỏ, lướt được về trước, bấm vào để nghe từ đó"): đúng khối `SignalPanel` của trang Giải
mã. Đang nghe thì khung bám "bây giờ" (12 s đầu đèn đi trái sang phải, sau đó đứng ở mép phải và
cảnh trôi sang trái); kéo/lăn để xem lại tới LIVE_KEEP_S giây trước. Bấm vào biểu đồ khi đang
nghe chỉ dời khung tới đó — phát ra loa lúc đang thu bằng micro thì micro thu lại chính tiếng đó
và giải mã trùng. Dừng nghe rồi thì phiên vừa thu nạp vào thanh phát: bấm chỗ nào nghe chỗ đó,
khung bám con trỏ phát y như trang Giải mã.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.audio_text import AudioText
from morsedesk.app.live_worker import LiveWorker, input_devices
from morsedesk.app.theme import NIGHT, mark_primary
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.icons import icon_button
from morsedesk.app.widgets.player_bar import PlayerBar
from morsedesk.app.widgets.signal_columns import LiveColumns
from morsedesk.app.widgets.signal_panel import SignalPanel
from morsedesk.app.widgets.stats_bar import Readout
from morsedesk.app.widgets.word_view import TENTATIVE_TEXT, WordView
from morsedesk.audio.engine import default_engine
from morsedesk.constants import SAMPLE_RATE
from morsedesk.warnings import WarningCode

# Cùng danh sách với trang Giải mã. `auto` đứng đầu và là mặc định: bắt người dùng chọn bảng mã
# trước khi nghe là bắt họ đoán thứ mà chính bản tin sẽ nói ra.
PROFILE_CHOICES = ("auto", "en", "ru", "kk-cyrl-ru")
log = logging.getLogger(__name__)
DEVICES_POLL_MS = 150       # chờ danh sách micro từ luồng thiết bị

# Xám đủ nhạt để thấy ngay là "chưa chắc", vẫn đủ đậm để đọc trên nền đêm (5,1:1).
TENTATIVE_COLOR = TENTATIVE_TEXT
LEVEL_SCALE = 3000      # RMS 0..~0,33 trải hết vạch: tín hiệu Morse điển hình rất nhỏ
# Lịch sử xem lại / nghe lại của phiên nghe: 10 phút = ~2,4 MB phổ + 9,6 MB âm thanh (int16).
LIVE_KEEP_S = 600.0


class LivePage(QWidget):
    """Chọn thiết bị, bật/tắt nghe, xem chữ chạy."""

    def __init__(self, worker: LiveWorker, parent=None) -> None:
        super().__init__(parent)
        self.worker = worker
        self._committed = ""
        self._tentative = ""
        self._clicks_warned = False     # banner "tiếng click phím" đang hiện
        self._listening = False
        self._rec_start = 0.0           # giây (kể từ lúc bấm Nghe) của mẫu đầu trong thanh phát
        self.columns = LiveColumns(LIVE_KEEP_S)
        self._pending_devices: tuple[Future, object] | None = None
        self._audio_text = AudioText(self)
        self._devices_timer = QTimer(self)
        self._devices_timer.setInterval(DEVICES_POLL_MS)
        self._devices_timer.timeout.connect(self._poll_devices)

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
        mark_primary(self.listen_button)
        self.level_label = QLabel(self)
        self.level_bar = QProgressBar(self)
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedWidth(110)
        for lb in (self.device_label, self.profile_label, self.level_label):
            lb.setProperty("role", "caption")

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self.device_label)
        top.addWidget(self.device_combo, 1)
        top.addWidget(self.refresh_button)
        top.addSpacing(8)
        top.addWidget(self.profile_label)
        top.addWidget(self.profile_combo)
        top.addSpacing(8)
        top.addWidget(self.level_label)
        top.addWidget(self.level_bar)
        top.addSpacing(6)
        top.addWidget(self.listen_button)

        self.banner = Banner(self)
        # Dải số đo trực tiếp, cùng kiểu với trang Giải mã.
        self.alphabet_cell = Readout(self, accent=True)
        self.tone_cell = Readout(self)
        self.speed_cell = Readout(self)
        self.snr_cell = Readout(self)
        self.heard_cell = Readout(self)
        self.readouts = QFrame(self)
        self.readouts.setProperty("panel", True)
        rl = QHBoxLayout(self.readouts)
        rl.setContentsMargins(6, 0, 12, 0)
        for i, cell in enumerate(self.live_cells()):
            if i:
                sep = QFrame(self)
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color: #2A3B60;")
                rl.addWidget(sep)
            rl.addWidget(cell, 1)
        rl.addStretch(1)
        # Khối Tín hiệu: đúng khối của trang Giải mã (3D hoặc phổ 2D, một khung thời gian).
        self.signal_panel = SignalPanel(live=True, parent=self)
        self.ridge = self.signal_panel.ridge
        self.spectrogram = self.signal_panel.strip
        self.ridge.setMinimumHeight(180)
        self.spectrogram.setMinimumHeight(180)
        # Bản chép: đúng widget trang Giải mã dùng (gạch chân theo độ tin cậy, tooltip), nên hai
        # trang đọc giống nhau và người dùng không phải học hai cách nhìn. Chữ tạm vẽ màu xám.
        self.word_view = WordView(self, live=True)
        self.word_view.set_background(NIGHT)
        self.word_view.setMinimumHeight(2 * self.word_view.line_height())
        # Chuỗi số đo một dòng: giữ cho sao chép/nhật ký, không hiện (dải ô ở trên thay nó).
        self.stats_label = QLabel(self)
        self.stats_label.hide()
        self.legend = QLabel(self)
        self.legend.setStyleSheet(f"color: {TENTATIVE_COLOR};")
        # Cùng bộ nút biểu tượng với trang Giải mã: một cách nhìn cho cả ứng dụng.
        self.copy_button = icon_button("copy", self)
        self.clear_button = icon_button("clear", self)
        # Nghe lại phiên vừa thu (chỉ khi đã dừng nghe): cùng thanh phát với trang Giải mã.
        self.player = PlayerBar(self)
        self.player.hide()
        bottom = QHBoxLayout()
        bottom.addWidget(self.legend, 1)
        bottom.addWidget(self.copy_button)
        bottom.addWidget(self.clear_button)

        self.split = QSplitter(Qt.Orientation.Vertical, self)
        self.split.addWidget(self.signal_panel)
        self.split.addWidget(self.word_view)
        self.split.setSizes([380, 240])
        self.split.setChildrenCollapsible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)
        lay.addLayout(top)
        lay.addWidget(self.banner)
        lay.addWidget(self.readouts)
        lay.addWidget(self.split, 1)
        lay.addWidget(self.stats_label)
        lay.addLayout(bottom)
        lay.addWidget(self.player)

        self.listen_button.clicked.connect(self._on_listen_clicked)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.copy_button.clicked.connect(self._copy)
        self.clear_button.clicked.connect(self.clear)
        self.signal_panel.seek_requested.connect(self._go_to)
        self.word_view.word_clicked.connect(self._go_to)
        self.player.position_changed.connect(self._on_playhead)
        self.player.error.connect(self.banner.show_warning)
        worker.text_ready.connect(self.on_text)
        worker.stats_ready.connect(self.on_stats)
        worker.block_ready.connect(self._on_block)
        worker.level.connect(self.on_level)
        worker.listening.connect(self.on_listening)
        worker.failed.connect(self.on_failed)

        self.refresh_devices()
        self.retranslate()

    # ---- thiết bị ----
    def _on_refresh(self) -> None:
        """Nút Làm mới: PortAudio chỉ liệt kê thiết bị lúc khởi tạo, nên phải khởi tạo lại mới thấy
        tai nghe vừa cắm (trước 27/09 nút này chỉ đọc lại danh sách cũ)."""
        default_engine().rescan()
        self.refresh_devices()

    def refresh_devices(self) -> None:
        """Nạp lại danh sách mic. Cần nút bấm vì người dùng hay cắm tai nghe SAU khi mở app.

        Liệt kê chạy ở luồng thiết bị; trang chờ bằng timer, không bao giờ chặn giao diện.
        """
        current = self.device_combo.currentData()
        result = input_devices()
        if isinstance(result, Future):
            self._pending_devices = (result, current)
            self.device_combo.setEnabled(False)
            self.listen_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self._devices_timer.start()
            self._poll_devices()            # bản inline (test) đã có kết quả ngay
            return
        self._fill_devices(list(result), current)

    def _poll_devices(self) -> None:
        pending = self._pending_devices
        if pending is None:
            self._devices_timer.stop()
            return
        fut, current = pending
        if not fut.done():
            return                          # driver kẹt: MainWindow đã hiện banner "không phản hồi"
        self._pending_devices = None
        self._devices_timer.stop()
        self.refresh_button.setEnabled(not self._listening)
        try:
            devices = list(fut.result())
        except Exception as e:
            log.warning("listing input devices failed: %s", e)
            devices = []
        self._fill_devices(devices, current)

    def _fill_devices(self, devices: list[tuple[int, str]], current) -> None:
        self.device_combo.clear()
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
        """Chuỗi cho nút sao chép; bản chép tự vẽ từ `on_stats` (có độ tin cậy từng từ)."""
        self._committed, self._tentative = committed, tentative

    def live_cells(self) -> list[Readout]:
        return [self.alphabet_cell, self.tone_cell, self.speed_cell, self.snr_cell, self.heard_cell]

    def _on_block(self, block) -> None:
        """Một khối audio (100 ms): thêm cột phổ; khối Tín hiệu vẽ lại nếu đang hiện."""
        if self.signal_panel.source() is None:          # khối đầu của phiên
            self.signal_panel.set_source(self.columns, fit=False)
        if self.columns.push(block):
            self.signal_panel.extend()

    def on_stats(self, update) -> None:
        """Thông số của lần giải mã gần nhất: từ (đã chốt + tạm), WPM, tone, SNR, ngôn ngữ."""
        committed = list(getattr(update, "committed_words", []) or [])
        tentative = list(getattr(update, "words", []) or [])
        self.word_view.set_words(committed + tentative, tentative_from=len(committed))
        self.signal_panel.set_words(committed + tentative)
        self._show_clicks_warning(WarningCode.KEY_CLICKS.value in (getattr(update, "warnings", []) or []))
        self.signal_panel.set_tone(getattr(update, "tone_hz", None))
        self.stats_label.setText(self._stats_text(update))
        wpm = getattr(update, "wpm", None)
        tone = getattr(update, "tone_hz", None)
        snr = getattr(update, "snr_db", None)
        hz, db, wpm_u, sec = self.tr("Hz"), self.tr("dB"), self.tr("WPM"), self.tr("s")
        self.tone_cell.value.setText(f"{tone:.0f} {hz}" if tone else "–")
        self.speed_cell.value.setText(f"{wpm:.1f} {wpm_u}" if wpm else "–")
        self.snr_cell.value.setText(f"{snr:.1f} {db}" if snr is not None else "–")
        lang = getattr(update, "language", "") or ""
        names = {"en": self.tr("English"), "ru": self.tr("Russian"), "kk-cyrl-ru": self.tr("Kazakh")}
        self.alphabet_cell.value.setText(names.get(lang, lang) or "–")
        heard = float(getattr(update, "audio_s", 0.0) or 0.0)
        self.heard_cell.value.setText(f"{heard:.0f} {sec}")

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
        self._listening = flag
        self.signal_panel.live_now = flag
        if flag:
            self.player.clear()
            self.player.hide()
        else:
            self.level_bar.setValue(0)
            self.signal_panel.set_cursor(None)
            self._load_recording()
        self.retranslate()

    def on_failed(self, message: str) -> None:
        self.banner.show_warning(self._audio_text.capture(message))
        self.listen_button.setChecked(False)

    # ---- xem lại / nghe lại ----
    def _load_recording(self) -> None:
        """Dừng nghe: nạp phần âm thanh còn giữ vào thanh phát để bấm chỗ nào nghe chỗ đó."""
        start, audio = self.columns.recording()
        if len(audio) < SAMPLE_RATE // 10:
            self.player.hide()
            return
        self._rec_start = start
        self.player.load(audio, SAMPLE_RATE)
        self.player.setEnabled(True)
        self.player.show()

    def _go_to(self, t_s: float) -> None:
        """Bấm một chỗ trên biểu đồ hay một từ. Đang nghe: chỉ dời khung tới đó (phát ra loa lúc đang
        thu thì micro thu lại). Đã dừng: nghe lại từ đó."""
        if self._listening or self.player.isHidden():
            self.signal_panel.timeline.center_on(t_s)
            return
        pos = max(0.0, t_s - self._rec_start)
        if pos >= self.player.playback.duration_s:
            self.signal_panel.timeline.center_on(t_s)
            return
        self.player.seek(pos)
        self.player.play()
        self.signal_panel.timeline.set_follow(True)

    def _on_playhead(self, pos: float) -> None:
        duration = self.player.playback.duration_s
        playing = self.player.playback.playing
        t = self._rec_start + pos
        active = playing or (duration > 0 and 0.01 < pos < duration - 0.05)
        self.word_view.set_playhead(t if active else None)
        self.signal_panel.play_position(t if active else None, playing)

    # ---- hành động ----
    def _on_listen_clicked(self) -> None:
        if self.listen_button.isChecked():
            self.banner.hide()
            self.player.clear()
            self.player.hide()
            self.columns.clear()
            self.signal_panel.set_source(self.columns, fit=False)
            self.word_view.clear()
            self.worker.start_listening(self.device_combo.currentData(),
                                        self.profile_combo.currentData())
        else:
            self.worker.stop_listening()

    def _show_clicks_warning(self, on: bool) -> None:
        """Tiếng click của phím (không có tone): nói thật thay vì để trống không lời giải thích."""
        if on and not self._clicks_warned:
            self.banner.show_warning(self._clicks_text())
        elif not on and self._clicks_warned:
            self.banner.hide()
        self._clicks_warned = on

    def _clicks_text(self) -> str:
        return self.tr("Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: "
                       "MorseDesk decodes Morse sent as a tone (radio CW); key clicks cannot be decoded yet.")

    def clear(self) -> None:
        """Xóa chữ và lịch sử tín hiệu. Giữa phiên nghe thì GIỮ mốc thời gian: bộ giải mã vẫn đếm
        tiếp, đặt lại mốc thì từ mới về sau lệch khỏi chỗ của nó trên biểu đồ."""
        self._committed = self._tentative = ""
        self._show_clicks_warning(False)
        self.word_view.clear()
        self.signal_panel.set_words([])
        self.columns.clear(keep_time=True)
        self.player.clear()
        self.player.hide()
        if self.signal_panel.source() is not None:
            self.signal_panel.extend()
        self.stats_label.clear()
        for c in self.live_cells():
            c.value.setText("–")

    def _copy(self) -> None:
        """Chép cả phần tạm: người vận hành cần nguyên văn những gì đang thấy."""
        text = " ".join(part.strip() for part in (self._committed, self._tentative) if part.strip())
        if text:
            QGuiApplication.clipboard().setText(text)

    def retranslate(self) -> None:
        listening = self.listen_button.isChecked()
        self.device_label.setText(self.tr("Input:"))
        self.profile_label.setText(self.tr("Alphabet:"))
        self.profile_combo.setToolTip(
            self.tr("Auto detects the alphabet from the message itself"))
        self.refresh_button.setText(self.tr("Refresh"))
        names = {"auto": self.tr("Auto"), "en": self.tr("English"), "ru": self.tr("Russian"),
                 "kk-cyrl-ru": self.tr("Kazakh")}
        for i in range(self.profile_combo.count()):
            self.profile_combo.setItemText(i, names[self.profile_combo.itemData(i)])
        self.refresh_button.setToolTip(self.tr("Look for newly plugged devices"))
        self.listen_button.setText(self.tr("Stop") if listening else self.tr("Listen"))
        self.level_bar.setToolTip(self.tr("Input level"))
        self.level_label.setText(self.tr("Level"))
        self.alphabet_cell.caption.setText(self.tr("Alphabet"))
        self.tone_cell.caption.setText(self.tr("Tone"))
        self.speed_cell.caption.setText(self.tr("Speed"))
        self.snr_cell.caption.setText(self.tr("SNR"))
        self.heard_cell.caption.setText(self.tr("Heard"))
        self.signal_panel.title.setText(self.tr("Signal"))
        self.ridge.placeholder = self.tr("Press Listen to see the band live in 3D.")
        self.spectrogram.placeholder = self.tr("Press Listen to see the band live.")
        self.signal_panel.retranslate()
        self.legend.setText(self.tr("Grey words may still change. Underlined words are uncertain; "
                                    "point at any word for details."))
        if self._clicks_warned:
            self.banner.show_warning(self._clicks_text())
        self.copy_button.setToolTip(self.tr("Copy the decoded text"))
        self.copy_button.setAccessibleName(self.tr("Copy"))
        self.clear_button.setToolTip(self.tr("Clear the text and start over"))
        self.clear_button.setAccessibleName(self.tr("Clear"))
        self.player.retranslate()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
