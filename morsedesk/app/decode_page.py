"""Trang Giải mã: chọn/kéo thả file, chọn ngôn ngữ bản tin, kết quả từ + spectrogram + chỉ số, xuất."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from morsedesk.api import DecodeResult
from morsedesk.app.settings import AppSettings
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.spectrogram import SpectrogramView
from morsedesk.app.widgets.stats_bar import StatsBar
from morsedesk.app.widgets.word_view import WordView
from morsedesk.app.worker import DecodeRequest, DecoderWorker, Spectrogram
from morsedesk.audio.io import SUPPORTED_EXT

PROFILE_CHOICES = ("auto", "en", "ru", "kk-cyrl-ru")


class DecodePage(QWidget):
    """Tab Giải mã: mở/kéo thả file audio, giải mã qua `DecoderWorker`, hiện kết quả và cho xuất."""

    def __init__(self, worker: DecoderWorker, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.worker = worker
        self.settings = settings
        self.result: DecodeResult | None = None
        self._path: Path | None = None
        self._t0 = 0.0
        self.setAcceptDrops(True)

        self.open_button = QPushButton(self)
        self.path_label = QLabel(self)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.profile_label = QLabel(self)
        self.profile_combo = QComboBox(self)
        for pid in PROFILE_CHOICES:
            self.profile_combo.addItem(pid, pid)
        self.lm_check = QCheckBox(self)
        self.lm_check.setChecked(True)
        self.decode_button = QPushButton(self)
        self.decode_button.setEnabled(False)
        top = QHBoxLayout()
        for w, stretch in (
            (self.open_button, 0),
            (self.path_label, 1),
            (self.profile_label, 0),
            (self.profile_combo, 0),
            (self.lm_check, 0),
            (self.decode_button, 0),
        ):
            top.addWidget(w, stretch)

        self.banner = Banner(self)
        self.spectrogram = SpectrogramView(self)
        self.word_view = WordView(self)
        split = QSplitter(Qt.Orientation.Vertical, self)
        split.addWidget(self.spectrogram)
        split.addWidget(self.word_view)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        self.stats = StatsBar(self)
        self.fallback_label = QLabel(self)
        self.fallback_label.setWordWrap(True)
        self.fallback_label.hide()
        self.copy_button = QPushButton(self)
        self.export_txt_button = QPushButton(self)
        self.export_json_button = QPushButton(self)
        bottom = QHBoxLayout()
        bottom.addWidget(self.copy_button)
        bottom.addWidget(self.export_txt_button)
        bottom.addWidget(self.export_json_button)
        bottom.addStretch(1)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.banner)
        lay.addWidget(split, 1)
        lay.addWidget(self.stats)
        lay.addWidget(self.fallback_label)
        lay.addLayout(bottom)

        self.open_button.clicked.connect(self._choose_file)
        self.decode_button.clicked.connect(self._request)
        self.profile_combo.currentIndexChanged.connect(lambda _i: self._request())
        self.lm_check.toggled.connect(lambda _c: self._request())
        self.copy_button.clicked.connect(self._copy)
        self.export_txt_button.clicked.connect(lambda: self._export("txt"))
        self.export_json_button.clicked.connect(lambda: self._export("json"))
        self.word_view.word_clicked.connect(self.spectrogram.set_cursor)
        worker.result_ready.connect(self.on_result)
        worker.failed.connect(self.on_failed)
        worker.busy.connect(self.on_busy)
        self._set_has_result(False)
        self.retranslate()

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
        self._path = Path(path)
        self.settings.last_dir = str(self._path.parent)
        self.path_label.setText(str(self._path))
        self.decode_button.setEnabled(True)
        self._request()

    def current_request(self) -> DecodeRequest | None:
        """Yêu cầu giải mã ứng với trạng thái hiện tại của biểu mẫu; `None` nếu chưa có file."""
        if self._path is None:
            return None
        return DecodeRequest(self._path, str(self.profile_combo.currentData()), self.lm_check.isChecked())

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
        self.word_view.set_words(result.words)
        self.spectrogram.set_spectrogram(spec)
        self.spectrogram.set_tone(result.tone_hz)
        self.spectrogram.set_word_marks([w.start_s for w in result.words])
        self.spectrogram.set_cursor(None)
        self.stats.set_result(result, time.perf_counter() - self._t0)
        if result.warnings:
            self.banner.show_warning("; ".join(result.warnings))
        if result.fallback_text is not None:
            self.fallback_label.setText(
                self.tr("DSP fallback result: {text}").format(text=result.fallback_text)
            )
            self.fallback_label.show()
        else:
            self.fallback_label.hide()
        self._set_has_result(True)

    def on_failed(self, message: str) -> None:
        """Slot nhận `DecoderWorker.failed`: xóa kết quả cũ, hiện banner đỏ, giữ trang dùng được."""
        self.result = None
        self.word_view.clear()
        self.spectrogram.clear()
        self.stats.set_result(None, None)
        self.fallback_label.hide()
        self.banner.show_error(message)
        self._set_has_result(False)

    def on_busy(self, flag: bool) -> None:
        """Slot nhận `DecoderWorker.busy`: khóa các điều khiển và hiện tiến trình trong lúc giải mã."""
        self.stats.set_busy(flag)
        for w in (self.open_button, self.profile_combo, self.lm_check):
            w.setEnabled(not flag)
        self.decode_button.setEnabled(not flag and self._path is not None)
        self.setAcceptDrops(not flag)  # khóa cả kéo-thả trong lúc giải mã, cùng tinh thần với các nút trên

    def _set_has_result(self, flag: bool) -> None:
        for b in (self.copy_button, self.export_txt_button, self.export_json_button):
            b.setEnabled(flag)

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

    def export_txt(self, path: Path) -> None:
        """Ghi văn bản đã giải mã ra file UTF-8 (rỗng nếu chưa có kết quả)."""
        Path(path).write_text(self.result.text if self.result else "", encoding="utf-8")

    def export_json(self, path: Path) -> None:
        """Ghi `DecodeResult.to_json()` ra file UTF-8 (`{}` nếu chưa có kết quả)."""
        Path(path).write_text(self.result.to_json() if self.result else "{}", encoding="utf-8")

    # ---- i18n ----
    def retranslate(self) -> None:
        self.open_button.setText(self.tr("Open file…"))
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
        self.decode_button.setText(self.tr("Decode"))
        self.copy_button.setText(self.tr("Copy"))
        self.export_txt_button.setText(self.tr("Export TXT…"))
        self.export_json_button.setText(self.tr("Export JSON…"))
        if self._path is None:
            self.path_label.setText(self.tr("No file selected. Drop an audio file here."))
        if self.result is not None and self.result.fallback_text is not None:
            self.fallback_label.setText(
                self.tr("DSP fallback result: {text}").format(text=self.result.fallback_text)
            )

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
