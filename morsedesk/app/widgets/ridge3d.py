"""Phong cảnh phổ 3D: các đường sống núi phối cảnh, màu theo độ cao — kiểu "3D waterfall" của SDR.

Vẽ bằng QPainter chứ không bằng OpenGL: máy air-gap và máy ảo thường không có driver OpenGL, và
một cảnh vài chục dải x vài trăm điểm vẽ được dưới 10 ms bằng đường dẫn thường.

Mỗi hàng của mặt `Z` (0..1) là một dải. Dải ở sau nhỏ và cao hơn trên màn hình, dải ở trước to và
thấp hơn; vẽ từ sau ra trước, mỗi dải tô kín phần dưới nên che dải phía sau — đó là thứ cho cảm giác
khối. Màu tô là dải màu phổ chung, neo theo ĐỘ CAO của chính dải đó: chân dải chìm vào nền đêm,
đỉnh lên vàng rồi đỏ.

Cả hai trang dùng CÙNG một cảnh: ngang là thời gian (trái sang phải), sâu là tần số quanh tone
(±250 Hz), nên các dấu Morse nhô lên thành một dãy khối đọc được bằng mắt.
- Trang Giải mã: `set_surface` một cửa sổ 12 s của file; khi nghe lại, `set_playhead` quét luồng
  sáng từ trái sang phải, phần chưa nghe tới chìm xuống.
- Trang Nghe (từ 25/09, người dùng: "realtime nhưng theo chiều từ trái sang phải thay vì cứ chạy ra
  sau"): quét như màn hình điện tim — luồng sáng là đầu ghi, đi từ trái sang phải rồi quay lại đầu;
  phía trước nó là lượt quét trước, hạ thấp (`ahead_level`) và có khe trống (`gap_width`) để thấy
  ngay đâu là mới. Dữ liệu do `live_sweep.LiveSweep` dựng. Trước đó cảnh này cuộn theo chiều sâu
  (hàng mới ở trước, cũ lùi ra sau).

Rê chuột (người dùng 25/09): điểm trên mặt cảnh dưới mũi chuột được chọn theo đúng thứ tự che khuất
(dải trước che dải sau), tô sáng dải tần đó + cột thời gian trên sàn + một cọc tới đỉnh; `describe`
của trang nói điểm đó là gì (hover_readout). Phần cảnh vẽ vào ảnh đệm, nên rê chuột chỉ vẽ lại lớp
trên chứ không vẽ lại cả cảnh.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from pyqtgraph.functions import arrayToQPath
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from morsedesk.app.theme import LAMP, LINE, MUTED, NIGHT, PANEL, READOUT_FONT, spectrum_stops
from morsedesk.app.widgets.hover_readout import HoverReadout, Line

MAX_COLS = 240
SUBMERGED = 0.12        # phần chưa nghe tới: còn 12 % chiều cao, đủ thấy hình, rõ là "chưa tới"
RISE_WIDTH = 0.02       # dốc nổi lên ngay sau con trỏ phát (tỉ lệ bề ngang cảnh)
# Dải động hiển thị tối đa: file SẠCH (khoảng lặng là số 0, như ba file mẫu) có nền -120 dB, chuẩn
# hóa từ đó thì đuôi phổ của cửa sổ Hann cũng nhô cao như tín hiệu và khối Morse nhòe thành đồi.
# 30 dB ~ khoảng cách đỉnh-nền (mỗi bin) của một bản tin SNR 15 dB: file sạch trông gọn như file có
# nhiễu. Gai nhỏ còn lại ở mép mỗi dấu là dải biên THẬT của sườn bật/tắt 5 ms, không phải nhiễu.
MAX_RANGE_DB = 30.0
# Mức "trên nền nhiễu" khi rê chuột: kẹp 0..60 dB, như phổ 2D (dB tương đối kẹp ở DB_FLOOR -60).
# File sạch có nền số 0 (-120 dB): không kẹp thì ô số đo nói "+154 dB" — đúng số học, vô nghĩa.
REL_CAP_DB = 60.0


@dataclass
class BandScene:
    """Mặt cảnh 3D + những gì cần để nói một điểm trên đó là gì khi rê chuột."""

    z: np.ndarray            # [hàng, cột] 0..1 — hàng 0 = tần số cao nhất (sau cùng)
    rel_db: np.ndarray       # cùng cỡ: dB trên nền nhiễu của dải
    freqs_hz: np.ndarray     # tần số của từng hàng


def normalize_band(band_db: np.ndarray, min_range_db: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """dB của một dải -> (mặt 0..1, dB trên nền). Nền = phân vị 20, đỉnh = phân vị 99,5.

    `min_range_db`: dải tối thiểu (trang Nghe: chỉ có nhiễu thì cảnh vẫn thấp, không bị kéo giãn
    thành núi). Dải tối đa MAX_RANGE_DB (xem trên) chỉ để VẼ; mức trên nền tính từ nền thật.
    """
    floor = float(np.percentile(band_db, 20))
    hi = float(np.percentile(band_db, 99.5))
    hi = max(hi, floor + min_range_db)
    lo = max(floor, hi - MAX_RANGE_DB)
    z = np.clip((band_db - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return (z ** 1.3).astype(np.float32), np.clip(band_db - floor, 0.0, REL_CAP_DB).astype(np.float32)


def band_scene(power_db: np.ndarray, freqs_hz: np.ndarray, tone_hz: float | None,
               half_band_hz: float = 250.0, max_cols: int = MAX_COLS) -> BandScene | None:
    """Dải tần quanh tone của spectrogram [n_bins, n_cols] -> cảnh [hàng tần số, cột thời gian].

    Gộp cột bằng MAX (không trung bình) để dit ngắn không bị xóa khi thu nhỏ. Chuẩn hóa theo nền
    nhiễu của chính dải, nên clip ồn hay sạch đều ra khối rõ. Hàng 0 = tần số cao nhất (sau cùng).
    """
    if power_db.size == 0 or tone_hz is None:
        return None
    rows = np.flatnonzero(np.abs(freqs_hz - tone_hz) <= half_band_hz)
    if rows.size == 0:
        return None
    band = power_db[rows[::-1], :].astype(np.float32)
    n_cols = band.shape[1]
    if n_cols > max_cols:
        edges = np.linspace(0, n_cols, max_cols + 1).astype(int)
        band = np.stack([band[:, a:b].max(axis=1) for a, b in zip(edges[:-1], edges[1:], strict=True)],
                        axis=1)
    z, rel = normalize_band(band)
    return BandScene(z, rel, np.asarray(freqs_hz, dtype=np.float32)[rows[::-1]])


def band_surface(power_db: np.ndarray, freqs_hz: np.ndarray, tone_hz: float,
                 half_band_hz: float = 250.0, max_cols: int = MAX_COLS) -> np.ndarray:
    """Chỉ mặt 0..1 của `band_scene`."""
    scene = band_scene(power_db, freqs_hz, tone_hz, half_band_hz, max_cols)
    return np.zeros((0, 0), np.float32) if scene is None else scene.z


class Ridge3DView(QWidget):
    hover_changed = Signal(object)      # (hàng, cột) dưới mũi chuột, hoặc None khi rời mặt cảnh

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._z = np.zeros((0, 0), np.float32)
        self.front_ticks: list[tuple[float, str]] = []   # (vị trí 0..1 dọc mép trước, nhãn)
        self.depth_label = ""
        self.front_label = ""
        self.placeholder = ""
        self._playhead: float | None = None     # 0..1 dọc mép trước; None = hiện đủ cả cảnh
        # Hình dạng phần trước con trỏ: trang Giải mã = "chưa nghe tới" (chìm sâu); trang Nghe =
        # lượt quét trước (hạ thấp) + khe trống ngay trước đầu ghi.
        self.ahead_level = SUBMERGED
        self.rise_width = RISE_WIDTH
        self.gap_width = 0.0
        # Trang đặt: (hàng, cột) -> các dòng của ô số đo. None = không hiện ô (vẫn tô điểm chọn).
        self.describe: Callable[[int, int], list[Line]] | None = None
        self._hover: tuple[int, int] | None = None
        self._mouse: QPoint | None = None
        self._marker: tuple[int | None, int] | None = None     # điểm do biểu đồ kia chỉ sang
        self._cache: QPixmap | None = None
        self.readout = HoverReadout(self)
        self.setMouseTracking(True)
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        stops = spectrum_stops()
        self._stops = [(p, QColor(c)) for p, c in stops]

    # ---- dữ liệu ----
    def set_surface(self, z: np.ndarray) -> None:
        self._z = np.asarray(z, dtype=np.float32)
        self._invalidate()
        self._refresh_hover()

    def surface(self) -> np.ndarray:
        return self._z

    def set_playhead(self, frac: float | None) -> None:
        """Khi nghe lại: phần ĐÃ nghe nổi lên đủ cao, phần chưa quét tới chìm xuống, và một luồng
        sáng từ trên chiếu xuống đi theo con trỏ phát. None = hiện đủ cả cảnh (không phát)."""
        ph = None if frac is None else max(0.0, min(1.0, float(frac)))
        if ph == self._playhead:
            return
        self._playhead = ph
        self._invalidate()
        if self._hover is not None:
            self._refresh_hover()

    def playhead(self) -> float | None:
        return self._playhead

    def heights(self, z: np.ndarray) -> np.ndarray:
        """Chiều cao thực vẽ: z nhân hệ số theo vị trí so với con trỏ phát."""
        if self._playhead is None or z.size == 0:
            return z
        xs = np.linspace(0.0, 1.0, z.shape[1])
        ramp = np.clip((self._playhead - xs) / max(self.rise_width, 1e-6), 0.0, 1.0)  # 1 = đã qua
        mult = self.ahead_level + (1.0 - self.ahead_level) * ramp
        if self.gap_width > 0:
            mult = np.where((xs >= self._playhead) & (xs < self._playhead + self.gap_width), 0.0, mult)
        return z * mult[None, :]

    def clear(self) -> None:
        self._z = np.zeros((0, 0), np.float32)
        self._playhead = None
        self._marker = None
        self._invalidate()
        self._refresh_hover()

    # ---- rê chuột ----
    def cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        """Điểm (hàng, cột) của mặt cảnh THẤY ĐƯỢC tại (x, y): dò từ dải trước ra sau, dải đầu tiên
        có phần tô chứa điểm đó là dải đang che (vẽ sau thì che trước). Vệt sàn ngay trước chân
        mỗi dải thuộc về dải đó, nên rê trên nền phẳng không có khe chết."""
        z = self._z
        if z.ndim != 2 or z.shape[0] < 2 or z.shape[1] < 2:
            return None
        h = self.heights(z)
        n_rows, n_cols = z.shape
        spacing = self._row_geometry(1.0)[2] - self._row_geometry(1.0 - 1.0 / (n_rows - 1))[2]
        tol = min(3.0, spacing / 2)
        for r in range(n_rows - 1, -1, -1):
            left, width, base, amp = self._row_geometry(r / (n_rows - 1))
            f = (x - left) / width
            if not 0.0 <= f <= 1.0:
                continue
            c = int(round(f * (n_cols - 1)))
            top = base - float(h[r, c]) * amp
            if top - tol <= y <= base + spacing / 2:
                return r, c
        return None

    def hover(self) -> tuple[int, int] | None:
        return self._hover

    def set_marker(self, row: int | None, col: int | None) -> None:
        """Điểm do biểu đồ kia chỉ sang (thác nước trang Nghe): cột thời gian + cọc nếu có hàng."""
        m = None if col is None else (row, int(col))
        if m != self._marker:
            self._marker = m
            self.update()

    def marker(self) -> tuple[int | None, int] | None:
        return self._marker

    def mouseMoveEvent(self, event) -> None:
        self._mouse = event.position().toPoint()
        self._refresh_hover()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._mouse = None
        self._refresh_hover()
        super().leaveEvent(event)

    def hover_at(self, pos: QPoint | None) -> None:
        """Như rê chuột tới `pos` (None = chuột rời đi) — cho test và ảnh chụp."""
        self._mouse = pos
        self._refresh_hover()

    def _refresh_hover(self) -> None:
        """Chọn lại điểm dưới chuột (chuột đứng yên mà cảnh đổi thì điểm dưới nó cũng đổi)."""
        cell = None if self._mouse is None else self.cell_at(self._mouse.x(), self._mouse.y())
        changed = cell != self._hover
        self._hover = cell
        lines = self.describe(*cell) if (cell is not None and self.describe is not None) else []
        self.readout.show_lines(lines, self._mouse or QPoint())
        if changed:
            self.hover_changed.emit(cell)
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
            self._paint_scene(cp)
            cp.end()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cache)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._z
        if z.size == 0 or z.shape[0] < 2:
            if self.placeholder:
                p.setPen(QColor(MUTED))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
        else:
            if self._marker is not None and self._hover is None:
                self._draw_pick(p, self._marker[0], self._marker[1], strong=False)
            if self._hover is not None:
                self._draw_pick(p, self._hover[0], self._hover[1], strong=True)
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
        n_rows, n_cols = z.shape
        xs = np.linspace(0.0, 1.0, n_cols)
        edge = QPen(QColor(230, 240, 255, 150))
        edge.setCosmetic(True)       # bút 1 px không khử răng cưa: viền khử răng cưa tốn 92 ms/khung
        # Đường dẫn dựng thẳng từ mảng numpy (arrayToQPath), và KHÔNG khử răng cưa: đo trên cảnh
        # 16 x 360 ở tỉ lệ 150 %, viền khử răng cưa tốn 92 ms/khung còn phần tô gradient chỉ 17 ms.
        # Bỏ khử răng cưa ở viền đưa một khung về mức đủ để quét theo thanh phát 20 lần/giây.
        for r in range(n_rows):
            t = r / (n_rows - 1)
            left, width, base, amp = self._row_geometry(t)
            px = left + width * xs
            py = base - z[r] * amp
            ridge = arrayToQPath(px, py)
            fill = arrayToQPath(np.concatenate([px, [left + width, left]]),
                                np.concatenate([py, [base, base]]))
            fill.closeSubpath()
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self._gradient(base, amp)))
            p.drawPath(fill)
            edge.setColor(QColor(230, 240, 255, int(60 + 120 * t)))
            p.setPen(edge)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ridge)
        if self._playhead is not None:
            self._draw_beam(p, self._playhead)

    def _draw_pick(self, p: QPainter, row: int | None, col: int, strong: bool) -> None:
        """Điểm đang xem: cột thời gian kẻ trên sàn (sau ra trước), dải tần của nó sáng lên, và một
        cọc từ chân tới đỉnh có chấm đèn. `strong` = điểm dưới chuột; không = điểm biểu đồ kia chỉ."""
        z = self._z
        n_rows, n_cols = z.shape
        if not 0 <= col < n_cols:
            return
        h = self.heights(z)
        fc = col / (n_cols - 1)
        lamp = QColor(LAMP)
        bl, bw, bb, _ = self._row_geometry(0.0)
        fl, fw, fb, _ = self._row_geometry(1.0)
        floor = QPen(QColor(lamp.red(), lamp.green(), lamp.blue(), 150 if strong else 110))
        floor.setWidthF(1.0)
        floor.setStyle(Qt.PenStyle.DashLine)
        p.setPen(floor)
        p.drawLine(QPointF(bl + bw * fc, bb), QPointF(fl + fw * fc, fb))
        if row is None or not 0 <= row < n_rows:
            return
        left, width, base, amp = self._row_geometry(row / (n_rows - 1))
        if strong:
            xs = np.linspace(0.0, 1.0, n_cols)
            ridge = arrayToQPath(left + width * xs, base - h[row] * amp)
            pen = QPen(QColor(lamp.red(), lamp.green(), lamp.blue(), 210))
            pen.setWidthF(1.6)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(ridge)
        x = left + width * fc
        top = base - float(h[row, col]) * amp
        pin = QPen(QColor(255, 241, 204, 220 if strong else 150))
        pin.setWidthF(1.4)
        p.setPen(pin)
        p.drawLine(QPointF(x, base), QPointF(x, top))
        p.setPen(QPen(QColor(NIGHT), 1.5))
        p.setBrush(lamp)
        r = 4.5 if strong else 3.5
        p.drawEllipse(QPointF(x, top), r, r)

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
        pen = QPen(QColor(LINE))
        pen.setWidthF(1.0)
        p.setPen(pen)
        back = self._row_geometry(0.0)
        front = self._row_geometry(1.0)
        for i in range(9):          # đường dọc hội tụ về phía sau
            f = i / 8
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
            x = left + width * pos
            p.drawLine(QPointF(x, base), QPointF(x, base + 4))
            p.drawText(QRectF(x - 40, base + 4, 80, 14), Qt.AlignmentFlag.AlignHCenter, text)
        if self.front_label:
            p.drawText(QRectF(left, base + 4, width, 14), Qt.AlignmentFlag.AlignRight, self.front_label)
        if self.depth_label:          # góc trên trái, không đè lên các dải phía sau
            p.drawText(QRectF(14, 6, self.width() - 28, 14), Qt.AlignmentFlag.AlignLeft, self.depth_label)


WINDOW_S = 12.0          # cửa sổ cảnh 3D ở trang Giải mã; 360 cột -> 33 ms/cột, đủ tách dit 40 WPM


def band_window_scene(x: np.ndarray, sample_rate: int, tone_hz: float | None, t0: float,
                      window_s: float = WINDOW_S, cols: int = 360) -> BandScene | None:
    """Cảnh 3D cho đoạn [t0, t0 + window_s) tính thẳng từ âm thanh ở độ phân giải đầy đủ.

    Spectrogram của trang Giải mã bị gộp còn ~0,9 s/cột với file một giờ — không tách nổi dit.
    STFT riêng cho 12 giây chỉ tốn vài mili giây, nên tính lại mỗi khi cửa sổ dời đi.
    """
    from morsedesk.dsp.stft import stft_power

    s0 = max(0, int(t0 * sample_rate))
    s1 = min(len(x), s0 + int(window_s * sample_rate))
    seg = np.asarray(x[s0:s1], dtype=np.float32)
    if len(seg) < 512 or tone_hz is None:
        return None
    power, freqs = stft_power(seg, sample_rate=sample_rate)
    db = 10.0 * np.log10(power + 1e-12)
    return band_scene(db, freqs, tone_hz, max_cols=cols)


def band_window(x: np.ndarray, sample_rate: int, tone_hz: float, t0: float,
                window_s: float = WINDOW_S, cols: int = 360) -> np.ndarray:
    """Chỉ mặt 0..1 của `band_window_scene`."""
    scene = band_window_scene(x, sample_rate, tone_hz, t0, window_s, cols)
    return np.zeros((0, 0), np.float32) if scene is None else scene.z
