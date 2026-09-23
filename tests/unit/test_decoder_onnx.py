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
    r = Decoder("en", engine="onnx", model_path=tmp_model, lm=False).decode_array(x)
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
@pytest.mark.skipif(
    not Path("models/acoustic.onnx").exists()
    or not Path("models/lm/en.bin").exists()
    or not Path("models/lm/ru.bin").exists(),
    reason="chưa có model đã huấn luyện hoặc thiếu models/lm/{en,ru}.bin",
)
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
    r = Decoder("en", engine="onnx", model_path=tmp_model, fallback=False, lm=False).decode_array(x)
    assert r.fallback_text is None



# Spec §7: không có tín hiệu -> kết quả rỗng, cảnh báo, KHÔNG bịa chữ. Test cũ kiểm điều này với
# engine `baseline`, mà đường đoán tone (fallback_tone_hz) chỉ chạy cho engine `onnx` — nên khi nó
# được thêm vào ngày 22/09, test vẫn xanh trong khi engine sản phẩm biến im lặng thành chữ `T`.
@pytest.mark.parametrize("n", [8000, 8000 * 12, 8000 * 30])
def test_onnx_digital_silence_is_empty_not_fabricated(tmp_model, n):
    import numpy as np

    from morsedesk.warnings import WarningCode

    r = Decoder("en", engine="onnx", model_path=tmp_model, lm=False).decode_array(
        np.zeros(n, dtype=np.float32))
    assert r.text == "" and r.words == []
    assert [w.code for w in r.warning_codes] == [WarningCode.NO_SIGNAL.value]


_HAS_REAL = Path("models/acoustic.onnx").exists() and Path("models/lm/en.bin").exists()


# Cổng độ tin cậy theo clip (MIN_CLIP_CONFIDENCE). Đo 23/09: 81/81 đầu vào KHÔNG có Morse ra chữ
# (nhiễu trắng `SEE`, sóng mang `73`/`CAR`, nhiễu xung `SEE`), độ tin cậy trung bình cả clip của
# chúng tối đa 0,113; còn clip Morse thật trên bộ dev không clip nào dưới 0,15.
@pytest.mark.skipif(not _HAS_REAL, reason="cần model đã huấn luyện và models/lm/en.bin")
@pytest.mark.parametrize("kind", ["white", "carrier", "qrn"])
def test_non_morse_input_is_not_turned_into_text(kind):
    import numpy as np

    from morsedesk.warnings import WarningCode

    rng = np.random.default_rng(7)
    n, t = 8000 * 20, np.arange(8000 * 20) / 8000
    x = {"white": rng.normal(0, 0.01, n),
         "carrier": 0.5 * np.sin(2 * np.pi * 700 * t) + rng.normal(0, 0.01, n),
         "qrn": rng.normal(0, 0.002, n)}[kind]
    if kind == "qrn":
        i = rng.integers(0, n, n // 400)
        x[i] += rng.normal(0, 0.5, len(i))
    r = Decoder("en", engine="onnx").decode_array(x.astype(np.float32))
    assert r.text == "", f"{kind}: bịa ra {r.text!r}"
    assert WarningCode.NO_SIGNAL.value in [w.code for w in r.warning_codes]


@pytest.mark.skipif(not _HAS_REAL, reason="cần model đã huấn luyện và models/lm/en.bin")
def test_confidence_gate_keeps_real_low_snr_morse():
    """Cổng không được nuốt Morse thật ở SNR thấp nhưng còn đọc được."""
    text = "CQ CQ DE R1ABC K"
    x = Encoder("en").to_audio(text, wpm=18, snr_db=0.0, seed=4)
    r = Decoder("en", engine="onnx").decode_array(x)
    assert r.text and cer(text, r.text) < 0.3, r.text


def test_gated_result_still_reports_the_tone_it_heard(tmp_model):
    """Model chưa huấn luyện cho độ tin cậy gần 0 -> văn bản rỗng, nhưng tone 700 Hz đo được vẫn
    phải báo ra: 'nghe thấy một tone ở 700 Hz nhưng không đọc ra Morse' khác hẳn 'không có gì'."""
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20)
    # fallback=False: tín hiệu sạch thì bộ DSP được chọn và giải đúng — hành vi đúng, nhưng
    # không đi qua cổng. Tắt DSP để chắc chắn đang kiểm đường MÔ HÌNH.
    r = Decoder("en", engine="onnx", model_path=tmp_model, lm=False, fallback=False).decode_array(x)
    from morsedesk.warnings import WarningCode

    assert r.text == "" and WarningCode.NO_SIGNAL.value in [w.code for w in r.warning_codes]
    assert r.tone_hz is not None and abs(r.tone_hz - 700) < 10
