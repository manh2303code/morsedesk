import math

import numpy as np
import pytest

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import (
    CharNGramLM,
    extend_hash,
    fnv1a64,
    load_arpa,
    load_bin,
    save_arpa,
    save_bin,
    train_small,
)

ALPHA = LMAlphabet(["<s>", "</s>", "<unk>", " ", "A", "B", "C"])
LINES = ["AB AB AC", "AB", "BA"]


@pytest.fixture(scope="module")
def lm():
    return train_small(LINES, ALPHA, order=3)


def test_fnv_and_extend_consistent():
    h = fnv1a64([4, 5])
    ext = extend_hash(np.uint64(fnv1a64([4])), np.array([5, 6]))
    assert int(ext[0]) == h
    assert int(ext[1]) == fnv1a64([4, 6])
    assert h != fnv1a64([5, 4])


def test_unigram_and_bigram_ordering(lm):
    a, b, c = ALPHA.index["A"], ALPHA.index["B"], ALPHA.index["C"]
    # sau A: B xuất hiện 3 lần, C 1 lần
    assert lm.score((a,), b) > lm.score((a,), c)
    # đơn vị: log tự nhiên, xác suất < 1
    assert lm.score((), a) < 0.0


def test_distribution_sums_to_one(lm):
    a = ALPHA.index["A"]
    for ctx in [(), (a,), (ALPHA.bos_id, a)]:
        total = sum(math.exp(lm.score(ctx, s)) for s in range(1, len(ALPHA.symbols)))  # bỏ <s>
        assert math.isclose(total, 1.0, abs_tol=1e-6), (ctx, total)


def test_unseen_context_backs_off(lm):
    c = ALPHA.index["C"]
    b = ALPHA.index["B"]
    # "CC" chưa từng xuất hiện làm context: lùi về bậc thấp hơn, không lỗi, hữu hạn
    s = lm.score((c, c), b)
    assert np.isfinite(s) and s < 0.0


def test_score_many_matches_score(lm):
    a = ALPHA.index["A"]
    syms = np.arange(1, len(ALPHA.symbols))
    many = lm.score_many((a,), syms)
    for s, v in zip(syms, many, strict=True):
        assert math.isclose(float(v), lm.score((a,), int(s)), rel_tol=1e-6)


def test_sentence_logprob_and_perplexity(lm):
    lp = lm.sentence_logprob("AB AB")
    assert lp < 0.0
    ppl = lm.perplexity(["AB AB", "AC"])
    assert ppl > 1.0
    assert lm.perplexity(["AB AB AC"]) < lm.perplexity(["CCC CCC"])


def test_arpa_roundtrip(tmp_path, lm):
    p = tmp_path / "lm.arpa"
    save_arpa(lm, p)
    text = p.read_text(encoding="utf-8")
    assert "\\data\\" in text and "\\3-grams:" in text
    lm2 = load_arpa(p, ALPHA)
    a, b = ALPHA.index["A"], ALPHA.index["B"]
    assert math.isclose(lm2.score((a,), b), lm.score((a,), b), abs_tol=1e-5)
    assert math.isclose(lm2.score((), b), lm.score((), b), abs_tol=1e-5)


def test_bin_roundtrip(tmp_path, lm):
    p = tmp_path / "lm.bin"
    save_bin(lm, p)
    lm2 = load_bin(p)
    assert lm2.alphabet.symbols == ALPHA.symbols
    assert lm2.order == 3
    a, b = ALPHA.index["A"], ALPHA.index["B"]
    assert math.isclose(lm2.score((a,), b), lm.score((a,), b), rel_tol=1e-6)


def test_train_small_empty_lines_and_order_one():
    lm1 = train_small(["A A B"], ALPHA, order=1)
    assert isinstance(lm1, CharNGramLM) and lm1.order == 1
    total = sum(math.exp(lm1.score((), s)) for s in range(1, len(ALPHA.symbols)))
    assert math.isclose(total, 1.0, abs_tol=1e-6)
