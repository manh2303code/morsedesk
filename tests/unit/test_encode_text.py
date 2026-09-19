import pytest

from morsedesk.encode.text import UnsupportedCharacter, normalize, text_to_tokens
from morsedesk.lm.profile import load_profile
from morsedesk.model.vocab import SPACE


@pytest.fixture(scope="module")
def en():
    return load_profile("en")


@pytest.fixture(scope="module")
def ru():
    return load_profile("ru")


@pytest.fixture(scope="module")
def kk():
    return load_profile("kk-cyrl-ru")


def test_normalize_upper_and_collapse_spaces(en):
    assert normalize("  cq   de  k1abc ", en) == "CQ DE K1ABC"


def test_normalize_applies_alias(ru):
    assert normalize("ёж", ru) == "ЕЖ"


def test_tokens_basic(en):
    assert text_to_tokens("CQ cq", en) == ["-.-.", "--.-", SPACE, "-.-.", "--.-"]


def test_tokens_no_leading_trailing_or_double_space(en):
    toks = text_to_tokens("  A   B  ", en)
    assert toks == [".-", SPACE, "-..."]


def test_prosign_syntax(en):
    assert text_to_tokens("SOS <SK>", en) == ["...", "---", "...", SPACE, "...-.-"]
    assert text_to_tokens("<sos>", en) == ["...---..."]


def test_shared_prosigns_in_text(en):
    assert text_to_tokens("<BT> 73 <AR> <KN>", en) == ["-...-", SPACE, "--...", "...--", SPACE, ".-.-.", SPACE, "-.--."]


def test_digits_and_punct(en):
    assert text_to_tokens("73?", en) == ["--...", "...--", "..--.."]


def test_unsupported_strict(en):
    with pytest.raises(UnsupportedCharacter) as ei:
        text_to_tokens("ABӘ", en)
    assert ei.value.char == "Ә"
    assert ei.value.position == 2


def test_unsupported_lenient(en):
    assert text_to_tokens("ABӘC", en, strict=False) == [".-", "-...", "-.-."]


def test_kazakh_letters(kk):
    assert text_to_tokens("ӘЛЕМ", kk) == [".-", ".-..", ".", "--"]
    assert text_to_tokens("ҚҰС", kk) == ["-.-", "..-", "..."]


def test_russian_hard_sign(ru):
    assert text_to_tokens("ОБЪЕМ", ru) == ["---", "-...", "-..-", ".", "--"]
