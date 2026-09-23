"""Điểm vào cho bản đóng gói: gọi thẳng GUI.

Tách khỏi `morsedesk.app.main` để PyInstaller có một file script thật làm gốc phân tích.

Không cần dàn xếp đường dẫn: `api.DEFAULT_MODEL_PATH` lấy `parents[1]` của gói `morsedesk` và
`lm.store.default_lm_dir` lấy `parents[2]` của `morsedesk/lm`, cả hai đều ra thư mục chứa gói —
đúng chỗ `packaging/morsedesk.spec` đặt `models/` trong bản đóng gói.
"""

from __future__ import annotations

import sys

SELF_TEST_FLAG = "--self-test"


def self_test(src: str, dst: str) -> int:
    """Giải mã `src` bằng đúng model + LM đóng trong gói, ghi kết quả JSON vào `dst`.

    Bản `.exe` không có console (stdout là None) nên kết quả phải ra file. Mục đích: kiểm một bản
    dựng MỚI thật sự giải mã được — thiếu model, LM, onnxruntime hay libsndfile trong gói đều lộ ra
    ở đây mà không cần mở cửa sổ. Profile `auto` để chạm cả ba LM.
    """
    import json
    from pathlib import Path

    from morsedesk.api import Decoder

    try:
        text = Decoder("auto", engine="onnx").decode_file(src).to_json()
        code = 0
    except Exception as e:                  # báo mọi lỗi ra file: đây là công cụ chẩn đoán
        text = json.dumps({"error": type(e).__name__, "detail": str(e)}, ensure_ascii=False)
        code = 1
    Path(dst).write_text(text, encoding="utf-8")
    return code


def main() -> int:
    argv = sys.argv[1:]
    if len(argv) == 3 and argv[0] == SELF_TEST_FLAG:
        return self_test(argv[1], argv[2])

    from morsedesk.app.main import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
