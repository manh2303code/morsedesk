"""Giải mã theo dòng: nhịp khối, cắt buffer, chốt theo mốc thời gian, chữ không lặp không mất.

Dùng bộ giải mã giả trả kết quả dựng sẵn: test ở đây kiểm LUẬT GHÉP của `StreamDecoder`, không
kiểm chất lượng mô hình (việc đó là của bộ đo T1/T2). Bộ giải mã giả cũng cho phép dựng đúng
những tình huống khó — ranh giới từ nhúc nhích, cửa sổ trượt qua chữ đã chốt — vốn hiếm gặp
đúng lúc nếu chờ mô hình thật.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from morsedesk.api import Word
from morsedesk.model.stream import CHUNK_S, StreamDecoder


@dataclass
class _Res:
    words: list
    text: str = ""


class FakeDecoder:
    """Trả sẵn một kết quả cho mỗi lần `decode_array`, theo thứ tự đã nạp.

    Mốc thời gian trong kết quả là TƯƠNG ĐỐI với đầu buffer, đúng như `api.Decoder` thật, nên
    test kiểm được cả phép quy đổi sang thời gian tuyệt đối của phiên.
    """

    def __init__(self, results: list[list[tuple[float, float, str]]]) -> None:
        self.results = results
        self.calls = 0

    def decode_array(self, x, sample_rate=None):
        i = min(self.calls, len(self.results) - 1)
        self.calls += 1
        words = [Word(t, s, e, 0.9) for s, e, t in self.results[i]]
        return _Res(words, " ".join(w.text for w in words))


def _blocks(seconds: float, sr: int = 8000, block_s: float = 0.1):
    n = int(seconds * sr)
    step = int(block_s * sr)
    for i in range(0, n, step):
        yield np.zeros(min(step, n - i), dtype=np.float32)


def test_decodes_only_once_per_chunk():
    """Đẩy 10 khối 0,1 s chỉ được chạy mô hình 2 lần (chunk 0,5 s), không phải 10."""
    fake = FakeDecoder([[(0.0, 0.5, "CQ")]])
    sd = StreamDecoder(decoder=fake)
    decoded = sum(1 for b in _blocks(1.0) if sd.push(b).decoded)
    assert decoded == 2 and fake.calls == 2


def test_committed_grows_and_never_repeats_words():
    """Cửa sổ trượt đọc lại chữ đã chốt: không được cộng thêm lần nữa."""
    fake = FakeDecoder([
        [(0.0, 0.6, "CQ")],
        [(0.0, 0.6, "CQ"), (0.9, 1.4, "DE")],
        [(0.0, 0.6, "CQ"), (0.9, 1.4, "DE"), (1.8, 2.5, "R1ABC")],
    ])
    sd = StreamDecoder(decoder=fake)
    for b in _blocks(1.5):
        sd.push(b)
    assert sd.text.split() == ["CQ", "DE", "R1ABC"]
    assert sd.text.count("CQ") == 1


def test_repeated_words_are_not_collapsed():
    """`CQ CQ` phải ra hai lần — đây là chỗ cách ghép theo chuỗi ký tự từng làm hỏng."""
    fake = FakeDecoder([
        [(0.0, 0.6, "CQ")],
        [(0.0, 0.6, "CQ"), (0.9, 1.5, "CQ")],
        [(0.0, 0.6, "CQ"), (0.9, 1.5, "CQ"), (1.9, 2.4, "DE")],
    ])
    sd = StreamDecoder(decoder=fake)
    for b in _blocks(1.5):
        sd.push(b)
    assert sd.text.split() == ["CQ", "CQ", "DE"]


def test_lookahead_holds_back_the_tail():
    """Từ nằm trong vùng nhìn trước còn thiếu tương lai nên phải ở dạng tạm, chưa chốt."""
    fake = FakeDecoder([[(0.0, 0.4, "CQ"), (1.0, 1.4, "DE")]])
    sd = StreamDecoder(decoder=fake, lookahead_s=1.0)
    for b in _blocks(CHUNK_S):
        sd.push(b)
    up = sd.push(np.zeros(0, dtype=np.float32))
    # Mới nhận 0,5 s audio: mọi thứ sau mốc -0,5 s đều nằm trong vùng nhìn trước.
    assert up.committed == "" and "CQ" in up.tentative


def test_flush_commits_everything():
    fake = FakeDecoder([[(0.0, 0.4, "CQ"), (1.0, 1.4, "DE")]])
    sd = StreamDecoder(decoder=fake, lookahead_s=5.0)
    for b in _blocks(1.0):
        sd.push(b)
    final = sd.flush()
    assert final.committed == "CQ DE" and final.tentative == ""
    assert sd.text == "CQ DE"


def test_buffer_is_trimmed_to_context_window():
    """Phiên trực hàng giờ không được dồn hết vào RAM."""
    fake = FakeDecoder([[]])
    sd = StreamDecoder(decoder=fake, left_context_s=2.0, lookahead_s=1.0)
    for b in _blocks(30.0):
        sd.push(b)
    assert len(sd._buf) <= int(3.0 * sd.sample_rate)
    assert sd.audio_s == pytest.approx(30.0, abs=0.01)      # vẫn đếm đúng tổng đã nhận


def test_timestamps_stay_absolute_after_trim():
    """Sau khi cắt buffer, mốc thời gian của kết quả phải được cộng bù, nếu không chữ bị bỏ."""
    fake = FakeDecoder([
        [(0.0, 0.5, "AAA")],
        [(0.0, 0.5, "BBB")],       # cùng mốc tương đối, nhưng buffer đã trượt -> là chữ MỚI
    ])
    sd = StreamDecoder(decoder=fake, left_context_s=0.5, lookahead_s=0.0)
    for b in _blocks(1.0):
        sd.push(b)
    sd.flush()
    assert "AAA" in sd.text and "BBB" in sd.text


def test_reset_clears_everything():
    fake = FakeDecoder([[(0.0, 0.5, "CQ")]])
    sd = StreamDecoder(decoder=fake)
    for b in _blocks(1.0):
        sd.push(b)
    sd.reset()
    assert sd.text == "" and sd.audio_s == 0.0 and len(sd._buf) == 0


def test_empty_push_does_not_decode():
    fake = FakeDecoder([[(0.0, 0.5, "CQ")]])
    sd = StreamDecoder(decoder=fake)
    up = sd.push(np.zeros(0, dtype=np.float32))
    assert not up.decoded and fake.calls == 0
