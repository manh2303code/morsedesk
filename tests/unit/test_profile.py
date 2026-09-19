import pytest

from morsedesk.lm.profile import UNK_DISPLAY, Profile, list_profiles, load_profile
from morsedesk.model.vocab import SPACE, UNK, VOCAB


@pytest.fixture(scope="module")
def en():
    return load_profile("en")


@pytest.fixture(scope="module")
def ru():
    return load_profile("ru")


@pytest.fixture(scope="module")
def kk():
    return load_profile("kk-cyrl-ru")


def test_list_profiles():
    assert set(list_profiles()) == {"en", "ru", "kk-cyrl-ru"}


def test_all_map_keys_are_vocab_patterns(en, ru, kk):
    for p in (en, ru, kk):
        for pattern in p.map:
            assert VOCAB.is_pattern(pattern), (p.id, pattern)
        for pattern in p.prosigns:
            assert VOCAB.is_pattern(pattern), (p.id, pattern)


def test_en_letters_digits_punct(en):
    letters = [pat for pat, ls in en.map.items() if ls[0].isalpha()]
    assert len(letters) == 26
    assert en.letter_to_pattern["Q"] == "--.-"
    assert en.letter_to_pattern["0"] == "-----"
    assert en.letter_to_pattern["?"] == "..--.."
    assert en.decode_options("----") == [UNK]
    assert en.decode_options("...-.-") == ["<SK>"]
    assert en.prosign_to_pattern["<SOS>"] == "...---..."


def test_ru_covers_32_letters_with_hard_sign(ru):
    # Ь (mềm) và Ъ (cứng) dùng chung mẫu -..-, nên 32 chữ cái ánh xạ trên 31 mẫu.
    letters = {L for ls in ru.map.values() for L in ls if L.isalpha()}
    assert len(letters) == 32
    assert ru.letter_to_pattern["Ш"] == "----"
    assert ru.letter_to_pattern["Э"] == "..-.."
    assert ru.decode_options("-..-") == ["Ь", "Ъ"]
    assert ru.canonical_letter("Ё") == "Е"
    assert ru.letter_to_pattern["Ъ"] == "-..-"


def test_kk_one_to_many(kk):
    assert kk.decode_options(".-") == ["А", "Ә"]
    assert kk.decode_options("..-") == ["У", "Ұ", "Ү"]
    assert kk.decode_options("....") == ["Х", "Һ"]
    assert kk.decode_options("..") == ["И", "І"]
    assert kk.letter_to_pattern["Ә"] == ".-"
    assert kk.letter_to_pattern["Қ"] == "-.-"
    assert kk.letter_to_pattern["Ң"] == "-."
    assert kk.letter_to_pattern["Ө"] == "---"
    assert kk.letter_to_pattern["Ғ"] == "--."


def test_render(en, ru):
    assert en.render(["-.-.", "--.-", SPACE, "-..", "."]) == "CQ DE"
    assert ru.render([".--.", ".-.", "..", ".--", ".", "-"]) == "ПРИВЕТ"
    assert en.render(["----"]) == UNK_DISPLAY
    assert en.render(["...-.-"]) == "<SK>"


def test_shared_prosigns_encode_but_render_as_punctuation(en):
    assert en.prosign_to_pattern["<AR>"] == ".-.-."
    assert en.prosign_to_pattern["<BT>"] == "-...-"
    assert en.prosign_to_pattern["<KN>"] == "-.--."
    assert en.prosign_to_pattern["<AS>"] == ".-..."
    assert en.decode_options(".-.-.") == ["+"]
    assert en.decode_options("-...-") == ["="]


def test_inverse_conflict_raises():
    with pytest.raises(ValueError):
        Profile(
            id="x", script="Latin", display_name="x", lm="",
            map={".-": ["A"], "-...": ["A"]}, prosigns={}, encode_aliases={}, lexicon_bonus=[],
        )


def test_load_by_path(tmp_path):
    p = load_profile("en")
    assert p.id == "en"
    from morsedesk.lm.profile import PROFILES_DIR
    assert load_profile(PROFILES_DIR / "ru.yaml").id == "ru"
