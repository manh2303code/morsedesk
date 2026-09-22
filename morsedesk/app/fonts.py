"""Font đóng gói cùng ứng dụng (CP-11).

Qt trên máy không có font nào sẽ vẽ mọi ký tự thành ô vuông — đã gặp khi chụp màn hình headless.
Máy air-gap tối giản có rủi ro tương tự, và nặng nhất với chữ Kazakh Ә Ғ Қ Ң Ө Ұ Ү Һ І, vì nhiều
font Latin phổ biến không có chúng.

Font nằm trong gói chứ không phải ngoài hệ thống, nên AppImage mang theo là đủ. Tải bằng
`uv run python tools/fetch_fonts.py`; thư mục không có trong repo (file nhị phân lớn).
"""

from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "fonts"
KAZAKH_LETTERS = "ӘҒҚҢӨҰҮҺІ"
# Thứ tự ưu tiên khi đặt font ứng dụng: DejaVu phủ Cyrillic mở rộng rộng nhất trong hai bộ.
PREFERRED_FAMILIES = ("DejaVu Sans", "Noto Sans")


def bundled_fonts() -> list[Path]:
    if not FONT_DIR.is_dir():
        return []
    return sorted(p for p in FONT_DIR.iterdir() if p.suffix.lower() in (".ttf", ".otf"))


def load_bundled_fonts() -> list[str]:
    """Nạp mọi font trong gói vào Qt, trả danh sách họ font đã đăng ký được."""
    from PySide6.QtGui import QFontDatabase

    families: list[str] = []
    for path in bundled_fonts():
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families += list(QFontDatabase.applicationFontFamilies(font_id))
    return list(dict.fromkeys(families))


def apply_application_font() -> str | None:
    """Đặt font ứng dụng theo thứ tự ưu tiên; trả họ đã chọn, hoặc None nếu không nạp được gì.

    Không ép font khi máy đã có sẵn font tốt hơn là chủ ý: chỉ đặt khi chính font trong gói được
    nạp thành công, để giao diện vẫn theo hệ thống ở nơi hệ thống có font đầy đủ.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    families = load_bundled_fonts()
    if not families:
        return None
    chosen = next((f for f in PREFERRED_FAMILIES if f in families), families[0])
    app = QApplication.instance()
    if app is not None:
        font = QFont(app.font())
        font.setFamilies([chosen, *families])
        app.setFont(font)
    return chosen
