"""Băng Morse: bản tin vẽ thành dải đèn tín hiệu, chữ cái nằm dưới nhóm dấu của nó.

Chuỗi `... --- ...` bằng ký tự ASCII khó đọc soát (dấu chấm và gạch ngang lẫn vào nhau ở cỡ chữ
thường). Ở đây dit là chấm tròn, dah là thanh bo tròn dài gấp ba, đúng tỉ lệ nhịp ITU — cùng hình
với logo và dải tên trên trang Giới thiệu — và mỗi nhóm có chữ cái của nó ngay bên dưới. Tự xuống
dòng theo bề rộng.

`MorseTapeView` (khung cuộn) là thứ trang Tạo mã đặt vào bố cục, KHÔNG phải `MorseTape` trần. Đo
25/09 (ảnh chụp người dùng): băng trần tự đặt chiều cao tối thiểu = số dòng x 40 px, nên bản tin
6 000 ký tự kéo cửa sổ cao 22 624 px — phần dưới trang rơi khỏi màn hình, xóa hết chữ thì khung nhập
phình ra chiếm chỗ vì cửa sổ vẫn cao như cũ — và mỗi phím gõ mất 60–300 ms vì vẽ lại toàn bộ.
Nay: băng nằm trong khung cuộn có chiều cao do bố cục chia; bố cục tính MỘT lần mỗi khi nội dung
hoặc bề rộng đổi; chỉ vẽ các dòng nằm trong vùng cần vẽ.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QWidget

from morsedesk.app.theme import LAMP, MUTED, TEXT, UI_FONT

UNIT = 6.0             # px cho một đơn vị dit
MARK_H = 8.0
LETTER_GAP = 3         # đơn vị giữa hai chữ (ITU)
WORD_GAP = 7
LINE_H = 40.0
TOP = 6.0


class MorseTape(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._words: list[list[tuple[str, str]]] = []
        self._units: list[list[float]] = []     # độ dài (đơn vị dit) từng chữ, tính một lần
        self._items: list[tuple[float, float, str, str]] = []   # (x, y, chữ, mẫu), theo thứ tự y
        self._item_ys: list[float] = []
        self._laid_width = -1
        self.placeholder = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(int(LINE_H) + 12)

    def set_words(self, words: list[list[tuple[str, str]]]) -> None:
        """words: danh sách từ, mỗi từ là danh sách (chữ hiển thị, mẫu chấm gạch)."""
        words = [[(c, p) for c, p in w if p] for w in words]
        words = [w for w in words if w]
        if words == self._words:
            return
        self._words = words
        self._units = [[self._char_units(p) for _, p in w] for w in words]
        self._laid_width = -1
        self._relayout()

    def words(self) -> list[list[tuple[str, str]]]:
        return self._words

    @staticmethod
    def _char_units(pattern: str) -> float:
        return sum(3.0 if s == "-" else 1.0 for s in pattern) + (len(pattern) - 1)

    def _layout(self, width: float) -> list[tuple[float, float, str, str]]:
        """(x, y, chữ, mẫu) cho từng chữ; xuống dòng nguyên từ khi hết chỗ."""
        out = []
        x, y = 8.0, TOP
        right = max(width - 8.0, 60.0)
        for word, units in zip(self._words, self._units, strict=True):
            w_units = sum(units) + LETTER_GAP * (len(word) - 1)
            if x > 8.0 and x + w_units * UNIT > right:
                x, y = 8.0, y + LINE_H
            last = len(word) - 1
            for i, ((ch, pat), u) in enumerate(zip(word, units, strict=True)):
                out.append((x, y, ch, pat))
                x += (u + (LETTER_GAP if i < last else 0)) * UNIT
            x += WORD_GAP * UNIT
        return out

    def content_height(self) -> int:
        lines = 1 + (int((self._items[-1][1] - TOP) // LINE_H) if self._items else 0)
        return int(lines * LINE_H) + 12

    def _relayout(self) -> None:
        width = self.width()
        if width != self._laid_width:
            self._items = self._layout(width)
            self._item_ys = [it[1] for it in self._items]
            self._laid_width = width
        h = self.content_height()
        if self.height() != h:
            self.setFixedHeight(h)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._relayout()

    def sizeHint(self) -> QSize:
        return QSize(400, self.height())

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._items:
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
        text = QColor(TEXT)
        clip = event.rect()
        # Chỉ các dòng giao với vùng cần vẽ: bản tin dài có hàng nghìn nhóm, khung cuộn chỉ lộ vài dòng.
        lo = bisect_left(self._item_ys, clip.top() - LINE_H)
        hi = bisect_right(self._item_ys, clip.bottom() + 1)
        for x, y, ch, pat in self._items[lo:hi]:
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
            p.setPen(text)
            p.drawText(QRectF(x - 6, y + 14, span + 12, 18), Qt.AlignmentFlag.AlignHCenter, ch)
        p.end()


class MorseTapeView(QScrollArea):
    """Băng Morse trong khung cuộn dọc: chiều cao do bố cục chia, không do độ dài bản tin."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tape = MorseTape(self)
        self.setWidget(self.tape)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.viewport().setAutoFillBackground(False)
        self.tape.setAutoFillBackground(False)
        self.setMinimumHeight(int(2 * LINE_H) + 12)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_words(self, words: list[list[tuple[str, str]]], follow_end: bool = False) -> None:
        """`follow_end`: đang gõ ở cuối văn bản -> cuộn theo chữ mới nhất."""
        self.tape.set_words(words)
        if follow_end:
            # dải cuộn chỉ cập nhật sau khi bố cục chạy: cuộn ngay thì nhắm vào đáy CŨ
            QTimer.singleShot(0, self, self._to_end)

    def _to_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def words(self) -> list[list[tuple[str, str]]]:
        return self.tape.words()

    @property
    def placeholder(self) -> str:
        return self.tape.placeholder

    @placeholder.setter
    def placeholder(self, text: str) -> None:
        self.tape.placeholder = text
        self.tape.update()

    def sizeHint(self) -> QSize:
        return QSize(400, int(4 * LINE_H))
