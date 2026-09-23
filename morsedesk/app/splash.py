"""Màn hình chờ động: phím Morse gõ ra `· · –` — chính logo — rồi mở cửa sổ chính.

Theo yêu cầu người dùng: khi bấm đúp file chạy, hiện một phím Morse tối giản giống logo đang nhấp
nháy, dòng chữ nhỏ bên dưới là bản quyền và tên tác giả. Mỗi lần nhấn: cần gõ hạ xuống, tiếp điểm
lóe sáng, dấu tương ứng sáng lên (dah dài dần trong lúc giữ phím). Hết ba dấu là logo hoàn chỉnh.

Vẽ bằng QPainter theo thời gian chứ không phát file GIF: sắc nét ở mọi độ phân giải, không kéo
thêm thư viện, và khung đầu tiên (`render_frame(..., 0)`) chính là ảnh tĩnh cho màn hình chờ của
PyInstaller trong lúc bản một file đang bung — nên hai màn hình nối nhau liền mạch.

Nhịp: đơn vị 120 ms (~10 WPM, chậm để mắt theo kịp), đúng tỉ lệ ITU dit 1, dah 3, cách 1.
"""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from morsedesk.app.branding import KEY_INK, MIST, TILE_BOTTOM, TILE_TOP
from morsedesk.app.key_art import paint_logo

AUTHOR = "Шабданбек Бақытжан Асанханұлы"
COPYRIGHT = f"© 2026 {AUTHOR}"
SIZE = QSize(520, 380)
UNIT_MS = 120
PRE_MS = 350
POST_MS = 450
# Khoảng "nhấn phím" của `· · –`, theo đơn vị: dit [0,1), dit [2,3), dah [4,7)
PRESSES = ((0, 1), (2, 3), (4, 7))
TOTAL_MS = PRE_MS + 7 * UNIT_MS + POST_MS
LEVER_DEG = 3.5


def frame_state(t_ms: float) -> tuple[float, tuple[float, float, float], float]:
    """(góc cần gõ, độ sáng ba dấu, tia lửa) tại thời điểm t."""
    u = (t_ms - PRE_MS) / UNIT_MS
    pressed = any(a <= u < b for a, b in PRESSES)
    dit1 = 1.0 if u >= PRESSES[0][0] else 0.0
    dit2 = 1.0 if u >= PRESSES[1][0] else 0.0
    a, b = PRESSES[2]
    dah = 0.0 if u < a else min(1.0, (u - a) / (b - a))
    return (LEVER_DEG if pressed else 0.0), (dit1, dit2, dah), (1.0 if pressed else 0.0)


def render_frame(p: QPainter, width: int, height: int, t_ms: float, subtitle: str = "") -> None:
    g = QLinearGradient(0, 0, 0, height)
    g.setColorAt(0.0, QColor(TILE_TOP))
    g.setColorAt(1.0, QColor(TILE_BOTTOM))
    p.fillRect(0, 0, width, height, g)
    art = 250.0
    lever, lit, spark = frame_state(t_ms)
    paint_logo(p, QRectF((width - art) / 2, 18, art, art), lever_deg=lever, lit=lit, tile=False,
               spark=spark)
    p.setPen(QColor(KEY_INK))
    f = QFont("Noto Sans")
    f.setPixelSize(24)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 262, width, 34), Qt.AlignmentFlag.AlignHCenter, "MorseDesk")
    if subtitle:
        f.setPixelSize(12)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(MIST))
        p.drawText(QRectF(0, 298, width, 18), Qt.AlignmentFlag.AlignHCenter, subtitle)
    f.setPixelSize(11)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor(MIST))
    p.drawText(QRectF(0, height - 30, width, 18), Qt.AlignmentFlag.AlignHCenter, COPYRIGHT)


def render_image(t_ms: float = 0.0, subtitle: str = "") -> QImage:
    img = QImage(SIZE, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    render_frame(p, SIZE.width(), SIZE.height(), t_ms, subtitle)
    p.end()
    return img


class SplashScreen(QWidget):
    finished = Signal()

    def __init__(self, subtitle: str = "") -> None:
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(SIZE)
        self.subtitle = subtitle
        self._t = 0.0
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._done = False

    def center_on_screen(self) -> None:
        screen = self.screen() or None
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def play(self) -> None:
        """Chạy hoạt cảnh một lần; phát `finished` khi xong."""
        self._clock.start()
        self._timer.start()

    def elapsed_ms(self) -> float:
        return self._t

    def _tick(self) -> None:
        self._t = float(self._clock.elapsed())
        self.update()
        if self._t >= TOTAL_MS and not self._done:
            self._done = True
            self._timer.stop()
            self.finished.emit()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        render_frame(p, self.width(), self.height(), self._t, self.subtitle)
        p.end()
