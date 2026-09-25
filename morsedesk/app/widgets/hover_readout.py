"""Ô số đo nổi theo chuột trên biểu đồ tín hiệu: cảnh 3D, thác nước, phổ 2D — một hình ở mọi nơi.

Người dùng 25/09: "phải có thể di chuột qua lại ở cả biểu đồ 2D và 3D". Rê chuột lên đâu thì ô này
nói điểm đó là gì: từ đã giải ở thời điểm ấy (nếu có), tần số, mức trên nền nhiễu, và thời điểm.
Là một QLabel con trong suốt với chuột (không cướp sự kiện của biểu đồ bên dưới), nên biểu đồ vẽ
bằng QPainter lẫn biểu đồ pyqtgraph dùng chung được.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QWidget

from morsedesk.app.theme import LAMP, LINE, MUTED, READOUT_FONT, TEXT

# Một dòng = (chữ, vai): "word" = từ đã giải (vàng đèn, đậm), "value" = số đo (chữ đơn cách như các
# ô số đo), "muted" = thời điểm / chú thích.
Line = tuple[str, str]
OFFSET = 16             # cách mũi chuột, để ô không che đúng điểm đang xem
EDGE = 4


def render(lines: list[Line]) -> str:
    parts = []
    for text, role in lines:
        t = escape(text)
        if role == "word":
            parts.append(f'<span style="color:{LAMP}; font-weight:700; font-size:12pt;">{t}</span>')
        elif role == "muted":
            parts.append(f'<span style="color:{MUTED};">{t}</span>')
        else:
            parts.append(f"<span style=\"font-family:'{READOUT_FONT}';\">{t}</span>")
    return "<br>".join(parts)


class HoverReadout(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet(f"QLabel {{ background: rgba(27, 41, 70, 238); color: {TEXT}; "
                           f"border: 1px solid {LINE}; border-radius: 6px; padding: 5px 9px; }}")
        self._lines: list[Line] = []
        self.hide()

    def lines(self) -> list[Line]:
        return [] if self.isHidden() else list(self._lines)

    def show_lines(self, lines: list[Line], at: QPoint) -> None:
        """Hiện `lines` cạnh điểm `at` (tọa độ widget cha); tràn mép thì lật sang phía kia."""
        self._lines = list(lines)
        if not lines:
            self.hide()
            return
        self.setText(render(lines))
        self.adjustSize()
        area = self.parentWidget().rect()
        x, y = at.x() + OFFSET, at.y() + OFFSET
        if x + self.width() > area.right() - EDGE:
            x = at.x() - OFFSET - self.width()
        if y + self.height() > area.bottom() - EDGE:
            y = at.y() - OFFSET - self.height()
        self.move(max(EDGE, x), max(EDGE, y))
        self.show()
        self.raise_()
