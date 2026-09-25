"""Vẽ logo (phím Morse + `· · –`) bằng QPainter, có thể nhấn cần gõ và thắp từng dấu.

Cùng hình học `branding.LOGO_LARGE` với biểu tượng (vẽ bằng SDF trong packaging/make_icon.py),
nên màn hình chờ động, trang Giới thiệu và biểu tượng thanh tác vụ luôn là một hình.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen

from morsedesk.app.branding import KEY_INK, LAMP, LOGO_LARGE, TILE_BOTTOM, TILE_TOP

LAMP_DIM = "#34406A"          # dấu chưa thắp: thấy hình, không tranh với dấu đã sáng


def _lerp(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def paint_logo(p: QPainter, rect: QRectF, lever_deg: float = 0.0, lit: tuple[float, ...] = (1, 1, 1),
               tile: bool = True, spark: float = 0.0, dah_grows: bool = True) -> None:
    """Vẽ logo vào `rect` (vuông).

    lever_deg: góc nhấn cần gõ quanh trục (dương = núm đi xuống). lit: độ sáng 0..1 của từng dấu
    (dit, dit, dah); với dah, giá trị < 1 còn là phần đã "gõ" xong (thanh dài dần). spark: độ sáng
    tia lửa ở tiếp điểm khi đang nhấn. dah_grows=False: dah luôn đủ dài, `lit` chỉ là độ sáng (phím
    động ở trang Tạo mã — dah mờ khi không kêu chứ không "đang gõ dở").
    """
    s = rect.width()
    ox, oy = rect.x(), rect.y()

    def pt(x: float, y: float) -> QPointF:
        return QPointF(ox + x * s, oy + y * s)

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if tile:
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        g.setColorAt(0.0, QColor(TILE_TOP))
        g.setColorAt(1.0, QColor(TILE_BOTTOM))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        inset = s / 32
        p.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), s * 0.22, s * 0.22)

    # ---- dấu · · – ----
    dim, lamp = QColor(LAMP_DIM), QColor(LAMP)
    for i, shape in enumerate(LOGO_LARGE["marks"]):
        level = lit[i] if i < len(lit) else 1.0
        color = _lerp(dim, lamp, level)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        if shape[0] == "circle":
            _, cx, cy, r = shape
            p.drawEllipse(pt(cx, cy), r * s, r * s)
        else:
            _, x0, y0, x1, y1, w = shape
            if level < 1.0 and i == 2 and dah_grows:
                # dah đang được gõ: vẽ nền mờ đủ dài, rồi phần sáng dài dần theo `level`
                pen = QPen(dim, 2 * w * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(pt(x0, y0), pt(x1, y1))
                if level > 0:
                    pen.setColor(lamp)
                    p.setPen(pen)
                    p.drawLine(pt(x0, y0), pt(x0 + (x1 - x0) * level, y1))
            else:
                p.setPen(QPen(color, 2 * w * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(pt(x0, y0), pt(x1, y1))

    # ---- phím ----
    ink = QColor(KEY_INK)
    shapes = LOGO_LARGE["key"]
    base, pivot_post, contact, lever, knob = shapes
    px, py = LOGO_LARGE["pivot"]

    def stroke(w: float) -> QPen:
        return QPen(ink, 2 * w * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    _, cx, cy, hx, hy, r, w = base
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(stroke(w))
    p.drawRoundedRect(QRectF(ox + (cx - hx) * s, oy + (cy - hy) * s, 2 * hx * s, 2 * hy * s), r * s, r * s)
    for post in (pivot_post, contact):
        _, x0, y0, x1, y1, w = post
        p.setPen(stroke(w))
        p.drawLine(pt(x0, y0), pt(x1, y1))
    if spark > 0.0:
        _, x0, y0, _x1, _y1, _w = contact
        glow = QColor(LAMP)
        glow.setAlphaF(0.85 * spark)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(pt(x0, y0 - 0.012), 0.03 * s * (0.6 + spark), 0.03 * s * (0.6 + spark))
    # cần gõ và núm xoay quanh trục
    p.save()
    p.translate(pt(px, py))
    p.rotate(lever_deg)
    p.translate(-pt(px, py))
    _, x0, y0, x1, y1, w = lever
    p.setPen(stroke(w))
    p.drawLine(pt(x0, y0), pt(x1, y1))
    _, kx, ky, kr = knob
    path = QPainterPath()
    path.addEllipse(pt(kx, ky), kr * s, kr * s)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ink)
    p.drawPath(path)
    p.restore()
    p.restore()
