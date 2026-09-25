"""Phím Morse động ở trang Tạo mã: cần gõ nhấn xuống ĐÚNG LÚC tone vang khi bấm Nghe thử.

Yêu cầu người dùng 25/09: chỗ trống dưới cụm nút Nghe thử / Dừng / Lưu dùng cho "hình bàn gõ Morse tối
giản giống logo khi bật app, đồng bộ với tiếng". Vẽ bằng đúng `key_art.paint_logo` của logo và màn
hình chờ (cần gõ hạ `LEVER_DEG`, tia lửa ở tiếp điểm), nên ba nơi là một hình. Trạng thái do trang
Tạo mã đẩy vào theo vị trí ĐANG RA LOA của `AudioPlayback`, không tự chạy đồng hồ riêng.

Theo góp ý người dùng (25/09, ảnh chụp): KHÔNG có ô nền bo tròn quanh phím, và phía trên chỉ có HAI
dấu `· –` — một chấm, một gạch — chứ không phải `· · –` của logo: khi tín hiệu là một chấm mà hai chấm
cùng sáng thì trông như phát hai chấm. Khi phát: dấu cùng loại với dấu đang kêu sáng lên, dấu kia
mờ; dưới phím là chữ đang phát và mẫu của nó. Khi không phát: cả hai dấu sáng như logo.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from morsedesk.app.key_art import LAMP_DIM, paint_logo
from morsedesk.app.splash import LEVER_DEG
from morsedesk.app.theme import LAMP, UI_FONT
from morsedesk.app.widgets.morse_tape import ACTIVE_GLOW

DIM = 0.22
CAPTION_H = 76
DOT, DAH, GAP = 11.0, 33.0, 9.0      # mẫu dưới chữ: cùng hình chấm/gạch với băng Morse
# Hai dấu trên phím, theo toạ độ chuẩn hóa của logo (bán kính 0,052 như logo), cân giữa: chấm tại
# 0,3515; gạch từ 0,4915 tới 0,6485; hàng y 0,275. Khe 0,036 giữa hai dấu như khe giữa các dấu logo.
MARK_Y, MARK_R = 0.275, 0.052
DOT_X, DAH_X0, DAH_X1 = 0.3515, 0.4915, 0.6485


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

    def lit(self) -> tuple[float, float]:
        """Độ sáng hai dấu trên phím (chấm, gạch)."""
        if not self._playing:
            return (1.0, 1.0)
        if not self._pressed:
            return (DIM, DIM)
        return (1.0, DIM) if self._symbol == "." else (DIM, 1.0)

    def sizeHint(self) -> QSize:
        return QSize(240, 240 + CAPTION_H)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        art = max(60.0, min(self.width() - 8.0, self.height() - CAPTION_H - 8.0, 280.0))
        rect = QRectF((self.width() - art) / 2, 4, art, art)
        paint_logo(p, rect, lever_deg=LEVER_DEG if self._pressed else 0.0, tile=False,
                   spark=1.0 if self._pressed else 0.0, marks=False)
        self._paint_marks(p, rect)
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

    def _paint_marks(self, p: QPainter, rect: QRectF) -> None:
        s, ox, oy = rect.width(), rect.x(), rect.y()
        dot, dah = self.lit()
        r = MARK_R * s
        cy = oy + MARK_Y * s
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_mix(dot))
        p.drawEllipse(QRectF(ox + DOT_X * s - r, cy - r, 2 * r, 2 * r))
        p.setBrush(_mix(dah))
        p.drawRoundedRect(QRectF(ox + DAH_X0 * s - r, cy - r, (DAH_X1 - DAH_X0) * s + 2 * r, 2 * r), r, r)

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


def _mix(level: float) -> QColor:
    """Giữa màu dấu tắt (LAMP_DIM) và đèn sáng (LAMP), như ba dấu của logo."""
    a, b = QColor(LAMP_DIM), QColor(LAMP)
    t = max(0.0, min(1.0, level))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))
