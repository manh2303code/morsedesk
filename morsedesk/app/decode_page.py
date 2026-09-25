"""Trang Giải mã: chọn/kéo thả file, chọn ngôn ngữ bản tin, kết quả + phổ 3D + số đo, xuất.

Bố cục theo thứ tự người dùng cần: file và nút Giải mã ở trên; dải số đo (ngôn ngữ, tone, tốc độ,
SNR — những thứ ứng dụng TỰ đo ra); vùng tín hiệu (phong cảnh 3D hoặc phổ 2D); bản giải mã chữ
lớn tô theo độ tin cậy; thanh phát và nút xuất ở đáy. Trong lúc giải mã, lớp phủ với vòng tiến
trình che vùng kết quả cũ; kết quả mới chỉ hiện khi mô hình ngôn ngữ đã xong.

Lần đầu mở ứng dụng, trang nạp sẵn một file mẫu "Xin chào" đúng ngôn ngữ giao diện
(`enable_samples`), nên người dùng thấy ngay một bản tin thật được giải mã.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from morsedesk.api import DecodeResult
from morsedesk.app.settings import AppSettings
from morsedesk.app.theme import mark_primary
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.busy_overlay import BusyOverlay
from morsedesk.app.widgets.icons import icon_button, line_icon
from morsedesk.app.widgets.player_bar import PlayerBar, format_time
from morsedesk.app.widgets.signal_columns import FileColumns
from morsedesk.app.widgets.signal_panel import SignalPanel
from morsedesk.app.widgets.stats_bar import StatsBar
from morsedesk.app.widgets.word_view import WordView
from morsedesk.app.worker import MAX_SECONDS, DecodeRequest, DecoderWorker, Spectrogram
from morsedesk.audio.io import SUPPORTED_EXT, load_audio
from morsedesk.warnings import WARNING_TEXTS, DecodeWarning, WarningCode

PROFILE_CHOICES = ("auto", "en", "ru", "kk-cyrl-ru")
MAX_MINUTES = int(MAX_SECONDS // 60)
SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLE_FILES = {"en": "hello_en.wav", "ru": "hello_ru.wav", "kk": "hello_kk.wav"}


def audio_duration_s(path: Path) -> float | None:
    """Thời lượng file mà không đọc cả file; None nếu libsndfile không đọc được đầu file."""
    try:
        import soundfile as sf

        return float(sf.info(str(path)).duration)
    except Exception:
        return None


def format_duration(seconds: float | None) -> str:
    """Cùng cách làm tròn với đồng hồ thanh phát, để đầu trang và thanh phát ghi cùng một số."""
    return "" if seconds is None else format_time(seconds)


FALLBACK_MAX_H = 58


class DecodePage(QWidget):
    """Tab Giải mã: mở/kéo thả file audio, giải mã qua `DecoderWorker`, hiện kết quả và cho xuất."""

    def __init__(self, worker: DecoderWorker, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.worker = worker
        self.settings = settings
        self.result: DecodeResult | None = None
        self._path: Path | None = None
        self._audio_loaded = False
        self._samples: tuple | None = None      # (x, sr) cho cảnh 3D, nạp một lần mỗi kết quả
        self._t0 = 0.0
        self._busy = False
        self._samples_enabled = False
        self._showing_sample = False
        self.setAcceptDrops(True)

        # ---- đầu trang: file + ngôn ngữ bản tin + nút Giải mã ----
        # Nút biểu tượng (thư mục mở) + tooltip + Ctrl+O. Chữ "Open file…" dài gấp ba ở tiếng Nga
        # và Kazakh; biểu tượng đọc được ở mọi ngôn ngữ giao diện.
        self.open_button = icon_button("open", self, px=22, size=40)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Open), self, activated=self._choose_file)
        self.path_label = QLabel(self)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self.file_meta = QLabel(self)
        self.file_meta.setProperty("role", "caption")
        self.sample_badge = QLabel(self)
        self.sample_badge.setStyleSheet(
            "color: #1A1206; background: #F5A524; border-radius: 4px; padding: 1px 6px;"
            " font-size: 8pt; font-weight: 700;")
        self.sample_badge.hide()
        self.profile_label = QLabel(self)
        self.profile_label.setProperty("role", "caption")
        self.profile_combo = QComboBox(self)
        # Tên ngôn ngữ dịch ra dài hơn tiếng Anh ('Английский' cần 65px so với
        # 'English' 40px): để mặc định combo giữ nguyên bề rộng và cắt mất chữ.
        self.profile_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for pid in PROFILE_CHOICES:
            self.profile_combo.addItem(pid, pid)
        self.lm_check = QCheckBox(self)
        self.lm_check.setChecked(True)
        self.decode_button = QPushButton(self)
        self.decode_button.setEnabled(False)
        mark_primary(self.decode_button)
        # Nút Hủy nằm trong lớp phủ tiến trình, ngay dưới vòng tròn (CP-09): đúng chỗ mắt đang nhìn.
        self.cancel_button = QPushButton(self)
        self.cancel_button.hide()
        file_col = QVBoxLayout()
        file_col.setSpacing(0)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(self.path_label)
        name_row.addWidget(self.sample_badge)
        name_row.addStretch(1)
        file_col.addLayout(name_row)
        file_col.addWidget(self.file_meta)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self.open_button)
        top.addSpacing(6)
        top.addLayout(file_col, 1)
        top.addWidget(self.profile_label)
        top.addWidget(self.profile_combo)
        top.addWidget(self.lm_check)
        top.addSpacing(6)
        top.addWidget(self.decode_button)

        self.banner = Banner(self)
        self.stats = StatsBar(self, show_progress=False)

        # ---- vùng tín hiệu: phong cảnh 3D hoặc phổ 2D (widgets/signal_panel.py, chung với trang
        # Nghe). Khung 12 s bám con trỏ phát với đèn ở giữa; kéo/lăn để lướt; bấm để nghe từ đó.
        self.signal_panel = SignalPanel(live=False, parent=self)
        self.signal_box = self.signal_panel
        self.ridge = self.signal_panel.ridge
        self.spectrogram = self.signal_panel.strip
        self.signal_stack = self.signal_panel.stack
        self.signal_title = self.signal_panel.title
        self.view_3d_button = self.signal_panel.view_3d_button
        self.view_2d_button = self.signal_panel.view_2d_button

        # ---- bản giải mã: khung "lời bài hát" là trọng tâm của trang ----
        self.word_view = WordView(self)
        self.result_title = QLabel(self)
        self.result_title.setProperty("role", "section")
        # Nút ẩn/hiện nằm ở tiêu đề CHÍNH khung văn bản thuần (người dùng 24/09: đặt ở khung kết
        # quả phía trên là sai chỗ). Ẩn thì khung thu lại còn dải tiêu đề, nút vẫn ở đó để mở lại.
        self.details_button = QToolButton(self)
        self.details_button.setProperty("flat", True)
        self.details_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_button.setCheckable(True)
        # Người vận hành còn cần đọc cả bản tin liền mạch và bôi chọn một đoạn để sao chép.
        self.text_view = QPlainTextEdit(self)
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText("")
        self.text_view.setStyleSheet(
            "QPlainTextEdit { font-size: 12pt; border: none; background: transparent; }")
        # `setStretchFactor` chỉ chia phần DƯ khi cửa sổ co giãn, không quyết định kích thước
        # ban đầu: nếu chỉ dựa vào nó, ô văn bản chiếm hơn 400 px còn biểu đồ phổ bị ép còn
        # khoảng 60 px (thấy rõ trên ảnh chụp). Phải đặt cả mức tối thiểu lẫn `setSizes`.
        self.spectrogram.setMinimumHeight(180)
        self.ridge.setMinimumHeight(180)
        self.word_view.setMinimumHeight(120)
        self.text_view.setMinimumHeight(56)
        self.text_view.setMaximumHeight(92)
        self.result_box = QFrame(self)
        self.result_box.setProperty("panel", True)
        rb = QVBoxLayout(self.result_box)
        rb.setContentsMargins(12, 8, 6, 6)
        rb.setSpacing(2)
        self._result_head = QHBoxLayout()
        self._result_head.setSpacing(8)
        self._result_head.addWidget(self.result_title)
        self._result_head.addStretch(1)
        rb.addLayout(self._result_head)
        rb.addWidget(self.word_view, 1)
        self.split = QSplitter(Qt.Orientation.Vertical, self)
        split = self.split
        split.addWidget(self.signal_box)
        split.addWidget(self.result_box)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        split.setSizes([215, 420])
        split.setChildrenCollapsible(False)
        self.content = QWidget(self)
        cl = QVBoxLayout(self.content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(split)
        self.overlay = BusyOverlay(self.content)
        self.overlay.add_widget(self.cancel_button)

        self.fallback_label = QLabel(self)
        self.fallback_label.setWordWrap(True)
        self.fallback_label.setProperty("role", "hint")
        self.fallback_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.fallback_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Kết quả thay thế của bản tin 13 phút dài cả trang: cho nó khung cuộn riêng, thấp.
        self.fallback_scroll = QScrollArea(self)
        self.fallback_scroll.setWidget(self.fallback_label)
        self.fallback_scroll.setWidgetResizable(True)
        self.fallback_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.fallback_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.fallback_scroll.hide()
        self.details = QFrame(self)
        self.details.setProperty("panel", True)
        self.details_title = QLabel(self)
        self.details_title.setProperty("role", "section")
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self.details_title)
        head.addStretch(1)
        head.addWidget(self.details_button)
        self.details_body = QWidget(self)
        self.details_body.setObjectName("detailsBody")
        self.details_body.setStyleSheet("#detailsBody { background: transparent; }")
        bl = QVBoxLayout(self.details_body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)
        bl.addWidget(self.text_view)
        bl.addWidget(self.fallback_scroll)
        dl = QVBoxLayout(self.details)
        dl.setContentsMargins(12, 6, 6, 6)
        dl.setSpacing(2)
        dl.addLayout(head)
        dl.addWidget(self.details_body)
        self.details_button.setChecked(settings.show_text_details)
        self.details_button.toggled.connect(self._on_details_toggled)

        # ---- đáy: nghe lại + xuất ----
        # Nghe lại chính file vừa giải mã: khi máy đọc sai một chỗ, cách duy nhất để biết lỗi
        # nằm ở tín hiệu hay ở mô hình là nghe đúng đoạn đó — mà máy air-gap có khi không có
        # ứng dụng phát nhạc nào khác.
        self.player = PlayerBar(self)
        self.player.setEnabled(False)
        # Tốc độ và âm lượng nghe lại: nhớ giữa các lần mở (chỉ tác động tiếng phát, không đụng giải mã).
        self.player.set_speed(settings.playback_speed)
        self.player.set_volume(settings.playback_volume)
        self.player.speed_changed.connect(lambda r: setattr(self.settings, "playback_speed", r))
        self.player.volume_changed.connect(lambda v: setattr(self.settings, "playback_volume", v))
        # Sao chép và xuất nằm ở đầu khung kết quả — chúng thao tác trên VĂN BẢN, không phải trên
        # âm thanh; chỗ cũ cạnh thanh phát nay dành cho tốc độ phát và âm lượng.
        self.copy_button = icon_button("copy", self, px=18, size=34)
        # MỘT nút xuất, bấm vào ra hai lựa chọn — thay cho hai nút chữ dài "Export TXT…/JSON…".
        self.export_button = icon_button("export", self, px=18, size=34)
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.export_menu = QMenu(self.export_button)
        self.export_txt_action = self.export_menu.addAction("")
        self.export_json_action = self.export_menu.addAction("")
        self.export_button.setMenu(self.export_menu)
        self._result_head.addWidget(self.copy_button)
        self._result_head.addWidget(self.export_button)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.addWidget(self.player, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)
        lay.addLayout(top)
        lay.addWidget(self.banner)
        lay.addWidget(self.stats)
        lay.addWidget(self.content, 1)
        lay.addWidget(self.details)
        lay.addLayout(bottom)

        self.open_button.clicked.connect(self._choose_file)
        self.decode_button.clicked.connect(self._request)
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.lm_check.toggled.connect(lambda _c: self._request())
        self.copy_button.clicked.connect(self._copy)
        self.export_txt_action.triggered.connect(lambda: self._export("txt"))
        self.export_json_action.triggered.connect(lambda: self._export("json"))
        self.word_view.word_clicked.connect(self._play_from)
        self.signal_panel.seek_requested.connect(self._play_from)
        self.player.position_changed.connect(self._on_playhead)
        self.player.error.connect(self.banner.show_warning)
        self.player.ensure_loaded = self._ensure_audio
        worker.result_ready.connect(self.on_result)
        worker.failed.connect(self.on_failed)
        worker.busy.connect(self.on_busy)
        worker.progress.connect(self.on_progress)
        worker.cancelled.connect(self.on_cancelled)
        self._sync_lm_check()
        self._set_has_result(False)
        self._on_details_toggled(self.details_button.isChecked(), save=False)
        self.retranslate()

    def _on_details_toggled(self, shown: bool, save: bool = True) -> None:
        """Ẩn/hiện thân khung văn bản thuần (tiêu đề và nút ở lại); nhớ lựa chọn cho lần sau."""
        self.details_body.setVisible(shown)
        self.details_button.setIcon(line_icon("chevron-up" if shown else "chevron-down", 16))
        self._retranslate_details_button()
        if save:
            self.settings.show_text_details = shown

    def _retranslate_details_button(self) -> None:
        shown = self.details_button.isChecked()
        self.details_button.setText(self.tr("Hide") if shown else self.tr("Show"))
        self.details_button.setToolTip(self.tr("Plain text to select and copy, and the alternative result"))

    def _show_fallback(self, text: str | None) -> None:
        """Kết quả thay thế (đường giải mã còn lại) trong phần chi tiết; None = ẩn."""
        if text is None:
            self.fallback_label.hide()
            self.fallback_scroll.hide()
            return
        self.fallback_label.setText(text)
        self.fallback_label.show()
        self.fallback_scroll.show()
        self._fit_fallback()

    def _fit_fallback(self) -> None:
        """Khung kết quả thay thế cao vừa đủ chữ, tối đa ~4 dòng (dài hơn thì cuộn)."""
        width = max(100, self.fallback_scroll.viewport().width() or self.width() - 40)
        need = self.fallback_label.heightForWidth(width)
        self.fallback_scroll.setFixedHeight(max(18, min(FALLBACK_MAX_H, need + 2)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.fallback_scroll.isVisibleTo(self):
            self._fit_fallback()

    # ---- file mẫu "Xin chào" ----
    def enable_samples(self) -> None:
        """Bật nạp file mẫu theo ngôn ngữ giao diện (chỉ ứng dụng thật gọi; test dựng trang trần)."""
        self._samples_enabled = True

    def showing_sample(self) -> bool:
        return self._showing_sample

    def load_sample(self, ui_language: str) -> bool:
        """Nạp và giải mã file mẫu của `ui_language`, nếu người dùng chưa mở file nào của họ."""
        if not self._samples_enabled or (self._path is not None and not self._showing_sample):
            return False
        path = SAMPLES_DIR / SAMPLE_FILES.get(ui_language, SAMPLE_FILES["en"])
        if not path.is_file() or (self._showing_sample and self._path == path):
            return False
        self._set_file(path, sample=True)
        self._request()
        return True

    def _set_file(self, path: Path, sample: bool) -> None:
        self._path = Path(path)
        self._showing_sample = sample
        self.sample_badge.setVisible(sample)
        self.path_label.setText(self._path.name)
        self.file_meta.setText(format_duration(audio_duration_s(self._path)))
        self.decode_button.setEnabled(not self._busy)

    # ---- chọn file ----
    def _choose_file(self) -> None:
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXT)
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open audio file"),
            self.settings.last_dir,
            self.tr("Audio files ({exts})").format(exts=exts),
        )
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> None:
        """Đặt file hiện hành, nhớ thư mục vào cài đặt và gửi yêu cầu giải mã."""
        self._set_file(Path(path), sample=False)
        self.settings.last_dir = str(self._path.parent)
        self._request()

    def current_request(self) -> DecodeRequest | None:
        """Yêu cầu giải mã ứng với trạng thái hiện tại của biểu mẫu; `None` nếu chưa có file."""
        if self._path is None:
            return None
        return DecodeRequest(self._path, str(self.profile_combo.currentData()), self.lm_check.isChecked())

    def _on_profile_changed(self, _index: int) -> None:
        self._sync_lm_check()
        self._request()

    def _sync_lm_check(self) -> None:
        """Profile `auto` bắt buộc dùng mô hình ngôn ngữ (lõi ném ValueError nếu không).

        Khóa ô đánh dấu và ép bật, để tổ hợp `auto` + tắt LM không bao giờ tới được lõi.
        """
        auto = str(self.profile_combo.currentData()) == "auto"
        self.lm_check.setEnabled(not auto and not self._busy)
        if auto and not self.lm_check.isChecked():
            self.lm_check.setChecked(True)      # toggled -> _request; hàng đợi độ dài 1 nên vô hại

    def _request(self) -> None:
        req = self.current_request()
        if req is None:
            return
        self.banner.clear()
        self._t0 = time.perf_counter()
        self.worker.request(req)

    # ---- kéo thả ----
    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in SUPPORTED_EXT:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.load_file(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    # ---- kết quả ----
    def on_result(self, result: DecodeResult, spec: Spectrogram, path: str) -> None:
        """Slot nhận `DecoderWorker.result_ready`: cập nhật mọi widget hiển thị kết quả."""
        if self._path is None or path != str(self._path):
            # Kết quả trễ của file đã bị thay (vd. do một load_file khác chen vào trước khi
            # worker kịp trả lời) -> bỏ qua, tránh vẽ đè kết quả sai lên file đang mở.
            return
        self.result = result
        self._audio_loaded = False          # nạp lười: chỉ đọc lại file khi người dùng bấm Nghe
        self._samples = None
        self._load_signal()
        self.player.clear()
        self.player.setEnabled(True)
        # có file để nạp -> bật nút ngay, audio nạp khi bấm; đồng hồ hiện luôn thời lượng file
        self.player.arm(audio_duration_s(self._path) if self._path is not None else None)
        self.word_view.set_words(result.words)
        self.text_view.setPlainText(result.text)
        self.stats.set_result(result, time.perf_counter() - self._t0)
        if result.warning_codes:
            self.banner.show_warning("; ".join(self._warning_text(w) for w in result.warning_codes))
        elif result.warnings:                       # kết quả cũ chưa có mã: hiện nguyên văn
            self.banner.show_warning("; ".join(result.warnings))
        if result.fallback_text is not None:
            self._show_fallback(
                self._fallback_caption(getattr(result, "decoded_by", "model"), result.fallback_text))
        else:
            self._show_fallback(None)
        self._set_has_result(True)

    # ---- nghe lại ----
    def _ensure_audio(self) -> None:
        """Nạp file vào thanh phát, chỉ một lần cho mỗi kết quả.

        Đọc đồng bộ ngay trong luồng giao diện: đo trên bản ghi ARRL dài 37,2 phút là 0,26 giây,
        dưới ngưỡng người dùng thấy giật, nên không đáng dựng thêm một luồng nữa cho việc này.
        """
        if self._audio_loaded or self._path is None:
            return
        self._audio_loaded = True           # đặt trước: file hỏng thì cũng đừng thử lại mỗi lần bấm
        samples = self._load_samples()
        if samples is None:
            self.player.setEnabled(False)
            return
        self.player.load(*samples)

    def _load_samples(self) -> tuple | None:
        """Âm thanh của file hiện hành, đọc MỘT lần cho cả cảnh 3D lẫn thanh phát."""
        if self._samples is None and self._path is not None:
            try:
                self._samples = load_audio(self._path)
            except Exception as e:
                self.banner.show_warning(self.tr("Cannot load audio for playback: {detail}")
                                         .format(detail=e))
                return None
        return self._samples

    # ---- tín hiệu ----
    def _load_signal(self) -> None:
        """Nguồn cho khối Tín hiệu: phổ theo cột tính lười từ chính âm thanh của file."""
        r = self.result
        samples = self._load_samples() if r is not None else None
        if samples is None:
            self.signal_panel.set_source(None)
            return
        self.signal_panel.set_source(FileColumns(samples[0], samples[1]), fit=True)
        self.signal_panel.set_tone(r.tone_hz)
        self.signal_panel.set_words(r.words)

    def _play_from(self, t_s: float) -> None:
        """Bấm vào một từ hay một chỗ trên biểu đồ: nghe từ đúng chỗ đó, khung bám theo lại."""
        self._ensure_audio()
        self.player.seek(t_s)
        self.player.play()
        self.signal_panel.timeline.set_follow(True)

    def _on_playhead(self, t_s: float) -> None:
        # Karaoke chỉ khi đang nghe (hoặc tạm dừng giữa chừng): lúc audio vừa nạp con trỏ ở 0 và
        # khi nghe hết thì cả bản tin trở lại sáng đều, không để phần "chưa tới" mờ mãi.
        duration = self.player.playback.duration_s
        listening = self.player.playback.playing or (duration > 0 and 0.01 < t_s < duration - 0.05)
        self.word_view.set_playhead(t_s if listening else None)
        # Khung tín hiệu bám con trỏ, đèn ở giữa (trừ nửa khung đầu/cuối file); tạm dừng thì giữ
        # nguyên chỗ; về đầu hoặc nghe hết thì hiện đủ cả cảnh, không còn phần chìm.
        self.signal_panel.play_position(t_s if listening else None, self.player.playback.playing)

    def _fallback_caption(self, decoded_by: str, text: str) -> str:
        """Nhãn cho dòng dự phòng, nói đúng nguồn của nó.

        Khi văn bản chính đến từ bộ DSP (tín hiệu sạch hơn dải huấn luyện) thì dòng dự phòng
        chính là kết quả của mô hình, chứ không còn luôn là kết quả DSP như trước.
        """
        if decoded_by == "dsp":
            return self.tr("Model result: {text}").format(text=text)
        return self.tr("DSP fallback result: {text}").format(text=text)

    def _warning_sources(self) -> dict[str, str]:
        """Chuỗi hiển thị cho từng mã cảnh báo của lõi, đã dịch sang ngôn ngữ giao diện.

        Viết bằng literal truyền thẳng cho `self.tr`, không tra `WARNING_TEXTS` qua biến, vì
        `pyside6-lupdate` chỉ trích được literal: tra qua biến thì chuỗi không bao giờ vào file
        `.ts` và Qt lặng lẽ trả lại nguyên văn tiếng Anh. `tests/unit/test_warning_codes.py`
        canh cho bảng này phủ đúng `WarningCode` và khớp từng ký tự với `WARNING_TEXTS`.
        """
        return {
            WarningCode.NO_SIGNAL.value: self.tr("No Morse signal found in this audio."),
            WarningCode.GUESSED_TONE.value: self.tr(
                "Tone not detected clearly; guessing from the spectral peak, so the result may be wrong."
            ),
            WarningCode.SECOND_TONE.value: self.tr(
                "A second tone was found at {second_hz:.0f} Hz; tracking {tracked_hz:.0f} Hz."
            ),
            WarningCode.LOW_CONFIDENCE.value: self.tr("Low confidence."),
            WarningCode.LOW_CONFIDENCE_WITH_DSP.value: self.tr(
                "Low confidence; the DSP decoder result is shown too."
            ),
            WarningCode.KEY_CLICKS.value: self.tr(
                "Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: "
                "MorseDesk decodes Morse sent as a tone (radio CW); key clicks cannot be decoded yet."
            ),
        }

    def _warning_text(self, w: DecodeWarning) -> str:
        """Một cảnh báo của lõi, đã dịch và đã thay tham số (CP-10)."""
        text = self._warning_sources().get(w.code)
        if text is None:                            # mã lạ (bản lõi mới hơn giao diện): hiện thô
            return WARNING_TEXTS.get(w.code, w.code)
        try:
            return text.format(**w.params)
        except (KeyError, IndexError, ValueError):  # bản dịch sai chỗ giữ chỗ
            return WARNING_TEXTS[w.code].format(**w.params)

    def failure_message(self, code: str, detail: str) -> str:
        """Thông điệp hiển thị cho một mã lỗi của worker, dựng hoàn toàn bằng `self.tr()`."""
        name = self._path.name if self._path else ""
        if code == "not_found":
            return self.tr("File not found: {path}").format(path=name)
        if code == "unsupported":
            return self.tr("Cannot read {path}. Supported formats: {exts}").format(
                path=name, exts=" ".join(SUPPORTED_EXT)
            )
        if code == "too_long":
            return self.tr("{path} is {minutes} min long; this version supports up to {limit} min.").format(path=name, minutes=detail, limit=MAX_MINUTES)
        if code == "config":
            return self.tr("Setup problem: a model or language model file is missing or unusable.")
        return self.tr("Internal error while decoding. See the log file for details.")

    def on_failed(self, code: str, detail: str, path: str) -> None:
        """Slot nhận `DecoderWorker.failed`: xóa kết quả cũ, hiện banner đỏ, giữ trang dùng được.

        `detail` (chuỗi gốc của lõi, không dịch) thành tooltip của banner. Lỗi của file không
        còn mở bị bỏ qua, y hệt `on_result`.
        """
        if self._path is None or path != str(self._path):
            return
        self.result = None
        self.word_view.clear()
        self.text_view.clear()
        self.signal_panel.set_source(None)
        self.stats.set_result(None, None)
        self._show_fallback(None)
        self.banner.show_error(self.failure_message(code, detail))
        self.banner.setToolTip(detail)
        self._set_has_result(False)

    def on_busy(self, flag: bool) -> None:
        """Slot nhận `DecoderWorker.busy`: khóa các điều khiển và hiện tiến trình trong lúc giải mã."""
        self._busy = flag
        self.stats.set_busy(flag)
        # Lớp phủ + vòng tiến trình che kết quả cũ: kết quả mới chỉ hiện khi LM đã xong. Số đo
        # và kết quả thay thế cũ mờ đi cùng lúc, để không ai đọc nhầm chúng là của file mới.
        if flag:
            self.overlay.start()
        else:
            self.overlay.stop()
        self._dim(self.stats, flag)
        self._dim(self.fallback_label, flag)
        self.cancel_button.setVisible(flag)
        self.cancel_button.setEnabled(flag)
        for w in (self.open_button, self.profile_combo):
            w.setEnabled(not flag)
        self._sync_lm_check()
        self.decode_button.setEnabled(not flag and self._path is not None)
        self._set_has_result(self.result is not None)
        self.setAcceptDrops(not flag)  # khóa cả kéo-thả trong lúc giải mã, cùng tinh thần với các nút trên

    @staticmethod
    def _dim(widget: QWidget, flag: bool) -> None:
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        if flag:
            eff = QGraphicsOpacityEffect(widget)
            eff.setOpacity(0.25)
            widget.setGraphicsEffect(eff)
        else:
            widget.setGraphicsEffect(None)

    def on_progress(self, done: int, total: int) -> None:
        """Slot nhận `DecoderWorker.progress`: đổi thanh vô định thành phần trăm (CP-08)."""
        self.stats.set_progress(done, total)
        self.overlay.set_progress(done, total)

    def on_cancel_clicked(self) -> None:
        """Xin worker dừng; nút tự mờ đi để không bấm hai lần, `busy(False)` sẽ ẩn hẳn."""
        self.cancel_button.setEnabled(False)
        self.worker.cancel()

    def on_cancelled(self, path: str) -> None:
        """Slot nhận `DecoderWorker.cancelled`: báo ngắn gọn, giữ nguyên kết quả cũ trên màn hình."""
        self.banner.show_warning(self.tr("Decoding cancelled."))

    def _set_has_result(self, flag: bool) -> None:
        """Nhóm nút cần kết quả; luôn tắt lúc bận để không sao chép/xuất kết quả của file trước."""
        for b in (self.copy_button, self.export_button, self.export_txt_action, self.export_json_action):
            b.setEnabled(flag and not self._busy)

    # ---- xuất ----
    def _copy(self) -> None:
        if self.result is not None:
            QGuiApplication.clipboard().setText(self.result.text)

    def _export(self, kind: str) -> None:
        if self.result is None:
            return
        stem = self._path.stem if self._path else "morsedesk"
        suggested = str(Path(self.settings.last_dir) / f"{stem}.{kind}")
        flt = self.tr("Text files (*.txt)") if kind == "txt" else self.tr("JSON files (*.json)")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export"), suggested, flt)
        if not path:
            return
        (self.export_txt if kind == "txt" else self.export_json)(Path(path))

    def _write_text(self, path: Path, text: str) -> bool:
        """Ghi UTF-8; lỗi hệ thống tệp (thư mục chỉ đọc, hết chỗ) -> banner đỏ, trả `False`.

        Trước đây `write_text` không được bắt nên xuất thất bại chỉ để lại traceback ở stderr.
        """
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as e:
            self.banner.show_error(
                self.tr("Cannot write {path}: {detail}").format(path=Path(path).name, detail=e.strerror or str(e))
            )
            self.banner.setToolTip(str(e))
            return False
        return True

    def export_txt(self, path: Path) -> bool:
        """Ghi văn bản đã giải mã ra file UTF-8 (rỗng nếu chưa có kết quả)."""
        return self._write_text(Path(path), self.result.text if self.result else "")

    def export_json(self, path: Path) -> bool:
        """Ghi `DecodeResult.to_json()` ra file UTF-8 (rỗng thành `{}` nếu chưa có kết quả)."""
        return self._write_text(Path(path), self.result.to_json() if self.result else "{}")

    # ---- i18n ----
    def retranslate(self) -> None:
        self.open_button.setToolTip(self.tr("Open audio file… (Ctrl+O)"))
        self.open_button.setAccessibleName(self.tr("Open audio file"))
        self.profile_label.setText(self.tr("Message language:"))
        names = {
            "auto": self.tr("Auto"),
            "en": self.tr("English"),
            "ru": self.tr("Russian"),
            "kk-cyrl-ru": self.tr("Kazakh"),
        }
        for i in range(self.profile_combo.count()):
            self.profile_combo.setItemText(i, names[self.profile_combo.itemData(i)])
        self.lm_check.setText(self.tr("Use language model"))
        self.lm_check.setToolTip(self.tr("Auto always uses the language model."))
        self._sync_lm_check()
        self.decode_button.setText(self.tr("Decode"))
        self.cancel_button.setText(self.tr("Cancel"))
        self.copy_button.setToolTip(self.tr("Copy the decoded text"))
        self.copy_button.setAccessibleName(self.tr("Copy"))
        self.export_button.setToolTip(self.tr("Export to a file: text or JSON with timings"))
        self.export_button.setAccessibleName(self.tr("Export"))
        self.export_txt_action.setText(self.tr("Text file (.txt)…"))
        self.export_json_action.setText(self.tr("JSON with word timings (.json)…"))
        self.result_title.setText(self.tr("Decoded text"))
        self.details_title.setText(self.tr("Plain text"))
        self._retranslate_details_button()
        if self._path is None:
            self.path_label.setText(self.tr("No file selected. Drop an audio file here."))
        self.sample_badge.setText(self.tr("Sample"))
        self.signal_title.setText(self.tr("Signal"))
        self.ridge.placeholder = self.tr("Open or drop an audio file to see its signal in 3D.")
        self.spectrogram.placeholder = self.tr("Open or drop an audio file to see its spectrogram.")
        self.overlay.retranslate()
        if self.result is not None and self.result.fallback_text is not None:
            self._show_fallback(self._fallback_caption(getattr(self.result, "decoded_by", "model"),
                                                       self.result.fallback_text))
        # Thanh phát là widget con có chữ riêng; thiếu dòng này nút "Play" giữ tiếng Anh sau khi đổi
        # ngôn ngữ (ảnh chụp AppImage tiếng Kazakh 23/09 lộ ra).
        self.player.retranslate()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
