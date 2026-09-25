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
# Chữ đang phát (Nghe thử ở trang Tạo mã): nền bo tròn + viền đèn; dấu đang kêu to và sáng hơn.
ACTIVE_FILL = "#233457"
ACTIVE_GLOW = "#FFF1CC"          # dấu đang kêu: trắng ấm, nổi hẳn trên vàng đèn
POP = 1.45                        # dấu đang kêu phóng to chừng này


class MorseTape(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._words: list[list[tuple[str, str]]] = []
        self._units: list[list[float]] = []     # độ dài (đơn vị dit) từng chữ, tính một lần
        self._items: list[tuple[float, float, str, str]] = []   # (x, y, chữ, mẫu), theo thứ tự y
        self._item_ys: list[float] = []
        self._laid_width = -1
        self._active: tuple[int, int, bool] | None = None      # (chữ, dấu, tone đang kêu)
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
        self._active = None
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

    def item_count(self) -> int:
        return len(self._items)

    def item_rect(self, i: int) -> QRectF:
        """Khung của chữ thứ `i` (dấu + chữ cái bên dưới), kể cả phần nền khi được tô."""
        x, y, _ch, pat = self._items[i]
        span = self._char_units(pat) * UNIT
        return QRectF(x - 9, y - 3, span + 18, LINE_H - 2)

    def active(self) -> tuple[int, int, bool] | None:
        return self._active

    def set_active(self, letter: int | None, element: int = 0, on: bool = False) -> None:
        """Tô chữ `letter` (None = bỏ tô); `on`: dấu `element` của nó đang kêu."""
        new = None if letter is None or not (0 <= letter < len(self._items)) else (letter, element, on)
        if new == self._active:
            return
        old, self._active = self._active, new
        for a in (old, new):
            if a is not None:
                self.update(self.item_rect(a[0]).adjusted(-6, -6, 6, 6).toAlignedRect())

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
        act = self._active
        for idx in range(lo, hi):
            x, y, ch, pat = self._items[idx]
            is_active = act is not None and act[0] == idx
            if is_active:
                p.setPen(QColor(LAMP))
                p.setBrush(QColor(ACTIVE_FILL))
                p.drawRoundedRect(self.item_rect(idx), 9, 9)
            cx = x
            for k, s in enumerate(pat):
                w = (3.0 if s == "-" else 1.0) * UNIT
                sounding = is_active and act[1] == k and act[2]
                h = MARK_H * (POP if sounding else 1.0)
                cy = y + 4 + MARK_H / 2
                if sounding:          # quầng sáng sau dấu đang kêu
                    halo = QColor(LAMP)
                    halo.setAlpha(80)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(halo)
                    p.drawRoundedRect(QRectF(cx - 5, cy - h / 2 - 5, max(w, h) + 10, h + 10), h / 2 + 5, h / 2 + 5)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(ACTIVE_GLOW) if sounding else lamp)
                if s == "-":
                    p.drawRoundedRect(QRectF(cx, cy - h / 2, w, h), h / 2, h / 2)
                else:
                    p.drawEllipse(QRectF(cx + w / 2 - h / 2, cy - h / 2, h, h))
                cx += w + UNIT
            span = self._char_units(pat) * UNIT
            p.setPen(lamp if is_active else text)
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

    def set_active(self, letter: int | None, element: int = 0, on: bool = False) -> None:
        """Tô chữ đang phát và cuộn để nó luôn trong tầm nhìn."""
        before = self.tape.active()
        self.tape.set_active(letter, element, on)
        if letter is not None and (before is None or before[0] != letter) and letter < self.tape.item_count():
            r = self.tape.item_rect(letter)
            self.ensureVisible(int(r.center().x()), int(r.center().y()), 20, int(LINE_H))

    @property
    def placeholder(self) -> str:
        return self.tape.placeholder

    @placeholder.setter
    def placeholder(self, text: str) -> None:
        self.tape.placeholder = text
        self.tape.update()

    def sizeHint(self) -> QSize:
        return QSize(400, int(4 * LINE_H))
