"""Phổ 2D (0–2000 Hz) trong CÙNG khung thời gian với cảnh 3D: dùng cho cả trang Giải mã lẫn trang Nghe.

Thay cho biểu đồ phổ pyqtgraph (cả file một lúc) ở trang Giải mã và thác nước cuộn riêng ở trang
Nghe (25/09, người dùng: "3D hay spectrogram, và khi con trỏ chạy thì view phải chạy theo"). Hai
biểu đồ đọc chung `signal_view.Timeline`, nên đổi 3D <-> 2D vẫn đúng đoạn đang xem; cùng cách lướt
(kéo, lăn) và cùng "bấm để nghe từ đó".

Vẽ bằng một QImage nhỏ (65 bin x vài trăm cột) phóng lên khung, cột đặt theo thời gian thật nên
trôi mượt từng điểm ảnh. Lớp trên: vạch tone, vạch + tên từ đã giải, vạch thời gian, con trỏ phát
(phần chưa nghe tới tối đi như cảnh 3D chìm xuống), chữ thập + ô số đo khi rê chuột.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy

from morsedesk.app.theme import LAMP, MUTED, NIGHT, READOUT_FONT, TEXT, spectrum_rgb
from morsedesk.app.widgets.hover_readout import HoverReadout, Line
from morsedesk.app.widgets.signal_view import TimelineCanvas

AXIS_H = 18             # dải vạch thời gian dưới ảnh
AHEAD_DIM = 150         # độ mờ (0..255) phủ lên phần chưa nghe tới


EDGE_PX = 40            # nhãn vạch thời gian sát mép: căn vào trong thay vì bị cắt mất nửa


def edge_align(x: float, left: float, right: float) -> Qt.AlignmentFlag:
    if x - left < EDGE_PX:
        return Qt.AlignmentFlag.AlignLeft
    if right - x < EDGE_PX:
        return Qt.AlignmentFlag.AlignRight
    return Qt.AlignmentFlag.AlignHCenter


def edge_label_rect(x: float, y: float, h: float, left: float, right: float) -> QRectF:
    if x - left < EDGE_PX:
        return QRectF(left, y, 2 * EDGE_PX, h)
    if right - x < EDGE_PX:
        return QRectF(right - 2 * EDGE_PX, y, 2 * EDGE_PX, h)
    return QRectF(x - EDGE_PX, y, 2 * EDGE_PX, h)


class SignalStrip(TimelineCanvas):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._img: QImage | None = None
        self._rgb: np.ndarray | None = None      # giữ bộ nhớ của QImage sống cùng nó
        self._xs = np.zeros(0, np.float32)
        self._times: np.ndarray | None = None
        self._freqs: np.ndarray | None = None
        self._rel: np.ndarray | None = None
        self.max_hz = 2000.0
        self.ticks: list[tuple[float, str]] = []
        self.words: list[tuple[float, str]] = []     # (vị trí 0..1, chữ) của từ bắt đầu trong khung
        self.tone_hz: float | None = None
        self.hz_unit = "Hz"
        self.placeholder = ""
        self._cursor: float | None = None
        self.dim_ahead = True
        self.describe: Callable[[float, float, float], list[Line]] | None = None
        self._mouse: QPoint | None = None
        self._hover: tuple[int, int] | None = None
        self.readout = HoverReadout(self)
        self.last_paint_ms = 0.0
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ---- dữ liệu ----
    def set_image(self, z: np.ndarray, xs: np.ndarray, times: np.ndarray, freqs: np.ndarray,
                  rel_db: np.ndarray) -> None:
        """`z` [bin, cột] 0..1 với bin 0 = 0 Hz; `xs` vị trí 0..1 từng cột trong khung."""
        z = np.asarray(z, np.float32)
        if z.size == 0:
            self.clear()
            return
        self._rgb = np.ascontiguousarray(spectrum_rgb(z[::-1]))       # hàng trên = tần số cao
        h, w = z.shape
        self._img = QImage(self._rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._xs = np.asarray(xs, np.float32)
        self._times, self._freqs, self._rel = times, freqs, rel_db
        self.max_hz = float(freqs[-1]) if len(freqs) else self.max_hz
        if self._mouse is not None:
            self._hover_at(self._mouse)
        self.update()

    def has_image(self) -> bool:
        return self._img is not None

    def set_cursor(self, frac: float | None) -> None:
        if frac != self._cursor:
            self._cursor = frac
            self.update()

    def cursor(self) -> float | None:
        return self._cursor

    def clear(self) -> None:
        self._img = self._rgb = None
        self._xs = np.zeros(0, np.float32)
        self._times = self._freqs = self._rel = None
        self._cursor = None
        self.ticks, self.words, self.tone_hz = [], [], None
        self._hover_at(None)

    # ---- hình học ----
    def plot_rect(self) -> QRectF:
        return QRectF(0, 0, self.width(), max(1, self.height() - AXIS_H))

    def axis_px(self) -> float:
        return self.plot_rect().width()

    def frac_at(self, pos: QPoint) -> float | None:
        r = self.plot_rect()
        if self._img is None or not (0 <= pos.x() <= r.right() and 0 <= pos.y() <= self.height()):
            return None
        return (pos.x() - r.left()) / r.width()

    def _y_of(self, hz: float) -> float:
        r = self.plot_rect()
        return r.bottom() - r.height() * min(max(hz, 0.0), self.max_hz) / self.max_hz

    # ---- rê chuột ----
    def hover(self) -> tuple[int, int] | None:
        return self._hover

    def hover_at(self, pos: QPoint | None) -> None:
        self._hover_at(pos)

    def _hover_at(self, pos: QPoint | None) -> None:
        self._mouse = pos
        self._hover = None
        lines: list[Line] = []
        r = self.plot_rect()
        if (pos is not None and not self.dragging() and self._img is not None and len(self._xs)
                and r.contains(QPointF(pos))):
            f = (pos.x() - r.left()) / r.width()
            col = int(np.abs(self._xs - f).argmin())
            hz = (r.bottom() - pos.y()) / r.height() * self.max_hz
            row = int(np.abs(self._freqs - hz).argmin())
            rel = float(self._rel[row, col])
            self._hover = (row, col)
            if np.isfinite(rel) and self.describe is not None:
                lines = self.describe(float(self._times[col]), hz, rel)
        self.readout.show_lines(lines, pos or QPoint())
        self.update()

    # ---- vẽ ----
    def sizeHint(self) -> QSize:
        return QSize(640, 240)

    def paintEvent(self, event) -> None:
        started = time.perf_counter()
        p = QPainter(self)
        try:
            p.fillRect(self.rect(), QColor(NIGHT))
            r = self.plot_rect()
            if self._img is None:
                if self.placeholder:
                    p.setPen(QColor(MUTED))
                    p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.placeholder)
                return
            dx = float(self._xs[1] - self._xs[0]) if len(self._xs) > 1 else 1.0
            x0 = r.left() + (float(self._xs[0]) - dx / 2) * r.width()
            x1 = r.left() + (float(self._xs[-1]) + dx / 2) * r.width()
            p.save()
            p.setClipRect(r)
            p.drawImage(QRectF(x0, r.top(), x1 - x0, r.height()), self._img)
            if self._cursor is not None and self.dim_ahead and self._cursor < 1.0:
                cx = r.left() + max(0.0, self._cursor) * r.width()
                p.fillRect(QRectF(cx, r.top(), r.right() - cx, r.height()), QColor(14, 22, 39, AHEAD_DIM))
            self._paint_marks(p, r)
            p.restore()
            self._paint_axis(p, r)
            self._paint_pointer(p, r)
        finally:
            p.end()
            self.last_paint_ms = (time.perf_counter() - started) * 1000.0

    def _paint_marks(self, p: QPainter, r: QRectF) -> None:
        f = QFont(READOUT_FONT)
        f.setPixelSize(11)
        p.setFont(f)
        # Thang tần số bên trái: không có nó thì phổ chỉ là hình trang trí.
        p.setPen(QPen(QColor(230, 230, 230, 150)))
        for hz in (500, 1000, 1500):
            y = self._y_of(hz)
            p.drawLine(QPointF(r.left(), y), QPointF(r.left() + 6, y))
            p.drawText(QPointF(r.left() + 9, y + 4), f"{hz}")
        lamp = QColor(LAMP)
        if self.tone_hz:
            y = self._y_of(self.tone_hz)
            pen = QPen(QColor(lamp.red(), lamp.green(), lamp.blue(), 170))
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        # Từ đã giải: vạch mảnh ở chỗ bắt đầu + tên từ trên đỉnh — biết ngay mình đang ở đoạn nào.
        for frac, text in self.words:
            x = r.left() + frac * r.width()
            p.setPen(QPen(QColor(255, 255, 255, 70)))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QColor(TEXT))
            p.drawText(QPointF(x + 4, r.top() + 13), text)
        if self._cursor is not None and 0.0 <= self._cursor <= 1.0:
            x = r.left() + self._cursor * r.width()
            glow = QPen(QColor(245, 165, 36, 90))
            glow.setWidthF(6.0)
            p.setPen(glow)
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QPen(QColor(255, 214, 140, 235), 1.6))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))

    def _paint_axis(self, p: QPainter, r: QRectF) -> None:
        p.setPen(QColor(MUTED))
        for frac, text in self.ticks:
            if not 0.0 <= frac <= 1.0:
                continue
            x = r.left() + frac * r.width()
            p.drawLine(QPointF(x, r.bottom()), QPointF(x, r.bottom() + 4))
            p.drawText(edge_label_rect(x, r.bottom() + 3, AXIS_H - 3, r.left(), r.right()),
                       edge_align(x, r.left(), r.right()), text)
        if self.tone_hz:
            y = self._y_of(self.tone_hz)
            label = f"{self.tone_hz:.0f} {self.hz_unit}"
            box = QRectF(r.right() - 76, max(r.top() + 2, y - 20), 72, 16)
            p.fillRect(box, QColor(14, 22, 39, 200))           # nền tối: nhãn không lẫn vào vệt tín hiệu
            p.setPen(QColor(LAMP))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_pointer(self, p: QPainter, r: QRectF) -> None:
        if self._hover is None or self._mouse is None:
            return
        pen = QPen(QColor(255, 255, 255, 110))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawLine(QPointF(self._mouse.x(), r.top()), QPointF(self._mouse.x(), r.bottom()))
        p.drawLine(QPointF(r.left(), self._mouse.y()), QPointF(r.right(), self._mouse.y()))
