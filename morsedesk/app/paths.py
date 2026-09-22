"""Đường dẫn dữ liệu của ứng dụng.

Tách khỏi `main.py` vì trang Cài đặt cũng cần, mà `main.py` nạp cả cửa sổ chính nên import từ
đó sẽ thành vòng lặp.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def log_directory() -> Path:
    """Thư mục log theo spec mục 7: `~/.local/share/morsedesk/logs/` trên Linux (CP-15).

    Không dùng thẳng `QStandardPaths.AppDataLocation` vì Qt ghép cả tên tổ chức lẫn tên ứng dụng
    và cho ra `~/.local/share/MorseDesk/MorseDesk/logs`, lệch spec. Linux là nền tảng đích nên ở
    đó theo đúng chuẩn XDG; các nền tảng khác (chỉ dùng để chạy test trên máy dev) vẫn theo Qt.
    """
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        return Path(base) / "morsedesk" / "logs"
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / "logs"
