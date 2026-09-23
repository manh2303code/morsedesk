"""Ảnh tĩnh cho màn hình chờ của PyInstaller: khung ĐẦU TIÊN của màn hình chờ động.

Bootloader của bản .exe một file hiện ảnh này trong lúc bung gói (trước khi Python chạy được);
ngay khi Python lên, `morsedesk.app.splash.SplashScreen` hiện ĐÚNG khung đó ở đúng chỗ rồi bắt đầu
gõ phím — nên người dùng thấy một màn hình liền mạch chứ không phải hai.

    uv run python packaging/make_splash.py        # ghi packaging/splash.png
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "packaging" / "splash.png"


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    from morsedesk.app.fonts import apply_application_font
    from morsedesk.app.splash import render_image

    apply_application_font()
    img = render_image(0.0)
    img.save(str(OUT))
    print(f"{OUT.relative_to(ROOT)} {img.width()}x{img.height()}")
    _ = app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
