"""Spectrogram 0–2 kHz bằng pyqtgraph, vạch tone, vạch đầu từ, con trỏ thời gian.

Dùng bảng màu phổ chung của giao diện (`theme.spectrum_lut`) — cùng bảng với thác nước và cảnh 3D.
Rê chuột (người dùng 25/09): chữ thập + ô số đo như cảnh 3D (từ ở đó, tần số, mức trên nền, giây).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QPointF, QRectF

from morsedesk.app.theme import LAMP, LINE, MUTED, NIGHT, spectrum_lut
from morsedesk.app.widgets.hover_readout import HoverReadout, Line
from morsedesk.app.widgets.ridge3d import REL_CAP_DB
from morsedesk.app.worker import DB_FLOOR, MAX_FREQ_HZ, Spectrogram

EMPTY_SPAN_S = 10.0     # trục thời gian khi chưa có file


class SpectrogramView(pg.PlotWidget):
    """Ảnh spectrogram (viridis, dB tương đối) cộng ba lớp vạch: tone, đầu từ, con trỏ."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, background=NIGHT)
        # PlotWidget.__init__ gán self.clear = plotItem.clear làm thuộc tính instance
        # (che mất phương thức clear() của lớp con này); bỏ nó để clear() bên dưới có hiệu lực.
        self.__dict__.pop("clear", None)
        self.retranslate()
        # Chừa 4 % phía trên: với padding=0 thì nhãn trên cùng (2000) nằm đúng mép và bị cắt
        # mất nửa — thấy rõ trên ảnh chụp GUI chạy thật.
        self.setYRange(0, MAX_FREQ_HZ * 1.04, padding=0)
        self.setMouseEnabled(x=True, y=False)
        for name in ("bottom", "left"):
            axis = self.getAxis(name)
            axis.setPen(pg.mkPen(LINE))
            axis.setTextPen(pg.mkPen(MUTED))
            # Tắt tiền tố SI tự động: với trục rỗng pyqtgraph từng hiện "−400…400 s (x0.001)".
            axis.enableAutoSIPrefix(False)
        self.setXRange(0.0, EMPTY_SPAN_S, padding=0)
        self.image = pg.ImageItem()
        self.image.setLookupTable(spectrum_lut())
        self.addItem(self.image)
        self.tone_line = pg.InfiniteLine(angle=0, pen=pg.mkPen(LAMP, width=1, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.tone_line.setVisible(False)
        self.addItem(self.tone_line)
        self.cursor_line = pg.InfiniteLine(angle=90, pen=pg.mkPen("#ffffff", width=1))
        self.cursor_line.setVisible(False)
        self.addItem(self.cursor_line)
        self.word_lines: list[pg.InfiniteLine] = []
        # Chữ thập theo chuột + ô số đo. `describe(giây, Hz, dB trên nền)` do trang đặt.
        self.describe: Callable[[float, float, float], list[Line]] | None = None
        self._spec: Spectrogram | None = None
        self._floor_db = DB_FLOOR
        self._hover: tuple[float, float] | None = None
        cross = pg.mkPen((255, 255, 255, 110), width=1)
        self.hover_v = pg.InfiniteLine(angle=90, pen=cross)
        self.hover_h = pg.InfiniteLine(angle=0, pen=cross)
        for ln in (self.hover_v, self.hover_h):
            ln.setVisible(False)
            self.addItem(ln, ignoreBounds=True)
        self.readout = HoverReadout(self)
        self.scene().sigMouseMoved.connect(self._on_mouse)

    def retranslate(self) -> None:
        self.setLabel("bottom", self.tr("s"))
        self.setLabel("left", self.tr("Hz"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (tên Qt)
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)

    def set_spectrogram(self, spec: Spectrogram | None) -> None:
        """Vẽ spectrogram mới; `None` hoặc rỗng (audio 0 mẫu) chỉ xóa ảnh, không lỗi."""
        if spec is None or spec.power_db.size == 0:
            self.image.clear()
            self._spec = None
            self._show_hover(None)
            return
        self._spec = spec
        self._floor_db = float(np.percentile(spec.power_db, 20))
        self.image.setImage(np.ascontiguousarray(spec.power_db.T), autoLevels=False, levels=(DB_FLOOR, 0.0))
        t_end = float(spec.times_s[-1] + (spec.times_s[1] - spec.times_s[0] if len(spec.times_s) > 1 else 0.02))
        f_end = float(spec.freqs_hz[-1])
        self.image.setRect(QRectF(0.0, 0.0, t_end, f_end))
        self.setXRange(0.0, t_end, padding=0)

    def set_tone(self, hz: float | None) -> None:
        """Vẽ vạch ngang ở tần số tone; `None` ẩn vạch."""
        if hz is None:
            self.tone_line.setVisible(False)
        else:
            self.tone_line.setValue(float(hz))
            self.tone_line.setVisible(True)

    def set_word_marks(self, starts_s: list[float]) -> None:
        """Thay toàn bộ vạch đứng đánh dấu thời điểm bắt đầu từ."""
        for ln in self.word_lines:
            self.removeItem(ln)
        self.word_lines = []
        for s in starts_s:
            ln = pg.InfiniteLine(angle=90, pos=float(s), pen=pg.mkPen((255, 255, 255, 80), width=1))
            self.addItem(ln)
            self.word_lines.append(ln)

    def set_cursor(self, t_s: float | None) -> None:
        """Vẽ vạch đứng con trỏ thời gian hiện tại (ví dụ khi phát thử); `None` ẩn vạch."""
        if t_s is None:
            self.cursor_line.setVisible(False)
        else:
            self.cursor_line.setValue(float(t_s))
            self.cursor_line.setVisible(True)

    # ---- rê chuột ----
    def point_at(self, t_s: float, hz: float) -> tuple[float, float, float] | None:
        """(giây, Hz, dB trên nền) của ô phổ gần (t_s, hz) nhất; None nếu ngoài dữ liệu."""
        spec = self._spec
        if spec is None or not len(spec.times_s):
            return None
        dt = float(spec.times_s[1] - spec.times_s[0]) if len(spec.times_s) > 1 else 0.02
        if not (0.0 <= t_s <= float(spec.times_s[-1]) + dt / 2 and 0.0 <= hz <= float(spec.freqs_hz[-1])):
            return None
        col = int(np.clip(np.searchsorted(spec.times_s, t_s), 0, len(spec.times_s) - 1))
        if col > 0 and abs(spec.times_s[col - 1] - t_s) < abs(spec.times_s[col] - t_s):
            col -= 1
        row = int(np.abs(spec.freqs_hz - hz).argmin())
        rel = float(np.clip(spec.power_db[row, col] - self._floor_db, 0.0, REL_CAP_DB))
        return t_s, hz, rel

    def hover(self) -> tuple[float, float] | None:
        return self._hover

    def hover_at(self, t_s: float | None, hz: float = 0.0) -> None:
        """Như rê chuột tới (giây, Hz) — cho test và ảnh chụp; None = chuột rời đi."""
        if t_s is None:
            self._show_hover(None)
            return
        self._on_mouse(self.getPlotItem().vb.mapViewToScene(QPointF(t_s, hz)))

    def _on_mouse(self, scene_pos) -> None:
        vb = self.getPlotItem().vb
        if not vb.sceneBoundingRect().contains(scene_pos):
            self._show_hover(None)
            return
        view = vb.mapSceneToView(scene_pos)
        pt = self.point_at(float(view.x()), float(view.y()))
        self._show_hover(pt, self.mapFromScene(scene_pos))

    def _show_hover(self, pt, at=None) -> None:
        if pt is None:
            self._hover = None
            for ln in (self.hover_v, self.hover_h):
                ln.setVisible(False)
            self.readout.show_lines([], at)
            return
        t_s, hz, rel = pt
        self._hover = (t_s, hz)
        self.hover_v.setValue(t_s)
        self.hover_h.setValue(hz)
        for ln in (self.hover_v, self.hover_h):
            ln.setVisible(True)
        self.readout.show_lines(self.describe(t_s, hz, rel) if self.describe else [], at)

    def leaveEvent(self, event) -> None:  # noqa: N802 (tên Qt)
        self._show_hover(None)
        super().leaveEvent(event)

    def clear(self) -> None:
        """Xóa ảnh và mọi vạch, quay về trạng thái rỗng ban đầu."""
        self.image.clear()
        self._spec = None
        self._show_hover(None)
        self.set_tone(None)
        self.set_word_marks([])
        self.set_cursor(None)
        self.setXRange(0.0, EMPTY_SPAN_S, padding=0)
