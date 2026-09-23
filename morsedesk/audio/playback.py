"""Phát audio có theo dõi vị trí, để giao diện chạy con trỏ và tô từ đang nghe.

`app.worker.Player` chỉ gọi `sounddevice.play()` rồi quên: đủ để nghe thử ở trang Tạo mã, nhưng
không biết đang phát tới đâu nên không thể đồng bộ với văn bản. Lớp ở đây mở `OutputStream` và
tự đếm khung đã đẩy ra, nên `position_s` luôn đúng với cái tai đang nghe.

Module thuộc lõi nên KHÔNG import Qt, và `sounddevice` được import trễ trong hàm: máy đích
air-gap có thể thiếu `libportaudio2`, khi đó `import sounddevice` ném ngay lúc nạp module và kéo
sập cả CLI lẫn GUI.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from morsedesk.constants import SAMPLE_RATE

log = logging.getLogger(__name__)

BLOCK_FRAMES = 1024     # ~128 ms ở 8 kHz: đủ nhỏ để con trỏ mượt, đủ lớn để không vỡ tiếng
# Co giãn thời gian (WSOLA) cho tốc độ khác 1×. Chỉ ảnh hưởng tiếng NGHE LẠI, không dính gì tới
# giải mã. Khung 30 ms chồng 50 % (cửa sổ Hann), mỗi khung được dời tối đa ±4 ms — hơn một chu kỳ
# của tone thấp nhất (300 Hz = 3,3 ms) — tới chỗ khớp pha nhất với phần nối tiếp tự nhiên của
# khung trước, nên tone Morse giữ đúng cao độ và không vỡ tiếng ở chỗ nối.
WSOLA_FRAME_S = 0.030
WSOLA_TOLERANCE_S = 0.004


_HANN: dict[int, np.ndarray] = {}


def _hann(n: int) -> np.ndarray:
    """Hann tuần hoàn: hai khung chồng 50 % cộng lại đúng bằng 1, nên biên độ không phập phồng."""
    w = _HANN.get(n)
    if w is None:
        w = _HANN[n] = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)
    return w


class PlaybackError(RuntimeError):
    """Không mở được thiết bị phát (thiếu PortAudio, thiết bị bận hoặc biến mất)."""


class _StopPlayback(Exception):
    """Thay thế khi chưa có `sounddevice.CallbackStop` (chỉ xảy ra trong test dùng stream giả)."""


class AudioPlayback:
    """Phát một mảng float32 và cho biết đang ở giây thứ mấy.

    Vị trí đếm theo số khung PortAudio đã YÊU CẦU, không phải đã nghe thấy: hai con số lệch nhau
    đúng bằng độ trễ đệm của thiết bị (thường 10-100 ms). Chấp nhận được cho việc tô chữ, và
    tránh hẳn việc phải hỏi `stream.time` vốn không đồng nhất giữa các backend.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, block: int = BLOCK_FRAMES) -> None:
        self.sample_rate = int(sample_rate)
        self.block = int(block)
        self._x: np.ndarray = np.zeros(0, dtype=np.float32)
        self._pos = 0                       # khung NGUỒN kế tiếp sẽ đẩy ra (kể cả khi phát nhanh/chậm)
        self._gain = 1.0
        self._speed = 1.0
        self._reset_stretch()
        self._stream = None
        self._lock = threading.Lock()       # callback chạy ở thread thời gian thực của PortAudio
        self._finished = False
        # Ngoại lệ PortAudio hiểu là "hết dữ liệu, dừng đẹp". Lấy từ sounddevice lúc mở stream
        # chứ không import ở tầng module, vì module này phải nạp được trên máy thiếu PortAudio.
        self._stop_exc: type[BaseException] = _StopPlayback

    # ---- trạng thái ----
    @property
    def duration_s(self) -> float:
        return len(self._x) / self.sample_rate if self.sample_rate else 0.0

    @property
    def position_s(self) -> float:
        with self._lock:
            return self._pos / self.sample_rate if self.sample_rate else 0.0

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def volume(self) -> float:
        return self._gain

    def set_volume(self, gain: float) -> None:
        """Hệ số âm lượng 0..1, có hiệu lực ngay cả khi đang phát."""
        with self._lock:
            self._gain = max(0.0, min(1.0, float(gain)))

    def set_speed(self, rate: float) -> None:
        """Tốc độ nghe lại 0,5..2 (1 = nguyên bản). Giữ cao độ; đổi được khi đang phát."""
        rate = max(0.5, min(2.0, float(rate)))
        with self._lock:
            if rate != self._speed:
                self._speed = rate
                self._reset_stretch()

    @property
    def playing(self) -> bool:
        return self._stream is not None and not self._finished

    @property
    def finished(self) -> bool:
        """True khi đã phát hết mảng (khác với dừng giữa chừng)."""
        return self._finished

    # ---- điều khiển ----
    def load(self, x: np.ndarray, sample_rate: int | None = None) -> None:
        """Nạp mảng mới và đưa con trỏ về đầu; dừng hẳn lần phát đang chạy."""
        self.stop()
        if sample_rate:
            self.sample_rate = int(sample_rate)
        self._x = np.asarray(x, dtype=np.float32).reshape(-1)
        with self._lock:
            self._pos = 0
            self._reset_stretch()
        self._finished = False

    # ---- co giãn thời gian (WSOLA, theo khối) ----
    def _reset_stretch(self) -> None:
        """Bỏ trạng thái nối khung: sau seek/đổi tốc độ, khung kế tiếp bắt đầu lại từ `_pos`."""
        self._ana: float | None = None      # vị trí phân tích (khung nguồn) của khung kế tiếp
        self._prev_start: int | None = None
        self._ola = np.zeros(0, dtype=np.float32)
        self._queue = np.zeros(0, dtype=np.float32)

    def _stretch_frame(self) -> bool:
        """Sinh thêm một bước nhảy (nửa khung) tiếng đã co giãn vào `_queue`. False khi hết nguồn."""
        x, sr = self._x, self.sample_rate
        n = max(16, int(WSOLA_FRAME_S * sr) // 2 * 2)
        hop = n // 2
        tol = max(1, int(WSOLA_TOLERANCE_S * sr))
        if self._ana is None:
            self._ana = float(self._pos)
            self._ola = np.zeros(hop, dtype=np.float32)
        a = int(round(self._ana))
        if a >= len(x):
            return False
        if self._prev_start is None:
            start = a
        else:
            # Phần nối tiếp TỰ NHIÊN của khung trước; chọn trong [a-tol, a+tol] đoạn giống nó nhất.
            nat = self._prev_start + hop
            target = x[nat: nat + n]
            lo = max(0, a - tol)
            region = x[lo: a + tol + n]
            if len(target) == n and len(region) >= n:
                corr = np.correlate(region, target, mode="valid")
                start = lo + int(np.argmax(corr))
            else:
                start = a
        frame = x[start: start + n]
        if len(frame) < n:
            frame = np.concatenate([frame, np.zeros(n - len(frame), dtype=np.float32)])
        frame = frame * _hann(n)
        out = self._ola + frame[:hop]
        self._ola = frame[hop:].astype(np.float32)
        self._queue = np.concatenate([self._queue, out.astype(np.float32)])
        self._prev_start = start
        self._pos = min(start, len(x))
        self._ana += hop * self._speed
        return True

    def _callback(self, outdata, frames, time_info, status) -> None:
        with self._lock:
            gain = self._gain
            if self._speed == 1.0:
                start = self._pos
                end = min(start + frames, len(self._x))
                chunk = self._x[start:end]
                self._pos = end
            else:
                while len(self._queue) < frames and self._stretch_frame():
                    pass
                chunk, self._queue = self._queue[:frames], self._queue[frames:]
                end = self._pos
                if len(chunk) < frames:             # nguồn đã cạn: đẩy nốt phần chồng khung
                    chunk = np.concatenate([chunk, self._ola])[:frames]
                    self._ola = np.zeros(0, dtype=np.float32)
                    self._pos = end = len(self._x)
        n = len(chunk)
        outdata[:n, 0] = chunk * gain if gain != 1.0 else chunk
        if n < frames:
            outdata[n:, 0] = 0.0        # đuôi im lặng, nếu không PortAudio phát lại rác của buffer
        if end >= len(self._x):
            # Đánh dấu ngay ở khối CUỐI chứ không đợi một callback rỗng nữa: khi độ dài chia hết
            # cho blocksize, đợi thêm nghĩa là `finished` còn False trong lúc loa đã im.
            self._finished = True
            # `CallbackStop` là cách PortAudio hiểu "phát nốt khối này rồi dừng". Không gọi
            # stop() ở đây: PortAudio cấm đóng stream từ trong chính callback của nó.
            raise self._stop_exc

    def play(self, from_s: float | None = None) -> None:
        """Bắt đầu (hoặc tiếp tục) phát. Gọi lại khi đang phát là vô hại."""
        if len(self._x) == 0:
            return
        if from_s is not None:
            self.seek(from_s)
        if self._stream is not None:
            return
        if self._finished or self.position_s >= self.duration_s:
            self.seek(0.0)
        sd = _sounddevice()
        self._stop_exc = getattr(sd, "CallbackStop", _StopPlayback)
        try:
            stream = sd.OutputStream(
                samplerate=self.sample_rate, blocksize=self.block, channels=1,
                dtype="float32", callback=self._callback,
                finished_callback=self._on_stream_finished,
            )
            stream.start()
        except Exception as e:
            raise PlaybackError(f"cannot open output device: {type(e).__name__}: {e}") from e
        self._finished = False
        self._stream = stream

    def pause(self) -> None:
        """Dừng nhưng GIỮ vị trí, để bấm phát lại là nghe tiếp."""
        stream, self._stream = self._stream, None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception:
            log.warning("closing output stream failed", exc_info=True)

    def stop(self) -> None:
        """Dừng và đưa con trỏ về đầu."""
        self.pause()
        with self._lock:
            self._pos = 0
            self._reset_stretch()
        self._finished = False

    def seek(self, seconds: float) -> None:
        """Nhảy tới một mốc thời gian; kẹp trong [0, độ dài]. An toàn khi đang phát."""
        frame = int(max(0.0, float(seconds)) * self.sample_rate)
        with self._lock:
            self._pos = min(frame, len(self._x))
            self._reset_stretch()
        if self._pos < len(self._x):
            self._finished = False

    def _on_stream_finished(self) -> None:
        self._stream = None

    def __enter__(self) -> AudioPlayback:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


def _sounddevice():
    try:
        import sounddevice as sd
    except Exception as e:      # ImportError (không cài) hoặc OSError (thiếu libportaudio2)
        raise PlaybackError(f"sounddevice unavailable: {type(e).__name__}: {e}") from e
    return sd
