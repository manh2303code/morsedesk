"""Sinh biểu tượng MorseDesk: một khuôn mặt cười ghép từ hai dấu chấm và một dấu gạch Morse.

Hai mắt là hai `dit`, miệng là một `dah` uốn cong. Đọc từ trên xuống: `· · –`, tức chữ U trong
Morse. Nền là ô vuông bo góc màu "hoàng hôn" #1F2B4D, nét màu "đèn tín hiệu" #F5A524 — Morse
cũng là ánh sáng (đèn Aldis) chứ không chỉ là âm thanh.

Vẽ bằng hàm khoảng cách có dấu (SDF) trên numpy, lấy mẫu dày rồi gộp lại để khử răng cưa, và ghi
PNG thủ công — không thêm phụ thuộc chỉ vì một biểu tượng. Ở cỡ 16–24 px, mắt và nét miệng được
làm DÀY hơn theo tỉ lệ (optical sizing): cùng hình học ở 16 px sẽ cho nét 1,9 px, nhòe trên thanh
tác vụ.

    uv run python packaging/make_icon.py            # ghi morsedesk/app/icons/ + packaging/appimage/
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "morsedesk" / "app" / "icons"
APPIMAGE_ICON = ROOT / "packaging" / "appimage" / "morsedesk.png"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

DUSK = (0x1F, 0x2B, 0x4D)
LAMP = (0xF5, 0xA5, 0x24)


def png_bytes(rgba: np.ndarray) -> bytes:
    """PNG RGBA 8 bit (color type 6) từ mảng [H, W, 4] uint8."""
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(rgba.shape[0]))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", rgba.shape[1], rgba.shape[0], 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def geometry(size: int) -> dict[str, float]:
    """Kích thước tương đối theo cỡ đích: nhỏ thì nét dày hơn và mắt đặt cao hơn để còn khe hở.

    Miệng là cung của một đường tròn LỚN có tâm đặt cao (arc_cy), lấy đoạn ±half độ quanh đáy:
    nụ cười thoải và hai đầu miệng không chạm mắt. Tâm đặt ngang mắt thì khe hở chỉ còn ~0,005.
    """
    if size <= 24:
        return {"eye_r": 0.105, "eye_dx": 0.175, "eye_y": 0.35, "stroke": 0.080,
                "arc_cy": 0.22, "arc_r": 0.42, "half": 30.0}
    if size <= 48:
        return {"eye_r": 0.088, "eye_dx": 0.165, "eye_y": 0.37, "stroke": 0.066,
                "arc_cy": 0.21, "arc_r": 0.43, "half": 29.0}
    return {"eye_r": 0.076, "eye_dx": 0.160, "eye_y": 0.38, "stroke": 0.058,
            "arc_cy": 0.20, "arc_r": 0.44, "half": 28.0}


def _sdf_round_box(px: np.ndarray, py: np.ndarray, half: float, radius: float) -> np.ndarray:
    qx = np.abs(px - 0.5) - (half - radius)
    qy = np.abs(py - 0.5) - (half - radius)
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    return outside + inside - radius


def _sdf_arc(px, py, cx, cy, r, a0, a1, half_width) -> np.ndarray:
    """Cung tròn tâm (cx, cy) bán kính r từ góc a0 tới a1 (radian, trục y hướng xuống), đầu tròn."""
    dx, dy = px - cx, py - cy
    ang = np.arctan2(dy, dx)
    on_arc = np.abs(np.hypot(dx, dy) - r)
    ends = np.minimum(np.hypot(px - (cx + r * np.cos(a0)), py - (cy + r * np.sin(a0))),
                      np.hypot(px - (cx + r * np.cos(a1)), py - (cy + r * np.sin(a1))))
    return np.where((ang >= a0) & (ang <= a1), on_arc, ends) - half_width


def render(size: int, supersample: int = 8) -> np.ndarray:
    """Ảnh RGBA [size, size, 4]."""
    g = geometry(size)
    n = size * supersample
    c = (np.arange(n) + 0.5) / n
    px, py = np.meshgrid(c, c)
    # Chừa 1/32 lề trong suốt: một số thanh tác vụ cắt sát mép, và góc bo cần chỗ để mềm.
    bg = _sdf_round_box(px, py, half=0.5 - 1 / 32, radius=0.22) <= 0.0
    eyes = ((np.hypot(px - (0.5 - g["eye_dx"]), py - g["eye_y"]) <= g["eye_r"])
            | (np.hypot(px - (0.5 + g["eye_dx"]), py - g["eye_y"]) <= g["eye_r"]))
    mouth = _sdf_arc(px, py, 0.5, g["arc_cy"], g["arc_r"], np.radians(90 - g["half"]),
                     np.radians(90 + g["half"]), g["stroke"]) <= 0.0
    ink = (eyes | mouth) & bg

    def pool(mask: np.ndarray) -> np.ndarray:
        return mask.reshape(size, supersample, size, supersample).mean(axis=(1, 3))

    a_bg, a_ink = pool(bg), pool(ink)
    rgb = np.empty((size, size, 3))
    for i in range(3):
        # Nét nằm TRÊN nền: pha màu theo tỉ lệ phủ của nét trong phần nền.
        t = np.divide(a_ink, a_bg, out=np.zeros_like(a_ink), where=a_bg > 0)
        rgb[..., i] = DUSK[i] * (1 - t) + LAMP[i] * t
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
