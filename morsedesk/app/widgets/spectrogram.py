"""Spectrogram 0–2 kHz bằng pyqtgraph, vạch tone, vạch đầu từ, con trỏ thời gian."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QRectF

from morsedesk.app.worker import DB_FLOOR, MAX_FREQ_HZ, Spectrogram


class SpectrogramView(pg.PlotWidget):
    """Ảnh spectrogram (viridis, dB tương đối) cộng ba lớp vạch: tone, đầu từ, con trỏ."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, background="k")
        # PlotWidget.__init__ gán self.clear = plotItem.clear làm thuộc tính instance
        # (che mất phương thức clear() của lớp con này); bỏ nó để clear() bên dưới có hiệu lực.
        self.__dict__.pop("clear", None)
        self.retranslate()
        # Chừa 4 % phía trên: với padding=0 thì nhãn trên cùng (2000) nằm đúng mép và bị cắt
        # mất nửa — thấy rõ trên ảnh chụp GUI chạy thật.
        self.setYRange(0, MAX_FREQ_HZ * 1.04, padding=0)
        self.setMouseEnabled(x=True, y=False)
        self.image = pg.ImageItem()
        self.image.setLookupTable(pg.colormap.get("viridis").getLookupTable())
        self.addItem(self.image)
        self.tone_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#ff5555", width=2))
        self.tone_line.setVisible(False)
        self.addItem(self.tone_line)
        self.cursor_line = pg.InfiniteLine(angle=90, pen=pg.mkPen("#ffffff", width=1))
        self.cursor_line.setVisible(False)
        self.addItem(self.cursor_line)
        self.word_lines: list[pg.InfiniteLine] = []

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
            return
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

    def clear(self) -> None:
        """Xóa ảnh và mọi vạch, quay về trạng thái rỗng ban đầu."""
        self.image.clear()
        self.set_tone(None)
        self.set_word_marks([])
        self.set_cursor(None)
