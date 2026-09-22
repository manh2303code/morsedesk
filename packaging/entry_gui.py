"""Điểm vào cho bản đóng gói: gọi thẳng GUI.

Tách khỏi `morsedesk.app.main` để PyInstaller có một file script thật làm gốc phân tích.

Không cần dàn xếp đường dẫn: `api.DEFAULT_MODEL_PATH` lấy `parents[1]` của gói `morsedesk` và
`lm.store.default_lm_dir` lấy `parents[2]` của `morsedesk/lm`, cả hai đều ra thư mục chứa gói —
đúng chỗ `packaging/morsedesk.spec` đặt `models/` trong bản đóng gói.
"""

from __future__ import annotations


def main() -> int:
    from morsedesk.app.main import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
