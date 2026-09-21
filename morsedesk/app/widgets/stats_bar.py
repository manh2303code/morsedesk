"""Hàng chỉ số: WPM, tone, SNR, ngôn ngữ nhận diện (tooltip điểm ba profile), thời gian, tiến trình."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from morsedesk.api import DecodeResult


class StatsBar(QWidget):
    """Hàng ngang gồm nhãn chỉ số, nhãn ngôn ngữ (tooltip điểm số) và thanh tiến trình bận."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result: DecodeResult | None = None
        self._seconds: float | None = None
        self.stats_widget = QLabel(self)
        self.language_widget = QLabel(self)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)  # không xác định (bận không rõ tiến độ %)
        self.progress.setMaximumWidth(120)
        self.progress.hide()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.addWidget(self.stats_widget, 1)
        lay.addWidget(self.language_widget, 0)
        lay.addWidget(self.progress, 0)
        self.retranslate()

    def language_label(self, code: str) -> str:
        """Tên hiển thị đã dịch cho mã ngôn ngữ/profile; `""` nghĩa là chưa nhận diện được."""
        names = {
            "en": self.tr("English"),
            "ru": self.tr("Russian"),
            "kk-cyrl-ru": self.tr("Kazakh"),
            "auto": self.tr("Auto"),
        }
        if code == "":
            return self.tr("not detected")
        return names.get(code, code)

    def set_result(self, result: DecodeResult | None, seconds: float | None) -> None:
        """Cập nhật kết quả giải mã hiện tại (None = chưa có) và thời gian giải mã (giây)."""
        self._result, self._seconds = result, seconds
        self.retranslate()

    def set_busy(self, flag: bool) -> None:
        """Hiện/ẩn thanh tiến trình không xác định trong lúc giải mã."""
        self.progress.setVisible(flag)

    def text(self) -> str:
        return self.stats_widget.text() + " " + self.language_widget.text()

    def retranslate(self) -> None:
        r = self._result
        if r is None:
            self.stats_widget.setText(self.tr("No result yet."))
            self.language_widget.setText("")
            self.language_widget.setToolTip("")
            return
        # Đơn vị cũng phải dịch ("Тон 570 Hz" lẫn tiếng Anh giữa câu tiếng Nga), và phải gọi
        # tr() ở câu lệnh riêng: pyside6-lupdate không trích được tr() nằm trong f-string.
        hz = self.tr("Hz")
        db = self.tr("dB")
        parts = [
            self.tr("WPM {v}").format(v=f"{r.wpm:.1f}" if r.wpm is not None else "–"),
            self.tr("Tone {v}").format(v=f"{r.tone_hz:.0f} {hz}" if r.tone_hz is not None else "–"),
            self.tr("SNR {v}").format(v=f"{r.snr_db:.1f} {db}" if r.snr_db is not None else "–"),
        ]
        if self._seconds is not None:
            parts.append(self.tr("{v} s").format(v=f"{self._seconds:.2f}"))
        self.stats_widget.setText(" · ".join(parts))
        lang = self.language_label(r.language)
        if r.language_scores:
            lang = self.tr("{lang} (auto)").format(lang=lang)
            tip = "\n".join(
                f"{self.language_label(k)}: {v:.2f}" for k, v in sorted(r.language_scores.items())
            )
        else:
            tip = ""
        self.language_widget.setText(self.tr("Language: {lang}").format(lang=lang))
        self.language_widget.setToolTip(tip)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
