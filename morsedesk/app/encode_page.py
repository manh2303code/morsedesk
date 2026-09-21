"""Trang Tạo mã: văn bản -> chuỗi chấm gạch, tham số timing/tone/nhiễu, nghe thử, lưu file."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from morsedesk.api import Encoder
from morsedesk.app.settings import AppSettings
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.charmap import CharMap
from morsedesk.app.worker import Player
from morsedesk.audio.io import save_audio
from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.text import normalize
from morsedesk.lm.profile import Profile, load_profile

FORMATS = (("WAV", ".wav"), ("FLAC", ".flac"), ("OGG", ".ogg"))
PROFILES = ("en", "ru", "kk-cyrl-ru")


def unsupported_chars(text: str, profile: Profile) -> list[str]:
    """Ký tự (sau `normalize`) không phải khoảng trắng/`<`/`>` và không có trong `profile`.

    Trả về duy nhất mỗi ký tự, theo thứ tự xuất hiện lần đầu trong văn bản.
    """
    seen: list[str] = []
    for ch in normalize(text, profile):
        if ch in " <>" or ch in profile.letter_to_pattern or ch in seen:
            continue
        seen.append(ch)
    return seen


class EncodePage(QWidget):
    """Tab Tạo mã: gõ văn bản, xem chuỗi chấm gạch trực tiếp, chỉnh tham số, nghe thử và lưu file."""

    def __init__(self, player: Player, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.player = player
        self.settings = settings
        self._profiles = {pid: load_profile(pid) for pid in PROFILES}

        self.text_label = QLabel(self)
        self.text_edit = QPlainTextEdit(self)
        self.charmap = CharMap(self)
        self.morse_label = QLabel(self)
        self.morse_view = QPlainTextEdit(self)
        self.morse_view.setReadOnly(True)
        self.morse_view.setMaximumHeight(90)
        self.warn_label = QLabel(self)
        self.warn_label.setStyleSheet("color:#4a3b00; background:#fff2b3; padding:3px;")
        self.warn_label.hide()
        left = QVBoxLayout()
        left.addWidget(self.text_label)
        left.addWidget(self.text_edit, 1)
        left.addWidget(self.charmap)
        left.addWidget(self.morse_label)
        left.addWidget(self.morse_view)
        left.addWidget(self.warn_label)

        self.profile_combo = QComboBox(self)
        for pid in PROFILES:
            self.profile_combo.addItem(pid, pid)
        self.wpm_spin = QSpinBox(self)
        self.wpm_spin.setRange(5, 60)
        self.wpm_spin.setValue(20)
        self.farnsworth_check = QCheckBox(self)
        self.farnsworth_spin = QSpinBox(self)
        self.farnsworth_spin.setRange(5, 60)
        self.farnsworth_spin.setValue(10)
        self.farnsworth_spin.setEnabled(False)
        self.weight_spin = QDoubleSpinBox(self)
        self.weight_spin.setRange(2.0, 4.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(3.0)
        self.tone_spin = QSpinBox(self)
        self.tone_spin.setRange(300, 1500)
        self.tone_spin.setValue(700)
        self.snr_check = QCheckBox(self)
        self.snr_spin = QSpinBox(self)
        self.snr_spin.setRange(-10, 30)
        self.snr_spin.setValue(10)
        self.snr_spin.setEnabled(False)
        self.format_combo = QComboBox(self)
        for name, ext in FORMATS:
            self.format_combo.addItem(name, ext)
        self.form = QFormLayout()
        self.form_labels = [QLabel(self) for _ in range(7)]
        rows = (
            self.profile_combo,
            self.wpm_spin,
            self._pair(self.farnsworth_check, self.farnsworth_spin),
            self.weight_spin,
            self.tone_spin,
            self._pair(self.snr_check, self.snr_spin),
            self.format_combo,
        )
        for label, w in zip(self.form_labels, rows, strict=True):
            self.form.addRow(label, w)
        self.play_button = QPushButton(self)
        self.stop_button = QPushButton(self)
        self.save_button = QPushButton(self)
        buttons = QHBoxLayout()
        buttons.addWidget(self.play_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.save_button)
        right = QVBoxLayout()
        right.addLayout(self.form)
        right.addLayout(buttons)
        right.addStretch(1)

        self.banner = Banner(self)
        body = QHBoxLayout()
        body.addLayout(left, 3)
        body.addLayout(right, 2)
        lay = QVBoxLayout(self)
        lay.addWidget(self.banner)
        lay.addLayout(body, 1)

        self.text_edit.textChanged.connect(self.refresh_morse)
        self.profile_combo.currentIndexChanged.connect(self._on_profile)
        self.charmap.char_clicked.connect(self._insert_char)
        self.farnsworth_check.toggled.connect(self.farnsworth_spin.setEnabled)
        self.snr_check.toggled.connect(self.snr_spin.setEnabled)
        self.play_button.clicked.connect(self.play)
        self.stop_button.clicked.connect(self.stop)
        self.save_button.clicked.connect(self._save_dialog)
        self._on_profile()
        self.retranslate()

    @staticmethod
    def _pair(check: QCheckBox, spin: QSpinBox) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(check)
        lay.addWidget(spin, 1)
        return w

    # ---- trạng thái ----
    def current_profile_id(self) -> str:
        return str(self.profile_combo.currentData())

    def current_text(self) -> str:
        return self.text_edit.toPlainText()

    def _encoder(self) -> Encoder:
        return Encoder(self._profiles[self.current_profile_id()])

    def _on_profile(self) -> None:
        self.charmap.set_profile(self.current_profile_id())
        self.refresh_morse()

    def _insert_char(self, ch: str) -> None:
        self.text_edit.insertPlainText(ch)
        self.text_edit.setFocus()

    def refresh_morse(self) -> None:
        """Cập nhật chuỗi chấm gạch và cảnh báo ký tự không hỗ trợ mỗi khi văn bản đổi."""
        profile = self._profiles[self.current_profile_id()]
        text = self.current_text()
        morse = self._encoder().to_morse_string(text, strict=False) if text.strip() else ""
        self.morse_view.setPlainText(morse)
        bad = unsupported_chars(text, profile)
        if bad:
            self.warn_label.setText(
                self.tr("Unsupported characters skipped: {chars}").format(chars=", ".join(bad))
            )
            self.warn_label.show()
        else:
            self.warn_label.hide()
        has = bool(morse)
        self.play_button.setEnabled(has)
        self.save_button.setEnabled(has)

    # ---- âm thanh ----
    def build_audio(self) -> np.ndarray:
        return self._encoder().to_audio(
            self.current_text(),
            wpm=float(self.wpm_spin.value()),
            farnsworth_wpm=(
                float(self.farnsworth_spin.value()) if self.farnsworth_check.isChecked() else None
            ),
            weight=float(self.weight_spin.value()),
            tone_hz=float(self.tone_spin.value()),
            sample_rate=SAMPLE_RATE,
            snr_db=float(self.snr_spin.value()) if self.snr_check.isChecked() else None,
            seed=0,
            strict=False,
        )

    def play(self) -> None:
        self.banner.clear()
        err = self.player.play(self.build_audio(), SAMPLE_RATE)
        if err:
            self.banner.show_warning(err)

    def stop(self) -> None:
        self.player.stop()

    def _save_dialog(self) -> None:
        ext = str(self.format_combo.currentData())
        suggested = str(Path(self.settings.last_dir) / f"morse{ext}")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save audio"), suggested, self.tr("Audio ({ext})").format(ext=f"*{ext}")
        )
        if path:
            self.save_to(Path(path))

    def save_to(self, path: Path) -> None:
        path = Path(path)
        ext = str(self.format_combo.currentData())
        if path.suffix.lower() != ext:
            path = path.with_suffix(ext)
        try:
            save_audio(path, self.build_audio(), SAMPLE_RATE)
        except Exception as e:  # soundfile báo lỗi định dạng/quyền ghi
            self.banner.show_error(str(e))
            return
        self.settings.last_dir = str(path.parent)
        self.banner.clear()

    # ---- i18n ----
    def retranslate(self) -> None:
        self.text_label.setText(self.tr("Text to encode"))
        self.morse_label.setText(self.tr("Morse code:"))
        self.text_edit.setPlaceholderText(self.tr("Type text to see its Morse code."))
        names = {"en": self.tr("English"), "ru": self.tr("Russian"), "kk-cyrl-ru": self.tr("Kazakh")}
        for i in range(self.profile_combo.count()):
            self.profile_combo.setItemText(i, names[self.profile_combo.itemData(i)])
        for label, text in zip(
            self.form_labels,
            (
                self.tr("Profile:"),
                self.tr("Speed (WPM):"),
                self.tr("Farnsworth (WPM):"),
                self.tr("Weight:"),
                self.tr("Tone (Hz):"),
                self.tr("Add noise, SNR (dB):"),
                self.tr("Format:"),
            ),
            strict=True,
        ):
            label.setText(text)
        self.play_button.setText(self.tr("Play"))
        self.stop_button.setText(self.tr("Stop"))
        self.save_button.setText(self.tr("Save…"))
        self.refresh_morse()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
