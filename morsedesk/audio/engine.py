"""Một luồng thiết bị duy nhất giữ MỌI lời gọi PortAudio; phát và thu không bao giờ mở cùng lúc.

Vì sao có module này (27/09). Người dùng: đang phát ở trang Tạo mã (hoặc Giải mã) rồi sang trang Nghe
bấm Nghe -> ứng dụng đơ hẳn, phải giết trong Task Manager. Dựng lại trên máy dev: mở micro lúc loa
đang phát làm bộ máy âm thanh của Windows treo — nhật ký ghi `AppHangXProcB1` (svchost.exe_Audiosrv
chờ audiodg.exe), dịch vụ Windows Audio bị giết rồi tự khởi động lại, audiodg.exe cũ kẹt trong driver
tới khi khởi động lại máy, và trong lúc đó MỌI lời gọi PortAudio (mở, dừng, đóng, kể cả
`import sounddevice` = `Pa_Initialize`) đứng im chờ RPC tới dịch vụ. Cùng dấu hiệu đã được báo trên
máy Realtek khác khi thu micro lúc đang phát (gọi Zoom); cơ chế khả dĩ: hiệu ứng khử tiếng vọng (APO)
của micro mở vòng thu lại loa làm tham chiếu — Microsoft ghi rõ việc đó có thể deadlock. Trước đây
luồng giao diện gọi thẳng PortAudio (mở/dừng loa, đọc `stream.time` 60 lần/giây, liệt kê micro), nên
driver treo là cửa sổ treo theo.

Máy mạnh không cứu được: đây không phải thiếu hiệu năng mà là một lời gọi driver không bao giờ trả
về. Nên thiết kế ở đây không dựa vào driver "tử tế":

1. Luồng giao diện KHÔNG BAO GIỜ gọi PortAudio. Mọi thao tác thiết bị là một lệnh xếp hàng cho MỘT
   luồng thiết bị (PortAudio cũng không an toàn khi mở/đóng stream từ nhiều luồng cùng lúc). Giao
   diện chỉ đọc trạng thái Python do callback ghi lại.
2. Mỗi lệnh có hạn giờ. Quá hạn -> `stuck()`: giao diện báo "thiết bị âm thanh không phản hồi", lệnh
   mở mới bị từ chối ngay (`AudioStuck`), phần còn lại của ứng dụng chạy bình thường. Lệnh treo trả
   về (dịch vụ âm thanh khởi động lại) thì PortAudio được khởi tạo lại để dò thiết bị mới.
3. Độc quyền: tại mỗi thời điểm chỉ MỘT stream mở. Bắt đầu nghe thì mọi tiếng đang phát dừng trước
   (đóng xong mới mở micro); đang nghe thì không phát (`AudioBusy`) — micro sẽ thu lại tiếng loa và
   giải mã trùng. Phát ở trang này thì tiếng ở trang kia dừng.
4. Thoát ứng dụng: `shutdown()` có hạn giờ; luồng thiết bị kẹt thì bên gọi thoát bằng `os._exit` thay
   vì chờ `Pa_Terminate` mãi mãi (main.py).

Module thuộc lõi: không import Qt, `sounddevice` chỉ được import BÊN TRONG luồng thiết bị.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger(__name__)

# Hạn giờ từng loại lệnh. Mở/đóng stream bình thường 10–100 ms. Lệnh đầu tiên (liệt kê micro khi dựng
# trang Nghe) kèm `Pa_Initialize`, dò mọi host API (Windows: MME, DirectSound, WASAPI, WDM-KS): 0,3–2 s.
OPEN_TIMEOUT_S = 5.0
CLOSE_TIMEOUT_S = 5.0
QUERY_TIMEOUT_S = 8.0
# Mã lỗi PortAudio nghĩa là "danh sách thiết bị đã cũ" (dịch vụ âm thanh vừa khởi động lại, tai nghe
# rút ra): khởi tạo lại PortAudio rồi thử MỘT lần nữa.
STALE_DEVICE_ERRORS = (-9996, -9985, -9999)     # paInvalidDevice, paDeviceUnavailable, paUnanticipatedHostError
# Đầu câu của mọi thông điệp "driver kẹt": giao diện nhận ra để thay bằng lời giải thích đã dịch.
STUCK_TEXT = "the sound device is not responding"


class AudioError(RuntimeError):
    """Lỗi thiết bị âm thanh, thông điệp đã sẵn sàng hiển thị."""


class AudioUnavailable(AudioError):
    """Không có PortAudio (máy air-gap thiếu libportaudio2): không bao giờ phát/thu được."""


class AudioBusy(AudioError):
    """Thiết bị đang được dùng để NGHE: không phát ra loa lúc này."""


class AudioStuck(AudioError):
    """Luồng thiết bị đang kẹt trong một lời gọi driver quá hạn."""


class Owner(Protocol):
    def _engine_close(self) -> None:
        """Đóng stream của mình NGAY (đang ở luồng thiết bị) vì thiết bị được nhường cho bên khác."""


@dataclass
class _Op:
    fn: Callable[[], Any]
    name: str
    timeout: float
    kind: str                           # "open" | "close" | "query"
    future: Future = field(default_factory=Future)


class AudioEngine:
    """Luồng thiết bị. `inline=True` (test): chạy lệnh ngay trong luồng gọi, tất định."""

    def __init__(self, inline: bool = False) -> None:
        self.inline = inline
        self._q: queue.Queue[_Op | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._current: tuple[str, float, float] | None = None     # (tên, lúc bắt đầu, hạn giờ)
        self._outputs: dict[int, Owner] = {}
        self._capture: Owner | None = None
        self._streams: set[int] = set()     # id các stream đang mở (khởi tạo lại PortAudio khi rỗng)
        self._needs_reinit = False
        self._closed = False
        self._initialised = False           # engine này đã chạm PortAudio (thì lúc thoát mới Pa_Terminate)
        self.last_devices: list | None = None   # kết quả liệt kê gần nhất (thô), đọc tự do

    # ---- trạng thái, đọc được từ mọi luồng (không gọi PortAudio) ----
    @property
    def capturing(self) -> bool:
        return self._capture is not None

    def stuck(self) -> str | None:
        """Tên lệnh đang chạy quá hạn giờ (driver không trả lời), None nếu mọi thứ bình thường."""
        with self._lock:
            cur = self._current
        if cur is None:
            return None
        name, started, timeout = cur
        return name if time.monotonic() - started > timeout else None

    # ---- xếp lệnh ----
    def submit(self, fn: Callable[[], Any], name: str, timeout: float = OPEN_TIMEOUT_S,
               kind: str = "open") -> Future:
        """Xếp `fn` cho luồng thiết bị; trả Future NGAY, không bao giờ chờ.

        Luồng đang kẹt thì lệnh mở/liệt kê bị từ chối tại chỗ (`AudioStuck`) thay vì chồng chất sau
        lệnh kẹt; lệnh ĐÓNG vẫn xếp hàng để stream được đóng khi driver trả lời lại.
        """
        op = _Op(fn, name, timeout, kind)
        if self._closed and kind != "close":
            op.future.set_exception(AudioError("audio engine is shut down"))
            return op.future
        if kind != "close" and (stuck := self.stuck()):
            op.future.set_exception(AudioStuck(f"{STUCK_TEXT} ({stuck})"))
            return op.future
        if self.inline:
            self._run(op)
            return op.future
        self._ensure_thread()
        self._q.put(op)
        return op.future

    def call(self, fn: Callable[[], Any], name: str, timeout: float = OPEN_TIMEOUT_S,
             kind: str = "open") -> Any:
        """`submit` rồi CHỜ kết quả — chỉ dành cho luồng KHÔNG phải giao diện (luồng nghe).

        Quá hạn -> `AudioStuck`; lệnh vẫn còn trong luồng thiết bị và sẽ chạy nốt khi driver trả lời,
        nên bên gọi phải tự dọn nếu lệnh đó mở ra thứ gì (xem AudioCapture.start).
        """
        fut = self.submit(fn, name, timeout, kind)
        try:
            # Chờ thêm phần lệnh khác đang đứng trước trong hàng (mỗi lệnh đã có hạn giờ riêng).
            return fut.result(timeout=timeout + CLOSE_TIMEOUT_S)
        except FutureTimeout:
            raise AudioStuck(f"{STUCK_TEXT} ({name})") from None

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            # daemon: luồng kẹt trong driver không được giữ tiến trình lại lúc thoát.
            self._thread = threading.Thread(target=self._loop, name="morsedesk-audio", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while True:
            op = self._q.get()
            if op is None:
                return
            self._run(op)

    def _run(self, op: _Op) -> None:
        if not op.future.set_running_or_notify_cancel():
            return
        started = time.monotonic()
        with self._lock:
            self._current = (op.name, started, op.timeout)
        try:
            op.future.set_result(op.fn())
        except BaseException as e:      # noqa: BLE001 — mọi lỗi về tay bên gọi qua Future
            op.future.set_exception(e)
        finally:
            with self._lock:
                self._current = None
            took = time.monotonic() - started
            if took > op.timeout:
                # Driver vừa hồi lại sau khi kẹt (thường do dịch vụ âm thanh khởi động lại): danh sách
                # thiết bị của PortAudio đã cũ, lần dùng sau phải dò lại.
                log.warning("audio op %r took %.1f s (limit %.1f s)", op.name, took, op.timeout)
                self._needs_reinit = True

    # ---- chỉ gọi TRONG luồng thiết bị (bên trong fn của một lệnh) ----
    def sd(self):
        """Module sounddevice. Lần đầu = `Pa_Initialize`; sau khi driver kẹt/đổi thiết bị thì khởi tạo
        lại (chỉ khi không còn stream nào mở — `Pa_Terminate` đóng mọi stream đang chạy)."""
        try:
            import sounddevice as sd
        except Exception as e:      # ImportError (không cài) hoặc OSError (thiếu libportaudio2)
            raise AudioUnavailable(f"sounddevice unavailable: {type(e).__name__}: {e}") from e
        self._initialised = True
        if self._needs_reinit and not self._streams:
            self._needs_reinit = False
            self._reinit(sd)
        return sd

    def rescan(self) -> None:
        """Dò lại thiết bị (người dùng vừa cắm tai nghe): PortAudio chỉ liệt kê lúc khởi tạo."""
        self._needs_reinit = True

    @staticmethod
    def _reinit(sd) -> None:
        term, init = getattr(sd, "_terminate", None), getattr(sd, "_initialize", None)
        if term is None or init is None:
            return
        try:
            term()
        except Exception:
            log.warning("Pa_Terminate failed", exc_info=True)
        init()

    def open_stream(self, make: Callable[[Any], Any]) -> Any:
        """`make(sd)` mở một stream; lỗi "thiết bị cũ" -> khởi tạo lại PortAudio và thử MỘT lần nữa."""
        try:
            stream = make(self.sd())
        except AudioError:
            raise
        except Exception as e:
            if getattr(e, "args", None) and self._stale(e) and not self._streams:
                log.warning("stale audio device (%s): re-initialising PortAudio", e)
                self._needs_reinit = True
                stream = make(self.sd())
            else:
                raise
        self._streams.add(id(stream))
        return stream

    @staticmethod
    def _stale(e: Exception) -> bool:
        code = e.args[1] if len(e.args) > 1 and isinstance(e.args[1], int) else None
        return code in STALE_DEVICE_ERRORS or "Invalid device" in str(e)

    def close_stream(self, stream, abort: bool = True) -> None:
        """Dừng và đóng `stream` (trong luồng thiết bị); lỗi driver chỉ ghi log."""
        self._streams.discard(id(stream))
        try:
            if abort:
                getattr(stream, "abort", stream.stop)()
            else:
                stream.stop()
            stream.close()
        except Exception:
            log.warning("closing audio stream failed", exc_info=True)

    def claim_output(self, owner: Owner) -> None:
        """Phát: từ chối khi đang nghe; tiếng khác đang phát thì dừng nó trước."""
        if self._capture is not None:
            raise AudioBusy("listening is on: stop listening before playing")
        for key, other in list(self._outputs.items()):
            if other is not owner:
                self._outputs.pop(key, None)
                other._engine_close()
        self._outputs[id(owner)] = owner

    def claim_input(self, owner: Owner) -> None:
        """Nghe: mọi tiếng đang phát dừng và ĐÓNG XONG trước khi micro được mở."""
        for key, other in list(self._outputs.items()):
            self._outputs.pop(key, None)
            other._engine_close()
        if self._capture is not None and self._capture is not owner:
            prev, self._capture = self._capture, None
            prev._engine_close()
        self._capture = owner

    def release(self, owner: Owner) -> None:
        self._outputs.pop(id(owner), None)
        if self._capture is owner:
            self._capture = None

    # ---- liệt kê thiết bị ----
    def query_devices(self, rescan: bool = False) -> Future:
        """Liệt kê thiết bị ở luồng thiết bị; kết quả cũng lưu ở `last_devices` cho ai cần đọc lại."""
        def run():
            if rescan:
                self.rescan()
            raw = [dict(d) for d in self.sd().query_devices()]
            self.last_devices = raw
            return raw
        return self.submit(run, "query devices", QUERY_TIMEOUT_S, kind="query")

    # ---- thoát ----
    def shutdown(self, timeout: float = 2.0) -> bool:
        """Đóng mọi stream + `Pa_Terminate` trong luồng thiết bị. False nếu luồng kẹt quá `timeout`:
        khi đó bên gọi nên thoát tiến trình bằng `os._exit` (atexit của sounddevice sẽ gọi lại
        `Pa_Terminate` và treo theo driver)."""
        if self._thread is None and not self.inline:
            self._closed = True
            return True

        def close_all():
            for key, other in list(self._outputs.items()):
                self._outputs.pop(key, None)
                other._engine_close()
            if self._capture is not None:
                prev, self._capture = self._capture, None
                prev._engine_close()
            if not self._initialised:
                return
            # Cùng luồng đã `Pa_Initialize` (Windows: CoInitialize/CoUninitialize phải cùng luồng). Xong
            # thì atexit của sounddevice không còn gì để terminate.
            import sys
            sd = sys.modules.get("sounddevice")
            term = getattr(sd, "_terminate", None)
            while term is not None and getattr(sd, "_initialized", 0) > 0:
                term()

        # Lệnh "close" vẫn xếp hàng khi luồng đang kẹt: driver trả lời trong hạn thì vẫn thoát gọn.
        fut = self.submit(close_all, "shut down audio", timeout, kind="close")
        self._closed = True
        if not self.inline:
            self._q.put(None)
        try:
            fut.result(timeout=timeout)
        except FutureTimeout:
            return False
        except Exception:
            log.warning("audio shutdown failed", exc_info=True)
        return True


_DEFAULT: AudioEngine | None = None
_DEFAULT_LOCK = threading.Lock()


def default_engine() -> AudioEngine:
    """Luồng thiết bị dùng chung của cả ứng dụng (tạo lười)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = AudioEngine()
        return _DEFAULT


def set_default_engine(engine: AudioEngine | None) -> None:
    """Cho test: thay luồng dùng chung (vd. bản `inline`)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        _DEFAULT = engine
