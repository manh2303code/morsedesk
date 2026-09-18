import json

import numpy as np
import pytest

from morsedesk.api import DecodeResult, Decoder, Encoder
from morsedesk.cli import main
from morsedesk.encode.synth import add_noise


def test_morse_string():
    assert Encoder("en").to_morse_string("CQ DE") == "-.-. --.- / -.. ."
    assert Encoder("ru").to_morse_string("Ёж") == ". ...-"


def test_encoder_decoder_roundtrip_english():
    text = "CQ CQ DE R1ABC K"
    x = Encoder("en").to_audio(text, wpm=22)
    r = Decoder("en").decode_array(x)
    assert isinstance(r, DecodeResult)
    assert r.text == text
    assert r.engine == "baseline"
    assert abs(r.wpm - 22) < 2.5
    assert abs(r.tone_hz - 700) < 10
    assert r.warnings == []
    assert [w.text for w in r.words] == text.split()
    for a, b in zip(r.words, r.words[1:]):
        assert a.end_s <= b.start_s
    assert all(0.0 <= w.confidence <= 1.0 for w in r.words)


def test_roundtrip_kazakh_profile_renders_first_option():
    x = Encoder("kk-cyrl-ru").to_audio("ӘЛЕМ", wpm=20)
    r = Decoder("kk-cyrl-ru").decode_array(x)
    assert r.text == "АЛЕМ"       # chưa có LM: chọn chữ đầu của mỗi mẫu


def test_decoder_resamples_other_rates():
    x = Encoder("en").to_audio("TEST", wpm=20, sample_rate=16000)
    r = Decoder("en").decode_array(x, sample_rate=16000)
    assert r.text == "TEST"


def test_noise_only_gives_warning():
    x = add_noise(np.zeros(8000 * 3, dtype=np.float32), 0.0, 0.32, rng=np.random.default_rng(1))
    r = Decoder("en").decode_array(x)
    assert r.text == ""
    assert any("không có tín hiệu" in w for w in r.warnings)


def test_auto_and_unknown_engine_not_yet_supported():
    with pytest.raises(NotImplementedError):
        Decoder("auto")
    with pytest.raises(NotImplementedError):
        Decoder("en", engine="foo")


def test_to_json_roundtrip():
    x = Encoder("en").to_audio("HI", wpm=20)
    r = Decoder("en").decode_array(x)
    d = json.loads(r.to_json())
    assert d["text"] == "HI" and d["engine"] == "baseline"
    assert isinstance(d["words"], list)


def test_cli_encode_and_decode(tmp_path, capsys):
    out = tmp_path / "cq.wav"
    assert main(["encode", "CQ DE K", "--profile", "en", "--wpm", "20", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "-.-. --.- / -.. . / -.-" in printed
    assert out.exists()

    assert main(["decode", str(out), "--profile", "en"]) == 0
    assert capsys.readouterr().out.strip() == "CQ DE K"

    assert main(["decode", str(out), "--profile", "en", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["text"] == "CQ DE K"


def test_cli_encode_lenient(tmp_path, capsys):
    assert main(["encode", "ABӘ", "--profile", "en", "--lenient"]) == 0
    assert capsys.readouterr().out.strip() == ".- -..."


def test_cli_encode_strict_error(capsys):
    assert main(["encode", "ABӘ", "--profile", "en"]) == 2
    assert "không hỗ trợ" in capsys.readouterr().err
