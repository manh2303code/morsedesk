import json

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.profile import load_profile


def test_for_profile_has_specials_first_and_all_letters():
    a = LMAlphabet.for_profile(load_profile("kk-cyrl-ru"))
    assert a.symbols[:4] == ["<s>", "</s>", "<unk>", " "]
    for ch in "АӘҒҚҢӨҰҮҺІ0.?":
        assert ch in a.index
    assert len(a.symbols) == len(set(a.symbols))


def test_encode_decode_roundtrip_and_unk():
    a = LMAlphabet.for_profile(load_profile("en"))
    ids = a.encode("CQ DE K")
    assert a.decode(ids) == "CQ DE K"
    assert ids[2] == a.space_id
    assert a.encode("Ә") == [a.unk_id]


def test_tokens_line_roundtrip():
    a = LMAlphabet.for_profile(load_profile("ru"))
    line = a.to_tokens_line("ПРИВЕТ МИР")
    assert line == "П Р И В Е Т ▁ М И Р"
    assert a.from_tokens_line(line) == "ПРИВЕТ МИР"


def test_save_load(tmp_path):
    a = LMAlphabet.for_profile(load_profile("en"))
    a.save(tmp_path / "a.json")
    b = LMAlphabet.load(tmp_path / "a.json")
    assert b.symbols == a.symbols
    assert json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))["symbols"][0] == "<s>"
