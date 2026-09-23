"""Bản giải mã dạng "lời bài hát": chữ to, cuộn được, từ đang phát sáng lên như karaoke.

Một bản tin 13 phút ở 40 WPM là hơn 500 từ; khung chip cố định cũ chỉ hiện được hai dòng rưỡi
và cắt ngang dòng thứ ba (ảnh chụp người dùng 24/09). Nay:
- toàn bộ bản tin nằm trong một khung cuộn có thanh kéo bên cạnh;
- khi nghe lại, từ đang phát tô nền đèn tín hiệu, phần đã nghe sáng, phần chưa tới mờ hơn, và
  khung tự cuộn để dòng đang phát nằm ở khoảng một phần ba phía trên — như lời bài hát;
- người dùng tự cuộn thì khung thôi bám theo vài giây rồi mới bám lại;
- độ tin cậy chỉ đánh dấu ở từ ĐÁNG NGỜ (gạch chân vàng/đỏ); từ chắc chắn không mang dấu gì,
  nên bản tin dài đọc như văn bản thường và mắt chỉ dừng ở chỗ cần soi.
Click một từ vẫn phát từ đúng chỗ đó; rê chuột lên từ hiện độ tin cậy và thời điểm.

Vẽ bằng MỘT widget tự xếp chữ, không phải mỗi từ một QLabel: đo 24/09, 2 400 nhãn (bản tin
60 phút ở 40 WPM) mất 7,5 giây chỉ để dựng, còn xếp chữ bằng QFontMetrics là vài mili giây.
"""

from __future__ import annotations

import time
from bisect import bisect_right

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QFrame, QScrollArea, QToolTip, QWidget

from morsedesk.api import FALLBACK_CONFIDENCE, Word

WORD_GOOD = 0.8
# Màu gạch chân theo độ tin cậy. Từ chắc chắn: không gạch.
COLOR_GOOD, COLOR_MID, COLOR_LOW = "transparent", "#E0B341", "#F26B5B"
# Ghim màu chữ thay vì lấy theo bảng màu hệ thống (bản đầu từng ra 1,25:1 trên ảnh chụp thật).
TEXT_COLOR = "#E6ECF7"          # 12,9:1 trên nền khung
UPCOMING_COLOR = "#95A3BF"      # phần chưa nghe tới khi đang phát: 6,4:1, vẫn đọc rõ
PLACEHOLDER_COLOR = "#95A3BF"
ACTIVE_BG = "#F5A524"           # từ đang phát: nền đèn tín hiệu
ACTIVE_TEXT = "#1A1206"         # 9,6:1 trên ACTIVE_BG
HOVER_BG = "#22335A"
FONT_PT = 20
PAD_X, PAD_TOP, PAD_BOTTOM = 7, 2, 6      # đệm quanh chữ; đáy chừa chỗ cho gạch chân
GAP_X, GAP_Y = 6, 6
MARGIN_X, MARGIN_Y = 0, 6        # chữ thẳng hàng với tiêu đề khung
FOLLOW_AT = 0.33                # dòng đang phát nằm ở một phần ba chiều cao khung
USER_SCROLL_GRACE_S = 4.0       # người dùng tự cuộn -> thôi bám theo chừng này giây
SCROLL_MS = 320
FADE_PX = 26                    # mép trên/dưới mờ dần như màn hình lời bài hát
FADE_COLOR = "#141F35"          # = theme.PANEL, nền khung kết quả


def confidence_color(c: float) -> str:
    """Màu gạch chân theo ngưỡng tin cậy: không gạch (>=WORD_GOOD), vàng (>=FALLBACK_CONFIDENCE), đỏ."""
    if c >= WORD_GOOD:
        return COLOR_GOOD
    if c >= FALLBACK_CONFIDENCE:
        return COLOR_MID
    return COLOR_LOW


class _Canvas(QWidget):
    """Nơi xếp và vẽ chữ. Mọi trạng thái nằm ở WordView; lớp này chỉ đo và vẽ."""

    def __init__(self, view: WordView) -> None:
        super().__init__(view)
        self.view = view
        self.setMouseTracking(True)
        font = QFont(self.font())
        font.setPointSize(FONT_PT)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self.rects: list[QRect] = []
        self.line_tops: list[int] = []        # y của từng dòng, tăng dần
        self.line_first: list[int] = []       # chỉ số từ đầu tiên của từng dòng
        self.hover = -1

    def relayout(self, width: int) -> int:
        """Xếp chữ cho bề rộng `width`; trả chiều cao cần có."""
        fm = QFontMetrics(self.font())
        h = fm.height() + PAD_TOP + PAD_BOTTOM
        x, y = MARGIN_X, MARGIN_Y
        rects: list[QRect] = []
        tops: list[int] = [] if not self.view._words else [MARGIN_Y]
        first: list[int] = [] if not self.view._words else [0]
        right = max(width - 8, MARGIN_X + 1)
        for i, w in enumerate(self.view._words):
            ww = fm.horizontalAdvance(w.text) + 2 * PAD_X
            if x > MARGIN_X and x + ww > right:
                x, y = MARGIN_X, y + h + GAP_Y
                tops.append(y)
                first.append(i)
            rects.append(QRect(x, y, ww, h))
            x += ww + GAP_X
        self.rects, self.line_tops, self.line_first = rects, tops, first
        if not rects:
            return MARGIN_Y * 2 + h
        return y + h + MARGIN_Y

    def index_at(self, pos) -> int:
        if not self.rects:
            return -1
        line = bisect_right(self.line_tops, pos.y()) - 1
        if line < 0:
            return -1
        lo = self.line_first[line]
        hi = self.line_first[line + 1] if line + 1 < len(self.line_first) else len(self.rects)
        for i in range(lo, hi):
            if self.rects[i].contains(pos):
                return i
        return -1

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        view = self.view
        if not view._words:
            p.setPen(QColor(PLACEHOLDER_COLOR))
            f = QFont(self.font())
            f.setPointSize(11)
            f.setWeight(QFont.Weight.Normal)
            p.setFont(f)
            p.drawText(self.rect().adjusted(PAD_X, MARGIN_Y, -PAD_X, -MARGIN_Y),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, view._placeholder)
            p.end()
            return
        clip = event.rect()
        first_line = max(0, bisect_right(self.line_tops, clip.top() - 80) - 1)
        start = self.line_first[first_line] if self.line_first else 0
        active = view._active_index
        playing = active is not None
        for i in range(start, len(self.rects)):
            r = self.rects[i]
            if r.top() > clip.bottom():
                break
            w = view._words[i]
            if i == active:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(ACTIVE_BG))
                p.drawRoundedRect(QRectF(r), 6, 6)
                color = ACTIVE_TEXT
            else:
                if i == self.hover:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(HOVER_BG))
                    p.drawRoundedRect(QRectF(r), 6, 6)
                color = UPCOMING_COLOR if playing and i > active else TEXT_COLOR
            under = confidence_color(w.confidence)
            if under != COLOR_GOOD and i != active:
                pen = QPen(QColor(under), 3)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                yb = r.bottom() - 2
                p.drawLine(r.left() + PAD_X - 1, yb, r.right() - PAD_X + 1, yb)
            p.setPen(QColor(color))
            p.drawText(r.adjusted(PAD_X, PAD_TOP, -PAD_X, -PAD_BOTTOM),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, w.text)
        p.end()

    def mouseMoveEvent(self, event) -> None:
        i = self.index_at(event.position().toPoint())
        if i != self.hover:
            old, self.hover = self.hover, i
            for k in (old, i):
                if 0 <= k < len(self.rects):
                    self.update(self.rects[k].adjusted(-2, -2, 2, 2))
            self.setCursor(Qt.CursorShape.PointingHandCursor if i >= 0 else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if 0 <= self.hover < len(self.rects):
            self.update(self.rects[self.hover].adjusted(-2, -2, 2, 2))
        self.hover = -1
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            i = self.index_at(event.position().toPoint())
            if i >= 0:
                self.view.word_clicked.emit(self.view._words[i].start_s)
        super().mousePressEvent(event)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ToolTip:
            i = self.index_at(event.pos())
            if i >= 0:
                QToolTip.showText(event.globalPos(), self.view.tooltip_for(i), self, self.rects[i])
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().event(event)


class _Fade(QWidget):
    """Dải mờ dần phủ lên mép khung cuộn: báo "còn chữ phía trên/dưới" mà không cắt ngang dòng."""

    def __init__(self, parent: QWidget, top: bool) -> None:
        super().__init__(parent)
        self.top = top
        self.color = FADE_COLOR
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        solid, clear = QColor(self.color), QColor(self.color)
        clear.setAlpha(0)
        g.setColorAt(0.0, solid if self.top else clear)
        g.setColorAt(1.0, clear if self.top else solid)
        p.fillRect(self.rect(), g)
        p.end()


class WordView(QScrollArea):
    """Bản giải mã cuộn được; rỗng thì hiện câu gợi ý.

    `live=True` (trang Nghe): khung bám theo từ MỚI NHẤT ở cuối thay vì theo con trỏ phát.
    """

    word_clicked = Signal(float)

    def __init__(self, parent=None, live: bool = False) -> None:
        super().__init__(parent)
        self._live = live
        self._words: list[Word] = []
        self._starts: list[float] = []
        self._active_index: int | None = None      # None = không phát; -1 = trước từ đầu tiên
        self._followed_y: int | None = None
        self._user_scroll_at = -1e9
        self._placeholder = ""
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.viewport().setAutoFillBackground(False)
        self._canvas = _Canvas(self)
        self._canvas.setAutoFillBackground(False)
        self.setWidget(self._canvas)
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(SCROLL_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.verticalScrollBar().sliderPressed.connect(self._mark_user_scroll)
        self._fade_top = _Fade(self.viewport(), top=True)
        self._fade_bottom = _Fade(self.viewport(), top=False)
        self.verticalScrollBar().valueChanged.connect(self._update_fades)
        self.verticalScrollBar().rangeChanged.connect(self._update_fades)
        self.retranslate()

    def set_background(self, color: str) -> None:
        """Màu nền nơi đặt khung: dải mờ mép phải hòa vào đúng màu đó (khung kết quả trang Giải
        mã là PANEL, dải chữ tạm trang Nghe nằm thẳng trên nền đêm)."""
        self._fade_top.color = self._fade_bottom.color = color
        self._fade_top.update()
        self._fade_bottom.update()

    def _update_fades(self, *_args) -> None:
        bar = self.verticalScrollBar()
        vw, vh = self.viewport().width(), self.viewport().height()
        self._fade_top.setGeometry(0, 0, vw, FADE_PX)
        self._fade_bottom.setGeometry(0, vh - FADE_PX, vw, FADE_PX)
        self._fade_top.setVisible(bar.value() > bar.minimum())
        self._fade_bottom.setVisible(bar.value() < bar.maximum())
        self._fade_top.raise_()
        self._fade_bottom.raise_()

    # ---- nội dung ----
    def set_placeholder(self, text: str) -> None:
        """Đặt văn bản hiện khi chưa có từ nào."""
        self._placeholder = text
        self._canvas.update()

    def placeholder(self) -> str:
        return self._placeholder

    def set_words(self, words: list[Word]) -> None:
        """Thay toàn bộ danh sách từ hiển thị bằng `words`."""
        at_bottom = self._at_bottom()
        self._anim.stop()
        self._words = list(words)
        self._starts = [w.start_s for w in self._words]
        self._active_index = None
        self._followed_y = None
        self._canvas.hover = -1
        self._relayout()
        self.setAccessibleDescription(" ".join(w.text for w in self._words))
        if self._live and at_bottom:
            QTimer.singleShot(0, self, self._scroll_to_bottom)   # hủy theo widget nếu nó bị xóa trước
        elif not self._live:
            self.verticalScrollBar().setValue(0)

    def clear(self) -> None:
        """Xóa toàn bộ từ, quay về câu gợi ý."""
        self.set_words([])

    def words(self) -> list[Word]:
        return list(self._words)

    def texts(self) -> list[str]:
        return [w.text for w in self._words]

    def tooltip_for(self, i: int) -> str:
        w = self._words[i]
        return self.tr("confidence {conf:.2f} · {start:.2f}–{end:.2f} s").format(
            conf=w.confidence, start=w.start_s, end=w.end_s)

    def word_rect(self, i: int) -> QRect:
        """Khung của từ thứ `i` trong tọa độ của vùng vẽ (cho test và bấm chuột)."""
        return QRect(self._canvas.rects[i])

    def canvas(self) -> QWidget:
        return self._canvas

    def line_height(self) -> int:
        """Chiều cao một dòng chữ kể cả lề — mức tối thiểu để một dòng hiện trọn, không cuộn."""
        return QFontMetrics(self._canvas.font()).height() + PAD_TOP + PAD_BOTTOM + 2 * MARGIN_Y

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.line_height() + 2)

    def _relayout(self) -> None:
        width = self.viewport().width()
        h = self._canvas.relayout(width)
        # Cao ĐÚNG bằng nội dung (không kéo bằng khung): kéo bằng khung thì lần khung co lại sau
        # đó để lại vùng vẽ cao hơn khung, và thanh cuộn thừa hiện ra dù không có gì để cuộn.
        self._canvas.resize(QSize(width, h))
        self._canvas.update()
        self._update_fades()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()
        self._followed_y = None

    # ---- karaoke ----
    def set_playhead(self, t_s: float | None) -> None:
        """Tô từ chứa mốc thời gian `t_s`; `None` để bỏ tô và trả mọi từ về màu thường.

        Con trỏ hay rơi vào khoảng lặng GIỮA hai từ. Khi đó giữ nguyên từ vừa qua thay vì bỏ
        trắng, nếu không vệt sáng sẽ nhấp nháy mỗi lần im lặng.
        """
        if t_s is None:
            if self._active_index is not None:
                self._active_index = None
                self._canvas.update()
            self._followed_y = None
            return
        i = bisect_right(self._starts, t_s) - 1            # -1: chưa tới từ đầu tiên
        if i == self._active_index:
            return
        old, self._active_index = self._active_index, i
        if old is None or abs(i - (old or 0)) > 1:
            self._canvas.update()                         # phần sáng/mờ đổi trên nhiều dòng
        else:
            for k in (old, i):
                if 0 <= k < len(self._canvas.rects):
                    self._canvas.update(self._canvas.rects[k].adjusted(-2, -2, 2, 2))
        if i >= 0:
            self._follow(i)

    def active_index(self) -> int | None:
        return self._active_index

    def _follow(self, i: int) -> None:
        """Cuộn để dòng của từ đang phát nằm ở FOLLOW_AT chiều cao khung (chỉ khi đổi dòng)."""
        if self._live or time.monotonic() - self._user_scroll_at < USER_SCROLL_GRACE_S:
            return
        y = self._canvas.rects[i].top()
        if y == self._followed_y:
            return
        self._followed_y = y
        bar = self.verticalScrollBar()
        target = max(bar.minimum(), min(bar.maximum(), int(y - self.viewport().height() * FOLLOW_AT)))
        self._anim.stop()
        if target == bar.value():
            return
        if not self.isVisible():
            bar.setValue(target)
            return
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(target)
        self._anim.start()

    def follow_target(self) -> int:
        """Giá trị thanh cuộn mà karaoke đang nhắm tới (cho test)."""
        if self._anim.state() == QPropertyAnimation.State.Running:
            return int(self._anim.endValue())
        return self.verticalScrollBar().value()

    # ---- người dùng tự cuộn ----
    def _mark_user_scroll(self) -> None:
        self._user_scroll_at = time.monotonic()
        self._followed_y = None           # bám lại thì cuộn về đúng dòng, kể cả khi chưa đổi dòng
        self._anim.stop()

    def viewportEvent(self, event) -> bool:
        if event.type() == QEvent.Type.Wheel:
            self._mark_user_scroll()
        elif event.type() == QEvent.Type.Resize and event.size().width() != self._canvas.width():
            # Thanh cuộn hiện/ẩn làm vùng nhìn đổi bề rộng mà khung ngoài không đổi: xếp lại chữ,
            # nếu không chữ vẫn theo bề rộng cũ và thanh cuộn có thể kẹt lại dù không cần.
            QTimer.singleShot(0, self, self._relayout)
        return super().viewportEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Up, Qt.Key.Key_Down,
                           Qt.Key.Key_Home, Qt.Key.Key_End):
            self._mark_user_scroll()
        super().keyPressEvent(event)

    def _at_bottom(self) -> bool:
        bar = self.verticalScrollBar()
        return bar.value() >= bar.maximum() - 4

    def _scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---- dịch ----
    def retranslate(self) -> None:
        self.set_placeholder(self.tr("Words appear here as they are heard.") if self._live
                             else self.tr("Open an audio file to decode."))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
