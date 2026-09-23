"""Cờ ba nước vẽ bằng QPainter, và thanh chọn ngôn ngữ giao diện bằng cờ.

Vì sao vẽ tay thay vì ký tự emoji cờ (🇬🇧): emoji cờ cần một font có bảng glyph vùng miền, thứ
mà bản Linux tối giản của máy đích thường không có — khi thiếu, Qt hiện ra hai chữ cái "GB" hoặc
hai ô vuông. Vì sao không dùng file PNG: thêm tài nguyên nhị phân vào bản đóng gói và vào cây
`datas` của PyInstaller cho ba hình 24x16 là không đáng.

Ở cỡ 24x16 px không chi tiết nào nhỏ hơn một pixel nhìn thấy được, nên cờ ở đây giữ đúng bố cục
và màu chính thức rồi lược phần không thể hiện nổi (đại bàng thảo nguyên của Kazakhstan, hoa văn
mép cột). Mục đích là nhận ra ngay lá nào, không phải bản vẽ kỹ thuật.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

# Màu lấy theo quy cách chính thức của từng nước.
_UK_BLUE = QColor("#012169")
_UK_RED = QColor("#C8102E")
_WHITE = QColor("#FFFFFF")
_RU_BLUE = QColor("#0039A6")
_RU_RED = QColor("#D52B1E")
_KZ_CYAN = QColor("#00AFCA")
_KZ_GOLD = QColor("#FEC50C")

FLAG_W, FLAG_H = 24, 16


def _uk(p: QPainter, w: int, h: int) -> None:
    """Union Jack: nền xanh, chéo trắng, chéo đỏ hẹp hơn, rồi thập trắng và thập đỏ đè lên."""
    p.fillRect(0, 0, w, h, _UK_BLUE)
    p.setRenderHint(QPainter.Antialiasing, True)
    for pen, width in ((QPen(_WHITE), h / 3.4), (QPen(_UK_RED), h / 7.0)):
        pen.setWidthF(width)
        p.setPen(pen)
        p.drawLine(QPointF(0, 0), QPointF(w, h))
        p.drawLine(QPointF(w, 0), QPointF(0, h))
    p.setRenderHint(QPainter.Antialiasing, False)
    # Thập thẳng vẽ SAU nên che phần chéo đi qua giữa, đúng như lá cờ thật.
    cw, ch = h / 2.4, h / 2.4
    p.fillRect(QRectF(w / 2 - cw / 2, 0, cw, h), _WHITE)
    p.fillRect(QRectF(0, h / 2 - ch / 2, w, ch), _WHITE)
    cw2, ch2 = cw * 0.55, ch * 0.55
    p.fillRect(QRectF(w / 2 - cw2 / 2, 0, cw2, h), _UK_RED)
    p.fillRect(QRectF(0, h / 2 - ch2 / 2, w, ch2), _UK_RED)


def _ru(p: QPainter, w: int, h: int) -> None:
    """Ba dải ngang bằng nhau: trắng, xanh, đỏ."""
    band = h / 3.0
    p.fillRect(QRectF(0, 0, w, band), _WHITE)
    p.fillRect(QRectF(0, band, w, band), _RU_BLUE)
    p.fillRect(QRectF(0, 2 * band, w, h - 2 * band), _RU_RED)


def _kz(p: QPainter, w: int, h: int) -> None:
    """Nền xanh, mặt trời vàng 32 tia ở giữa. Đại bàng bên dưới bị lược: ở 16 px nó thành một vệt."""
    p.fillRect(0, 0, w, h, _KZ_CYAN)
    p.setRenderHint(QPainter.Antialiasing, True)
    cx, cy, r = w * 0.5, h * 0.46, h * 0.19
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(_KZ_GOLD))
    p.drawEllipse(QPointF(cx, cy), r, r)
    pen = QPen(_KZ_GOLD)
    pen.setWidthF(max(0.6, h / 22.0))
    p.setPen(pen)
    for i in range(16):                                  # 16 tia vẽ được; 32 tia thật sẽ dính vào nhau
        a = 2.0 * math.pi * i / 16.0
        p.drawLine(QPointF(cx + math.cos(a) * r * 1.25, cy + math.sin(a) * r * 1.25),
                   QPointF(cx + math.cos(a) * r * 1.75, cy + math.sin(a) * r * 1.75))
    p.setRenderHint(QPainter.Antialiasing, False)


_PAINTERS = {"en": _uk, "ru": _ru, "kk": _kz}


def flag_pixmap(code: str, w: int = FLAG_W, h: int = FLAG_H, dpr: float = 1.0) -> QPixmap:
    """Pixmap lá cờ cho mã ngôn ngữ giao diện, có viền mảnh để lá trắng không tan vào nền sáng."""
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    try:
        path = QPainterPath()
        path.addRect(QRectF(0, 0, w, h))
        p.setClipPath(path)
        _PAINTERS.get(code, _uk)(p, w, h)
        p.setClipping(False)
        p.setPen(QPen(QColor(0, 0, 0, 90)))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRect(0, 0, w - 1, h - 1))
    finally:
        p.end()
    return pm


class LanguageBar(QWidget):
    """Ba nút cờ để chọn ngôn ngữ giao diện, thay cho hộp chọn.

    Nút dùng `setCheckable` trong một nhóm loại trừ lẫn nhau nên trạng thái đang chọn do Qt vẽ
    theo đúng chủ đề hệ thống — không tự tô màu nền, vì giao diện sáng và tối cần hai màu khác
    nhau và đã có tiền lệ chữ trắng trên nền sáng ở chip độ tin cậy.

    Cờ không phải ngôn ngữ (tiếng Nga còn là ngôn ngữ làm việc ở Kazakhstan), nên mỗi nút vẫn
    mang tên ngôn ngữ trong `toolTip` và `accessibleName` để người dùng trình đọc màn hình và
    người rê chuột đều biết chắc mình chọn gì.
    """

    def __init__(self, codes, names: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self.buttons: dict[str, QToolButton] = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        dpr = float(self.devicePixelRatioF() or 1.0)
        for code in codes:
            b = QToolButton(self)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setIcon(flag_pixmap(code, dpr=dpr))
            b.setIconSize(QSize(FLAG_W, FLAG_H))
            b.setToolButtonStyle(Qt.ToolButtonIconOnly)
            b.setFocusPolicy(Qt.StrongFocus)
            b.setToolTip(names.get(code, code))
            b.setAccessibleName(names.get(code, code))
            lay.addWidget(b)
            self.buttons[code] = b

    def set_names(self, names: dict[str, str]) -> None:
        for code, b in self.buttons.items():
            b.setToolTip(names.get(code, code))
            b.setAccessibleName(names.get(code, code))

    def set_current(self, code: str) -> None:
        b = self.buttons.get(code)
        if b is not None and not b.isChecked():
            b.setChecked(True)


class FlagLabel(QLabel):
    """Một lá cờ tĩnh, dùng ở chỗ cần chỉ ra bảng mã đang dùng chứ không phải để bấm."""

    def __init__(self, code: str, parent=None) -> None:
        super().__init__(parent)
        self.setPixmap(flag_pixmap(code, dpr=float(self.devicePixelRatioF() or 1.0)))


def profile_flag(profile_id: str) -> str:
    """Mã cờ cho một bảng mã Morse. `kk-cyrl-ru` là bảng Kazakh nên mang cờ Kazakhstan."""
    if profile_id.startswith("kk"):
        return "kk"
    if profile_id.startswith("ru"):
        return "ru"
    return "en"
