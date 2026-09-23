"""Luồng nghe trực tiếp: thu từ card âm thanh, giải mã theo dòng, đẩy chữ ra giao diện.

Đây là luồng THỨ HAI, độc lập với `DecoderWorker`: không dùng `moveToThread` để chuyển worker cũ
sang. Hai việc có nhịp hoàn toàn khác nhau — giải mã file là một lượt dài có thể hủy, còn nghe
trực tiếp là vòng lặp không dứt — và nhồi chung một luồng thì một bản tin 37 phút đang giải sẽ
chặn đứng dòng chữ đang chạy.

Mỗi luồng giữ `Decoder` riêng. `Decoder` không an toàn khi gọi song song (nó có trạng thái nội
bộ cho beam và bộ nhớ đệm đặc trưng), nên chia sẻ giữa hai luồng là hỏng ngầm, khó tái hiện.
"""

from __future__ import annotations

import logging
import time

import numpy as np
from PySide6.QtCore import QThread, Signal

from morsedesk.api import DEFAULT_MODEL_PATH, Decoder
from morsedesk.audio.capture import AudioCapture, CaptureError
from morsedesk.constants import SAMPLE_RATE
from morsedesk.lm.store import LMStore
from morsedesk.model.stream import StreamDecoder

log = logging.getLogger(__name__)

LEVEL_EVERY_S = 0.2     # nhịp cập nhật vạch mức tín hiệu, đủ để mắt thấy liên tục


class LiveWorker(QThread):
    """Vòng lặp nghe: `start_listening()` để bật, `stop_listening()` để tắt.

    Luồng sống suốt phiên chứ không dựng lại mỗi lần bật: mở `Decoder` mất vài trăm mili giây
    (nạp ONNX và ba mô hình ngôn ngữ 41 MB), trả giá đó mỗi lần bấm nút thì cảm giác như treo.
    """

    text_ready = Signal(str, str)       # (đã chốt, tạm thời)
    stats_ready = Signal(object)        # StreamUpdate đầy đủ: từ + độ tin cậy, WPM, tone, SNR
    block_ready = Signal(object)        # khối audio thô, cho thác nước tần số
    level = Signal(float)               # RMS của khối vừa thu, cho vạch mức
    listening = Signal(bool)
    failed = Signal(str)                # thông điệp lỗi thiết bị, đã sẵn sàng hiển thị

    def __init__(self, profile: str = "auto", engine: str = "onnx",
                 model_path=None, lm_dir=None, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.engine = engine
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.lm_dir = lm_dir
        self._decoder: Decoder | None = None
        self._stream: StreamDecoder | None = None
        self._device: int | None = None
        self._want = False              # người dùng muốn đang nghe hay không
        self._running = True
        self._error: str | None = None

    # ---- điều khiển từ luồng giao diện ----
    def start_listening(self, device: int | None = None, profile: str | None = None) -> None:
        """Bắt đầu nghe. `profile` khác lần trước thì dựng lại bộ giải mã."""
        self._device = device
        if profile is not None and profile != self.profile:
            self.profile = profile
            self._stream = None         # buộc dựng lại với bảng mã mới
            self._decoder = None
        self._want = True

    def stop_listening(self) -> None:
        self._want = False

    def shutdown(self) -> None:
        """Dừng hẳn luồng. Gọi từ `closeEvent` để cửa sổ không treo lúc thoát."""
        self._want = False
        self._running = False

    # ---- chạy trong luồng riêng ----
    def _ensure_decoder(self) -> StreamDecoder:
        if self._stream is None:
            lm_store = LMStore(self.lm_dir) if self.lm_dir else None
            # `fallback=False`: bộ giải mã DSP dự phòng chạy lại trên TOÀN cửa sổ mỗi nửa giây,
            # tốn khoảng một phần năm thời gian mà ở chế độ live không dùng vào việc gì — quyết
            # định chọn đường đã cần cả clip mới có nghĩa.
            # `skip_silent_windows=True` CHỈ ở chế độ nghe: phần lớn thời gian micro không có
            # ai phát, và mô hình đọc nhiễu nền thành chữ (30 giây nhiễu trắng thuần ra `WE
            # ARE`). Ở chế độ file thì ngược lại, cờ này làm CER xấu từ 9,70 % lên 13,28 % vì
            # clip SNR thấp bị vạ lây — nên nó phải là lựa chọn của từng đường, không phải
            # mặc định chung.
            self._decoder = Decoder(self.profile, engine=self.engine, model_path=self.model_path,
                                    lm_store=lm_store, fallback=False,
                                    skip_silent_windows=True)
            self._stream = StreamDecoder(decoder=self._decoder)
        return self._stream

    def run(self) -> None:
        while self._running:
            if not self._want:
                self.msleep(50)
                continue
            try:
                stream = self._ensure_decoder()
            except Exception as e:
                log.exception("không dựng được bộ giải mã cho chế độ nghe")
                self._fail(f"{type(e).__name__}: {e}")
                continue
            stream.reset()
            self.text_ready.emit("", "")
            try:
                self._listen(stream)
            except CaptureError as e:
                self._fail(str(e))
            except Exception as e:            # lỗi lạ: dừng nghe chứ không kéo sập cả ứng dụng
                log.exception("vòng nghe hỏng")
                self._fail(f"{type(e).__name__}: {e}")

    def _listen(self, stream: StreamDecoder) -> None:
        cap = AudioCapture(device=self._device)
        cap.start()
        self.listening.emit(True)
        last_level = 0.0
        try:
            while self._want and self._running:
                block = cap.get(timeout=0.2)
                if block is None:
                    continue
                now = time.monotonic()
                if now - last_level >= LEVEL_EVERY_S:
                    last_level = now
                    self.level.emit(float(np.sqrt(np.mean(np.square(block)))) if len(block) else 0.0)
                self.block_ready.emit(block)
                up = stream.push(block)
                if up.decoded:
                    self.text_ready.emit(up.committed, up.tentative)
                    self.stats_ready.emit(up)
        finally:
            cap.stop()
            # Giải mã nốt phần đuôi còn trong bộ đệm: nếu không, câu cuối của phiên bị cụt.
            try:
                final = stream.flush()
                self.text_ready.emit(final.committed, "")
                self.stats_ready.emit(final)
            except Exception:
                log.warning("flush cuối phiên nghe thất bại", exc_info=True)
            self.listening.emit(False)

    def _fail(self, message: str) -> None:
        self._want = False
        self._error = message
        self.failed.emit(message)
        self.listening.emit(False)


def input_devices() -> list[tuple[int, str]]:
    """(chỉ số, tên) của thiết bị thu; rỗng nếu máy không có hoặc thiếu PortAudio.

    Bọc lỗi thành danh sách rỗng vì giao diện chỉ cần biết "có gì để chọn không" — lỗi chi tiết
    sẽ hiện khi người dùng thật sự bấm nghe, kèm đúng ngữ cảnh.
    """
    from morsedesk.audio.capture import list_input_devices

    try:
        return [(d.index, d.name) for d in list_input_devices()]
    except CaptureError:
        return []


DEFAULT_SAMPLE_RATE = SAMPLE_RATE
