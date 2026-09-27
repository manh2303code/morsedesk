"""Phát audio có theo dõi vị trí, để giao diện chạy con trỏ và tô từ đang nghe.

`app.worker.Player` chỉ gọi `sounddevice.play()` rồi quên: đủ để nghe thử ở trang Tạo mã, nhưng
không biết đang phát tới đâu nên không thể đồng bộ với văn bản. Lớp ở đây mở `OutputStream` và
tự đếm khung đã đẩy ra, nên `position_s` luôn đúng với cái tai đang nghe.

Module thuộc lõi nên KHÔNG import Qt. Từ 27/09 lớp này KHÔNG tự gọi PortAudio: mở/dừng/đóng stream là
lệnh gửi cho luồng thiết bị (audio/engine.py) và trả về ngay — driver âm thanh treo thì chỉ luồng đó
kẹt, cửa sổ vẫn chạy. Vị trí đang nghe tính từ mốc thời gian callback ghi lại, không gọi `stream.time`
từ luồng giao diện.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

import numpy as np

from morsedesk.audio.engine import (
    CLOSE_TIMEOUT_S,
    OPEN_TIMEOUT_S,
    STUCK_TEXT,
    AudioBusy,
    AudioEngine,
    AudioError,
    AudioStuck,
    AudioUnavailable,
    default_engine,
)
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
    """Không phát được. `kind`: "busy" (đang nghe), "stuck" (driver không phản hồi), "unavailable"
    (máy không có PortAudio — bấm lại cũng vô ích, tắt hẳn nút), "device" (lỗi mở thiết bị khác)."""

    def __init__(self, message: str, kind: str = "device") -> None:
        super().__init__(message)
        self.kind = kind

    @property
    def permanent(self) -> bool:
        return self.kind == "unavailable"


def _as_playback_error(e: BaseException) -> PlaybackError:
    if isinstance(e, PlaybackError):
        return e
    for cls, kind in ((AudioBusy, "busy"), (AudioStuck, "stuck"), (AudioUnavailable, "unavailable")):
        if isinstance(e, cls):
            return PlaybackError(str(e), kind)
    if isinstance(e, AudioError):
        return PlaybackError(str(e))
    return PlaybackError(f"cannot open output device: {type(e).__name__}: {e}")


class _StopPlayback(Exception):
    """Thay thế khi chưa có `sounddevice.CallbackStop` (chỉ xảy ra trong test dùng stream giả)."""


class AudioPlayback:
    """Phát một mảng float32 và cho biết đang ở giây thứ mấy — giây ĐANG RA LOA.

    Trước 24/09 vị trí đếm theo khung đã GỬI cho PortAudio. Đo trên máy thật
    (tools/playback_sync.py): hình (karaoke, vệt quét 3D, con trỏ phổ) đi TRƯỚC tiếng 315 ms ở 1×,
    628 ms (giây của file) ở 2× — đúng bằng độ trễ đệm của thiết bị, nhân theo tốc độ — và chỉ nhảy
    theo khối 128 ms. Nay mỗi callback ghi lúc mẫu đầu khối tới loa (`outputBufferDacTime`), và
    `position_s` nội suy giây của file gốc đang phát lúc này. Thiết bị/stream không báo thời gian
    (stream giả trong test) thì quay về cách đếm cũ.

    27/09: "lúc này" không còn đọc bằng `stream.time` (một lời gọi PortAudio, 60 lần/giây từ luồng giao
    diện). Mỗi callback ghi lúc khối tới loa theo ĐỒNG HỒ CỦA TA (`clock`): lúc callback chạy + (DAC −
    currentTime) mà PortAudio báo. Mở/dừng/đóng là lệnh cho luồng thiết bị; `play()` trả về ngay,
    `playing` đúng từ lúc bấm, lỗi mở thiết bị (không đồng bộ) nằm ở `error`.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, block: int = BLOCK_FRAMES,
                 engine: AudioEngine | None = None, clock=time.perf_counter) -> None:
        self.sample_rate = int(sample_rate)
        self.block = int(block)
        self._engine = engine
        self._clock = clock
        self._x: np.ndarray = np.zeros(0, dtype=np.float32)
        self._pos = 0                       # khung NGUỒN kế tiếp sẽ đẩy ra (kể cả khi phát nhanh/chậm)
        self._gain = 1.0
        self._speed = 1.0
        self._latency = 0.0
        # (lúc mẫu đầu khối tới loa theo `clock`, khung nguồn đầu khối, khung nguồn cuối khối, giây)
        self._blocks: deque[tuple[float, float, float, float]] = deque(maxlen=64)
        self._reset_stretch()
        self._stream = None
        self._lock = threading.Lock()       # callback chạy ở thread thời gian thực của PortAudio
        self._finished = False
        # Người dùng đang muốn nghe: True từ lúc bấm phát (stream có thể còn đang mở ở luồng thiết bị)
        # tới khi dừng / hết / lỗi / bị nhường thiết bị cho trang Nghe.
        self._active = False
        self._gen = 0                       # tăng mỗi lần phát/dừng: callback của stream cũ tự im
        self._heard_any = False             # callback của lần phát hiện tại đã chạy ít nhất một lần
        self.error: PlaybackError | None = None     # lỗi mở thiết bị gần nhất, cho giao diện báo
        self.preempted = False              # bị dừng vì thiết bị được nhường (bắt đầu nghe, trang khác phát)
        # Ngoại lệ PortAudio hiểu là "hết dữ liệu, dừng đẹp". Lấy từ sounddevice lúc mở stream
        # chứ không import ở tầng module, vì module này phải nạp được trên máy thiếu PortAudio.
        self._stop_exc: type[BaseException] = _StopPlayback

    @property
    def engine(self) -> AudioEngine:
        return self._engine if self._engine is not None else default_engine()

    # ---- trạng thái ----
    @property
    def duration_s(self) -> float:
        return len(self._x) / self.sample_rate if self.sample_rate else 0.0

    @property
    def position_s(self) -> float:
        if not self.sample_rate:
            return 0.0
        with self._lock:
            heard = self._heard_frame()
            return (self._pos if heard is None else heard) / self.sample_rate

    def _heard_frame(self) -> float | None:
        """Khung nguồn đang ra loa lúc này (gọi khi đang giữ khóa); None nếu không đo được."""
        if not self._active or not self._blocks:
            return None
        now = self._clock()
        at0, first, _, _ = self._blocks[0]
        if now < at0:
            return first                          # stream vừa mở, khối đầu chưa tới loa
        for at, s0, s1, dur in reversed(self._blocks):
            if now >= at:
                f = min(1.0, (now - at) / dur) if dur > 0 else 1.0
                return s0 + (s1 - s0) * f
        return first

    def _log_block(self, time_info, frames: int, src0: float, src1: float) -> None:
        """Ghi lúc khối vừa gửi sẽ tới loa, theo `clock` của ta (gọi trong callback, đang giữ khóa)."""
        if time_info is None:
            return
        dac = float(getattr(time_info, "outputBufferDacTime", 0.0) or 0.0)
        now = float(getattr(time_info, "currentTime", 0.0) or 0.0)
        if dac > 0.0 and now > 0.0:
            ahead = dac - now
        elif dac > 0.0 or now > 0.0:
            ahead = self._latency                  # backend chỉ báo một trong hai: ước theo độ trễ stream
        else:
            return
        at = self._clock() + max(0.0, ahead)
        self._blocks.append((at, float(src0), float(src1), frames / self.sample_rate))

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
        """Đang phát (kể cả lúc stream còn đang mở, và phần đệm cuối vẫn đang ra loa).

        Luồng thiết bị kẹt trong driver mà tiếng của lần phát này CHƯA HỀ ra loa (lệnh mở còn xếp hàng
        sau lệnh kẹt, hoặc chính nó đang kẹt): bỏ cuộc ngay tại đây, `error` nói vì sao — không để
        trang đứng ở trạng thái "đang phát" (văn bản bị khóa) vô thời hạn. Đo 27/09 trên máy dev có
        âm thanh Windows kẹt thật.
        """
        if self._active and not self._heard_any and self.engine.stuck():
            self._detach()
            self.error = PlaybackError(f"{STUCK_TEXT} (open output)", "stuck")
        return self._active

    @property
    def finished(self) -> bool:
        """True khi đã phát HẾT, tới mẫu cuối cùng ra loa (khác với dừng giữa chừng)."""
        return self._finished and not self._active

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
            self._blocks.clear()
        self._finished = False

    # ---- co giãn thời gian (WSOLA, theo khối) ----
    def _reset_stretch(self) -> None:
        """Bỏ trạng thái nối khung: sau seek/đổi tốc độ, khung kế tiếp bắt đầu lại từ `_pos`."""
        self._ana: float | None = None      # vị trí phân tích (khung nguồn) của khung kế tiếp
        self._prev_start: int | None = None
        self._ola = np.zeros(0, dtype=np.float32)
        self._queue = np.zeros(0, dtype=np.float32)
        # Vị trí nguồn DANH NGHĨA của từng mẫu trong `_queue`: số khung WSOLA mỗi khối đổi 8/9, nên
        # lấy đầu khung làm mốc thì con trỏ trên hình tiến giật cục; gắn vị trí cho từng mẫu thì đều.
        self._queue_src = np.zeros(0, dtype=np.float64)

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
        self._queue_src = np.concatenate([self._queue_src, self._ana + np.arange(hop) * self._speed])
        self._prev_start = start
        self._ana += hop * self._speed
        return True

    def _callback(self, outdata, frames, time_info, status) -> None:
        with self._lock:
            src0 = self._pos
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
                srcs, self._queue_src = self._queue_src[:frames], self._queue_src[frames:]
                if len(srcs):
                    src0 = float(srcs[0])
                    self._pos = int(min(srcs[-1] + self._speed, len(self._x)))
                end = self._pos
                if len(chunk) < frames:             # nguồn đã cạn: đẩy nốt phần chồng khung
                    chunk = np.concatenate([chunk, self._ola])[:frames]
                    self._ola = np.zeros(0, dtype=np.float32)
                    self._pos = end = len(self._x)
            self._log_block(time_info, frames, src0, self._pos)
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
        """Bắt đầu (hoặc tiếp tục) phát; trả về NGAY. Gọi lại khi đang phát là vô hại.

        Ném `PlaybackError` tại chỗ khi biết trước là không phát được (đang nghe, thiết bị đang kẹt);
        lỗi lúc mở thiết bị tới sau, ở `error`, và `playing` trở về False.
        """
        if len(self._x) == 0:
            return
        if from_s is not None:
            self.seek(from_s)
        if self._active:
            return
        if self._finished or self._pos >= len(self._x):
            self.seek(0.0)
        eng = self.engine
        if eng.capturing:
            raise PlaybackError("listening is on: stop listening before playing", "busy")
        with self._lock:
            self._active = True
            self._heard_any = False
            self._gen += 1
            gen = self._gen
            self._blocks.clear()
        self._finished = False
        self.error = None
        self.preempted = False
        fut = eng.submit(lambda: self._open(gen), "open output", OPEN_TIMEOUT_S)
        fut.add_done_callback(lambda f: self._opened(gen, f))
        if fut.done() and fut.exception() is not None:
            self.error = None                               # báo một lần, bằng ngoại lệ này
            raise _as_playback_error(fut.exception())       # biết ngay (bản inline, thiết bị kẹt)

    def _open(self, gen: int) -> None:
        """Luồng thiết bị: giành thiết bị, mở stream, chạy. Bị hủy trước khi tới lượt thì thôi."""
        if gen != self._gen:
            return
        eng = self.engine
        eng.claim_output(self)
        holder: list = []

        def make(sd):
            self._stop_exc = getattr(sd, "CallbackStop", _StopPlayback)
            return sd.OutputStream(
                samplerate=self.sample_rate, blocksize=self.block, channels=1,
                dtype="float32", callback=lambda o, f, t, st: self._stream_callback(gen, o, f, t, st),
                finished_callback=lambda: self._stream_done(gen, holder),
            )

        stream = eng.open_stream(make)
        holder.append(stream)
        with self._lock:
            cancelled = gen != self._gen
            if not cancelled:
                self._stream = stream
                self._latency = float(getattr(stream, "latency", 0.0) or 0.0)
                self._blocks.clear()
        if cancelled:                               # dừng ngay trong lúc đang mở
            eng.close_stream(stream)
            if not self._active:
                eng.release(self)
            return
        # KHÔNG giữ khóa khi gọi PortAudio: MME mồi bộ đệm bằng cách gọi callback ngay trong start().
        stream.start()

    def _opened(self, gen: int, fut) -> None:
        exc = fut.exception()
        if exc is None:
            return
        log.warning("playback failed: %s", exc)
        with self._lock:
            if gen == self._gen:
                self._active = False
                self._stream = None
        self.error = _as_playback_error(exc)
        if not isinstance(exc, AudioStuck):
            self.engine.release(self)

    def _stream_callback(self, gen, outdata, frames, time_info, status) -> None:
        """Callback của MỘT stream: stream đã bị dừng/thay (gen cũ) thì chỉ phát im lặng."""
        if gen != self._gen or not self._active:
            outdata[:] = 0.0
            return
        self._heard_any = True
        self._callback(outdata, frames, time_info, status)

    def _stream_done(self, gen: int, holder: list) -> None:
        """PortAudio: stream đã ngừng (phát hết, hoặc bị dừng). Đóng nó ở luồng thiết bị."""
        with self._lock:
            mine = gen == self._gen and self._stream is not None
            if mine:
                self._active = False
                self._stream = None
        if mine and holder:
            stream = holder[0]
            self.engine.submit(lambda: self._close(stream), "close output", CLOSE_TIMEOUT_S, kind="close")

    def _close(self, stream) -> None:
        eng = self.engine
        eng.close_stream(stream)
        if not self._active:
            eng.release(self)

    def _engine_close(self) -> None:
        """Luồng thiết bị giành lại loa cho bên khác (bắt đầu nghe, trang khác phát): dừng tại chỗ đang
        nghe, như bấm tạm dừng."""
        stream = self._detach()
        self.preempted = True
        if stream is not None:
            self.engine.close_stream(stream)

    def _detach(self):
        """Thôi phát, giữ vị trí ĐANG NGHE; trả stream cần đóng (hoặc None)."""
        with self._lock:
            heard = self._heard_frame()
            self._active = False
            self._gen += 1
            stream, self._stream = self._stream, None
            if heard is not None:
                self._pos = min(int(heard), len(self._x))
                self._finished = False
                self._reset_stretch()
            self._blocks.clear()
        return stream

    def pause(self) -> None:
        """Dừng NGAY nhưng giữ vị trí đang nghe, để bấm phát lại là nghe tiếp đúng chỗ đó.

        Stream bị `abort` (bỏ phần còn trong bộ đệm thiết bị) ở luồng thiết bị; callback của nó im từ
        lúc này nên con trỏ không trôi tiếp dù driver có chậm đóng.
        """
        stream = self._detach()
        if stream is not None:
            self.engine.submit(lambda: self._close(stream), "close output", CLOSE_TIMEOUT_S, kind="close")

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
        restart = self._active
        if restart:
            self.pause()                # bỏ phần đệm của chỗ cũ: nghe ngay chỗ mới
        with self._lock:
            self._pos = min(frame, len(self._x))
            self._reset_stretch()
            self._blocks.clear()
        if self._pos < len(self._x):
            self._finished = False
        if restart:
            self.play()

    def _on_stream_finished(self) -> None:
        """Như PortAudio báo stream hiện tại đã phát xong (test)."""
        with self._lock:
            self._active = False
            self._stream = None

    def __enter__(self) -> AudioPlayback:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
