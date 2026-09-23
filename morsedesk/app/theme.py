"""Giao diện "thiết bị đo": nền đêm, một màu hành động, dữ liệu vẽ bằng bảng màu phổ.

Theo hướng người dùng chỉ định (tham chiếu SDR Console): máy thu có nền tối để phổ và thác nước
nổi lên, số đo đọc như mặt đồng hồ. Ba nguyên tắc giữ cho nó khỏi thành một theme tối chung chung:

- Nền là xanh ĐÊM (#0E1627), không phải đen xám — cùng họ với nền logo.
- Chỉ MỘT màu hành động: vàng đèn tín hiệu (LAMP). Nút chính, tab đang chọn, dấu Morse đều
  dùng nó; mọi thứ khác lùi về các sắc xanh xám.
- Dữ liệu (phổ, thác nước, phong cảnh 3D) dùng CHUNG một bảng màu phổ `spectrum_rgb`. Trước đây
  trang Giải mã và trang Nghe mỗi trang một bảng màu.

Stylesheet đặt ở cấp QApplication, nên widget giữ nguyên tên và hành vi — các test cũ vẫn đúng.
KHÔNG đặt `font-family`/`font-size` cho `QWidget` trong stylesheet: quy tắc đó đè mọi `setFont` của
mã (chuỗi Morse mất chữ đơn cách, số đo mất kiểu mặt đồng hồ — thấy trên ảnh chụp). Font giao diện
đặt bằng `QApplication.setFont` trong `fonts.apply_application_font`.
"""

from __future__ import annotations

import numpy as np

from morsedesk.app.branding import LAMP

NIGHT = "#0E1627"        # nền cửa sổ
PANEL = "#141F35"        # vùng nội dung
RAISED = "#1B2946"       # ô nhập, nút phụ
LINE = "#2A3B60"         # đường kẻ, viền
TEXT = "#E6ECF7"         # chữ chính (13,9:1 trên NIGHT)
MUTED = "#95A3BF"        # chữ phụ (6,4:1 trên NIGHT)
LAMP_HOVER = "#FFB846"
LAMP_TEXT = "#1A1206"    # chữ trên nền LAMP (9,6:1)
DANGER = "#F26B5B"

# Độ tin cậy trên nền tối: màu cho viền dưới và chữ số, nền chip là màu đó pha loãng.
CONF_GOOD = "#46C47A"
CONF_MID = "#E0B341"
CONF_LOW = "#F26B5B"

UI_FONT = "Noto Sans"
READOUT_FONT = "DejaVu Sans Mono"

# Bảng màu phổ kiểu SDR: nền nhiễu chìm vào màu đêm, tín hiệu mạnh lên vàng rồi đỏ. Điểm neo đầu
# gần NIGHT để mặt nhiễu không thành một mảng xanh chói như bảng viridis cũ.
_SPECTRUM_STOPS = np.array([
    [14, 22, 39],      # 0.00 nền đêm
    [22, 48, 110],     # 0.18 lam đậm
    [24, 110, 190],    # 0.36 lam
    [22, 190, 200],    # 0.52 lục lam
    [90, 220, 110],    # 0.66 lục
    [245, 225, 60],    # 0.80 vàng
    [250, 150, 40],    # 0.90 cam
    [240, 70, 50],     # 1.00 đỏ
], dtype=np.float32)
_SPECTRUM_POS = np.array([0.0, 0.18, 0.36, 0.52, 0.66, 0.80, 0.90, 1.0], dtype=np.float32)


def spectrum_rgb(v: np.ndarray) -> np.ndarray:
    """Giá trị 0..1 -> RGB uint8 theo bảng màu phổ chung."""
    v = np.clip(np.asarray(v, dtype=np.float32), 0.0, 1.0)
    out = np.empty(v.shape + (3,), dtype=np.uint8)
    for c in range(3):
        out[..., c] = np.interp(v, _SPECTRUM_POS, _SPECTRUM_STOPS[:, c]).astype(np.uint8)
    return out


def spectrum_lut(n: int = 256) -> np.ndarray:
    """Bảng tra màu cho pyqtgraph.ImageItem (n x 3, uint8)."""
    return spectrum_rgb(np.linspace(0.0, 1.0, n))


def spectrum_stops() -> list[tuple[float, str]]:
    """Điểm neo dạng (vị trí, #rrggbb) cho QLinearGradient."""
    return [(float(p), "#{:02x}{:02x}{:02x}".format(*tuple(int(x) for x in c)))
            for p, c in zip(_SPECTRUM_POS, _SPECTRUM_STOPS, strict=True)]


def stylesheet() -> str:
    return f"""
QWidget {{ background: {NIGHT}; color: {TEXT}; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE}; padding: 4px 6px; }}
QToolBar {{ background: {NIGHT}; border: none; border-bottom: 1px solid {LINE}; padding: 4px 10px;
            spacing: 8px; }}
QTabWidget::pane {{ border: none; border-top: 1px solid {LINE}; background: {PANEL}; }}
QTabBar {{ background: {NIGHT}; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 9px 18px 8px 18px; margin: 0;
                border: none; border-bottom: 3px solid transparent; font-weight: 600; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 3px solid {LAMP}; }}
QLabel {{ background: transparent; }}
QPushButton {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE}; border-radius: 6px;
               padding: 6px 14px; }}
QPushButton:hover {{ border-color: {MUTED}; }}
QPushButton:focus {{ border-color: {LAMP}; }}
QPushButton:disabled {{ color: #5E6B86; border-color: #22304F; background: #172238; }}
QPushButton[primary="true"] {{ background: {LAMP}; color: {LAMP_TEXT}; border: 1px solid {LAMP};
                               font-weight: 700; padding: 7px 20px; }}
QPushButton[primary="true"]:hover {{ background: {LAMP_HOVER}; }}
QPushButton[primary="true"]:disabled {{ background: #4A3D22; color: #8F7C55; border-color: #4A3D22; }}
QPushButton:checked {{ background: {LAMP}; color: {LAMP_TEXT}; border-color: {LAMP}; }}
QToolButton {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE}; border-radius: 8px;
               padding: 0px; }}
QToolButton:hover {{ border-color: {MUTED}; background: #22335A; }}
QToolButton:focus {{ border-color: {LAMP}; }}
QToolButton:pressed, QToolButton:open {{ background: {LINE}; }}
QToolButton:disabled {{ border-color: #22304F; background: #172238; }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}
QToolButton[flat="true"] {{ background: transparent; border: none; color: {MUTED}; padding: 2px 6px;
                            font-weight: 600; }}
QToolButton[flat="true"]:hover {{ color: {TEXT}; }}
QMenu {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE}; border-radius: 6px; padding: 4px; }}
QMenu::item {{ padding: 7px 18px 7px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {LINE}; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE};
                                       border-radius: 6px; padding: 4px 8px; min-height: 22px; }}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {MUTED}; }}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: #5E6B86; }}
QComboBox QAbstractItemView {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE};
                               selection-background-color: {LINE}; }}
QPlainTextEdit, QTextEdit {{ background: {PANEL}; color: {TEXT}; border: 1px solid {LINE};
                             border-radius: 8px; padding: 6px; selection-background-color: #36507F; }}
QCheckBox {{ background: transparent; spacing: 6px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {MUTED}; border-radius: 4px;
                        background: {RAISED}; }}
QCheckBox::indicator:checked {{ background: {LAMP}; border-color: {LAMP}; }}
QCheckBox:disabled {{ color: #5E6B86; }}
QProgressBar {{ background: {RAISED}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {LAMP}; border-radius: 3px; }}
QSlider::groove:horizontal {{ height: 4px; background: {LINE}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {LAMP}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 12px; height: 12px; margin: -5px 0;
                              border-radius: 6px; }}
QSplitter::handle {{ background: {NIGHT}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #34496F; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {LINE}; border-radius: 4px; min-width: 30px; }}
QFrame[panel="true"] {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; }}
QLabel[role="caption"] {{ color: {MUTED}; font-size: 9pt; }}
QLabel[role="section"] {{ color: {TEXT}; font-size: 11pt; font-weight: 700; }}
QLabel[role="hint"] {{ color: {MUTED}; }}
"""


def mark_primary(button) -> None:
    """Nút hành động chính của trang (chỉ một nút mỗi trang)."""
    button.setProperty("primary", True)
    button.style().unpolish(button)
    button.style().polish(button)


def apply_theme(app) -> None:
    """Đặt bảng màu Qt + stylesheet cho toàn ứng dụng. Gọi sau khi đã nạp font."""
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, NIGHT), (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Base, PANEL), (QPalette.ColorRole.AlternateBase, RAISED),
        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.Button, RAISED),
        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, "#36507F"),
        (QPalette.ColorRole.HighlightedText, TEXT), (QPalette.ColorRole.ToolTipBase, RAISED),
        (QPalette.ColorRole.ToolTipText, TEXT), (QPalette.ColorRole.PlaceholderText, MUTED),
        (QPalette.ColorRole.Link, LAMP),
    ):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    font = app.font()
    font.setPointSizeF(10.0)
    app.setFont(font)
    app.setStyleSheet(stylesheet())
