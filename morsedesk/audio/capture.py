"""Thu âm thanh trực tiếp: liệt kê thiết bị và đẩy khối PortAudio vào hàng đợi.

Module thuộc lõi nên KHÔNG import Qt. Từ 27/09 mọi lời gọi PortAudio (liệt kê, mở, đóng) chạy ở luồng
thiết bị (audio/engine.py) với hạn giờ: driver âm thanh treo thì luồng nghe nhận `CaptureError` ("thiết
bị không phản hồi") thay vì đứng im mãi, và mở micro luôn đợi mọi tiếng đang phát đóng xong trước.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass

import numpy as np

from morsedesk.audio.engine import (
    CLOSE_TIMEOUT_S,
    OPEN_TIMEOUT_S,
    QUERY_TIMEOUT_S,
    STUCK_TEXT,
    AudioEngine,
    AudioError,
    AudioStuck,
    default_engine,
)
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


def _devices(key: str, engine: AudioEngine | None = None, rescan: bool = False) -> list[AudioDevice]:
    """Liệt kê ở luồng thiết bị và CHỜ kết quả (có hạn giờ). Giao diện nên dùng
    `engine.query_devices()` (không chờ) — hàm này dành cho CLI, test và luồng nghe."""
    eng = engine or default_engine()
    try:
        raw = eng.query_devices(rescan=rescan).result(timeout=QUERY_TIMEOUT_S + CLOSE_TIMEOUT_S)
    except AudioError as e:                 # gồm AudioStuck, AudioUnavailable
        raise CaptureError(str(e)) from e
    except TimeoutError as e:
        raise CaptureError(f"{STUCK_TEXT} (query devices)") from e
    except Exception as e:
        raise CaptureError(f"cannot query audio devices: {type(e).__name__}: {e}") from e
    return devices_from(raw, key)


def devices_from(raw, key: str) -> list[AudioDevice]:
    """`key` = "max_input_channels" / "max_output_channels": các thiết bị có kênh loại đó."""
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


def list_input_devices(engine: AudioEngine | None = None, rescan: bool = False) -> list[AudioDevice]:
    """Thiết bị có kênh thu; ném `CaptureError` nếu không dùng được sounddevice hoặc driver kẹt."""
    return _devices("max_input_channels", engine, rescan)


def list_output_devices(engine: AudioEngine | None = None) -> list[AudioDevice]:
    """Thiết bị có kênh phát; ném `CaptureError` nếu không dùng được sounddevice hoặc driver kẹt."""
    return _devices("max_output_channels", engine)


class AudioCapture:
    """Bọc `sounddevice.InputStream`: callback đẩy khối mono float32 vào `queue.Queue`.

    Hàng đợi đầy nghĩa là bên tiêu thụ (LiveWorker) không theo kịp: bỏ khối vừa tới và
    tăng `dropped`. Tuyệt đối không chặn trong callback — PortAudio gọi nó từ thread
    thời gian thực, chặn ở đó làm méo âm và có thể treo driver.
    """

    def __init__(self, device: int | None = None, block_ms: int = BLOCK_MS,
                 sample_rate: int = SAMPLE_RATE, max_blocks: int = MAX_BLOCKS,
                 engine: AudioEngine | None = None) -> None:
        self.device = device
        self._engine = engine
        self.block_ms = int(block_ms)
        self.sample_rate = int(sample_rate)
        self.blocksize = int(self.sample_rate * self.block_ms / 1000)
        self._queue: queue.Queue = queue.Queue(maxsize=int(max_blocks))
        self._dropped = 0
        self._stream = None
        self._abandoned = False         # start() đã bỏ cuộc (quá hạn): lệnh mở tới muộn phải tự đóng

    @property
    def engine(self) -> AudioEngine:
        return self._engine if self._engine is not None else default_engine()

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
        """Mở và chạy luồng thu (chờ luồng thiết bị, có hạn giờ); gọi lại khi đã chạy là vô hại.

        Chỉ gọi từ luồng KHÔNG phải giao diện (LiveWorker). Mọi tiếng đang phát trong app bị dừng và
        đóng xong TRƯỚC khi micro mở (engine.claim_input).
        """
        if self._stream is not None:
            return
        eng = self.engine
        self._abandoned = False

        def open_input():
            eng.claim_input(self)
            stream = eng.open_stream(lambda sd: sd.InputStream(
                samplerate=self.sample_rate, blocksize=self.blocksize, device=self.device,
                channels=1, dtype="float32", callback=self._callback,
            ))
            stream.start()
            if self._abandoned:                 # bên gọi đã thôi chờ: đừng để micro mở mồ côi
                eng.close_stream(stream)
                eng.release(self)
                return None
            return stream

        try:
            stream = eng.call(open_input, "open input", OPEN_TIMEOUT_S)
        except AudioStuck as e:
            self._abandoned = True
            raise CaptureError(str(e)) from e
        except AudioError as e:
            eng.release(self)
            raise CaptureError(str(e)) from e
        except Exception as e:
            eng.release(self)
            raise CaptureError(f"cannot open input device {self.device}: {type(e).__name__}: {e}") from e
        self._stream = stream

    def _engine_close(self) -> None:
        """Luồng thiết bị giành micro cho phiên nghe khác: đóng tại chỗ."""
        stream, self._stream = self._stream, None
        if stream is not None:
            self.engine.close_stream(stream)

    def stop(self) -> None:
        """Dừng và đóng luồng; an toàn khi chưa start hoặc start đã hỏng. Không chờ driver."""
        stream, self._stream = self._stream, None
        if stream is None:
            return
        eng = self.engine
        # Nhả quyền NGAY: nút Phát bật lại cùng lúc với "đã dừng nghe". Loa vẫn chỉ mở SAU khi micro
        # đóng xong, vì lệnh mở xếp hàng sau lệnh đóng này ở cùng luồng thiết bị.
        eng.release(self)

        def close():
            eng.close_stream(stream)
            eng.release(self)

        eng.submit(close, "close input", CLOSE_TIMEOUT_S, kind="close")

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
