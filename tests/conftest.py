import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _no_audio_module():
    """`sounddevice` thay thế mặc định cho MỌI test: không thiết bị nào, mở stream là lỗi.

    27/09: trang Nghe liệt kê micro ngay khi dựng, và trước đây mọi test dựng MainWindow đều chạm
    PortAudio THẬT (`Pa_Initialize`). Máy dev có driver âm thanh treo (audiodg kẹt) thì cả bộ test đứng
    im ở test_contrast. Test cần stream thì dùng fixture `fake_sounddevice` (ghi đè cái này)."""
    mod = types.ModuleType("sounddevice")

    class PortAudioError(Exception):
        pass

    class CallbackStop(Exception):
        pass

    def no_stream(**kwargs):
        raise PortAudioError("no sound device in tests (tests/conftest.py)")

    mod.PortAudioError = PortAudioError
    mod.CallbackStop = CallbackStop
    mod.query_devices = lambda: []
    mod.OutputStream = mod.InputStream = no_stream
    mod.play = mod.stop = lambda *a, **kw: None
    return mod


@pytest.fixture(autouse=True)
def inline_audio_engine(monkeypatch):
    """Mỗi test một luồng thiết bị `inline` (lệnh chạy ngay trong luồng gọi): tất định, và không test
    nào để lại stream hay trạng thái "đang nghe" cho test sau. Test luồng thiết bị THẬT (hạn giờ,
    driver kẹt) tự dựng `AudioEngine()` riêng. Không test nào chạm PortAudio thật (`_no_audio_module`)."""
    from morsedesk.audio.engine import AudioEngine, set_default_engine

    monkeypatch.setitem(sys.modules, "sounddevice", _no_audio_module())
    engine = AudioEngine(inline=True)
    set_default_engine(engine)
    yield engine
    set_default_engine(None)


@pytest.fixture
def fake_sounddevice(monkeypatch):
    """Thay `sounddevice` bằng module giả trong `sys.modules`.

    Máy đích là Linux air-gap tối giản, có thể không có `libportaudio2`; khi đó
    `import sounddevice` ném `OSError` ngay. Test ở đây kiểm lớp bọc của mình chứ không
    kiểm PortAudio, nên phải chạy được ở cả hai nơi. Đã gặp thật ở tuần 4: ba test xanh
    trên Windows nhưng đỏ trên Ubuntu vì thiếu libportaudio2.

    `InputStream` giả không tự sinh audio: test gọi `stream.feed(block)` để đẩy một khối
    qua đúng callback mà `AudioCapture` đã đăng ký.
    """
    mod = types.ModuleType("sounddevice")
    mod.calls = []

    class PortAudioError(Exception):
        pass

    mod.PortAudioError = PortAudioError
    mod.play = lambda x, sr, **kw: mod.calls.append(("play", len(x), sr))
    mod.stop = lambda: mod.calls.append(("stop",))
    mod.devices = [
        {"name": "Mic giả", "max_input_channels": 1, "max_output_channels": 0, "default_samplerate": 44100.0},
        {"name": "Loa giả", "max_input_channels": 0, "max_output_channels": 2, "default_samplerate": 48000.0},
        {"name": "Cả hai", "max_input_channels": 2, "max_output_channels": 2, "default_samplerate": 48000.0},
    ]
    mod.query_devices = lambda: mod.devices

    class InputStream:
        instances: list["InputStream"] = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = False
            self.closed = False
            InputStream.instances.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def close(self):
            self.closed = True

        def feed(self, block):
            """Gọi callback đúng như PortAudio: mảng [frames, channels] float32."""
            data = np.asarray(block, dtype=np.float32).reshape(-1, 1)
            self.kwargs["callback"](data, len(data), None, None)

    class OutputStream:
        """`OutputStream` giả: `pump()` gọi callback đúng như PortAudio và trả khối đã ghi ra.

        PortAudio thật gọi callback từ luồng riêng theo nhịp thiết bị; test cần nhịp đó tất định
        nên tự bơm. `CallbackStop` do callback ném ra được bắt ở đây giống hệt PortAudio: dừng
        stream rồi gọi `finished_callback`.
        """

        instances: list["OutputStream"] = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = False
            self.closed = False
            self.stopped_by_callback = False
            # Đồng hồ stream như PortAudio (`stream.time`); test tự đặt để giả thời điểm đang nghe.
            self.time = 0.0
            self.latency = 0.0
            OutputStream.instances.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def close(self):
            self.closed = True

        def pump(self, frames=None, dac=None):
            """`dac`: lúc mẫu đầu khối tới loa (giây, đồng hồ stream). None = thiết bị không báo
            thời gian — khi đó AudioPlayback đếm theo khung đã gửi như trước."""
            import types

            n = int(frames or self.kwargs.get("blocksize") or 1024)
            out = np.zeros((n, 1), dtype=np.float32)
            info = None if dac is None else types.SimpleNamespace(outputBufferDacTime=dac,
                                                                   currentTime=dac - 0.3)
            try:
                self.kwargs["callback"](out, n, info, None)
            except mod.CallbackStop:
                self.stopped_by_callback = True
                self.started = False
                cb = self.kwargs.get("finished_callback")
                if cb is not None:
                    cb()
            return out[:, 0]

    class CallbackStop(Exception):
        pass

    InputStream.instances = []
    OutputStream.instances = []
    mod.InputStream = InputStream
    mod.OutputStream = OutputStream
    mod.CallbackStop = CallbackStop
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return mod
