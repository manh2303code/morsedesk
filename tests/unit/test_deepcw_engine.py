import numpy as np
import pytest

from morsedesk.api import Decoder, Encoder
from morsedesk.audio.io import save_audio
from morsedesk.cli import main
from morsedesk.model.deepcw import DeepCwOutput

CHARS = [",", ".", "/", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "?",
         *[chr(c) for c in range(ord("A"), ord("Z") + 1)], " "]


class FakeDeepCw:
    """Model DeepCW giả: phát ra một chuỗi chữ cố định ở các khung cho trước."""

    chars = CHARS
    blank = 41
    sample_rate = 3200
    hop_length = 48
    frame_rate = 3200 / 48

    def __init__(self, text: str = "CQ DE K", prob: float = 0.9, n_frames: int = 400) -> None:
        self.emissions = [(ch, 10 * i + 5, prob) for i, ch in enumerate(text)]
        self.n_frames = n_frames
        self.calls = 0

    def load(self):
        return self

    def log_probs(self, x, sample_rate):
        self.calls += 1
        lp = np.full((self.n_frames, 42), np.log(0.1 / 41.0), dtype=np.float32)
        lp[:, self.blank] = np.log(0.9)
        for ch, f, p in self.emissions:
            lp[f, self.blank] = np.log(1.0 - p)
            lp[f, CHARS.index(ch)] = np.log(p)
        return lp

    def decode_greedy(self, x, sample_rate):
        self.calls += 1
        return DeepCwOutput(list(self.emissions), self.n_frames, self.frame_rate, 0.9)


def cq_audio() -> np.ndarray:
    return Encoder("en").to_audio("CQ DE K", wpm=20)


def test_deepcw_rejects_non_en_profile():
    with pytest.raises(ValueError, match="deepcw"):
        Decoder("ru", engine="deepcw", acoustic_model=FakeDeepCw(), lm=False)


def test_deepcw_rejects_auto_profile():
    with pytest.raises(ValueError, match="deepcw"):
        Decoder("auto", engine="deepcw", acoustic_model=FakeDeepCw(), lm=False)


def test_deepcw_decodes_words_with_timings_and_wpm():
    model = FakeDeepCw()
    dec = Decoder("en", engine="deepcw", acoustic_model=model, lm=False)
    r = dec.decode_array(cq_audio(), 8000)
    assert r.text == "CQ DE K"
    assert r.engine == "deepcw" and r.language == "en"
    assert [w.text for w in r.words] == ["CQ", "DE", "K"]
    assert r.words[0].start_s < r.words[1].start_s < r.words[2].start_s
    assert r.words[0].end_s <= r.words[1].start_s
    assert all(0.0 < w.confidence <= 1.0 for w in r.words)
    assert r.wpm is not None and r.wpm > 0
    assert r.tone_hz is not None and 600.0 < r.tone_hz < 800.0
    assert model.calls == 1


def test_deepcw_low_confidence_adds_dsp_fallback():
    dec = Decoder("en", engine="deepcw", acoustic_model=FakeDeepCw(prob=0.2), lm=False)
    r = dec.decode_array(cq_audio(), 8000)
    assert any("DSP" in w for w in r.warnings)
    assert r.fallback_text is not None


def test_deepcw_no_signal_returns_empty():
    """Không dò được tone VÀ model cũng không ra chữ nào -> rỗng kèm cảnh báo (spec §7)."""
    dec = Decoder("en", engine="deepcw", acoustic_model=FakeDeepCw(text=""), lm=False)
    r = dec.decode_array(np.zeros(8000, dtype=np.float32), 8000)
    assert r.text == "" and r.words == [] and r.warnings


def test_deepcw_decodes_even_when_tone_estimator_finds_nothing():
    """Cổng dò tone không được chặn engine deepcw.

    DeepCW nghe cả dải 400-1200 Hz và không dùng ước lượng tone. Đo được 15/167 clip `en` của T1
    (SNR 0-3 dB, phần lớn qsb) bị cổng này trả rỗng dù model giải mã được, làm CER xấu từ 22,9 %
    lên 27,2 %. Clip dưới đây là nhiễu trắng: `estimate_tone` không thấy tín hiệu, nhưng model
    vẫn phải được chạy.
    """
    rng = np.random.default_rng(0)
    noise = rng.normal(0.0, 0.05, 8000).astype(np.float32)
    dec = Decoder("en", engine="deepcw", acoustic_model=FakeDeepCw(text="CQ"), lm=False)
    r = dec.decode_array(noise, 8000)
    assert r.text == "CQ", r.text
    assert r.tone_hz is None                  # không dò được tone thì báo cáo trung thực là None
    assert r.fallback_text is None            # bộ giải mã DSP cần tone, không chạy được


def test_cli_decode_deepcw_rejects_cyrillic_profile(tmp_path, capsys):
    p = tmp_path / "cq.wav"
    save_audio(p, cq_audio(), 8000)
    assert main(["decode", str(p), "--profile", "ru", "--engine", "deepcw"]) == 2
    assert "deepcw" in capsys.readouterr().err


def test_cli_decode_deepcw_reports_missing_model(tmp_path, capsys):
    p = tmp_path / "cq.wav"
    save_audio(p, cq_audio(), 8000)
    rc = main(["decode", str(p), "--profile", "en", "--engine", "deepcw", "--no-lm",
               "--model", str(tmp_path / "nope.onnx")])
    assert rc == 2
    assert "fetch_deepcw" in capsys.readouterr().err


def test_cli_bench_accepts_deepcw_engine():
    from morsedesk.cli import build_parser

    a = build_parser().parse_args(["bench", "--manifest", "m.jsonl", "--engine", "deepcw"])
    assert a.engine == "deepcw"
