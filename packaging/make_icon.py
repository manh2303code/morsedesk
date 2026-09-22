"""Sinh icon PNG 256x256 cho AppImage: chữ M bằng mã Morse trên nền tối.

Vẽ bằng numpy rồi ghi PNG thủ công để không phải thêm phụ thuộc chỉ vì một biểu tượng.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

SIZE = 256
BG = (18, 20, 24)
FG = (86, 214, 138)


def png_bytes(rgb: np.ndarray) -> bytes:
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(rgb.shape[0]))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", rgb.shape[1], rgb.shape[0], 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "morsedesk.png")
    img = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    img[:, :] = BG
    # "M" trong Morse là hai gạch; vẽ hai thanh dày ở giữa, cách nhau một dit.
    unit = SIZE // 16
    y0, y1 = SIZE // 2 - unit, SIZE // 2 + unit
    x = 2 * unit
    for _ in range(2):
        img[y0:y1, x: x + 5 * unit] = FG
        x += 6 * unit
    out.write_bytes(png_bytes(img))
    print(f"đã ghi {out} ({out.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
