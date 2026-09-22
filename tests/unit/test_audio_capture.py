import sys

import numpy as np
import pytest

from morsedesk.audio.capture import (
    AudioCapture,
    AudioDevice,
    CaptureError,
    list_input_devices,
    list_output_devices,
)
from morsedesk.constants import SAMPLE_RATE


def test_list_devices_splits_input_and_output(fake_sounddevice):
    ins = list_input_devices()
    outs = list_output_devices()
    assert [d.name for d in ins] == ["Mic giả", "Cả hai"]
    assert [d.index for d in ins] == [0, 2]
    assert [d.name for d in outs] == ["Loa giả", "Cả hai"]
    assert isinstance(ins[0], AudioDevice)
    assert ins[0].channels == 1 and ins[0].samplerate == 44100.0


def test_list_devices_without_portaudio_raises_capture_error(monkeypatch):
    """Máy Linux tối giản thiếu libportaudio2: `import sounddevice` hỏng ngay."""
    monkeypatch.setitem(sys.modules, "sounddevice", None)   # làm import ném ImportError
    with pytest.raises(CaptureError):
        list_input_devices()


def test_list_devices_reports_query_failure(fake_sounddevice):
    def boom():
        raise fake_sounddevice.PortAudioError("host api gone")

    fake_sounddevice.query_devices = boom
    with pytest.raises(CaptureError) as e:
        list_input_devices()
    assert "host api gone" in str(e.value)


def test_capture_pushes_blocks_and_mixes_to_mono(fake_sounddevice):
    cap = AudioCapture(device=0, block_ms=100)
    assert cap.blocksize == SAMPLE_RATE // 10
    cap.start()
    try:
        stream = fake_sounddevice.InputStream.instances[-1]
        assert stream.started and stream.kwargs["samplerate"] == SAMPLE_RATE
        assert stream.kwargs["blocksize"] == 800 and stream.kwargs["device"] == 0
        assert stream.kwargs["channels"] == 1 and stream.kwargs["dtype"] == "float32"
        assert cap.get(timeout=0.01) is None                       # chưa có khối nào
        stream.feed(np.full(800, 0.25, dtype=np.float32))
        block = cap.get(timeout=1.0)
        assert block is not None and block.shape == (800,)
        assert block.dtype == np.float32 and np.allclose(block, 0.25)
        assert cap.dropped == 0 and cap.pending == 0
    finally:
        cap.stop()
    assert stream.closed and not stream.started
    assert cap.get(timeout=0.01) is None


def test_capture_counts_dropped_blocks_when_queue_is_full(fake_sounddevice):
    """Tràn buffer live (spec gốc §7): bỏ khối, tăng bộ đếm, không ném trong callback."""
    cap = AudioCapture(device=None, block_ms=100, max_blocks=2)
    cap.start()
    try:
        stream = fake_sounddevice.InputStream.instances[-1]
        for _ in range(5):
            stream.feed(np.zeros(800, dtype=np.float32))
        assert cap.pending == 2 and cap.dropped == 3
        assert cap.get(timeout=1.0) is not None
        stream.feed(np.zeros(800, dtype=np.float32))
        assert cap.dropped == 3                                    # có chỗ trống -> không bỏ nữa
    finally:
        cap.stop()


def test_capture_open_failure_raises_capture_error(fake_sounddevice):
    def boom(**kwargs):
        raise fake_sounddevice.PortAudioError("device busy")

    fake_sounddevice.InputStream = boom
    cap = AudioCapture(device=7)
    with pytest.raises(CaptureError) as e:
        cap.start()
    assert "device busy" in str(e.value)
    cap.stop()                                                     # stop sau lỗi không được ném


def test_capture_context_manager_stops_stream(fake_sounddevice):
    with AudioCapture(device=0) as cap:
        stream = fake_sounddevice.InputStream.instances[-1]
        assert cap.pending == 0 and stream.started
    assert stream.closed


def test_queue_must_be_drained_after_stopping(fake_sounddevice):
    """Đọc hết hàng đợi trong khi luồng còn chạy là một vòng lặp không bao giờ kết thúc.

    Đã vấp thật khi thử với card âm thanh: `while cap.get() is not None` treo vô hạn vì
    callback vẫn nạp khối mới nhanh hơn tốc độ đọc. Thứ tự đúng là dừng luồng trước, rồi mới
    vét phần còn lại — và sau khi dừng thì `get` phải trả `None` trong một `timeout`.
    """
    cap = AudioCapture()
    cap.start()
    stream = fake_sounddevice.InputStream.instances[-1]
    stream.feed(np.zeros(800, dtype=np.float32))
    stream.feed(np.ones(800, dtype=np.float32))
    cap.stop()

    drained = []
    while (block := cap.get(timeout=0.01)) is not None:
        drained.append(block)
    assert len(drained) == 2
    assert cap.get(timeout=0.01) is None
