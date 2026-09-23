"""Nhận diện của MorseDesk: biểu tượng, bảng màu, và định danh để thanh tác vụ hiện đúng logo.

Bảng màu "đèn tín hiệu lúc hoàng hôn": Morse là ánh sáng (đèn Aldis) cũng như âm thanh. Nền hero
và biểu tượng dùng DUSK, nét tín hiệu dùng LAMP. Bề mặt đọc (trang Giới thiệu, tài liệu kỹ thuật)
là PAPER lạnh, không phải kem ấm. Trong tài liệu kỹ thuật, MỖI TẦNG XỬ LÝ có một màu riêng và
giữ màu đó suốt tài liệu — màu ở đây mang thông tin (đang đọc tầng nào), không phải trang trí.
"""

from __future__ import annotations

import sys
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent / "icons"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

# Định danh ứng dụng. Windows: thiếu AppUserModelID thì khi chạy từ mã nguồn, thanh tác vụ gom
# cửa sổ vào python.exe và hiện biểu tượng Python. Linux/Wayland: app_id = tên file .desktop,
# là thứ dock dùng để tìm biểu tượng.
APP_USER_MODEL_ID = "MorseDesk.MorseDesk"
DESKTOP_FILE_NAME = "morsedesk"

DUSK = "#1F2B4D"        # nền hero, nền biểu tượng
DUSK_DEEP = "#172039"   # viền dưới hero
LAMP = "#F5A524"        # nét tín hiệu: dit, dah, nút chính trên nền DUSK
PAPER = "#F4F6FA"       # bề mặt đọc
INK = "#1B2233"         # chữ trên PAPER (tương phản 14,9:1)
SLATE = "#56627A"       # chữ phụ trên PAPER (5,6:1)
MIST = "#C9D2E3"        # chữ phụ trên DUSK (8,9:1)

# Màu theo tầng xử lý, dùng chung cho trang Giới thiệu và tài liệu kỹ thuật. Cặp (đậm, nhạt):
# đậm cho chữ/viền (đạt 4,5:1 trên PAPER), nhạt cho nền khối.
LAYER_COLORS = {
    "signal": ("#0B6E78", "#E1F1F2"),     # tầng tín hiệu: dò tone, đặc trưng, cửa sổ
    "model": ("#9A5B00", "#FBEFD9"),      # model âm thanh CTC
    "language": ("#5B3FA6", "#ECE7F7"),   # beam + mô hình ngôn ngữ + nhận diện ngôn ngữ
    "dsp": ("#2F4F8F", "#E4EAF6"),        # bộ giải mã DSP và quy tắc chọn đường
    "safety": ("#A63A32", "#F7E4E2"),     # độ tin cậy, chống bịa chữ, cảnh báo
}


def icon_paths() -> list[Path]:
    return [ICON_DIR / f"morsedesk-{s}.png" for s in ICON_SIZES if (ICON_DIR / f"morsedesk-{s}.png").exists()]


def app_icon():
    """QIcon nhiều cỡ: thanh tác vụ lấy 16–48, Alt-Tab và dock lấy 64–256."""
    from PySide6.QtGui import QIcon

    icon = QIcon()
    for path in icon_paths():
        icon.addFile(str(path))
    return icon


def set_windows_app_id() -> bool:
    """Gọi TRƯỚC khi hiện cửa sổ nào; không phải Windows thì không làm gì."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        return True
    except (AttributeError, OSError):
        return False


def install_app_identity(app) -> None:
    """Biểu tượng cho mọi cửa sổ + app_id cho Wayland. Gọi ngay sau khi có QApplication."""
    app.setWindowIcon(app_icon())
    app.setDesktopFileName(DESKTOP_FILE_NAME)


def morse_elements(text: str) -> list[tuple[float, float]]:
    """(bắt đầu, độ dài) theo đơn vị dit cho mọi dấu bật của `text` theo bảng tiếng Anh.

    Nhịp chuẩn ITU: dit 1, dah 3, khoảng trong ký tự 1, giữa ký tự 3, giữa từ 7. Dùng để vẽ tên
    ứng dụng thành chuỗi đèn tín hiệu trên trang Giới thiệu — đúng mã, không phải hoa văn.
    """
    from morsedesk.lm.profile import load_profile

    patterns = {chars[0]: code for code, chars in load_profile("en").map.items()}
    out: list[tuple[float, float]] = []
    t = 0.0
    for wi, word in enumerate(text.upper().split()):
        if wi:
            t += 4.0                       # 3 đã cộng sau ký tự cuối + 4 = 7
        for ch in word:
            for sym in patterns[ch]:
                length = 3.0 if sym == "-" else 1.0
                out.append((t, length))
                t += length + 1.0
            t += 2.0                       # 1 sau dấu cuối + 2 = 3
    return out
