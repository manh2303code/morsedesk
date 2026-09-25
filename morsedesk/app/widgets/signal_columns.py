"""Phổ theo CỘT THỜI GIAN cho cảnh 3D và phổ 2D, dùng chung cho trang Giải mã và trang Nghe.

Mỗi cột = 32 ms âm thanh: công suất lớn nhất (MAX, không trung bình — dit ngắn không bị xóa) của
4 khung Hann 256 mẫu bước 64, giữ các bin 0–2000 Hz (bin 31,25 Hz). Khung đặt CÂN quanh tâm cột,
nên cột j là đúng khoảng [j·32 ms, (j+1)·32 ms). Hai nguồn cùng một lưới cột:

- `FileColumns`: cả file đã có; tính LƯỜI theo từng ô 12 s khi khung nhìn cần tới (một ô ~3 ms),
  giữ tối đa MAX_TILES ô. File một giờ không phải tính hết trước khi xem được đoạn đầu.
- `LiveColumns`: âm thanh đang vào; vòng đệm giữ `keep_s` giây gần nhất (cột float16 + âm thanh
  int16 để nghe lại sau khi dừng). 10 phút = ~2,4 MB cột + 9,6 MB âm thanh.

Mức hiển thị (`Levels`) tính cho CẢ nguồn, không theo khung nhìn: khung trượt liên tục mà mức
tính lại theo khung thì núi phồng xẹp theo từng bước cuộn.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.constants import SAMPLE_RATE

COL_SAMPLES = 256
COL_S = COL_SAMPLES / SAMPLE_RATE           # 0,032 s
N_FFT = 256
FRAME_HOP = 64
FRAMES_PER_COL = COL_SAMPLES // FRAME_HOP
LEAD = (N_FFT - FRAME_HOP) // 2             # khung đầu bắt đầu trước cột 96 mẫu -> 4 khung cân quanh tâm
BIN_HZ = SAMPLE_RATE / N_FFT
MAX_HZ = 2000.0
N_BINS = int(MAX_HZ / BIN_HZ) + 1           # 65 bin, 0..2000 Hz
FREQS = (np.arange(N_BINS) * BIN_HZ).astype(np.float32)
TILE_COLS = 375                             # 12 s
MAX_TILES = 48                              # ~10 phút của file đang xem, ~4,7 MB
_WINDOW = np.hanning(N_FFT).astype(np.float32)
_OFFS = (np.arange(FRAMES_PER_COL)[:, None] * FRAME_HOP + np.arange(N_FFT)[None, :])   # [4, 256]


def columns_db(seg: np.ndarray, n: int) -> np.ndarray:
    """`seg` bắt đầu LEAD mẫu trước cột đầu và đủ dài cho `n` cột -> dB [N_BINS, n]."""
    starts = np.arange(n)[:, None, None] * COL_SAMPLES
    frames = seg[starts + _OFFS[None]] * _WINDOW                        # [n, 4, 256]
    power = np.abs(np.fft.rfft(frames, axis=-1)[..., :N_BINS]) ** 2
    return (10.0 * np.log10(power.max(axis=1) + 1e-12)).T.astype(np.float32)


def span_needed(n: int) -> int:
    """Số mẫu (tính từ LEAD trước cột đầu) mà `n` cột cần."""
    return (n - 1) * COL_SAMPLES + FRAMES_PER_COL * FRAME_HOP + N_FFT - FRAME_HOP if n > 0 else 0


class FileColumns:
    def __init__(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"cần âm thanh {SAMPLE_RATE} Hz")
        self._x = np.asarray(x, dtype=np.float32).reshape(-1)
        self.n_cols = int(np.ceil(len(self._x) / COL_SAMPLES))
        self._tiles: dict[int, np.ndarray] = {}

    @property
    def duration_s(self) -> float:
        return len(self._x) / SAMPLE_RATE

    def col_range(self) -> tuple[int, int]:
        return 0, self.n_cols

    def _tile(self, k: int) -> np.ndarray:
        t = self._tiles.pop(k, None)
        if t is None:
            c0 = k * TILE_COLS
            n = min(TILE_COLS, self.n_cols - c0)
            s0 = c0 * COL_SAMPLES - LEAD
            need = span_needed(n)
            seg = self._x[max(0, s0):s0 + need]
            if s0 < 0 or len(seg) < need:                  # mép file: đệm số 0
                pad_l = max(0, -s0)
                seg = np.concatenate([np.zeros(pad_l, np.float32), seg,
                                      np.zeros(max(0, need - pad_l - len(seg)), np.float32)])
            t = columns_db(seg, n)
            if len(self._tiles) >= MAX_TILES:
                self._tiles.pop(next(iter(self._tiles)))    # bỏ ô dùng lâu nhất
        self._tiles[k] = t                                  # dict giữ thứ tự: cuối = mới dùng
        return t

    def columns(self, c0: int, c1: int) -> np.ndarray:
        """dB [N_BINS, c1 - c0]; cột ngoài file là NaN."""
        out = np.full((N_BINS, max(0, c1 - c0)), np.nan, np.float32)
        a, b = max(c0, 0), min(c1, self.n_cols)
        k = a // TILE_COLS
        while a < b:
            tile = self._tile(k)
            lo = k * TILE_COLS
            hi = min(b, lo + tile.shape[1])
            out[:, a - c0:hi - c0] = tile[:, a - lo:hi - lo]
            a = hi
            k += 1
        return out

    def sample(self, max_tiles: int = 16) -> np.ndarray:
        """Các ô rải đều cả file (để tính mức hiển thị cho cả file mà không tính hết file)."""
        n_tiles = max(1, int(np.ceil(self.n_cols / TILE_COLS)))
        picks = np.unique(np.linspace(0, n_tiles - 1, min(n_tiles, max_tiles)).round().astype(int))
        return np.concatenate([self._tile(int(k)) for k in picks], axis=1) if self.n_cols else \
            np.zeros((N_BINS, 0), np.float32)


class LiveColumns:
    """Cột của âm thanh đang vào. Cột j = [j·32 ms, (j+1)·32 ms) kể từ lúc bấm Nghe."""

    def __init__(self, keep_s: float = 600.0) -> None:
        self.keep_cols = int(keep_s / COL_S)
        self._cols = np.zeros((N_BINS, self.keep_cols), np.float16)
        self._audio_cap = self.keep_cols * COL_SAMPLES
        self._audio = np.zeros(self._audio_cap, np.int16)
        self.clear()

    def clear(self, keep_time: bool = False) -> None:
        """Xóa lịch sử. `keep_time`: giữ mốc thời gian (nút Xóa giữa phiên — bộ giải mã đếm tiếp)."""
        if not keep_time:
            self._written = 0
            self._samples = 0
            self._pending = np.zeros(LEAD, np.float32)       # đệm số 0 trước cột đầu
        self._first = self._written                          # cột cũ nhất còn giữ
        self._audio_first = self._samples

    @property
    def written(self) -> int:
        return self._written

    @property
    def now_s(self) -> float:
        """Giây âm thanh đã nhận (kể cả phần chưa đủ thành cột)."""
        return self._samples / SAMPLE_RATE

    def col_range(self) -> tuple[int, int]:
        return max(self._first, self._written - self.keep_cols), self._written

    def push(self, block) -> int:
        b = np.asarray(block, dtype=np.float32).reshape(-1)
        if len(b):
            self._store_audio(b)
            self._pending = np.concatenate([self._pending, b])
        n = 0
        if len(self._pending) >= span_needed(1):
            n = (len(self._pending) - span_needed(1)) // COL_SAMPLES + 1
            db = columns_db(self._pending, n)
            for i in range(n):
                self._cols[:, (self._written + i) % self.keep_cols] = db[:, i]
            self._written += n
            self._pending = self._pending[n * COL_SAMPLES:]
        return n

    def _store_audio(self, b: np.ndarray) -> None:
        pcm = (np.clip(b, -1.0, 1.0) * 32767).astype(np.int16)[-self._audio_cap:]
        i = self._samples % self._audio_cap
        first = min(len(pcm), self._audio_cap - i)
        self._audio[i:i + first] = pcm[:first]
        self._audio[:len(pcm) - first] = pcm[first:]
        self._samples += len(b)

    def columns(self, c0: int, c1: int) -> np.ndarray:
        out = np.full((N_BINS, max(0, c1 - c0)), np.nan, np.float32)
        lo, hi = self.col_range()
        a, b = max(c0, lo), min(c1, hi)
        if a < b:
            idx = np.arange(a, b) % self.keep_cols
            out[:, a - c0:b - c0] = self._cols[:, idx]
        return out

    def recent(self, seconds: float) -> np.ndarray:
        lo, hi = self.col_range()
        return self.columns(max(lo, hi - int(seconds / COL_S)), hi)

    def recording(self) -> tuple[float, np.ndarray]:
        """(giây bắt đầu, âm thanh float32) của phần còn giữ — để nghe lại sau khi dừng."""
        start = max(self._audio_first, self._samples - self._audio_cap)
        n = self._samples - start
        if n <= 0:
            return start / SAMPLE_RATE, np.zeros(0, np.float32)
        idx = np.arange(start, self._samples) % self._audio_cap
        return start / SAMPLE_RATE, self._audio[idx].astype(np.float32) / 32767.0


@dataclass
class Levels:
    """Mức hiển thị: nền (phân vị 20) và khoảng [lo, hi] trải lên hết chiều cao / thang màu."""

    floor: float
    lo: float
    hi: float

    @classmethod
    def of(cls, db: np.ndarray, min_range: float, max_range: float) -> Levels | None:
        v = db[np.isfinite(db)]
        if v.size == 0:
            return None
        floor = float(np.percentile(v, 20))
        hi = max(float(np.percentile(v, 99.5)), floor + min_range)
        return cls(floor, max(floor, hi - max_range), hi)

    def scale(self, db: np.ndarray, gamma: float = 1.0) -> np.ndarray:
        z = np.clip((db - self.lo) / max(self.hi - self.lo, 1e-6), 0.0, 1.0)
        z = np.nan_to_num(z, nan=0.0)
        return (z ** gamma).astype(np.float32) if gamma != 1.0 else z.astype(np.float32)

    def above_floor(self, db: np.ndarray, cap: float) -> np.ndarray:
        return np.clip(db - self.floor, 0.0, cap).astype(np.float32)


def band_rows(tone_hz: float, half_bins: int = 8) -> np.ndarray:
    """Chỉ số bin của 17 hàng quanh tone (±250 Hz), hàng 0 = tần số CAO nhất (sau cùng cảnh 3D)."""
    c = int(round(tone_hz / BIN_HZ))
    c = max(half_bins, min(N_BINS - 1 - half_bins, c))
    return np.arange(c + half_bins, c - half_bins - 1, -1)


def peak_hz(db: np.ndarray, min_db: float = 10.0) -> float | None:
    """Tone nổi rõ nhất (mức lúc phím nhấn = phân vị 90 theo thời gian); None nếu không có đỉnh rõ."""
    ok = db[:, np.isfinite(db[0])] if db.size else db
    if ok.shape[1] < 8:
        return None
    keep = (FREQS >= 150.0) & (FREQS <= 1950.0)
    level = np.percentile(ok[keep], 90, axis=1)
    i = int(np.argmax(level))
    if level[i] - float(np.median(level)) < min_db:
        return None
    return float(FREQS[keep][i])
