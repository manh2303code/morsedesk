"""Khung nhìn thời gian dùng chung cho cảnh 3D và phổ 2D: bám con trỏ, kéo/lăn để lướt, bấm để nghe.

Người dùng 25/09: "cố định góc nhìn — trừ 6 s đầu và 6 s cuối của đoạn audio thì đèn chạy từ đầu
vào giữa và từ giữa ra cuối — còn hầu như khi nghe lại thì đoạn đã nghe nằm hết nửa bên trái, đoạn
chưa nghe yên ắng bên phải, đèn chiếu xuống chính giữa". Tức kiểu "đầu phát ghim giữa" (Audacity
gọi là Pinned Play Head): khung dài `span` bám con trỏ t theo

    t0 = kẹp(t − span/2, đầu dữ liệu, cuối dữ liệu − span)

nên đèn ở giữa, trừ nửa khung đầu và nửa khung cuối. Trang Nghe dùng ĐÚNG công thức với "cuối dữ
liệu" = bây giờ: 12 s đầu đèn đi từ trái sang phải, sau đó đèn đứng ở mép phải (không có tương lai
để hiện bên phải) và cảnh trôi sang trái.

Người dùng lướt (kéo hoặc lăn chuột) thì khung thôi bám — không giật về giữa lúc đang xem đoạn cũ —
cho tới khi bấm nút "Theo con trỏ"/"Về trực tiếp", bấm vào biểu đồ, bấm một từ hay bấm phát.
Cả hai biểu đồ đọc CÙNG một `Timeline`, nên đổi qua lại 3D/2D vẫn đúng đoạn đang xem.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtWidgets import QWidget

WINDOW_S = 12.0
WHEEL_FRAC = 1.0 / 6.0      # một nấc lăn chuột = 1/6 khung (2 s)
DRAG_PX = 4                 # dưới ngưỡng này là bấm, không phải kéo


class Timeline(QObject):
    changed = Signal()
    follow_changed = Signal(bool)

    def __init__(self, span_s: float = WINDOW_S, parent=None) -> None:
        super().__init__(parent)
        self.span_s = span_s
        self._lo = self._hi = 0.0
        self._fit = True
        self._t0 = 0.0
        self._cursor: float | None = None
        self._follow = True

    # ---- trạng thái ----
    def reset(self, lo: float = 0.0, hi: float = 0.0, fit: bool = True) -> None:
        """Nguồn mới. `fit`: file ngắn hơn khung thì khung co bằng file (trang Giải mã); trang Nghe
        giữ khung 12 s ngay từ đầu (phần bên phải là tương lai, còn trống)."""
        self._lo, self._hi, self._fit = float(lo), float(hi), fit
        self._t0 = self._lo
        self._cursor = None
        self._set_follow(True)
        self.changed.emit()

    def span(self) -> float:
        if self._fit and self._hi > self._lo:
            return min(self.span_s, self._hi - self._lo)
        return self.span_s

    def t0(self) -> float:
        return self._t0

    def window(self) -> tuple[float, float]:
        return self._t0, self._t0 + self.span()

    def data_range(self) -> tuple[float, float]:
        return self._lo, self._hi

    def cursor(self) -> float | None:
        return self._cursor

    def following(self) -> bool:
        return self._follow

    def frac(self, t: float) -> float:
        return (t - self._t0) / self.span()

    def time_at(self, frac: float) -> float:
        return self._t0 + frac * self.span()

    # ---- thay đổi ----
    def update(self, lo: float | None = None, hi: float | None = None, cursor: float | None = ...) -> None:
        """Đổi dải dữ liệu và/hoặc con trỏ trong MỘT lần (một lần vẽ lại). `cursor=None` = không phát."""
        if lo is not None:
            self._lo = float(lo)
        if hi is not None:
            self._hi = float(hi)
        if cursor is not ...:
            self._cursor = cursor
        if self._follow and self._cursor is not None:
            self._t0 = self._clamp(self._cursor - self.span() / 2)
        else:
            self._t0 = self._clamp(self._t0)
        self.changed.emit()

    def set_cursor(self, t: float | None) -> None:
        self.update(cursor=t)

    def pan(self, dt: float) -> None:
        """Người dùng lướt: dời khung `dt` giây và thôi bám con trỏ (nếu khung thật sự dời)."""
        t0 = self._clamp(self._t0 + dt)
        if abs(t0 - self._t0) < 1e-9:
            return
        self._t0 = t0
        self._set_follow(False)
        self.changed.emit()

    def center_on(self, t: float) -> None:
        self._t0 = self._clamp(t - self.span() / 2)
        self._set_follow(False)
        self.changed.emit()

    def set_follow(self, on: bool = True) -> None:
        self._set_follow(on)
        self.update()

    def _set_follow(self, on: bool) -> None:
        if on != self._follow:
            self._follow = on
            self.follow_changed.emit(on)

    def _clamp(self, t0: float) -> float:
        return min(max(t0, self._lo), max(self._lo, self._hi - self.span()))


def time_ticks(t0: float, span: float, unit: str) -> list[tuple[float, str]]:
    """Vạch thời gian trong khung [t0, t0 + span): (vị trí 0..1, nhãn). Dưới 1 phút ghi "12 s",
    từ 1 phút ghi "1:04" như đồng hồ thanh phát."""
    step = 1 if span <= 6 else 2 if span <= 15 else 5 if span <= 40 else 10
    k = int(-(-t0 // step))
    out = []
    while k * step <= t0 + span + 1e-6:
        t = k * step
        out.append(((t - t0) / span, f"{t:g} {unit}" if t < 60 else f"{int(t) // 60}:{int(t) % 60:02d}"))
        k += 1
    return out


def clock(t: float, unit: str) -> str:
    """Thời điểm trong ô số đo: "12.40 s", từ 1 phút "1:23.4"."""
    if t < 60:
        return f"{t:.2f} {unit}"
    m, s = divmod(t, 60.0)
    return f"{int(m)}:{s:04.1f}"


class TimelineCanvas(QWidget):
    """Nền chung của hai biểu đồ: kéo = lướt, lăn = lướt, bấm (không kéo) = nghe từ đó.

    Lớp con cho biết `axis_px()` (số điểm ảnh ứng với cả khung, để kéo dời đúng theo tay) và
    `frac_at(pos)` (vị trí 0..1 trong khung dưới điểm bấm, None nếu ngoài vùng vẽ), và vẽ ô số đo
    khi rê chuột trong `_hover_at(pos | None)`.
    """

    pan_requested = Signal(float)       # dời khung: phần của khung, dương = về sau
    seek_requested = Signal(float)      # bấm tại vị trí 0..1 của khung

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._press: QPoint | None = None
        self._last_x = 0
        self._dragging = False

    def axis_px(self) -> float:
        return float(max(1, self.width()))

    def frac_at(self, pos: QPoint) -> float | None:
        return None

    def _hover_at(self, pos: QPoint | None) -> None:
        pass

    def dragging(self) -> bool:
        return self._dragging

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
            self._last_x = self._press.x()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._dragging and abs(pos.x() - self._press.x()) > DRAG_PX:
                self._dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._hover_at(None)
            if self._dragging:
                dx = pos.x() - self._last_x
                self._last_x = pos.x()
                if dx:
                    self.pan_requested.emit(-dx / self.axis_px())       # nội dung đi theo tay
                return
        self._hover_at(pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            if not self._dragging:
                f = self.frac_at(event.position().toPoint())
                if f is not None:
                    self.seek_requested.emit(f)
            self._press = None
            self._dragging = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._hover_at(event.position().toPoint())
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        d = event.angleDelta()
        steps = (d.y() if abs(d.y()) >= abs(d.x()) else -d.x()) / 120.0
        if steps:
            self.pan_requested.emit(-steps * WHEEL_FRAC)            # lăn xuống = về sau
            event.accept()
            return
        super().wheelEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._dragging:
            self._hover_at(None)
        super().leaveEvent(event)
