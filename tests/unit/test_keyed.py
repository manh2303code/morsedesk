"""Đối chiếu với nhịp phím (morsedesk/keyed.py) — bài học số, chữ số đơn, giọng nói xen Morse (27/09)."""

from __future__ import annotations

import numpy as np
import pytest

from morsedesk.api import Word
from morsedesk.constants import SAMPLE_RATE
from morsedesk.dsp.frontend import mix_envelope
from morsedesk.encode.synth import elements_to_audio
from morsedesk.encode.timing import Element
from morsedesk.keyed import (
    Keyed,
    KeyedChar,
    not_morse_clip,
    read_keying,
    reconcile,
    two_clusters,
)
from morsedesk.lm.profile import load_profile

EN = load_profile("en")
U = 0.08                                                  # dit 15 WPM


def keyed_audio(patterns: list[str], gaps_units: list[float], snr_db: float = 30.0, seed: int = 0,
                dropout_at: tuple[int, int] | None = None) -> np.ndarray:
    """Âm thanh gõ máy: các ký tự `patterns`, khoảng lặng sau ký tự i = gaps_units[i] dit.
    `dropout_at` = (ký tự, phần tử): phần tử đó bị rớt tín hiệu 0,2 dit ở giữa."""
    el: list[Element] = []
    for k, p in enumerate(patterns):
        for j, s in enumerate(p):
            if j:
                el.append(Element(False, U))
            d = U if s == "." else 3 * U
            if dropout_at == (k, j):
                el += [Element(True, d * 0.45), Element(False, 0.2 * U), Element(True, d * 0.55 - 0.2 * U)]
            else:
                el.append(Element(True, d))
        if k < len(patterns) - 1:
            el.append(Element(False, gaps_units[k] * U))
    x = elements_to_audio(el, 700.0, SAMPLE_RATE, 0.8)
    pad = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
    x = np.concatenate([pad, x, pad])
    rng = np.random.default_rng(seed)
    return (x + 0.8 / np.sqrt(2) * 10 ** (-snr_db / 20) * rng.standard_normal(len(x))).astype(np.float32)


def test_all_dah_message_is_read_by_the_gap_unit():
    """Bài học số 0: toàn gạch — bộ DSP phân cụm độ dài xung thất bại (một cụm). Dit đo từ khoảng lặng
    GIỮA các phần tử nên 5 gạch vẫn là `-----`, và lặng 40 dit là dấu cách."""
    x = keyed_audio(["-----"] * 10, [40, 59] * 4 + [40])        # lặng như bài học số 0 thật
    k = read_keying(x, mix_envelope(x, 700.0), 700.0)
    assert [c.pattern for c in k.chars] == ["-----"] * 10
    assert abs(k.unit - U) < 0.01
    assert k.breaks == set(range(9))


def test_dropout_inside_a_dash_is_one_element():
    """Rớt tín hiệu giữa một gạch (khóa UA3AFO thật: `...--.`, số 0 vỡ thành dấu phẩy `--..--`)."""
    x = keyed_audio(["...--", "-----", "...--"], [7, 7], dropout_at=(1, 2))
    k = read_keying(x, mix_envelope(x, 700.0), 700.0)
    assert [c.pattern for c in k.chars] == ["...--", "-----", "...--"]


def test_gap_clusters_farnsworth_versus_lessons():
    """Farnsworth 5 WPM: giữa chữ 23 dit, giữa từ 55 dit (tỉ lệ 7:3) -> hai cụm, cụm dưới KHÔNG là dấu
    cách. Bài học đánh từng chữ số với lặng 30/49 dit -> một cụm, mọi khoảng là dấu cách."""
    assert two_clusters(np.log([23, 23, 23, 23, 55, 23, 23, 23, 23, 55])) is not None
    assert two_clusters(np.log([30, 49, 30, 30, 49, 30, 49, 30])) is None
    assert two_clusters(np.log([23, 31, 40, 59, 27, 44, 36, 51])) is None


def test_uniform_gaps_are_ambiguous_but_varied_long_gaps_are_spaces():
    """Chữ số đơn cách nhau ĐỀU (7 dit, hay 30 dit) là CÙNG âm thanh với một từ đánh Farnsworth — T1 có đúng
    loại đó (`СПАСИБО` từng bị tách thành `С П А С И Б О`): nhịp phím không quyết, để mô hình. Bài học thật
    có lặng LỆCH nhau (30/49 dit): mọi khoảng là dấu cách."""
    pats = [EN.letter_to_pattern[c] for c in "05026741"]
    for gap in (7, 30):
        x = keyed_audio(pats, [gap] * 7)
        assert read_keying(x, mix_envelope(x, 700.0), 700.0).breaks == set(), gap
    x = keyed_audio(pats + pats, [30, 49] * 7 + [30])
    assert read_keying(x, mix_envelope(x, 700.0), 700.0).breaks == set(range(15))


def _words(text: str, t0: float = 1.0, step: float = 1.0, conf: float = 1.0) -> list[Word]:
    out, t = [], t0
    for w in text.split():
        chars = []
        for ch in w:
            chars.append((ch, t))
            t += step
        out.append(Word(w, chars[0][1], t, conf, chars))
        t += step
    return out


def _keyed(patterns: list[str | None], tonal: list[float] | None = None, gap: float = 30.0,
           breaks: set[int] | None = None) -> Keyed:
    tonal = tonal or [0.9] * len(patterns)
    chars = [KeyedChar(p, 1.0 + 2 * i, 1.5 + 2 * i, tonal[i], gap, True, 0.3) for i, p in enumerate(patterns)]
    return Keyed(chars, set(range(len(patterns) - 1)) if breaks is None else breaks, set(), U,
                 stable=True, precise=True)


def test_reconcile_fixes_substitutions_inserts_misses_and_splits():
    """Bài học số 0 thật: mô hình đọc vài số 0 thành Ш/Ч và bỏ sót một số; nhịp phím rõ -> sửa, chèn,
    tách thành từng chữ số."""
    words = _words("00900 0900")                   # 9 ký tự, hai số 0 đọc thành 9; nhịp phím có 10 số 0
    k = _keyed(["-----"] * 10)
    out = reconcile(words, k, EN)
    assert out is not None and " ".join(w.text for w in out) == " ".join("0" * 10)


def test_reconcile_drops_letters_read_from_speech_but_keeps_confident_ones():
    """Giọng đọc xen Morse: chữ mô hình đọc ra trên đoạn KHÔNG thuần tone bị bỏ (trừ từ rất chắc)."""
    words = _words("3 3 ТЕ 3", conf=0.7)
    k = _keyed(["...--", "...--", None, None, "...--"], tonal=[0.9, 0.9, 0.1, 0.1, 0.9])
    out = reconcile(words, k, EN)
    assert out is not None and " ".join(w.text for w in out) == "3 3 3"


def test_reconcile_keeps_the_model_letter_when_the_pattern_agrees():
    """Kazakh: `Ә` và `А` cùng mẫu `.-` — khớp mẫu thì giữ chữ LM đã chọn."""
    kk = load_profile("kk-cyrl-ru")
    words = _words("ӘҚ Ә ҚҚ")
    k = _keyed([".-", "-.-", ".-", "-.-", "-.-"], breaks={1, 2})
    assert reconcile(words, k, kk) is None          # không có gì để sửa


def test_reconcile_refuses_when_keying_disagrees_everywhere():
    """Trong NHÓM (không đứng riêng), mô hình và nhịp phím lệch nhau khắp nơi = nhịp phím đọc nhầm nhiễu
    (trạm số M14 thu sóng ngắn: đồng ý 0,735) -> không đụng."""
    words = _words("12345 67890")
    k = _keyed(["..", "..", "..", "..", "..", "..", "..", "..", "..", ".."], gap=3.0, breaks=set())
    assert reconcile(words, k, EN) is None


def test_whole_clip_not_morse_only_for_long_unconfident_clips():
    words = _words("GOOD MMTM0 SO", conf=0.7)
    k = _keyed([None] * 20, tonal=[0.3] * 20)
    assert not_morse_clip(words, k, EN, 257.0)
    assert not not_morse_clip(words, k, EN, 12.0)                     # clip ngắn (T1 fading sâu): không phán
    assert not not_morse_clip(_words("GOOD MMTM0", conf=0.95), k, EN, 257.0)


def test_isolated_digits_with_long_pauses_decode_as_separate_words():
    """Tích hợp với mô hình thật: bài học đánh từng chữ số, lặng như các bài học thật (30/49 dit; dải liền
    23–59 dit). Chú ý: lặng TRỘN 15/30/50 dit thì chính là Farnsworth (15 giữa chữ, 30/50 giữa từ) —
    nhập nhằng thật, và T2 (ARRL 5–15 WPM, Farnsworth) cần đúng cách đọc đó."""
    from morsedesk.api import DEFAULT_MODEL_PATH, Decoder

    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip("cần models/acoustic.onnx")
    digits = "412715887739"
    for gaps in ([30, 49, 30, 30, 49, 30, 49, 30, 30, 49, 30], [23, 41, 59, 31, 27, 52, 36, 45, 24, 57, 33]):
        x = keyed_audio([EN.letter_to_pattern[c] for c in digits], gaps)
        assert Decoder("en", engine="onnx").decode_array(x).text == " ".join(digits), gaps
    zeros = keyed_audio(["-----"] * 10, [50] * 9, seed=3)
    assert Decoder("en", engine="onnx").decode_array(zeros).text == " ".join("0" * 10)


def test_reconcile_stays_out_of_fading_and_hand_keying():
    """Fading (biên độ không ổn định) -> không đụng; gõ tay (nhịp không như máy) -> không sửa chữ."""
    words = _words("00900 0900")
    faded = _keyed(["-----"] * 10)
    faded.stable = False
    assert reconcile(words, faded, EN) is None
    hand = _keyed(["-----"] * 10)
    hand.precise = False
    out = reconcile(words, hand, EN)
    assert out is None or "9" in " ".join(w.text for w in out)
