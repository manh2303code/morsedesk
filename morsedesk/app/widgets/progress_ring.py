"""Vòng tiến trình: quay khi chưa biết tổng, hiện phần trăm chạy mượt khi đã biết.

Thay cho QProgressBar theo yêu cầu người dùng, và giữ ĐÚNG giao diện của nó (`setRange`, `value`,
`minimum`, `maximum`) để mã và test cũ không phải biết đã đổi widget.

Con số hiển thị đuổi theo giá trị thật (mỗi khung đi 25 % quãng còn lại) thay vì nhảy cóc: lõi
báo tiến trình của beam cứ mỗi giây âm thanh một lần, nếu vẽ thẳng thì vòng giật từng nấc.
Bộ đếm giờ chỉ chạy khi widget đang hiện VÀ còn việc để vẽ (đang quay, hoặc số chưa đuổi kịp).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from morsedesk.app.theme import LAMP, LINE, READOUT_FONT, TEXT

FRAME_MS = 16
SPIN_DEG_PER_FRAME = 6.0
EASE = 0.25


class ProgressRing(QWidget):
    def __init__(self, diameter: int = 96, thickness: int = 8, show_text: bool = True,
                 parent=None) -> None:
        super().__init__(parent)
        self._d = int(diameter)
        self._w = int(thickness)
        self._show_text = show_text
        self._min, self._max, self._value = 0, 0, 0
        self._shown = 0.0            # phần đã vẽ, 0..1, đuổi theo giá trị thật
        self._angle = 90.0           # góc bắt đầu cung khi quay vô định
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(self._d + 4, self._d + 4)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ---- giao diện kiểu QProgressBar ----
    def setRange(self, lo: int, hi: int) -> None:  # noqa: N802 (tên Qt)
        self._min, self._max = int(lo), int(hi)
        if self._max <= self._min:
            self._shown = 0.0
        self._kick()

    def setValue(self, v: int) -> None:  # noqa: N802
        self._value = max(self._min, min(int(v), self._max)) if self._max > self._min else int(v)
        self._kick()

    def value(self) -> int:
        return self._value

    def minimum(self) -> int:
        return self._min

    def maximum(self) -> int:
        return self._max

    def reset(self) -> None:
        self.setRange(0, 0)
        self._value = 0

    def indeterminate(self) -> bool:
        return self._max <= self._min

    def fraction(self) -> float:
        if self.indeterminate():
            return 0.0
        return (self._value - self._min) / (self._max - self._min)

    def percent(self) -> int:
        return int(round(100 * self.fraction()))

    # ---- vẽ ----
    def sizeHint(self) -> QSize:
        return QSize(self._d + 4, self._d + 4)

    def _kick(self) -> None:
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._kick()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        if self.indeterminate():
            self._angle = (self._angle - SPIN_DEG_PER_FRAME) % 360.0
        else:
            target = self.fraction()
            self._shown += (target - self._shown) * EASE
            if abs(target - self._shown) < 0.002:
                self._shown = target
                self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = 2 + self._w / 2
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        track = QPen(QColor(LINE), self._w)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track)
        p.drawEllipse(rect)
        arc = QPen(QColor(LAMP), self._w)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc)
        if self.indeterminate():
            p.drawArc(rect, int(self._angle * 16), int(-100 * 16))
        elif self._shown > 0.0:
            p.drawArc(rect, 90 * 16, int(-360 * 16 * self._shown))
        if self._show_text and not self.indeterminate():
            f = QFont(READOUT_FONT)
            f.setPixelSize(max(10, int(self._d * 0.24)))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(TEXT))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(round(100 * self._shown))}%")
        p.end()
