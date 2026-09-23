"""Băng Morse: bản tin vẽ thành dải đèn tín hiệu, chữ cái nằm dưới nhóm dấu của nó.

Chuỗi `... --- ...` bằng ký tự ASCII khó đọc soát (dấu chấm và gạch ngang lẫn vào nhau ở cỡ chữ
thường). Ở đây dit là chấm tròn, dah là thanh bo tròn dài gấp ba, đúng tỉ lệ nhịp ITU — cùng hình
với logo và dải tên trên trang Giới thiệu — và mỗi nhóm có chữ cái của nó ngay bên dưới. Tự xuống
dòng theo bề rộng; chiều cao tối thiểu tự tăng theo số dòng.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from morsedesk.app.theme import LAMP, MUTED, TEXT, UI_FONT

UNIT = 6.0             # px cho một đơn vị dit
MARK_H = 8.0
LETTER_GAP = 3         # đơn vị giữa hai chữ (ITU)
WORD_GAP = 7
LINE_H = 40.0


class MorseTape(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._words: list[list[tuple[str, str]]] = []
        self.placeholder = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(int(LINE_H) + 12)

    def set_words(self, words: list[list[tuple[str, str]]]) -> None:
        """words: danh sách từ, mỗi từ là danh sách (chữ hiển thị, mẫu chấm gạch)."""
        self._words = [[(c, p) for c, p in w if p] for w in words]
        self._words = [w for w in self._words if w]
        self._relayout()

    def words(self) -> list[list[tuple[str, str]]]:
        return self._words

    @staticmethod
    def _char_units(pattern: str) -> float:
        return sum(3.0 if s == "-" else 1.0 for s in pattern) + (len(pattern) - 1)

    def _layout(self, width: float) -> list[tuple[float, float, str, str]]:
        """(x, y, chữ, mẫu) cho từng chữ; xuống dòng nguyên từ khi hết chỗ."""
        out = []
        x, y = 8.0, 6.0
        right = max(width - 8.0, 60.0)
        for word in self._words:
            w_units = sum(self._char_units(p) for _, p in word) + LETTER_GAP * (len(word) - 1)
            if x > 8.0 and x + w_units * UNIT > right:
                x, y = 8.0, y + LINE_H
            for i, (ch, pat) in enumerate(word):
                out.append((x, y, ch, pat))
                x += (self._char_units(pat) + (LETTER_GAP if i < len(word) - 1 else 0)) * UNIT
            x += WORD_GAP * UNIT
        return out

    def _relayout(self) -> None:
        items = self._layout(self.width())
        lines = 1 + (int((items[-1][1] - 6.0) // LINE_H) if items else 0)
        self.setMinimumHeight(int(lines * LINE_H) + 12)
        self.updateGeometry()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def sizeHint(self) -> QSize:
        return QSize(400, self.minimumHeight())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        items = self._layout(self.width())
        if not items:
            if self.placeholder:
                p.setPen(QColor(MUTED))
                p.drawText(self.rect().adjusted(8, 0, 0, 0),
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.placeholder)
            p.end()
            return
        f = QFont(UI_FONT)
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        lamp = QColor(LAMP)
        for x, y, ch, pat in items:
            cx = x
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(lamp)
            for s in pat:
                w = (3.0 if s == "-" else 1.0) * UNIT
                if s == "-":
                    p.drawRoundedRect(QRectF(cx, y + 4, w, MARK_H), MARK_H / 2, MARK_H / 2)
                else:
                    p.drawEllipse(QRectF(cx + w / 2 - MARK_H / 2, y + 4, MARK_H, MARK_H))
                cx += w + UNIT
            span = self._char_units(pat) * UNIT
            p.setPen(QColor(TEXT))
            p.drawText(QRectF(x - 6, y + 14, span + 12, 18), Qt.AlignmentFlag.AlignHCenter, ch)
        p.end()
