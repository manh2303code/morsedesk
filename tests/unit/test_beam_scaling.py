"""Beam search phải tuyến tính theo độ dài, không bậc hai.

Đo trên bản ghi thật ngày 22/09: 30 s -> 3,6 s; 60 s -> 3,7; 120 s -> 5,9; **240 s -> 18,7**.
Gấp đôi độ dài làm thời gian gấp hơn ba, vì mỗi tiền tố giữ cả tuple ký tự làm khóa từ điển nên
mỗi lần mở rộng phải sao chép và băm lại toàn bộ chuỗi. Clip T1 dài 13 ký tự nên không lộ; bản
tin thật 3 746 ký tự thì không chạy nổi.
"""

import time

import numpy as np
import pytest

from morsedesk.lm.beam import BeamParams, beam_search
from morsedesk.lm.profile import load_profile
from morsedesk.model.vocab import VOCAB


def lattice(n_chars: int, seed: int = 0) -> np.ndarray:
    """Lưới CTC phát ra `n_chars` ký tự rõ ràng, xen blank — dài tuỳ ý mà nội dung ổn định."""
    rng = np.random.default_rng(seed)
    rows = []
    # chỉ lấy mẫu chấm gạch thật: bỏ blank, <space>, <unk> và prosign
    ids = [i for i, t in enumerate(VOCAB.tokens) if t and set(t) <= {".", "-"}][:20]
    for k in range(n_chars):
        peak = np.full(len(VOCAB), np.log(0.02 / len(VOCAB)), dtype=np.float32)
        peak[ids[k % len(ids)]] = np.log(0.98)
        blank = np.full(len(VOCAB), np.log(0.02 / len(VOCAB)), dtype=np.float32)
        blank[VOCAB.blank_id] = np.log(0.98)
        rows += [peak, blank, blank]
    _ = rng
    return np.vstack(rows)


def elapsed(n_chars: int) -> float:
    lp = lattice(n_chars)
    profile = load_profile("en")
    t0 = time.perf_counter()
    beam_search(lp, profile, None, BeamParams(beam=16))
    return time.perf_counter() - t0


@pytest.mark.slow
def test_cost_grows_roughly_linearly_with_length():
    """Gấp tám độ dài không được làm thời gian gấp quá mười lần.

    Đo ngày 22/09 trước khi sửa: 0,10 ms mỗi ký tự ở 100 ký tự nhưng 0,24 ms ở 800 — tỉ lệ 19x
    cho 8x độ dài. Sau khi chuyển sang chuỗi liên kết: 0,097 / 0,080 / 0,101 / 0,092 / 0,088 ms
    mỗi ký tự ở 100 / 200 / 400 / 800 / 1600, tức hằng số, tỉ lệ đo được 7,6x. Biên 12x cho
    phép nhiễu đo trên máy đang bận mà vẫn bắt được bậc hai.
    """
    short = min(elapsed(100) for _ in range(3))
    long = min(elapsed(800) for _ in range(3))
    assert long < short * 12.0, f"{short:.4f}s -> {long:.4f}s, tỉ lệ {long / short:.1f}x"


def test_result_is_stable_for_a_long_lattice():
    """Chuỗi dài vẫn ra đúng số ký tự — bảo vệ phần dựng chuỗi khi đổi biểu diễn."""
    hyp = beam_search(lattice(60), load_profile("en"), None, BeamParams(beam=8))[0]
    assert len(hyp.tokens) == 60
    assert len(hyp.frames) == len(hyp.probs) == 60
    assert list(hyp.frames) == sorted(hyp.frames)
    assert hyp.text == "".join(hyp.letters)
