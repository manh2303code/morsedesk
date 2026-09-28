import numpy as np
import pytest

from morsedesk.data.channel import (
    ChannelParams,
    apply_channel,
    clean,
    ffmpeg_available,
    mp3_roundtrip,
    sample_channel_params,
)
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine, sample_keyer_params
from morsedesk.data.synth import SynthConfig, SynthGenerator
from morsedesk.data.text import BUILTIN_WORDS, TextSampler, translit_via_patterns
from morsedesk.dsp.baseline import BaselineDecoder
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.profile import load_profile
from morsedesk.metrics import cer
from morsedesk.model.vocab import SPACE, VOCAB


@pytest.fixture(scope="module")
def profiles():
    return {pid: load_profile(pid) for pid in ("en", "ru", "kk-cyrl-ru")}


# ---- text ----

def test_builtin_words_are_encodable(profiles):
    for pid, words in BUILTIN_WORDS.items():
        for w in words:
            assert text_to_tokens(w, profiles[pid]), (pid, w)


def test_translit_callsign_to_cyrillic(profiles):
    assert translit_via_patterns("UN7ABC", profiles["en"], profiles["ru"]) == "УН7АБЦ"


def test_sampler_outputs_supported_text(profiles):
    ts = TextSampler(profiles)
    rng = np.random.default_rng(0)
    for pid in profiles:
        for _ in range(30):
            s = ts.sample(pid, rng)
            assert s and text_to_tokens(s, profiles[pid])       # strict không lỗi


def test_sampler_corpus(tmp_path, profiles):
    corpus = tmp_path / "en.txt"
    corpus.write_text("HELLO WORLD FROM CORPUS\nSECOND LINE HERE\n", encoding="utf-8")
    ts = TextSampler(profiles, corpus={"en": corpus}, ham_ratio=0.0, random_ratio=0.0)
    s = ts.sample("en", np.random.default_rng(1))
    assert "CORPUS" in s or "LINE" in s


def test_sampler_fallback_is_profile_native(tmp_path, profiles):
    corpus = tmp_path / "ru.txt"
    corpus.write_text("ONLY LATIN LINE\n", encoding="utf-8")   # không mã hóa được trong profile ru
    ts = TextSampler(profiles, corpus={"ru": corpus}, ham_ratio=0.0, random_ratio=0.0)
    s = ts.sample("ru", np.random.default_rng(0))
    assert s == BUILTIN_WORDS["ru"][0]
    assert text_to_tokens(s, profiles["ru"])                     # strict không lỗi
    gen = SynthGenerator(SynthConfig(mp3_enabled=False, corpus={"ru": corpus}))
    ex = gen.generate(3, profile_id="ru")
    assert ex.text and ex.profile_id == "ru"


# ---- keyer ----

def test_sample_keyer_ranges():
    rng = np.random.default_rng(0)
    for _ in range(200):
        k = sample_keyer_params(rng)
        assert 5.0 <= k.wpm <= 60.0
        assert 2.0 <= k.weight <= 4.5
        assert 0.03 <= k.jitter <= 0.20
        assert -0.15 <= k.drift <= 0.15
        if k.farnsworth_wpm is not None:
            assert k.wpm < 18 and 5.0 <= k.farnsworth_wpm <= k.wpm


def test_machine_keyer_is_identity():
    els = tokens_to_elements(["-.-.", SPACE, "--.-"], TimingParams(wpm=20))
    out = apply_keyer(els, machine(20), np.random.default_rng(0))
    assert out == els


def test_drift_lengthens_later_elements():
    els = tokens_to_elements(["....."] * 5, TimingParams(wpm=20))
    k = KeyerParams(20, None, 3.0, 0.0, False, 0.10, 0.0)
    out = apply_keyer(els, k, np.random.default_rng(0))
    assert out[-1].duration > out[0].duration * 1.05


def test_jitter_changes_but_keeps_positive():
    els = tokens_to_elements(["....."] * 5, TimingParams(wpm=20))
    k = KeyerParams(20, None, 3.0, 0.15, True, 0.0, 0.05)
    out = apply_keyer(els, k, np.random.default_rng(0))
    assert len(out) == len(els)
    assert all(e.duration > 0 for e in out)
    assert any(abs(a.duration - b.duration) > 1e-6 for a, b in zip(els, out, strict=True))


# ---- channel ----

def test_sample_channel_ranges():
    rng = np.random.default_rng(0)
    for _ in range(200):
        c = sample_channel_params(rng)
        # SNR lấy mẫu hai đoạn rời: vùng khó -6..25 dB và đuôi sạch 25..65 dB (bản ghi
        # thật của ARRL đo 61,7 dB, xem tests/unit/test_snr_range.py).
        assert 400 <= c.tone_hz <= 1200 and -6 <= c.snr_db <= 65
        assert c.qrm_kind in ("none", "morse", "carrier")
        assert c.mp3_kbps in (None, 48, 64, 96, 128)


def test_clean_channel_keeps_signal():
    from tests.helpers import make_morse
    x, _ = make_morse("PARIS PARIS", wpm=20)
    y = apply_channel(x, clean(snr_db=30.0), np.random.default_rng(0))
    c = np.corrcoef(x, y)[0, 1]
    assert c > 0.95 and y.dtype == np.float32 and len(y) == len(x)


def test_qsb_reduces_envelope_minimum():
    from tests.helpers import make_morse
    x, _ = make_morse("EEEEEEEEEEEEEEEEEEEE", wpm=20)
    p = ChannelParams(700, 0, 40, qsb_depth_db=20, qsb_period_s=1.0, qrm_offset_hz=0, qrm_level_db=0,
                      qrm_kind="none", qrn_rate_per_s=0, bandpass=False, gain=1.0, clip=False,
                      dc_offset=0.0, mp3_kbps=None)
    y = apply_channel(x, p, np.random.default_rng(0))
    assert np.max(np.abs(y)) > 0.5 * np.max(np.abs(x))
    assert np.max(np.abs(y)) > 2 * np.percentile(np.abs(y[np.abs(x) > 0.5]), 5)


def test_mp3_roundtrip_without_ffmpeg_is_identity_or_close():
    x = np.random.default_rng(0).normal(0, 0.1, 8000).astype(np.float32)
    y = mp3_roundtrip(x, 8000, 64)
    assert len(y) == len(x)
    if not ffmpeg_available():
        assert np.array_equal(x, y)


# ---- generator ----

def test_generator_reproducible_and_valid():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    a = gen.generate(42)
    b = gen.generate(42)
    assert np.array_equal(a.audio, b.audio) and a.labels == b.labels and a.text == b.text
    assert a.tokens[0] != SPACE and a.tokens[-1] != SPACE
    assert all(0 <= i < len(VOCAB) for i in a.labels)
    assert all(VOCAB.token(i) == t for i, t in zip(a.labels, a.tokens, strict=True))
    assert 4.0 <= a.seconds <= 12.0 + 1.6 + 1e-6
    assert a.profile_id in ("en", "ru", "kk-cyrl-ru")


def test_generator_duration_bounds_over_many_seeds():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    seeds = list(range(1000, 1200)) + [117, 816, 962, 1494, 1794, 1830, 2244, 2324, 2961, 861, 2462]
    for seed in seeds:
        ex = gen.generate(seed)
        # tín hiệu trong [4, 12] s cộng đệm 0.2–0.8 s mỗi đầu
        assert 4.0 + 0.4 - 1e-6 <= ex.seconds <= 12.0 + 1.6 + 1e-6, (seed, ex.seconds)


def test_sample_tokens_bounds_with_default_window():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))     # min 4 s, max 12 s
    for seed in range(20):
        rng = np.random.default_rng(seed)
        for pid in ("en", "ru", "kk-cyrl-ru"):
            for wpm in (5.0, 12.0, 30.0, 60.0):
                keyer = machine(wpm)
                toks, original = gen._sample_tokens(gen.profiles[pid], keyer, rng, target_s=8.0)
                assert text_to_tokens(original, gen.profiles[pid]) == toks
                d = gen.tokens_duration(toks, keyer)
                assert 4.0 - 1e-9 <= d <= 12.0 + 1e-9, (seed, pid, wpm, d)
                assert toks[0] != SPACE and toks[-1] != SPACE


def test_sample_tokens_tight_window_never_exceeds_max():
    # cửa sổ hẹp: chỉ đảm bảo trần; sàn là nỗ lực tốt nhất (xem docstring _sample_tokens)
    gen = SynthGenerator(SynthConfig(min_seconds=4.0, max_seconds=6.0, mp3_enabled=False))
    for seed in range(20):
        rng = np.random.default_rng(seed)
        for pid in ("en", "ru", "kk-cyrl-ru"):
            toks, original = gen._sample_tokens(gen.profiles[pid], machine(5.0), rng, target_s=5.0)
            assert gen.tokens_duration(toks, machine(5.0)) <= 6.0 + 1e-9, (seed, pid)


def test_generator_different_seeds_differ():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    assert gen.generate(1).text != gen.generate(2).text


def test_generator_fixed_params_decodable_by_baseline():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    ex = gen.generate(7, profile_id="en", keyer=machine(20), channel=clean(snr_db=30.0))
    res, est = BaselineDecoder().decode_audio(ex.audio)
    hyp = load_profile("en").render(res.tokens)
    assert cer(ex.text, hyp) < 0.05


def test_mp3_roundtrip_tolerates_ffmpeg_failure(monkeypatch):
    import subprocess

    from morsedesk.data import channel

    monkeypatch.setattr(channel, "ffmpeg_available", lambda: True)

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"encoder not found")

    monkeypatch.setattr(channel.subprocess, "run", boom)
    x = np.linspace(-0.5, 0.5, 8000, dtype=np.float32)
    y = channel.mp3_roundtrip(x, 8000, 64)
    assert np.array_equal(x, y)


# ---- E20 (28/09): lối phím nhẹ + điện văn mạng CW (docs/research/06) ----

def test_fist_off_draws_no_extra_randomness():
    """fist_p = 0 không rút thêm số ngẫu nhiên nào: T1/dev và dữ liệu E18 sinh lại y hệt."""
    a, b = np.random.default_rng(7), np.random.default_rng(7)
    pa, pb = sample_keyer_params(a), sample_keyer_params(b, fist_p=0.0)
    assert pa == pb and pa.dit_scale == 1.0 and pa.after_dah == 1.0
    assert a.random() == b.random()


def test_fist_shortens_dits_and_keeps_rhythm():
    from morsedesk.data.keyer import apply_fist
    from morsedesk.encode.timing import Element
    u = 0.08
    el = [Element(True, 3 * u), Element(False, u), Element(True, u), Element(False, 3 * u),   # N, rồi E
          Element(True, u)]
    p = KeyerParams(wpm=15.0, farnsworth_wpm=None, weight=1.0, jitter=0.0, bug=False, drift=0.0,
                    spacing_error_rate=0.0, dit_scale=0.7, after_dah=0.5)
    out = apply_fist(el, p, u)
    assert len(out) == len(el) and out[0].duration == 3 * u
    assert abs(out[2].duration - 0.35 * u) < 1e-9                   # chấm ngay sau gạch: 0,7 x 0,5
    assert abs(out[4].duration - 0.7 * u) < 1e-9                    # chấm đầu ký tự: chỉ 0,7
    assert abs(sum(e.duration for e in out[:4]) - sum(e.duration for e in el[:4])) < 1e-9   # nhịp giữ


def test_fist_sampled_when_asked():
    rng = np.random.default_rng(3)
    ps = [sample_keyer_params(rng, fist_p=1.0) for _ in range(200)]
    assert all(0.5 <= p.dit_scale <= 1.15 for p in ps)
    light = [p for p in ps if p.after_dah < 1.0]
    assert 60 < len(light) < 140 and all(0.15 <= p.after_dah <= 0.75 for p in light)


def test_net_traffic_text_is_encodable(profiles):
    from morsedesk.data.numeric_text import numeric_text
    en = profiles["en"]
    rng = np.random.default_rng(11)
    texts = [numeric_text(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), rng, 6, net_share=1.0) for _ in range(300)]
    joined = " ".join(texts)
    for marker in ("RMKS", " DE ", "<ERR>", " ?", "CK"):
        assert marker in joined
    groups = [w for t in texts for w in t.split() if len(w) == 4 and all(c in "0123456789TAUVDN" for c in w)]
    assert len(groups) > 300
    for t in texts:
        assert text_to_tokens(t, en)
