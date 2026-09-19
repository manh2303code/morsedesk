from pathlib import Path

import pytest

from morsedesk.api import (
    Decoder,
    Encoder,
    emissions_to_words,
    estimate_wpm_from_emissions,
    pattern_units,
)
from morsedesk.cli import main
from morsedesk.lm.profile import load_profile
from morsedesk.metrics import cer
from morsedesk.model.vocab import SPACE


@pytest.fixture(scope="module")
def tmp_model(tmp_path_factory):
    torch = pytest.importorskip("torch")
    pytest.importorskip("onnxruntime")
    from tools.export_onnx import export
    from tools.net_torch import CONFIG_DEFAULT, MorseNet

    tmp = tmp_path_factory.mktemp("m")
    torch.manual_seed(0)
    ckpt = tmp / "best.pt"
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                "config": CONFIG_DEFAULT}, ckpt)
    onnx_path = tmp / "acoustic.onnx"
    export(ckpt, onnx_path, version="test")
    return onnx_path


def test_pattern_units():
    assert pattern_units(".-") == 1 + 3 + 1
    assert pattern_units("-") == 3
    assert pattern_units(".....") == 5 + 4


def test_estimate_wpm_from_emissions():
    u = 12  # 20 WPM -> dit 60 ms = 12 khung
    em = [(".-", 0, 0.9), ("-...", 8 * u, 0.9), ("-.-.", (8 + 9 + 3) * u, 0.9)]
    assert abs(estimate_wpm_from_emissions(em, 200) - 20.0) < 0.5
    em2 = [(".-", 0, 0.9), (SPACE, 5 * u, 1.0), ("-...", 12 * u, 0.9), ("-", (12 + 9 + 3) * u, 0.9)]
    assert abs(estimate_wpm_from_emissions(em2, 200) - 20.0) < 0.5
    assert estimate_wpm_from_emissions([(".-", 0, 0.9)], 200) is None


def test_emissions_to_words():
    en = load_profile("en")
    em = [("-.-.", 0, 0.9), ("--.-", 100, 0.4), (SPACE, 200, 1.0), ("-..", 300, 0.81), (".", 400, 0.81)]
    words = emissions_to_words(em, en, 200, 500)
    assert [w.text for w in words] == ["CQ", "DE"]
    assert abs(words[0].confidence - (0.9 * 0.4) ** 0.5) < 1e-6
    assert abs(words[1].confidence - 0.81) < 1e-6
    assert words[0].start_s == 0.0 and words[0].end_s == 1.0
    assert words[1].start_s == 1.5 and words[1].end_s == 2.5


def test_onnx_engine_runs_with_untrained_model(tmp_model):
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20)
    r = Decoder("en", engine="onnx", model_path=tmp_model).decode_array(x)
    assert r.engine == "onnx"
    assert isinstance(r.text, str)
    assert abs(r.tone_hz - 700) < 10
    assert r.fallback_text is None or isinstance(r.fallback_text, str)


def test_missing_model_raises(tmp_path):
    pytest.importorskip("onnxruntime")
    with pytest.raises(FileNotFoundError):
        Decoder("en", engine="onnx", model_path=tmp_path / "none.onnx")


def test_cli_missing_model_exit_2(tmp_path, capsys):
    pytest.importorskip("onnxruntime")
    wav = tmp_path / "a.wav"
    from morsedesk.audio.io import save_audio
    save_audio(wav, Encoder("en").to_audio("CQ", wpm=20), 8000)
    assert main(["decode", str(wav), "--engine", "onnx", "--model", str(tmp_path / "none.onnx")]) == 2
    assert "lỗi" in capsys.readouterr().err


@pytest.mark.gate
@pytest.mark.skipif(not Path("models/acoustic.onnx").exists(), reason="chưa có model đã huấn luyện")
def test_trained_model_roundtrip():
    text = "CQ CQ DE R1ABC R1ABC K"
    x = Encoder("en").to_audio(text, wpm=20, snr_db=10.0, seed=1)
    r = Decoder("en", engine="onnx").decode_array(x)
    assert cer(text, r.text) < 0.05, r.text
    assert abs(r.wpm - 20) < 4.0
    x2 = Encoder("ru").to_audio("ПРИВЕТ МИР", wpm=25, snr_db=6.0, seed=2)
    r2 = Decoder("ru", engine="onnx").decode_array(x2)
    assert cer("ПРИВЕТ МИР", r2.text) < 0.1, r2.text


def test_no_fallback_disables_baseline_text(tmp_model):
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20)
    r = Decoder("en", engine="onnx", model_path=tmp_model, fallback=False).decode_array(x)
    assert r.fallback_text is None

