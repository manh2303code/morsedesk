"""Phím Morse động ở trang Tạo mã: cần gõ nhấn xuống ĐÚNG LÚC tone vang khi bấm Nghe thử.

Yêu cầu người dùng 25/09: chỗ trống dưới cụm nút Nghe thử / Dừng / Lưu dùng cho "hình bàn gõ Morse tối
giản giống logo khi bật app, đồng bộ với tiếng". Vẽ bằng đúng `key_art.paint_logo` của logo và màn
hình chờ (cần gõ hạ `LEVER_DEG`, tia lửa ở tiếp điểm), nên ba nơi là một hình. Trạng thái do trang
Tạo mã đẩy vào theo vị trí ĐANG RA LOA của `AudioPlayback`, không tự chạy đồng hồ riêng.

Khi phát: ba dấu của logo mờ đi, dấu cùng loại với dấu đang kêu (chấm hoặc gạch) sáng lên; dưới phím
là chữ đang phát và mẫu của nó. Khi không phát: logo tĩnh.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from morsedesk.app.key_art import paint_logo
from morsedesk.app.splash import LEVER_DEG
from morsedesk.app.theme import LAMP, UI_FONT
from morsedesk.app.widgets.morse_tape import ACTIVE_GLOW

DIM = 0.22
CAPTION_H = 76
DOT, DAH, GAP = 11.0, 33.0, 9.0      # mẫu dưới chữ: cùng hình chấm/gạch với băng Morse


class KeyAnimation(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._playing = False
        self._pressed = False
        self._symbol = ""
        self._letter = ""
        self._pattern = ""
        self._element = -1
        self.setMinimumSize(QSize(150, 150 + CAPTION_H))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_state(self, playing: bool, pressed: bool = False, symbol: str = "", letter: str = "",
                  pattern: str = "", element: int = -1) -> None:
        state = (playing, pressed and playing, symbol, letter, pattern, element)
        if state == (self._playing, self._pressed, self._symbol, self._letter, self._pattern, self._element):
            return
        self._playing, self._pressed, self._symbol, self._letter, self._pattern, self._element = state
        self.update()

    @property
    def pressed(self) -> bool:
        return self._pressed

    def lit(self) -> tuple[float, float, float]:
        """Độ sáng ba dấu của logo (chấm, chấm, gạch)."""
        if not self._playing:
            return (1.0, 1.0, 1.0)
        if not self._pressed:
            return (DIM, DIM, DIM)
        return (1.0, 1.0, DIM) if self._symbol == "." else (DIM, DIM, 1.0)

    def sizeHint(self) -> QSize:
        return QSize(240, 240 + CAPTION_H)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        art = max(60.0, min(self.width() - 8.0, self.height() - CAPTION_H - 8.0, 280.0))
        rect = QRectF((self.width() - art) / 2, 4, art, art)
        paint_logo(p, rect, lever_deg=LEVER_DEG if self._pressed else 0.0, lit=self.lit(), tile=True,
                   spark=1.0 if self._pressed else 0.0, dah_grows=False)
        if self._playing and self._letter:
            f = QFont(UI_FONT)
            f.setPixelSize(30)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(LAMP))
            p.drawText(QRectF(0, rect.bottom() + 4, self.width(), 36), Qt.AlignmentFlag.AlignHCenter,
                       self._letter)
            self._paint_pattern(p, rect.bottom() + 52)
        p.end()

    def _paint_pattern(self, p: QPainter, cy: float) -> None:
        """Mẫu của chữ đang phát bằng chấm/gạch như trên băng; dấu đang kêu trắng sáng và to hơn."""
        widths = [DAH if s == "-" else DOT for s in self._pattern]
        x = (self.width() - (sum(widths) + GAP * max(0, len(widths) - 1))) / 2
        p.setPen(Qt.PenStyle.NoPen)
        for k, (s, w) in enumerate(zip(self._pattern, widths, strict=True)):
            sounding = k == self._element and self._pressed
            h = DOT * (1.35 if sounding else 1.0)
            color = QColor(ACTIVE_GLOW if sounding else LAMP)
            if not sounding and k != self._element:
                color.setAlpha(150)
            p.setBrush(color)
            r = QRectF(x - (h - DOT) / 2 if s == "." else x, cy - h / 2, h if s == "." else w, h)
            p.drawRoundedRect(r, h / 2, h / 2)
            x += w + GAP
