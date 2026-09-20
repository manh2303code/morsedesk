import numpy as np

from morsedesk.data.channel import clean
from morsedesk.data.keyer import machine
from morsedesk.data.synth import Example, SynthConfig, SynthGenerator
from morsedesk.data.text import TextSampler, keep_supported
from morsedesk.encode.text import text_to_tokens
from morsedesk.lm.profile import load_profile

P = {pid: load_profile(pid) for pid in ("en", "ru", "kk-cyrl-ru")}
KAZAKH_ONLY = set("ӘҒҚҢӨҰҮҺІ")


def test_keep_supported_keeps_kazakh_letters_and_prosigns():
    assert keep_supported("Сәлем, әлем! <SK> Ёж", P["kk-cyrl-ru"]) == "СӘЛЕМ, ӘЛЕМ! <SK> ЕЖ"
    assert keep_supported("héllo   wörld", P["en"]) == "HLLO WRLD"
    assert keep_supported("<XYZ> ok", P["en"]) == "OK"            # prosign lạ bị bỏ, dấu < > không mã hóa
    assert keep_supported("", P["en"]) == ""


def test_keep_supported_rewrites_prosigns_colliding_with_letters():
    """<AR> <BT> <KN> <AS> dùng chung mẫu với + = ( &: bộ giải mã luôn trả chữ nên ghi thành chữ."""
    assert keep_supported("73 <AR> K", P["en"]) == "73 + K"
    assert keep_supported("<BT> <KN> <AS>", P["en"]) == "= ( &"
    assert keep_supported("<SK>", P["en"]) == "<SK>"              # mẫu riêng: giữ tên prosign
    assert keep_supported("<SOS> <ERR>", P["en"]) == "<SOS> <ERR>"


def test_sampler_keeps_original_kazakh_letters():
    ts = TextSampler(P)
    seen = False
    for seed in range(60):
        s = ts.sample("kk-cyrl-ru", np.random.default_rng(seed))
        text_to_tokens(s, P["kk-cyrl-ru"])                        # luôn mã hóa được
        seen |= bool(set(s) & KAZAKH_ONLY)
    assert seen


def test_example_has_text_original_consistent_with_text():
    gen = SynthGenerator(SynthConfig(min_seconds=3.0, max_seconds=5.0, mp3_enabled=False))
    differs = False
    for seed in range(12):
        ex = gen.generate(seed, profile_id="kk-cyrl-ru", keyer=machine(25), channel=clean(30.0))
        assert isinstance(ex, Example)
        tokens = text_to_tokens(ex.text_original, P["kk-cyrl-ru"])
        assert tokens == ex.tokens
        assert P["kk-cyrl-ru"].render(tokens) == ex.text
        differs |= ex.text_original != ex.text
    assert differs
    en = gen.generate(3, profile_id="en", keyer=machine(25), channel=clean(30.0))
    assert en.text_original == en.text
