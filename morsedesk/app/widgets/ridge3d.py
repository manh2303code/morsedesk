"""Phong cảnh phổ 3D: các đường sống núi phối cảnh, màu theo độ cao — kiểu "3D waterfall" của SDR.

Vẽ bằng QPainter chứ không bằng OpenGL: máy air-gap và máy ảo thường không có driver OpenGL, và
một cảnh vài chục dải x vài trăm điểm vẽ được dưới 10 ms bằng đường dẫn thường.

Mỗi hàng của mặt `Z` (0..1) là một dải. Dải ở sau nhỏ và cao hơn trên màn hình, dải ở trước to và
thấp hơn; vẽ từ sau ra trước, mỗi dải tô kín phần dưới nên che dải phía sau — đó là thứ cho cảm giác
khối. Màu tô là dải màu phổ chung, neo theo ĐỘ CAO của chính dải đó: chân dải chìm vào nền đêm,
đỉnh lên vàng rồi đỏ.

Cả hai trang dùng CÙNG một cảnh: ngang là thời gian (trái sang phải), sâu là tần số ±250 Hz quanh
tone, nên các dấu Morse nhô lên thành một dãy khối đọc được bằng mắt. Khung thời gian do
`signal_view.Timeline` quyết (đèn ghim giữa khi nghe lại, ở mép phải khi nghe trực tiếp); cột
được đặt theo vị trí thời gian thật `xs`, nên cảnh trôi mượt từng điểm ảnh chứ không nhảy từng cột.
Phần bên phải đèn (chưa nghe tới) chìm xuống; đèn có thể nằm ngoài khung khi người dùng lướt đi
xem đoạn khác — khi đó không vẽ đèn, nhưng phần đã/chưa nghe vẫn đúng.

Rê chuột: điểm trên mặt cảnh dưới mũi chuột chọn theo đúng thứ tự che khuất (dải trước che dải sau),
tô sáng dải đó + cột thời gian trên sàn + một cọc tới đỉnh; `describe(giây, Hz, dB)` của trang nói
điểm đó là gì. Kéo/lăn để lướt, bấm để nghe từ đó (signal_view.TimelineCanvas). Phần cảnh vẽ vào
ảnh đệm: rê chuột chỉ vẽ lại lớp trên.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
from pyqtgraph.functions import arrayToQPath, arrayToQPolygonF
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QSizePolicy

from morsedesk.app.theme import LAMP, LINE, MUTED, NIGHT, PANEL, READOUT_FONT, spectrum_stops
from morsedesk.app.widgets.hover_readout import HoverReadout, Line
from morsedesk.app.widgets.signal_strip import edge_align, edge_label_rect
from morsedesk.app.widgets.signal_view import TimelineCanvas

SUBMERGED = 0.12        # phần chưa nghe tới: còn 12 % chiều cao, đủ thấy hình, rõ là "chưa tới"
RISE_WIDTH = 0.02       # dốc nổi lên ngay sau con trỏ phát (tỉ lệ bề ngang cảnh)
# Tô mỗi dải thành nhiều đa giác ~32 cột thay vì một đa giác 377 đỉnh: bộ tô của Qt tốn theo số
# cạnh trên mỗi dòng quét, đo 25/09 (17 dải x 377 cột, 1150 x 350 px): một khối 28 ms, 12 khối
# 11 ms, hình giống hệt (không khử răng cưa nên các khối liền mép không lộ đường nối).
FILL_CHUNK_COLS = 32


class Ridge3DView(TimelineCanvas):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._z = np.zeros((0, 0), np.float32)
        self._xs = np.zeros(0, np.float32)
        self._times: np.ndarray | None = None
        self._freqs: np.ndarray | None = None
        self._rel: np.ndarray | None = None
        self.front_ticks: list[tuple[float, str]] = []   # (vị trí 0..1 dọc mép trước, nhãn)
        self.depth_label = ""
        self.placeholder = ""
        self._playhead: float | None = None     # vị trí đèn trong khung (có thể ngoài 0..1); None = không phát
        self.ahead_level = SUBMERGED
        self.rise_width = RISE_WIDTH
        # Trang đặt: (giây, Hz, dB trên nền) -> các dòng của ô số đo.
        self.describe: Callable[[float, float, float], list[Line]] | None = None
        self._hover: tuple[int, int] | None = None
        self._mouse: QPoint | None = None
        self._cache: QPixmap | None = None
        self.last_paint_ms = 0.0             # vẽ lại cả cảnh lần gần nhất (ngân sách vẽ của khối Tín hiệu)
        self.readout = HoverReadout(self)
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._stops = [(p, QColor(c)) for p, c in spectrum_stops()]

    # ---- dữ liệu ----
    def set_surface(self, z: np.ndarray, xs: np.ndarray | None = None, times: np.ndarray | None = None,
                    freqs: np.ndarray | None = None, rel_db: np.ndarray | None = None) -> None:
        """Mặt [hàng, cột] 0..1 (hàng 0 = tần số cao nhất, ở sau cùng). `xs`: vị trí 0..1 của từng cột
        trong khung (mặc định trải đều); `times`/`freqs`/`rel_db`: để nói điểm dưới chuột là gì."""
        self._z = np.asarray(z, dtype=np.float32)
        n = self._z.shape[1] if self._z.ndim == 2 else 0
        self._xs = np.linspace(0.0, 1.0, n).astype(np.float32) if xs is None else np.asarray(xs, np.float32)
        self._times, self._freqs, self._rel = times, freqs, rel_db
        self._invalidate()
        if self._mouse is not None:
            self._hover_at(self._mouse)

    def surface(self) -> np.ndarray:
        return self._z

    def xs(self) -> np.ndarray:
        return self._xs

    def set_playhead(self, frac: float | None) -> None:
        """Vị trí đèn trong khung: phần bên trái nổi đủ cao, bên phải chìm. None = hiện đủ cả cảnh."""
        ph = None if frac is None else float(frac)
        if ph == self._playhead:
            return
        self._playhead = ph
        self._invalidate()

    def playhead(self) -> float | None:
        return self._playhead

    def heights(self, z: np.ndarray) -> np.ndarray:
        """Chiều cao thực vẽ: z nhân hệ số theo vị trí so với đèn."""
        if self._playhead is None or z.size == 0:
            return z
        xs = self._xs if len(self._xs) == z.shape[1] else np.linspace(0.0, 1.0, z.shape[1])
        ramp = np.clip((self._playhead - xs) / max(self.rise_width, 1e-6), 0.0, 1.0)  # 1 = đã qua
        return z * (self.ahead_level + (1.0 - self.ahead_level) * ramp)[None, :]

    def clear(self) -> None:
        self._z = np.zeros((0, 0), np.float32)
        self._xs = np.zeros(0, np.float32)
        self._times = self._freqs = self._rel = None
        self._playhead = None
        self.front_ticks = []
        self.depth_label = ""
        self._invalidate()
        self._hover_at(None)

    # ---- chuột ----
    def axis_px(self) -> float:
        return self._row_geometry(1.0)[1]          # kéo ở mép trước: cảnh đi đúng theo tay

    def _nearest_col(self, f: float) -> int:
        i = int(np.searchsorted(self._xs, f))
        if i >= len(self._xs) or (i > 0 and f - self._xs[i - 1] < self._xs[i] - f):
            i -= 1
        return max(0, i)

    def cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        """Điểm (hàng, cột) của mặt cảnh THẤY ĐƯỢC tại (x, y): dò từ dải trước ra sau, dải đầu tiên
        có phần tô chứa điểm đó là dải đang che. Vệt sàn ngay trước chân mỗi dải thuộc về dải đó,
        nên rê trên nền phẳng không có khe chết."""
        z = self._z
        if z.ndim != 2 or z.shape[0] < 2 or z.shape[1] < 1:
            return None
        h = self.heights(z)
        n_rows = z.shape[0]
        spacing = self._row_geometry(1.0)[2] - self._row_geometry(1.0 - 1.0 / (n_rows - 1))[2]
        tol = min(3.0, spacing / 2)
        for r in range(n_rows - 1, -1, -1):
            left, width, base, amp = self._row_geometry(r / (n_rows - 1))
            f = (x - left) / width
            if not 0.0 <= f <= 1.0:
                continue
            c = self._nearest_col(f)
            top = base - float(h[r, c]) * amp
            if top - tol <= y <= base + spacing / 2:
                return r, c
        return None

    def frac_at(self, pos: QPoint) -> float | None:
        """Bấm lên mặt cảnh: thời điểm của cột đó; bấm chỗ khác trong khung: theo mép trước."""
        cell = self.cell_at(pos.x(), pos.y())
        if cell is not None:
            return float(self._xs[cell[1]])
        left, width, _, _ = self._row_geometry(1.0)
        f = (pos.x() - left) / width
        return f if 0.0 <= f <= 1.0 and self._z.size else None

    def hover(self) -> tuple[int, int] | None:
        return self._hover

    def hover_at(self, pos: QPoint | None) -> None:
        """Như rê chuột tới `pos` (None = chuột rời đi) — cho test và ảnh chụp."""
        self._hover_at(pos)

    def _hover_at(self, pos: QPoint | None) -> None:
        self._mouse = pos
        cell = None if pos is None or self.dragging() else self.cell_at(pos.x(), pos.y())
        self._hover = cell
        lines: list[Line] = []
        if cell is not None and self.describe is not None and self._times is not None:
            r, c = cell
            rel = float(self._rel[r, c]) if self._rel is not None else float("nan")
            if np.isfinite(rel):
                lines = self.describe(float(self._times[c]), float(self._freqs[r]), rel)
        self.readout.show_lines(lines, pos or QPoint())
        self.update()

    def _invalidate(self) -> None:
        self._cache = None
        self.update()

    def resizeEvent(self, event) -> None:
        self._cache = None
        super().resizeEvent(event)

    # ---- hình học ----
    def _frame(self) -> tuple[float, float, float, float]:
        m = 14.0
        return m, m, self.width() - 2 * m, self.height() - 2 * m - 16

    def _row_geometry(self, t: float) -> tuple[float, float, float, float]:
        """Với độ sâu t (0 sau, 1 trước): (x trái, bề rộng, đường chân, biên độ)."""
        x0, y0, w, h = self._frame()
        width = w * (0.62 + 0.38 * t)
        left = x0 + (w - width) / 2
        base = y0 + h * (0.46 + 0.54 * t)
        amp = h * 0.52 * (0.60 + 0.40 * t)
        return left, width, base, amp

    def _gradient(self, base: float, amp: float) -> QLinearGradient:
        g = QLinearGradient(0.0, base, 0.0, base - amp)
        for p, c in self._stops:
            g.setColorAt(p, c)
        return g

    # ---- vẽ ----
    def sizeHint(self) -> QSize:
        return QSize(640, 240)

    def paintEvent(self, event) -> None:
        dpr = self.devicePixelRatioF()
        if self._cache is None or self._cache.size() != self.size() * dpr:
            self._cache = QPixmap(self.size() * dpr)
            self._cache.setDevicePixelRatio(dpr)
            cp = QPainter(self._cache)
            started = time.perf_counter()
            self._paint_scene(cp)
            cp.end()
            self.last_paint_ms = (time.perf_counter() - started) * 1000.0
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cache)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._z
        if z.size == 0 or z.shape[0] < 2:
            if self.placeholder:
                p.setPen(QColor(MUTED))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
        else:
            if self._hover is not None:
                self._draw_pick(p, self._hover[0], self._hover[1])
            self._draw_labels(p)
        p.end()

    def _paint_scene(self, p: QPainter) -> None:
        """Nền, sàn, các dải và luồng sáng — phần đắt, vẽ vào ảnh đệm."""
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, QColor(NIGHT))
        bg.setColorAt(1.0, QColor(PANEL))
        p.fillRect(self.rect(), QBrush(bg))
        self._draw_floor(p)
        z = self._z
        if z.size == 0 or z.shape[0] < 2:
            return
        z = self.heights(z)
        n_rows = z.shape[0]
        xs = self._xs
        edge = QPen(QColor(230, 240, 255, 150))
        edge.setCosmetic(True)       # bút 1 px không khử răng cưa: viền khử răng cưa tốn 92 ms/khung
        # Đường dẫn dựng thẳng từ mảng numpy (arrayToQPath), và KHÔNG khử răng cưa: đo trên cảnh
        # 16 x 360 ở tỉ lệ 150 %, viền khử răng cưa tốn 92 ms/khung còn phần tô gradient chỉ 17 ms.
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        n_cols = z.shape[1]
        bounds = list(range(0, n_cols - 1, FILL_CHUNK_COLS)) + [n_cols - 1]
        for r in range(n_rows):
            t = r / (n_rows - 1)
            left, width, base, amp = self._row_geometry(t)
            px = left + width * xs
            py = base - z[r] * amp
            ridge = arrayToQPath(px, py)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self._gradient(base, amp)))
            for a, b in zip(bounds[:-1], bounds[1:], strict=True):
                p.drawPolygon(arrayToQPolygonF(np.concatenate([px[a:b + 1], [px[b], px[a]]]),
                                               np.concatenate([py[a:b + 1], [base, base]])))
            edge.setColor(QColor(230, 240, 255, int(60 + 120 * t)))
            p.setPen(edge)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ridge)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._playhead is not None and 0.0 <= self._playhead <= 1.0:
            self._draw_beam(p, self._playhead)

    def _draw_pick(self, p: QPainter, row: int, col: int) -> None:
        """Điểm đang xem: cột thời gian kẻ trên sàn (sau ra trước), dải tần của nó sáng lên, và một
        cọc từ chân tới đỉnh có chấm đèn."""
        z = self._z
        n_rows = z.shape[0]
        h = self.heights(z)
        fc = float(self._xs[col])
        lamp = QColor(LAMP)
        bl, bw, bb, _ = self._row_geometry(0.0)
        fl, fw, fb, _ = self._row_geometry(1.0)
        floor = QPen(QColor(lamp.red(), lamp.green(), lamp.blue(), 150))
        floor.setWidthF(1.0)
        floor.setStyle(Qt.PenStyle.DashLine)
        p.setPen(floor)
        p.drawLine(QPointF(bl + bw * fc, bb), QPointF(fl + fw * fc, fb))
        left, width, base, amp = self._row_geometry(row / (n_rows - 1))
        ridge = arrayToQPath(left + width * self._xs, base - h[row] * amp)
        pen = QPen(QColor(lamp.red(), lamp.green(), lamp.blue(), 210))
        pen.setWidthF(2.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)     # đường khử răng cưa: ~5 ms mỗi lần rê
        p.drawPath(ridge)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x = left + width * fc
        top = base - float(h[row, col]) * amp
        pin = QPen(QColor(255, 241, 204, 220))
        pin.setWidthF(1.4)
        p.setPen(pin)
        p.drawLine(QPointF(x, base), QPointF(x, top))
        p.setPen(QPen(QColor(NIGHT), 1.5))
        p.setBrush(lamp)
        p.drawEllipse(QPointF(x, top), 4.5, 4.5)

    def _draw_beam(self, p: QPainter, ph: float) -> None:
        """Luồng sáng như đèn chiếu từ trên xuống, đi theo con trỏ phát, cộng vạch quét trên sàn."""
        bl, bw, bb, _ = self._row_geometry(0.0)
        fl, fw, fb, _ = self._row_geometry(1.0)
        xb, xf = bl + bw * ph, fl + fw * ph
        top_x = xb + (xb - xf) * 0.25              # nguồn sáng hơi lệch về phía sau, trên cao
        cone = QPolygonF([QPointF(top_x - 4, 0.0), QPointF(top_x + 4, 0.0),
                          QPointF(xf + 34, fb), QPointF(xb + 16, bb), QPointF(xb - 16, bb),
                          QPointF(xf - 34, fb)])
        g = QLinearGradient(0.0, 0.0, 0.0, fb)
        g.setColorAt(0.0, QColor(255, 236, 190, 0))
        g.setColorAt(1.0, QColor(255, 214, 140, 70))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawPolygon(cone)
        glow = QPen(QColor(245, 165, 36, 90))
        glow.setWidthF(7.0)
        glow.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(glow)
        p.drawLine(QPointF(xb, bb), QPointF(xf, fb))
        line = QPen(QColor(255, 214, 140, 230))
        line.setWidthF(1.6)
        p.setPen(line)
        p.drawLine(QPointF(xb, bb), QPointF(xf, fb))

    def _draw_floor(self, p: QPainter) -> None:
        """Sàn: đường dọc hội tụ về phía sau ĐẶT Ở CÁC VẠCH THỜI GIAN, nên sàn trôi cùng cảnh."""
        pen = QPen(QColor(LINE))
        pen.setWidthF(1.0)
        p.setPen(pen)
        back = self._row_geometry(0.0)
        front = self._row_geometry(1.0)
        fracs = [f for f, _ in self.front_ticks] or [i / 8 for i in range(9)]
        for f in fracs:
            if 0.0 <= f <= 1.0:
                p.drawLine(QPointF(back[0] + back[1] * f, back[2]), QPointF(front[0] + front[1] * f, front[2]))
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            left, width, base, _ = self._row_geometry(t)
            p.drawLine(QPointF(left, base), QPointF(left + width, base))

    def _draw_labels(self, p: QPainter) -> None:
        f = QFont(READOUT_FONT)
        f.setPixelSize(11)
        p.setFont(f)
        p.setPen(QColor(MUTED))
        left, width, base, _ = self._row_geometry(1.0)
        for pos, text in self.front_ticks:
            if not 0.0 <= pos <= 1.0:
                continue
            x = left + width * pos
            p.drawLine(QPointF(x, base), QPointF(x, base + 4))
            p.drawText(edge_label_rect(x, base + 4, 14, 0.0, float(self.width())),
                       edge_align(x, 0.0, float(self.width())), text)
        if self.depth_label:          # góc trên trái, không đè lên các dải phía sau
            p.drawText(QRectF(14, 6, self.width() - 28, 14), Qt.AlignmentFlag.AlignLeft, self.depth_label)
