"""Sinh biểu tượng MorseDesk: phím Morse vẽ nét, phía trên là `· · –` màu đèn tín hiệu.

Hình học nằm ở `morsedesk/app/branding.py` (LOGO_LARGE / LOGO_SMALL) và dùng chung với màn hình
chờ động và trang Giới thiệu. Cảm hứng từ logo GGMorse (ô bo góc, phím Morse nét đơn) nhưng là hình
riêng; hàng `· · –` (chữ U) là dấu hiệu nhận diện giữ lại từ logo đầu tiên.

Vẽ bằng hàm khoảng cách có dấu (SDF) trên numpy, lấy mẫu dày rồi gộp để khử răng cưa, ghi PNG thủ
công — không thêm phụ thuộc chỉ vì một biểu tượng. Ở 16–24 px dùng bản rút gọn (LOGO_SMALL): nét
0,03 của bản lớn chỉ còn nửa điểm ảnh ở cỡ thanh tác vụ.

    uv run python packaging/make_icon.py            # ghi morsedesk/app/icons/ + packaging/appimage/
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from morsedesk.app.branding import (  # noqa: E402  (cần ROOT trên sys.path trước)
    KEY_INK,
    LAMP,
    TILE_BOTTOM,
    TILE_TOP,
    logo_geometry,
)

ICON_DIR = ROOT / "morsedesk" / "app" / "icons"
APPIMAGE_ICON = ROOT / "packaging" / "appimage" / "morsedesk.png"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


LAMP_RGB = _rgb(LAMP)
INK_RGB = _rgb(KEY_INK)
TOP_RGB, BOTTOM_RGB = _rgb(TILE_TOP), _rgb(TILE_BOTTOM)


def png_bytes(rgba: np.ndarray) -> bytes:
    """PNG RGBA 8 bit (color type 6) từ mảng [H, W, 4] uint8."""
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(rgba.shape[0]))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", rgba.shape[1], rgba.shape[0], 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _sdf_round_box(px: np.ndarray, py: np.ndarray, half: float, radius: float) -> np.ndarray:
    qx = np.abs(px - 0.5) - (half - radius)
    qy = np.abs(py - 0.5) - (half - radius)
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    return outside + inside - radius


def _sdf_capsule(px, py, x0, y0, x1, y1, half_width) -> np.ndarray:
    dx, dy = x1 - x0, y1 - y0
    t = np.clip(((px - x0) * dx + (py - y0) * dy) / max(dx * dx + dy * dy, 1e-12), 0.0, 1.0)
    return np.hypot(px - (x0 + t * dx), py - (y0 + t * dy)) - half_width


def _sdf_shape(px, py, shape) -> np.ndarray:
    kind, *a = shape
    if kind == "circle":
        cx, cy, r = a
        return np.hypot(px - cx, py - cy) - r
    if kind == "capsule":
        return _sdf_capsule(px, py, *a)
    if kind == "round_box":                     # khung rỗng: |sdf| - nửa độ dày nét
        cx, cy, hx, hy, r, w = a
        qx = np.abs(px - cx) - (hx - r)
        qy = np.abs(py - cy) - (hy - r)
        d = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0)) + np.minimum(np.maximum(qx, qy), 0.0) - r
        return np.abs(d) - w
    raise ValueError(kind)


def render(size: int, supersample: int = 8) -> np.ndarray:
    """Ảnh RGBA [size, size, 4]."""
    geo = logo_geometry(size)
    n = size * supersample
    c = (np.arange(n) + 0.5) / n
    px, py = np.meshgrid(c, c)
    # Chừa 1/32 lề trong suốt: một số thanh tác vụ cắt sát mép, và góc bo cần chỗ để mềm.
    bg = _sdf_round_box(px, py, half=0.5 - 1 / 32, radius=0.22) <= 0.0
    marks = np.zeros_like(bg)
    for shp in geo["marks"]:
        marks |= _sdf_shape(px, py, shp) <= 0.0
    key = np.zeros_like(bg)
    for shp in geo["key"]:
        key |= _sdf_shape(px, py, shp) <= 0.0
    marks &= bg
    key &= bg & ~marks

    def pool(mask: np.ndarray) -> np.ndarray:
        return mask.reshape(size, supersample, size, supersample).mean(axis=(1, 3))

    a_bg, a_marks, a_key = pool(bg), pool(marks), pool(key)
    t_row = (np.arange(size) + 0.5) / size
    tile = np.empty((size, size, 3))
    for i in range(3):
        tile[..., i] = (TOP_RGB[i] * (1 - t_row) + BOTTOM_RGB[i] * t_row)[:, None]
    safe = np.where(a_bg > 0, a_bg, 1.0)
    fm, fk = a_marks / safe, a_key / safe            # tỉ lệ phủ trong phần nền
    rgb = np.empty((size, size, 3))
    for i in range(3):
        rgb[..., i] = tile[..., i] * (1 - fm - fk) + LAMP_RGB[i] * fm + INK_RGB[i] * fk
    rgba = np.dstack([rgb, a_bg * 255.0])
    return np.clip(np.rint(rgba), 0, 255).astype(np.uint8)


def ico_bytes(pngs: list[tuple[int, bytes]]) -> bytes:
    """ICO nhiều cỡ, mỗi mục là một PNG nguyên vẹn (Windows Vista trở đi đọc được)."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, data in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out_dir = Path(argv[0]) if argv else ICON_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for size in SIZES:
        path = out_dir / f"morsedesk-{size}.png"
        path.write_bytes(png_bytes(render(size)))
        written.append(path)
    if not argv:
        APPIMAGE_ICON.write_bytes((out_dir / "morsedesk-256.png").read_bytes())
        written.append(APPIMAGE_ICON)
    for p in written:
        print(f"  {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} ({p.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
