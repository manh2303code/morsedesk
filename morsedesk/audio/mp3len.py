"""Độ dài THẬT của MP3 — libsndfile đoán sai với MP3 VBR không có header Xing/Info.

Đo 27/09 trên hai bài tập số tải từ internet ("Азбука Морзе - 30/60 знаков цифры"): libsndfile đọc
89,4 s / 82,6 s trong khi file dài 130,7 s / 113,8 s (ffmpeg giải hết) — MẤT LẶNG LẼ ~30 % bản tin.
Không có header Xing, libsndfile (mpg123) ước lượng độ dài bằng bitrate của KHUNG ĐẦU TIÊN (731 byte
= 224 kbps trong khi trung bình thật 165 kbps) rồi dừng đọc đúng ở đó; đọc tiếp theo khối cũng không
qua được.

Sửa không cần ffmpeg (máy air-gap có thể không có): đếm khung bằng cách duyệt header từng khung, rồi
nếu khác con số libsndfile sẽ dùng thì chèn (hoặc vá) một khung Xing ghi đúng số khung — đúng cách
LAME làm; mpg123 đọc số đó và giải hết file.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Layer III: bitrate (kbps) theo chỉ số, cho MPEG1 và MPEG2/2.5
_BR_V1 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
_BR_V2 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
_SR = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}   # theo mã phiên bản


@dataclass(frozen=True)
class Mp3Layout:
    first: int              # byte của khung âm thanh đầu tiên
    frames: int             # số khung âm thanh (không kể khung Xing/Info)
    samples_per_frame: int
    sample_rate: int
    header: bytes           # 4 byte header khung đầu
    info_at: int | None     # vị trí chữ "Xing"/"Info" trong khung đầu (nếu khung đầu là khung thông tin)
    info_frames: int | None  # số khung mà khung thông tin khai

    @property
    def seconds(self) -> float:
        return self.frames * self.samples_per_frame / self.sample_rate


def _parse(h: bytes) -> tuple[int, int, int, int] | None:
    """(độ dài khung, số mẫu/khung, tần số lấy mẫu, độ lệch side info) của header Layer III; None nếu sai."""
    if len(h) < 4 or h[0] != 0xFF or (h[1] & 0xE0) != 0xE0:
        return None
    ver, layer = (h[1] >> 3) & 3, (h[1] >> 1) & 3
    bri, sri, pad = (h[2] >> 4) & 15, (h[2] >> 2) & 3, (h[2] >> 1) & 1
    if ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
        return None
    sr = _SR[ver][sri]
    mono = (h[3] >> 6) & 3 == 3
    if ver == 3:
        br, length, spf, side = _BR_V1[bri], 144000 * _BR_V1[bri] // sr + pad, 1152, (17 if mono else 32)
    else:
        br, length, spf, side = _BR_V2[bri], 72000 * _BR_V2[bri] // sr + pad, 576, (9 if mono else 17)
    return (length, spf, sr, 4 + side) if br else None


def _skip_id3(data: bytes) -> int:
    if data[:3] == b"ID3" and len(data) >= 10:
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        return 10 + size + (10 if data[5] & 0x10 else 0)
    return 0


def layout(data: bytes) -> Mp3Layout | None:
    """Duyệt khung MP3 (Layer III). Khung được nhận khi header hợp lệ VÀ khung kế tiếp cũng bắt đầu
    bằng header hợp lệ (hoặc hết file) — tránh nhận nhầm 0xFFE trong dữ liệu ảnh bìa/rác."""
    i, n = _skip_id3(data), len(data)
    first = hdr = None
    frames = spf = sr = 0
    info_at = info_frames = None
    while i + 4 <= n:
        p = _parse(data[i:i + 4])
        if p is None:
            i += 1
            continue
        length, s_pf, s_r, side = p
        nxt = i + length
        if nxt + 4 <= n and _parse(data[nxt:nxt + 4]) is None and data[nxt:nxt + 3] not in (b"TAG", b"ID3", b"APE"):
            i += 1
            continue
        if first is None:
            first, hdr, spf, sr = i, data[i:i + 4], s_pf, s_r
            tag = data[i + side:i + side + 4]
            if tag in (b"Xing", b"Info"):
                info_at = i + side
                flags = struct.unpack(">I", data[i + side + 4:i + side + 8])[0]
                if flags & 1:
                    info_frames = struct.unpack(">I", data[i + side + 8:i + side + 12])[0]
                i = nxt
                continue                                # khung thông tin không phải âm thanh
        frames += 1
        i = nxt
    if first is None or not frames:
        return None
    return Mp3Layout(first, frames, spf, sr, hdr, info_at, info_frames)


def with_true_length(data: bytes, reported_frames: int | None = None) -> bytes | None:
    """Bản MP3 mà libsndfile sẽ đọc HẾT; None nếu không cần sửa (hoặc không phải MP3 Layer III).

    `reported_frames`: số mẫu libsndfile khai cho file gốc — khớp với số khung đếm được thì thôi."""
    lay = layout(data)
    if lay is None:
        return None
    if lay.info_frames == lay.frames:
        return None                                     # header đã đúng
    true_samples = lay.frames * lay.samples_per_frame
    # libsndfile trừ độ trễ bộ mã hóa + đệm cuối (gapless, < 3 khung) — lệch cỡ đó là đúng
    if reported_frames is not None and abs(reported_frames - true_samples) <= 3 * lay.samples_per_frame:
        return None
    if lay.info_at is not None:
        flags = struct.unpack(">I", data[lay.info_at + 4:lay.info_at + 8])[0]
        if flags & 1:                                   # vá số khung tại chỗ
            k = lay.info_at + 8
            return data[:k] + struct.pack(">I", lay.frames) + data[k + 4:]
    # chèn khung Xing: cùng header với khung đầu, không CRC, không padding
    h = bytearray(lay.header)
    h[1] |= 0x01
    h[2] &= ~0x02 & 0xFF
    parsed = _parse(bytes(h))
    if parsed is None:
        return None
    length, _, _, side = parsed
    frame = bytearray(length)
    frame[:4] = h
    frame[side:side + 12] = b"Xing" + struct.pack(">II", 1, lay.frames)
    start = lay.first if lay.info_at is None else lay.first    # khung thông tin cũ (không có số khung) giữ nguyên
    return data[:start] + bytes(frame) + data[start:]
