import pytest

from morsedesk.model import vocab
from morsedesk.model.vocab import VOCAB, BLANK, SPACE, UNK


def test_size_is_65():
    assert len(VOCAB) == 65


def test_special_indices():
    assert VOCAB.id(BLANK) == 0
    assert VOCAB.id(SPACE) == 1
    assert VOCAB.id(UNK) == 2
    assert VOCAB.blank_id == 0 and VOCAB.space_id == 1 and VOCAB.unk_id == 2


def test_tokens_unique_and_roundtrip():
    assert len(set(VOCAB.tokens)) == len(VOCAB.tokens)
    for i, tok in enumerate(VOCAB.tokens):
        assert VOCAB.id(tok) == i
        assert VOCAB.token(i) == tok


def test_group_counts():
    assert len(vocab.LATIN) == 26
    assert len(vocab.RUSSIAN_ONLY) == 5
    assert len(vocab.DIGITS) == 10
    assert len(vocab.PUNCT) == 18
    assert len(vocab.PROSIGNS) == 3


def test_russian_only_patterns_present():
    for p in ["----", "---.", "..--", ".-.-", "..-.."]:
        assert VOCAB.is_pattern(p)
        assert VOCAB.id(p) >= 3


def test_unknown_token_raises():
    with pytest.raises(KeyError):
        VOCAB.id("......-")


def test_is_pattern_false_for_specials():
    assert not VOCAB.is_pattern(BLANK)
    assert not VOCAB.is_pattern(SPACE)
    assert not VOCAB.is_pattern(UNK)
