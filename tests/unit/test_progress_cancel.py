"""Tiến trình theo cửa sổ và hủy giữa chừng cho lần giải mã đang chạy (CP-08, CP-09).

File 20 phút mất vài phút để giải mã. Không có hai thứ này thì người dùng chỉ thấy thanh chạy
vô định và phải chờ hết, kể cả khi mở nhầm file.
"""

import numpy as np
import pytest

from morsedesk.api import Decoder
from morsedesk.progress import DecodeCancelled, DecodeProgress
from tests.helpers import make_morse


@pytest.fixture(scope="module")
def audio():
    x, _ = make_morse("CQ CQ DE R1ABC K", profile_id="en", wpm=20)
    return np.tile(x, 3)                     # đủ dài để có nhiều cửa sổ


@pytest.fixture(scope="module")
def decoder():
    """Engine onnx: đây là engine chia cửa sổ, tức nơi tiến trình có ý nghĩa thật."""
    from pathlib import Path

    if not Path("models/acoustic.onnx").is_file():
        pytest.skip("cần models/acoustic.onnx")
    return Decoder("en", engine="onnx", lm=False)


def test_progress_reports_monotonic_steps_up_to_total(decoder, audio):
    seen: list[tuple[int, int]] = []
    decoder.decode_array(audio, progress=DecodeProgress(on_step=lambda d, t: seen.append((d, t))))
    assert seen, "bộ giải mã không báo tiến trình lần nào"
    dones = [d for d, _ in seen]
    totals = {t for _, t in seen}
    assert len(totals) == 1, f"tổng số bước đổi giữa chừng: {totals}"
    assert dones == sorted(dones)
    assert dones[-1] == seen[0][1] and dones[0] >= 1
    assert all(1 <= d <= t for d, t in seen)


def test_cancel_stops_before_finishing(decoder, audio):
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] >= 2               # cho chạy một bước rồi mới hủy

    with pytest.raises(DecodeCancelled):
        decoder.decode_array(audio, progress=DecodeProgress(should_cancel=should_cancel))


def test_no_progress_object_keeps_the_old_behaviour(audio):
    res = Decoder("en", engine="baseline").decode_array(audio)
    assert res.text


def test_progress_step_raises_only_when_asked():
    p = DecodeProgress()
    p.step(1, 2)                             # không callback nào: không được nổ
    p = DecodeProgress(should_cancel=lambda: True)
    with pytest.raises(DecodeCancelled):
        p.step(1, 2)
