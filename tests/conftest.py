import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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

    InputStream.instances = []
    mod.InputStream = InputStream
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return mod
