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


class _LangDecoder:
    """Bộ giải mã giả: mỗi lần trả một từ mới (thời gian tăng dần) với ngôn ngữ và điểm LM theo kịch
    bản (`scores`: pid -> nat/chữ, cao hơn là giống hơn)."""

    auto = True                         # như Decoder("auto") chưa khóa

    def __init__(self, languages, scores=None):
        self.languages = list(languages)
        self.scores = list(scores or [{lang: -1.0, "zz": -2.0} for lang in languages])
        self.calls = 0
        self.pinned = []

    def pin_language(self, pid):
        self.pinned.append(pid)
        return True

    def decode_array(self, x, sr):
        from types import SimpleNamespace

        lang = self.languages[min(self.calls, len(self.languages) - 1)]
        scores = self.scores[min(self.calls, len(self.scores) - 1)]
        self.calls += 1
        dur = len(x) / sr
        word = SimpleNamespace(text="ABCDEFGHIJ", start_s=max(0.0, dur - 2.2), end_s=dur - 1.6,
                               confidence=0.9)
        return SimpleNamespace(words=[word], wpm=20.0, tone_hz=700.0, snr_db=10.0, language=lang,
                               language_scores=scores)


def test_live_session_pins_its_language_once_certain_and_unpins_on_reset():
    """Nghe trực tiếp: đủ 50 chữ đã chốt + bằng chứng cả phiên rõ ràng -> khóa; reset -> mở khóa."""
    from morsedesk.model.stream import PIN_MIN_LETTERS, StreamDecoder

    dec = _LangDecoder(["ru", "en"] + ["en"] * 40,
                       [{"ru": -1.0, "en": -1.1}] + [{"en": -1.0, "ru": -1.5}] * 41)
    sd = StreamDecoder(dec, sample_rate=1000, chunk_s=0.5)
    block = np.zeros(500, dtype=np.float32)
    for _ in range(40):
        sd.push(block)
        if sd.pinned_language:
            break
    assert sd.pinned_language == "en" and dec.pinned == ["en"]
    assert sum(1 for c in sd.committed if not c.isspace()) >= PIN_MIN_LETTERS
    sd.reset()
    assert sd.pinned_language is None and dec.pinned == ["en", None]



def test_live_session_does_not_pin_on_a_short_run_that_contradicts_the_whole_session():
    """Luật cũ khóa theo 3 lần giải mã liền nhau trên bộ đệm ~9,5 s: 26/54 bản tin 2 phút bị khóa
    NHẦM (Nga/Kazakh sang Anh giữa chừng). Nay bằng chứng tích lũy cả phiên thắng một quãng ngắn."""
    from morsedesk.model.stream import StreamDecoder

    ru, en = {"ru": -1.0, "en": -1.6}, {"en": -1.0, "ru": -1.1}
    # Mỗi bộ đệm ngắn tự chọn ngôn ngữ lúc Nga lúc Anh (nhưng Nga rõ hơn nhiều), rồi 3 lần liền Anh.
    langs = ["ru", "en"] * 5 + ["en"] * 3 + ["ru"] * 30
    dec = _LangDecoder(langs, [ru if lang == "ru" else en for lang in langs])
    sd = StreamDecoder(dec, sample_rate=1000, chunk_s=0.5)
    block = np.zeros(500, dtype=np.float32)
    for _ in range(len(langs)):
        sd.push(block)
    assert sd.pinned_language == "ru" and dec.pinned == ["ru"]


def test_live_session_waits_when_the_evidence_is_too_close_then_takes_the_leader():
    """Bằng chứng quá sát (nhóm mã, tiếng Nga với Kazakh): chờ — chữ vẫn ở dạng tạm, KHÔNG chốt; quá
    PIN_FORCE_LETTERS thì khóa theo ngôn ngữ dẫn đầu để phiên không treo ở dạng tạm mãi."""
    from morsedesk.model.stream import PIN_FORCE_LETTERS, StreamDecoder

    dec = _LangDecoder(["ru"] * 60, [{"ru": -1.0, "kk-cyrl-ru": -1.05}] * 60)
    sd = StreamDecoder(dec, sample_rate=1000, chunk_s=0.5)
    block = np.zeros(500, dtype=np.float32)
    letters = 0
    while letters + 10 < PIN_FORCE_LETTERS:
        up = sd.push(block)
        letters = sum(1 for w in up.words for c in w.text if not c.isspace())
    assert sd.pinned_language is None and dec.pinned == [] and sd.committed == ""
    for _ in range(6):
        sd.push(block)
    assert sd.pinned_language == "ru" and dec.pinned == ["ru"] and sd.committed


def test_live_session_never_mixes_alphabets_while_choosing():
    """Trước khi khóa, mỗi lần giải bộ đệm ngắn có thể ra ngôn ngữ khác — nhưng dòng chữ hiện ra
    (tạm) và phần chốt sau đó đều chỉ dùng MỘT bảng chữ (bản ghi phím 1930 của người dùng, 25/09)."""
    from types import SimpleNamespace

    from morsedesk.model.stream import StreamDecoder

    class Flipping(_LangDecoder):
        """Lần chẵn giải ra chữ Latin (en), lần lẻ ra chữ Kirin (ru) — cùng một mẫu Morse."""

        def decode_array(self, x, sr):
            lang = "en" if self.calls % 2 == 0 else "ru"
            self.calls += 1
            dur = len(x) / sr
            text = "CQ" if lang == "en" else "ЦЩ"
            word = SimpleNamespace(text=text, start_s=max(0.0, dur - 2.2), end_s=dur - 1.6, confidence=0.9)
            return SimpleNamespace(words=[word], wpm=20.0, tone_hz=700.0, snr_db=10.0, language=lang,
                                   language_scores={"ru": -1.0, "en": -1.6})

    dec = Flipping([])
    sd = StreamDecoder(dec, sample_rate=1000, chunk_s=0.5)
    block = np.zeros(500, dtype=np.float32)
    for _ in range(10):
        up = sd.push(block)
        shown = (up.committed + " " + up.tentative).replace(" ", "")
        assert not (any("A" <= c <= "Z" for c in shown) and any("А" <= c <= "Я" for c in shown)), shown
    final = sd.flush()
    assert final.text.replace(" ", "") and set(final.text.replace(" ", "")) <= set("ЦЩ")


def test_update_carries_words_with_confidence_and_the_shown_language():
    """Trang Nghe gạch chân từng từ theo độ tin cậy: cả phần chốt lẫn phần tạm phải là Word (mốc
    tuyệt đối), và `language` là chuỗi tên ngôn ngữ (từng bị lệch trường thành danh sách từ)."""
    from morsedesk.model.stream import StreamDecoder

    dec = _LangDecoder(["en"] * 40, [{"en": -1.0, "ru": -2.0}] * 40)
    sd = StreamDecoder(dec, sample_rate=1000, chunk_s=0.5)
    block = np.zeros(500, dtype=np.float32)
    for _ in range(12):
        up = sd.push(block)
    assert up.language == "en" and isinstance(up.wpm, float)
    assert up.committed_words and all(hasattr(w, "confidence") for w in up.committed_words)
    assert " ".join(w.text for w in up.committed_words) == up.committed
    starts = [w.start_s for w in up.committed_words]
    assert starts == sorted(starts) and starts[-1] > 2.0            # thời gian TUYỆT ĐỐI của phiên
