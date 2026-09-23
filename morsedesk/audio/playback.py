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
        self._pos = 0                       # khung kế tiếp sẽ đẩy ra
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
        self._finished = False

    def _callback(self, outdata, frames, time_info, status) -> None:
        with self._lock:
            start = self._pos
            end = min(start + frames, len(self._x))
            chunk = self._x[start:end]
            self._pos = end
        n = len(chunk)
        outdata[:n, 0] = chunk
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
        self._finished = False

    def seek(self, seconds: float) -> None:
        """Nhảy tới một mốc thời gian; kẹp trong [0, độ dài]. An toàn khi đang phát."""
        frame = int(max(0.0, float(seconds)) * self.sample_rate)
        with self._lock:
            self._pos = min(frame, len(self._x))
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
