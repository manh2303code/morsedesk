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
    QPlainTextEdit,
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
from morsedesk.app.worker import MAX_SECONDS, DecodeRequest, DecoderWorker, Spectrogram
from morsedesk.audio.io import SUPPORTED_EXT
from morsedesk.warnings import WARNING_TEXTS, DecodeWarning, WarningCode

PROFILE_CHOICES = ("auto", "en", "ru", "kk-cyrl-ru")
MAX_MINUTES = int(MAX_SECONDS // 60)


class DecodePage(QWidget):
    """Tab Giải mã: mở/kéo thả file audio, giải mã qua `DecoderWorker`, hiện kết quả và cho xuất."""

    def __init__(self, worker: DecoderWorker, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.worker = worker
        self.settings = settings
        self.result: DecodeResult | None = None
        self._path: Path | None = None
        self._t0 = 0.0
        self._busy = False
        self.setAcceptDrops(True)

        self.open_button = QPushButton(self)
        self.path_label = QLabel(self)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.profile_label = QLabel(self)
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
        # Nút Hủy chỉ hiện trong lúc giải mã (CP-09); để cạnh nút Giải mã nên không làm nhảy bố cục.
        self.cancel_button = QPushButton(self)
        self.cancel_button.hide()
        top = QHBoxLayout()
        for w, stretch in (
            (self.open_button, 0),
            (self.path_label, 1),
            (self.profile_label, 0),
            (self.profile_combo, 0),
            (self.lm_check, 0),
            (self.decode_button, 0),
            (self.cancel_button, 0),
        ):
            top.addWidget(w, stretch)

        self.banner = Banner(self)
        self.spectrogram = SpectrogramView(self)
        self.word_view = WordView(self)
        # Chip từng từ tiện để soi độ tin cậy, nhưng người vận hành còn cần đọc cả bản tin liền
        # mạch và bôi chọn một đoạn để sao chép — và vùng dưới chip vốn bỏ trống với bản tin ngắn.
        self.text_view = QPlainTextEdit(self)
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText("")
        # `setStretchFactor` chỉ chia phần DƯ khi cửa sổ co giãn, không quyết định kích thước
        # ban đầu: nếu chỉ dựa vào nó, ô văn bản chiếm hơn 400 px còn biểu đồ phổ bị ép còn
        # khoảng 60 px (thấy rõ trên ảnh chụp). Phải đặt cả mức tối thiểu lẫn `setSizes`.
        self.spectrogram.setMinimumHeight(220)
        self.word_view.setMinimumHeight(56)
        self.text_view.setMinimumHeight(70)
        self.text_view.setMaximumHeight(200)
        self.split = QSplitter(Qt.Orientation.Vertical, self)
        split = self.split
        split.addWidget(self.spectrogram)
        split.addWidget(self.word_view)
        split.addWidget(self.text_view)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 2)
        split.setSizes([340, 90, 140])
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
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.lm_check.toggled.connect(lambda _c: self._request())
        self.copy_button.clicked.connect(self._copy)
        self.export_txt_button.clicked.connect(lambda: self._export("txt"))
        self.export_json_button.clicked.connect(lambda: self._export("json"))
        self.word_view.word_clicked.connect(self.spectrogram.set_cursor)
        worker.result_ready.connect(self.on_result)
        worker.failed.connect(self.on_failed)
        worker.busy.connect(self.on_busy)
        worker.progress.connect(self.on_progress)
        worker.cancelled.connect(self.on_cancelled)
        self._sync_lm_check()
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
        self.word_view.set_words(result.words)
        self.text_view.setPlainText(result.text)
        self.spectrogram.set_spectrogram(spec)
        self.spectrogram.set_tone(result.tone_hz)
        self.spectrogram.set_word_marks([w.start_s for w in result.words])
        self.spectrogram.set_cursor(None)
        self.stats.set_result(result, time.perf_counter() - self._t0)
        if result.warning_codes:
            self.banner.show_warning("; ".join(self._warning_text(w) for w in result.warning_codes))
        elif result.warnings:                       # kết quả cũ chưa có mã: hiện nguyên văn
            self.banner.show_warning("; ".join(result.warnings))
        if result.fallback_text is not None:
            self.fallback_label.setText(
                self._fallback_caption(getattr(result, "decoded_by", "model"), result.fallback_text)
            )
            self.fallback_label.show()
        else:
            self.fallback_label.hide()
        self._set_has_result(True)

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
        self.spectrogram.clear()
        self.stats.set_result(None, None)
        self.fallback_label.hide()
        self.banner.show_error(self.failure_message(code, detail))
        self.banner.setToolTip(detail)
        self._set_has_result(False)

    def on_busy(self, flag: bool) -> None:
        """Slot nhận `DecoderWorker.busy`: khóa các điều khiển và hiện tiến trình trong lúc giải mã."""
        self._busy = flag
        self.stats.set_busy(flag)
        self.cancel_button.setVisible(flag)
        self.cancel_button.setEnabled(flag)
        for w in (self.open_button, self.profile_combo):
            w.setEnabled(not flag)
        self._sync_lm_check()
        self.decode_button.setEnabled(not flag and self._path is not None)
        self._set_has_result(self.result is not None)
        self.setAcceptDrops(not flag)  # khóa cả kéo-thả trong lúc giải mã, cùng tinh thần với các nút trên

    def on_progress(self, done: int, total: int) -> None:
        """Slot nhận `DecoderWorker.progress`: đổi thanh vô định thành phần trăm (CP-08)."""
        self.stats.set_progress(done, total)

    def on_cancel_clicked(self) -> None:
        """Xin worker dừng; nút tự mờ đi để không bấm hai lần, `busy(False)` sẽ ẩn hẳn."""
        self.cancel_button.setEnabled(False)
        self.worker.cancel()

    def on_cancelled(self, path: str) -> None:
        """Slot nhận `DecoderWorker.cancelled`: báo ngắn gọn, giữ nguyên kết quả cũ trên màn hình."""
        self.banner.show_warning(self.tr("Decoding cancelled."))

    def _set_has_result(self, flag: bool) -> None:
        """Nhóm nút cần kết quả; luôn tắt lúc bận để không sao chép/xuất kết quả của file trước."""
        for b in (self.copy_button, self.export_txt_button, self.export_json_button):
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
        self.lm_check.setToolTip(self.tr("Auto always uses the language model."))
        self._sync_lm_check()
        self.decode_button.setText(self.tr("Decode"))
        self.cancel_button.setText(self.tr("Cancel"))
        self.copy_button.setText(self.tr("Copy"))
        self.export_txt_button.setText(self.tr("Export TXT…"))
        self.export_json_button.setText(self.tr("Export JSON…"))
        if self._path is None:
            self.path_label.setText(self.tr("No file selected. Drop an audio file here."))
        if self.result is not None and self.result.fallback_text is not None:
            self.fallback_label.setText(
                self._fallback_caption(getattr(self.result, "decoded_by", "model"),
                                       self.result.fallback_text)
            )

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
