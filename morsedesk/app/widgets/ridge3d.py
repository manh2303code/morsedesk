"""Phong cảnh phổ 3D: các đường sống núi phối cảnh, màu theo độ cao — kiểu "3D waterfall" của SDR.

Vẽ bằng QPainter chứ không bằng OpenGL: máy air-gap và máy ảo thường không có driver OpenGL, và
một cảnh vài chục dải x vài trăm điểm vẽ được dưới 10 ms bằng đường dẫn thường.

Mỗi hàng của mặt `Z` (0..1) là một dải. Dải ở sau nhỏ và cao hơn trên màn hình, dải ở trước to và
thấp hơn; vẽ từ sau ra trước, mỗi dải tô kín phần dưới nên che dải phía sau — đó là thứ cho cảm giác
khối. Màu tô là dải màu phổ chung, neo theo ĐỘ CAO của chính dải đó: chân dải chìm vào nền đêm,
đỉnh lên vàng rồi đỏ.

Hai cách dùng:
- `set_surface(Z, ...)`: cảnh tĩnh (trang Giải mã: ngang là thời gian, sâu là tần số quanh tone,
  nên các dấu Morse nhô lên thành một dãy khối đọc được bằng mắt).
- `push_row(row)`: cảnh cuộn (trang Nghe: ngang là tần số, sâu là thời gian, hàng mới ở trước).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from morsedesk.app.theme import LINE, MUTED, NIGHT, PANEL, READOUT_FONT, spectrum_stops

MAX_COLS = 240


def band_surface(power_db: np.ndarray, freqs_hz: np.ndarray, tone_hz: float,
                 half_band_hz: float = 250.0, max_cols: int = MAX_COLS) -> np.ndarray:
    """Dải tần quanh tone của spectrogram [n_bins, n_cols] -> mặt 0..1 [hàng tần số, cột thời gian].

    Gộp cột bằng MAX (không trung bình) để dit ngắn không bị xóa khi thu nhỏ. Chuẩn hóa theo nền
    nhiễu của chính dải (phân vị 20) và đỉnh (phân vị 99,5), nên clip ồn hay sạch đều ra khối rõ.
    Hàng 0 = tần số cao nhất (ở sau cùng của cảnh).
    """
    if power_db.size == 0 or tone_hz is None:
        return np.zeros((0, 0), np.float32)
    rows = np.flatnonzero(np.abs(freqs_hz - tone_hz) <= half_band_hz)
    if rows.size == 0:
        return np.zeros((0, 0), np.float32)
    band = power_db[rows[::-1], :].astype(np.float32)
    n_cols = band.shape[1]
    if n_cols > max_cols:
        edges = np.linspace(0, n_cols, max_cols + 1).astype(int)
        band = np.stack([band[:, a:b].max(axis=1) for a, b in zip(edges[:-1], edges[1:], strict=True)],
                        axis=1)
    lo = float(np.percentile(band, 20))
    hi = float(np.percentile(band, 99.5))
    z = np.clip((band - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return (z ** 1.3).astype(np.float32)


class Ridge3DView(QWidget):
    def __init__(self, rows: int = 48, cols: int = 200, parent=None) -> None:
        super().__init__(parent)
        self._z = np.zeros((0, 0), np.float32)
        self._rows_live = rows
        self._cols_live = cols
        self.front_ticks: list[tuple[float, str]] = []   # (vị trí 0..1 dọc mép trước, nhãn)
        self.depth_label = ""
        self.front_label = ""
        self.placeholder = ""
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        stops = spectrum_stops()
        self._stops = [(p, QColor(c)) for p, c in stops]

    # ---- dữ liệu ----
    def set_surface(self, z: np.ndarray) -> None:
        self._z = np.asarray(z, dtype=np.float32)
        self.update()

    def surface(self) -> np.ndarray:
        return self._z

    def clear(self) -> None:
        self._z = np.zeros((0, 0), np.float32)
        self.update()

    def push_row(self, row: np.ndarray) -> None:
        """Thêm một hàng mới ở TRƯỚC (cảnh cuộn); hàng cũ lùi dần ra sau rồi biến mất."""
        r = np.asarray(row, dtype=np.float32).reshape(-1)
        if r.size != self._cols_live:
            r = np.interp(np.linspace(0, r.size - 1, self._cols_live), np.arange(r.size), r)
        if self._z.shape != (self._rows_live, self._cols_live):
            self._z = np.zeros((self._rows_live, self._cols_live), np.float32)
        self._z = np.roll(self._z, -1, axis=0)
        self._z[-1] = np.clip(r, 0.0, 1.0)
        self.update()

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
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, QColor(NIGHT))
        bg.setColorAt(1.0, QColor(PANEL))
        p.fillRect(self.rect(), QBrush(bg))
        self._draw_floor(p)
        z = self._z
        if z.size == 0 or z.shape[0] < 2:
            if self.placeholder:
                p.setPen(QColor(MUTED))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
            p.end()
            return
        n_rows, n_cols = z.shape
        xs = np.linspace(0.0, 1.0, n_cols)
        edge = QPen(QColor(230, 240, 255, 150))
        edge.setWidthF(1.0)
        for r in range(n_rows):
            t = r / (n_rows - 1)
            left, width, base, amp = self._row_geometry(t)
            px = left + width * xs
            py = base - z[r] * amp
            ridge = [QPointF(float(a), float(b)) for a, b in zip(px, py, strict=True)]
            poly = QPolygonF(ridge + [QPointF(left + width, base), QPointF(left, base)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self._gradient(base, amp)))
            p.drawPolygon(poly)
            edge.setColor(QColor(230, 240, 255, int(60 + 120 * t)))
            p.setPen(edge)
            p.drawPolyline(QPolygonF(ridge))
        self._draw_labels(p)
        p.end()

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


def band_window(x: np.ndarray, sample_rate: int, tone_hz: float, t0: float,
                window_s: float = WINDOW_S, cols: int = 360) -> np.ndarray:
    """Mặt 3D cho đoạn [t0, t0 + window_s) tính thẳng từ âm thanh ở độ phân giải đầy đủ.

    Spectrogram của trang Giải mã bị gộp còn ~0,9 s/cột với file một giờ — không tách nổi dit.
    STFT riêng cho 12 giây chỉ tốn vài mili giây, nên tính lại mỗi khi cửa sổ dời đi.
    """
    from morsedesk.dsp.stft import stft_power

    s0 = max(0, int(t0 * sample_rate))
    s1 = min(len(x), s0 + int(window_s * sample_rate))
    seg = np.asarray(x[s0:s1], dtype=np.float32)
    if len(seg) < 512 or tone_hz is None:
        return np.zeros((0, 0), np.float32)
    power, freqs = stft_power(seg, sample_rate=sample_rate)
    db = 10.0 * np.log10(power + 1e-12)
    return band_surface(db, freqs, tone_hz, max_cols=cols)
