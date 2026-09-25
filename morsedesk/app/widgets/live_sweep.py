"""Dữ liệu cho cảnh 3D trang Nghe: quét từ trái sang phải như màn hình điện tim.

Người dùng 25/09: cảnh 3D trực tiếp phải "realtime nhưng theo chiều từ trái sang phải thay vì cứ
chạy ra sau". Nên cảnh nay giống hệt cảnh 3D trang Giải mã — ngang là thời gian, sâu là tần số
±250 Hz quanh tone — chỉ khác là dữ liệu tới dần: một đầu ghi đi từ trái sang phải, hết
`SWEEP_S` giây thì quay về trái và ghi đè lượt trước. Cảnh đứng yên, chỉ đầu ghi chạy.

Vòng đệm giữ phổ ĐỦ dải (không chỉ dải quanh tone) cho từng cột, nên khi bộ giải mã báo tone mới
thì cả cảnh vẽ lại quanh tone đó, không có nửa cảnh cũ nửa cảnh mới. Mốc thời gian là số giây kể từ
lúc bấm Nghe — đúng mốc của `StreamDecoder` (Word.start_s), nên rê chuột nói được từ nào ở đó.
"""

from __future__ import annotations

import numpy as np

from morsedesk.app.widgets.ridge3d import BandScene, normalize_band
from morsedesk.constants import SAMPLE_RATE

SWEEP_S = 12.0              # một lượt quét = cửa sổ cảnh 3D trang Giải mã
COL_SAMPLES = 256           # 32 ms/cột ở 8 kHz (trang Giải mã: 33 ms) — dit 40 WPM vẫn chiếm ~1 cột
N_COLS = int(round(SWEEP_S * SAMPLE_RATE / COL_SAMPLES))      # 375
N_FFT = 256                 # bin 31,25 Hz, như dsp/stft của trang Giải mã
FRAME_HOP = 64              # 4 khung mỗi cột, gộp bằng MAX (dit ngắn không bị xóa)
FRAMES_PER_COL = COL_SAMPLES // FRAME_HOP
HALF_BINS = 8               # ±8 bin = ±250 Hz -> 17 hàng, như trang Giải mã
DEFAULT_CENTER_HZ = 700.0   # chưa có tone nào: đặt dải ở tone Morse phổ biến nhất
# Chỉ có nhiễu thì phân vị 99,5 cũng chỉ trên nền vài dB; kéo giãn chừng đó lên hết chiều cao là
# vẽ nhiễu thành núi. Dải tối thiểu 20 dB giữ cảnh nhiễu thấp, tín hiệu thật vẫn chạm đỉnh.
MIN_RANGE_DB = 20.0
PEAK_MIN_DB = 10.0          # tự tìm tone khi bộ giải mã chưa báo: đỉnh phải nổi hơn nền chừng này
PEAK_LO_HZ, PEAK_HI_HZ = 150.0, 1950.0
# Dời dải khi tâm mới lệch quá chừng này. Đỉnh phổ tự tìm nhảy theo nhiễu: ngưỡng ~3/4 bin để cảnh
# khỏi giật. Tone bộ giải mã báo thì ổn định: ngưỡng nhỏ, nhãn "720 Hz ± 250 Hz" khớp ô Tone.
RECENTER_HZ = 23.0
RECENTER_TONE_HZ = 8.0


class LiveSweep:
    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = int(sample_rate)
        self.freqs = np.fft.rfftfreq(N_FFT, 1.0 / self.sample_rate).astype(np.float32)
        self.bin_hz = float(self.freqs[1])
        self._window = np.hanning(N_FFT).astype(np.float32)
        self._frame_idx = np.arange(FRAMES_PER_COL)[:, None] * FRAME_HOP + np.arange(N_FFT)[None, :]
        self.clear()

    def clear(self, keep_time: bool = False) -> None:
        """Xóa cảnh. `keep_time`: giữ mốc thời gian (nút Xóa giữa phiên nghe — bộ giải mã vẫn đếm tiếp)."""
        self._db = np.full((len(self.freqs), N_COLS), np.nan, dtype=np.float32)
        if not keep_time:
            self._written = 0
            self._pending = np.zeros(0, dtype=np.float32)
        self._tone_hz: float | None = None
        self._center_hz: float | None = None

    # ---- dữ liệu vào ----
    def push(self, block) -> int:
        """Thêm audio; trả số cột mới. Mỗi cột = MAX công suất của 4 khung Hann 256 mẫu."""
        b = np.asarray(block, dtype=np.float32).reshape(-1)
        if len(b):
            self._pending = np.concatenate([self._pending, b]) if len(self._pending) else b
        need = COL_SAMPLES + N_FFT - FRAME_HOP
        n = 0
        while len(self._pending) >= need:
            frames = self._pending[self._frame_idx] * self._window
            power = np.abs(np.fft.rfft(frames, axis=1)) ** 2
            self._db[:, self._written % N_COLS] = 10.0 * np.log10(power.max(axis=0) + 1e-12)
            self._written += 1
            self._pending = self._pending[COL_SAMPLES:]
            n += 1
        return n

    def set_tone(self, hz: float | None) -> None:
        """Tone bộ giải mã đang bám — đáng tin hơn đỉnh phổ tự tìm; None = giữ tone cũ."""
        if hz:
            self._tone_hz = float(hz)

    # ---- vị trí ----
    @property
    def written(self) -> int:
        return self._written

    def cursor(self) -> int:
        """Ô sẽ được ghi tiếp theo (cũng là ô cũ nhất của lượt trước)."""
        return self._written % N_COLS

    def playhead(self) -> float | None:
        """Vị trí đầu ghi 0..1 trên cảnh (cùng thang với cột: cột k ở k / (N_COLS - 1))."""
        if self._written == 0:
            return None
        return min(1.0, self.cursor() / (N_COLS - 1))

    def now_s(self) -> float:
        return self._written * COL_SAMPLES / self.sample_rate

    def column_time(self, k: int) -> float | None:
        """Giây (kể từ lúc bấm Nghe) ở giữa cột ô `k`; None nếu ô chưa có dữ liệu."""
        cur = self.cursor()
        start = self._written - cur                     # cột đầu của lượt đang ghi
        j = start + k if k < cur else start - N_COLS + k
        if not 0 <= j < self._written:
            return None
        return (j + 0.5) * COL_SAMPLES / self.sample_rate

    def column_of(self, t_s: float | None) -> int | None:
        """Ô chứa giây `t_s`, nếu giây đó còn trên cảnh (trong lượt này hoặc phần còn của lượt trước)."""
        if t_s is None:
            return None
        j = int(np.floor(t_s * self.sample_rate / COL_SAMPLES))
        if not (max(0, self._written - N_COLS) <= j < self._written):
            return None
        return j % N_COLS

    # ---- dải tần ----
    def center_hz(self) -> float:
        """Tâm dải: tone bộ giải mã báo; chưa có thì đỉnh phổ nổi rõ; không có gì thì 700 Hz."""
        target = self._tone_hz if self._tone_hz else self._peak_hz()
        if target is None:
            target = self._center_hz if self._center_hz is not None else DEFAULT_CENTER_HZ
        limit = RECENTER_TONE_HZ if self._tone_hz else RECENTER_HZ
        if self._center_hz is None or abs(target - self._center_hz) > limit:
            self._center_hz = float(target)
        return self._center_hz

    def _peak_hz(self) -> float | None:
        filled = self._db[:, ~np.isnan(self._db[0])]
        if filled.shape[1] < 8:
            return None
        keep = (self.freqs >= PEAK_LO_HZ) & (self.freqs <= PEAK_HI_HZ)
        level = np.percentile(filled[keep], 90, axis=1)     # mức lúc phím nhấn, không phải trung bình
        i = int(np.argmax(level))
        if level[i] - float(np.median(level)) < PEAK_MIN_DB:
            return None
        return float(self.freqs[keep][i])

    def band_bins(self) -> np.ndarray:
        """Chỉ số bin của 17 hàng, hàng 0 = tần số cao nhất (sau cùng của cảnh)."""
        c = int(round(self.center_hz() / self.bin_hz))
        c = max(HALF_BINS + 1, min(len(self.freqs) - HALF_BINS - 1, c))
        return np.arange(c + HALF_BINS, c - HALF_BINS - 1, -1)

    def scene(self) -> BandScene:
        """Cảnh [17 hàng, N_COLS cột]: ô chưa có dữ liệu thì phẳng (0) và không có mức dB."""
        bins = self.band_bins()
        band = self._db[bins, :]
        filled = ~np.isnan(band[0])
        z = np.zeros(band.shape, np.float32)
        rel = np.full(band.shape, np.nan, np.float32)
        if filled.any():
            z_f, rel_f = normalize_band(band[:, filled], min_range_db=MIN_RANGE_DB)
            z[:, filled] = z_f
            rel[:, filled] = rel_f
        return BandScene(z, rel, self.freqs[bins])
