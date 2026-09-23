"""Dải số đo kiểu mặt máy thu: ngôn ngữ, tone, tốc độ, SNR, đường giải mã, thời gian.

Đây là những thứ MorseDesk TỰ đo ra từ tín hiệu — điểm mạnh nhất của ứng dụng — nên chúng phải
đọc được ngay bằng mắt như số trên mặt máy, chứ không phải một dòng chữ nhỏ ở đáy cửa sổ như bản
đầu. Mỗi ô: nhãn nhỏ màu phụ ở trên, giá trị lớn bằng chữ đơn cách đậm ở dưới.

Giữ nguyên giao diện cũ (`text()`, `language_widget` với tooltip điểm ba ngôn ngữ, `progress`,
`set_busy`, `set_progress`) để bên gọi và test không phải biết widget đã đổi.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QWidget

from morsedesk.api import DecodeResult
from morsedesk.app.theme import LAMP, READOUT_FONT
from morsedesk.app.widgets.progress_ring import ProgressRing


def readout_font(px: int = 22) -> QFont:
    f = QFont(READOUT_FONT)
    f.setPixelSize(px)
    f.setBold(True)
    return f


class Readout(QWidget):
    """Một ô số đo: nhãn nhỏ + giá trị lớn."""

    def __init__(self, parent=None, accent: bool = False) -> None:
        super().__init__(parent)
        self.caption = QLabel(self)
        self.caption.setProperty("role", "caption")
        self.value = QLabel("–", self)
        self.value.setFont(readout_font())
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if accent:
            self.value.setStyleSheet(f"color: {LAMP};")
        lay = QGridLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setVerticalSpacing(2)
        lay.addWidget(self.caption, 0, 0)
        lay.addWidget(self.value, 1, 0)


class StatsBar(QFrame):
    """Dải ô số đo + vòng tiến trình (ẩn được nếu trang có chỗ hiện tiến trình riêng)."""

    def __init__(self, parent=None, show_progress: bool = True) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        self._result: DecodeResult | None = None
        self._seconds: float | None = None
        self._show_progress = show_progress
        self.language_cell = Readout(self, accent=True)
        self.tone_cell = Readout(self)
        self.speed_cell = Readout(self)
        self.snr_cell = Readout(self)
        self.path_cell = Readout(self)
        self.time_cell = Readout(self)
        # Tên cũ: `language_widget` mang tooltip điểm số từng ngôn ngữ; `stats_widget` là ô đầu tiên.
        self.language_widget = self.language_cell.value
        self.stats_widget = self.tone_cell.value
        self.progress = ProgressRing(diameter=34, thickness=4, show_text=False, parent=self)
        self.progress.hide()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 12, 0)
        lay.setSpacing(0)
        cells = (self.language_cell, self.tone_cell, self.speed_cell, self.snr_cell,
                 self.path_cell, self.time_cell)
        for i, cell in enumerate(cells):
            if i:
                sep = QFrame(self)
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color: #2A3B60;")
                lay.addWidget(sep)
            lay.addWidget(cell, 2 if cell is self.language_cell else 1)
        lay.addStretch(1)
        lay.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignVCenter)
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
        """Hiện/ẩn vòng tiến trình và đưa nó về trạng thái quay vô định.

        Mỗi lần giải mã bắt đầu vô định vì tổng số bước chỉ biết được sau khi đọc file;
        `set_progress` chuyển sang phần trăm ngay ở bước đầu tiên.
        """
        self.progress.setVisible(flag and self._show_progress)
        self.progress.setRange(0, 0)

    def set_progress(self, done: int, total: int) -> None:
        """Chuyển sang phần trăm (CP-08). Tổng không hợp lệ thì giữ vô định; `done` bị kẹp."""
        if total <= 0:
            self.progress.setRange(0, 0)
            return
        self.progress.setRange(0, int(total))
        self.progress.setValue(max(0, min(int(done), int(total))))

    def cells(self) -> list[Readout]:
        return [self.language_cell, self.tone_cell, self.speed_cell, self.snr_cell,
                self.path_cell, self.time_cell]

    def text(self) -> str:
        return " ".join(f"{c.caption.text()} {c.value.text()}" for c in self.cells())

    def retranslate(self) -> None:
        self.language_cell.caption.setText(self.tr("Language"))
        self.tone_cell.caption.setText(self.tr("Tone"))
        self.speed_cell.caption.setText(self.tr("Speed"))
        self.snr_cell.caption.setText(self.tr("SNR"))
        self.path_cell.caption.setText(self.tr("Decoded by"))
        self.time_cell.caption.setText(self.tr("Took"))
        r = self._result
        if r is None:
            self.language_cell.value.setText(self.tr("No result yet."))
            for c in self.cells()[1:]:
                c.value.setText("–")
            self.language_widget.setToolTip("")
            return
        # Đơn vị cũng phải dịch ("Тон 570 Hz" lẫn tiếng Anh giữa câu tiếng Nga), và phải gọi
        # tr() ở câu lệnh riêng: pyside6-lupdate không trích được tr() nằm trong f-string.
        hz = self.tr("Hz")
        db = self.tr("dB")
        wpm = self.tr("WPM")
        sec = self.tr("s")
        self.tone_cell.value.setText(f"{r.tone_hz:.0f} {hz}" if r.tone_hz is not None else "–")
        self.speed_cell.value.setText(f"{r.wpm:.1f} {wpm}" if r.wpm is not None else "–")
        self.snr_cell.value.setText(f"{r.snr_db:.1f} {db}" if r.snr_db is not None else "–")
        by = getattr(r, "decoded_by", "model")
        self.path_cell.value.setText(self.tr("classic DSP") if by == "dsp" else self.tr("neural model"))
        self.time_cell.value.setText(f"{self._seconds:.2f} {sec}" if self._seconds is not None else "–")
        lang = self.language_label(r.language)
        if r.language_scores:
            lang = self.tr("{lang} (auto)").format(lang=lang)
            tip = "\n".join(
                f"{self.language_label(k)}: {v:.2f}" for k, v in sorted(r.language_scores.items())
            )
        else:
            tip = ""
        self.language_widget.setText(lang)
        self.language_widget.setToolTip(tip)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
