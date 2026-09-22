"""Thu âm thanh trực tiếp: liệt kê thiết bị và đẩy khối PortAudio vào hàng đợi.

Module thuộc lõi nên KHÔNG import Qt. `sounddevice` được import trễ trong hàm: máy đích
air-gap có thể thiếu `libportaudio2`, khi đó `import sounddevice` ném `OSError` ngay lúc
nạp module và sẽ kéo sập cả CLI lẫn GUI nếu import ở đầu file.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass

import numpy as np

from morsedesk.constants import SAMPLE_RATE

log = logging.getLogger(__name__)

BLOCK_MS = 100          # độ dài một khối thu; 100 ms = 800 mẫu ở 8 kHz
MAX_BLOCKS = 50         # hàng đợi 5 giây; tràn thì bỏ khối MỚI và tăng bộ đếm


class CaptureError(RuntimeError):
    """Không liệt kê hoặc không mở được thiết bị thu (thiếu PortAudio, thiết bị bận/biến mất)."""


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    channels: int
    samplerate: float


def _sounddevice():
    try:
        import sounddevice as sd
    except Exception as e:      # ImportError (không cài) hoặc OSError (thiếu libportaudio2)
        raise CaptureError(f"sounddevice unavailable: {type(e).__name__}: {e}") from e
    return sd


def _devices(key: str) -> list[AudioDevice]:
    sd = _sounddevice()
    try:
        raw = sd.query_devices()
    except Exception as e:
        raise CaptureError(f"cannot query audio devices: {type(e).__name__}: {e}") from e
    out: list[AudioDevice] = []
    for i, d in enumerate(raw):
        channels = int(d.get(key, 0) or 0)
        if channels <= 0:
            continue
        out.append(AudioDevice(
            index=int(d.get("index", i)),
            name=str(d.get("name", f"device {i}")),
            channels=channels,
            samplerate=float(d.get("default_samplerate", SAMPLE_RATE) or SAMPLE_RATE),
        ))
    return out


def list_input_devices() -> list[AudioDevice]:
    """Thiết bị có kênh thu; ném `CaptureError` nếu không dùng được sounddevice."""
    return _devices("max_input_channels")


def list_output_devices() -> list[AudioDevice]:
    """Thiết bị có kênh phát; ném `CaptureError` nếu không dùng được sounddevice."""
    return _devices("max_output_channels")


class AudioCapture:
    """Bọc `sounddevice.InputStream`: callback đẩy khối mono float32 vào `queue.Queue`.

    Hàng đợi đầy nghĩa là bên tiêu thụ (LiveWorker) không theo kịp: bỏ khối vừa tới và
    tăng `dropped`. Tuyệt đối không chặn trong callback — PortAudio gọi nó từ thread
    thời gian thực, chặn ở đó làm méo âm và có thể treo driver.
    """

    def __init__(self, device: int | None = None, block_ms: int = BLOCK_MS,
                 sample_rate: int = SAMPLE_RATE, max_blocks: int = MAX_BLOCKS) -> None:
        self.device = device
        self.block_ms = int(block_ms)
        self.sample_rate = int(sample_rate)
        self.blocksize = int(self.sample_rate * self.block_ms / 1000)
        self._queue: queue.Queue = queue.Queue(maxsize=int(max_blocks))
        self._dropped = 0
        self._stream = None

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    def _callback(self, indata, frames, time_info, status) -> None:
        data = np.asarray(indata, dtype=np.float32)
        mono = data.mean(axis=1) if data.ndim > 1 and data.shape[1] > 1 else data.reshape(-1)
        try:
            self._queue.put_nowait(np.array(mono, dtype=np.float32, copy=True))
        except queue.Full:
            self._dropped += 1

    def start(self) -> None:
        """Mở và chạy luồng thu; gọi lại khi đã chạy là vô hại."""
        if self._stream is not None:
            return
        sd = _sounddevice()
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate, blocksize=self.blocksize, device=self.device,
                channels=1, dtype="float32", callback=self._callback,
            )
            stream.start()
        except Exception as e:
            raise CaptureError(f"cannot open input device {self.device}: {type(e).__name__}: {e}") from e
        self._stream = stream

    def stop(self) -> None:
        """Dừng và đóng luồng; an toàn khi chưa start hoặc start đã hỏng."""
        stream, self._stream = self._stream, None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception:
            log.warning("closing input stream failed", exc_info=True)

    def get(self, timeout: float = 0.2) -> np.ndarray | None:
        """Khối tiếp theo, hoặc `None` khi hết `timeout` (để vòng lặp kiểm cờ dừng)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def __enter__(self) -> AudioCapture:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
