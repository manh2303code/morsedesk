"""Biểu tượng nét (line icon) vẽ bằng QPainter — một bộ dùng chung cho mọi trang.

Vẽ thay vì dùng ký tự Unicode hay font biểu tượng: máy air-gap tối giản không bảo đảm có font nào
chứa 📂 ⧉ ⤓, còn QPainter cho hình sắc nét ở mọi tỉ lệ màn hình (pixmap 1× và 2×). Hình học theo
lưới 24 đơn vị kiểu Lucide, nét tròn đầu, để các biểu tượng cùng một "giọng".
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QToolButton

INK = "#E6ECF7"             # = theme.TEXT
INK_DISABLED = "#7482A0"    # = theme.DISABLED_TEXT
KINDS = ("open", "copy", "export", "clear", "stop", "chevron-down", "chevron-up")


def _path(kind: str) -> tuple[QPainterPath, bool]:
    """Đường vẽ trên lưới 24×24 và cờ `filled` (tô đặc thay vì vẽ nét)."""
    p = QPainterPath()
    if kind == "open":                                      # thư mục đang mở
        p.moveTo(3, 19)
        p.lineTo(3, 6)
        p.quadTo(3, 4, 5, 4)
        p.lineTo(9, 4)
        p.lineTo(11, 6.5)
        p.lineTo(18, 6.5)
        p.quadTo(20, 6.5, 20, 8.5)
        p.lineTo(20, 10)
        p.moveTo(3, 19)
        p.lineTo(6.2, 11.2)
        p.quadTo(6.6, 10, 7.9, 10)
        p.lineTo(21, 10)
        p.quadTo(22.3, 10, 21.9, 11.3)
        p.lineTo(19.6, 18.2)
        p.quadTo(19.2, 19.5, 17.8, 19.5)
        p.lineTo(3.5, 19.5)
        return p, False
    if kind == "copy":                                      # hai tờ giấy chồng nhau
        p.addRoundedRect(QRectF(8.5, 8.5, 12.5, 12.5), 2, 2)
        p.moveTo(5, 15.5)
        p.quadTo(3, 15.5, 3, 13.5)
        p.lineTo(3, 5)
        p.quadTo(3, 3, 5, 3)
        p.lineTo(13.5, 3)
        p.quadTo(15.5, 3, 15.5, 5)
        return p, False
    if kind == "export":                                    # mũi tên xuống vào khay = lưu ra file
        p.moveTo(12, 3.5)
        p.lineTo(12, 15)
        p.moveTo(7, 10)
        p.lineTo(12, 15)
        p.lineTo(17, 10)
        p.moveTo(3.5, 15)
        p.lineTo(3.5, 18.5)
        p.quadTo(3.5, 20.5, 5.5, 20.5)
        p.lineTo(18.5, 20.5)
        p.quadTo(20.5, 20.5, 20.5, 18.5)
        p.lineTo(20.5, 15)
        return p, False
    if kind == "clear":                                     # thùng rác
        p.moveTo(3.5, 6.5)
        p.lineTo(20.5, 6.5)
        p.moveTo(18.5, 6.5)
        p.lineTo(17.7, 19)
        p.quadTo(17.6, 21, 15.6, 21)
        p.lineTo(8.4, 21)
        p.quadTo(6.4, 21, 6.3, 19)
        p.lineTo(5.5, 6.5)
        p.moveTo(9, 6.5)
        p.lineTo(9, 4.5)
        p.quadTo(9, 3, 10.5, 3)
        p.lineTo(13.5, 3)
        p.quadTo(15, 3, 15, 4.5)
        p.lineTo(15, 6.5)
        p.moveTo(10, 11)
        p.lineTo(10, 16.5)
        p.moveTo(14, 11)
        p.lineTo(14, 16.5)
        return p, False
    if kind == "stop":
        p.addRoundedRect(QRectF(5.5, 5.5, 13, 13), 2.2, 2.2)
        return p, True
    if kind in ("chevron-down", "chevron-up"):
        y0, y1 = (9, 15) if kind == "chevron-down" else (15, 9)
        p.moveTo(6, y0)
        p.lineTo(12, y1)
        p.lineTo(18, y0)
        return p, False
    raise ValueError(f"không có biểu tượng '{kind}'")


def _pixmap(kind: str, px: int, color: str, scale: int) -> QPixmap:
    size = px * scale
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    path, filled = _path(kind)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    if filled:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
    else:
        pen = QPen(QColor(color), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def line_icon(kind: str, px: int = 20, color: str = INK) -> QIcon:
    """QIcon có sẵn bản 1×/2× và bản mờ cho trạng thái bị khóa."""
    icon = QIcon()
    for scale in (1, 2):
        icon.addPixmap(_pixmap(kind, px, color, scale), QIcon.Mode.Normal)
        icon.addPixmap(_pixmap(kind, px, INK_DISABLED, scale), QIcon.Mode.Disabled)
    return icon


def icon_button(kind: str, parent=None, px: int = 20, size: int = 38) -> QToolButton:
    """Nút vuông chỉ có biểu tượng. Chữ nằm ở tooltip và tên trợ năng — bên gọi đặt trong
    `retranslate()` để đổi theo ngôn ngữ giao diện."""
    b = QToolButton(parent)
    b.setIcon(line_icon(kind, px))
    b.setIconSize(QSize(px, px))
    b.setFixedSize(size, size)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    return b


def icon_center_of_mass(kind: str, px: int = 24) -> QPointF:
    """Trọng tâm nét vẽ (cho test: biểu tượng không lệch hẳn về một góc ô)."""
    img = _pixmap(kind, px, "#FFFFFF", 1).toImage()
    sx = sy = n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 64:
                sx, sy, n = sx + x, sy + y, n + 1
    return QPointF(sx / max(n, 1), sy / max(n, 1))
