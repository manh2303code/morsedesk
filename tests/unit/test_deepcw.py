import json

import numpy as np
import pytest

from morsedesk.model import deepcw
from morsedesk.model.deepcw import (
    DeepCwModel,
    Remapper,
    audio_to_spectrogram,
    emissions_to_text,
    frequency_bin_range,
    greedy_ctc_emissions,
    mean_frame_confidence,
    read_wav_mono,
    resample_to,
)

# Bản sao metadata thật của DeepCW (model.onnx.json), đủ để chạy tiền xử lý mà không cần model 15 MB.
META = {
    "chars": [",", ".", "/", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "?",
              *[chr(c) for c in range(ord("A"), ord("Z") + 1)], " "],
    "blank_index": 41,
    "sample_rate": 3200,
    "fft_length": 256,
    "hop_length": 48,
    "spectrogram_min_freq_hz": 400.0,
    "spectrogram_max_freq_hz": 1200.0,
    "spectrogram_frequency_bins": 65,
    "normalization": "log1p",
    "onnx_input_name": "spectrogram",
    "onnx_output_name": "log_probs",
    "num_classes": 42,
}
BLANK = META["blank_index"]


def lattice(rows: list[int | None], n_classes: int = 42, peak: float = 0.95) -> np.ndarray:
    """Lưới log-prob nhọn: mỗi hàng là một lớp chắc chắn (None = blank)."""
    rest = np.log((1.0 - peak) / (n_classes - 1))
    lp = np.full((len(rows), n_classes), rest, dtype=np.float32)
    for t, c in enumerate(rows):
        lp[t, BLANK if c is None else c] = np.log(peak)
    return lp


class FakeSession:
    """Phiên onnxruntime giả: ghi lại đầu vào, trả lưới cố định."""

    def __init__(self, lp: np.ndarray) -> None:
        self.lp = lp[None]
        self.seen: list[np.ndarray] = []

    def run(self, outputs, feeds):
        self.seen.append(feeds["spectrogram"])
        return [self.lp]


def test_frequency_bin_range_gives_65_bins():
    assert frequency_bin_range(3200, 256, 400.0, 1200.0) == (32, 97)


def test_audio_to_spectrogram_shape_and_peak_bin():
    t = np.arange(3200) / 3200.0
    audio = np.sin(2 * np.pi * 700.0 * t).astype(np.float32)
    spec = audio_to_spectrogram(audio, META)
    assert spec.shape == (1, 1, 67, 65) and spec.dtype == np.float32
    assert float(spec.min()) >= 0.0                       # log1p của biên độ không âm
    assert int(spec[0, 0].mean(axis=0).argmax()) == 24    # 700 Hz = bin 56, lệch start_bin 32


def test_audio_to_spectrogram_rejects_wrong_normalization():
    with pytest.raises(ValueError, match="chuẩn hóa"):
        audio_to_spectrogram(np.zeros(1024, dtype=np.float32), dict(META, normalization="cmvn"))


def test_resample_to_filters_out_of_band_energy():
    t = np.arange(8000) / 8000.0
    keep = np.sin(2 * np.pi * 700.0 * t).astype(np.float32)
    fold = np.sin(2 * np.pi * 2500.0 * t).astype(np.float32)   # trên Nyquist 1600 Hz của 3200 Hz
    assert len(resample_to(keep, 8000, 3200)) == 3200
    assert float(np.sqrt(np.mean(resample_to(keep, 8000, 3200) ** 2))) > 0.5
    assert float(np.sqrt(np.mean(resample_to(fold, 8000, 3200) ** 2))) < 0.05
    same = resample_to(keep, 8000, 8000)
    assert np.allclose(same, keep)


def test_greedy_ctc_emissions_collapses_repeats_and_blanks():
    c, q = META["chars"].index("C"), META["chars"].index("Q")
    lp = lattice([None, c, c, None, q, None, q])
    got = greedy_ctc_emissions(lp, META["chars"], BLANK)
    assert [ch for ch, _, _ in got] == ["C", "Q", "Q"]
    assert [f for _, f, _ in got] == [1, 4, 6]
    assert all(0.9 < p < 1.0 for _, _, p in got)
    assert emissions_to_text(got) == "CQQ"
    assert greedy_ctc_emissions(np.zeros((0, 42), dtype=np.float32), META["chars"], BLANK) == []


def test_mean_frame_confidence():
    assert mean_frame_confidence(lattice([None, 5, 6])) == pytest.approx(0.95, abs=1e-3)
    assert mean_frame_confidence(np.zeros((0, 42), dtype=np.float32)) == 0.0


def test_remapper_latin_to_cyrillic():
    remap = Remapper()
    assert remap("DE GM", "en") == "DE GM"
    assert remap("DE GM", "ru") == "ДЕ ГМ"
    assert remap("KUN KALA", "kk-cyrl-ru") == "КУН КАЛА"
    assert " " in remap.reachable_chars("ru", META["chars"])


def test_model_uses_injected_session_and_reports_frames():
    c, q = META["chars"].index("C"), META["chars"].index("Q")
    session = FakeSession(lattice([None, c, None, q]))
    model = DeepCwModel(meta=META, session=session)
    assert model.chars[:3] == [",", ".", "/"] and model.blank == 41
    assert model.sample_rate == 3200 and model.hop_length == 48
    assert model.frame_rate == pytest.approx(3200 / 48)
    out = model.decode_greedy(np.zeros(8000, dtype=np.float32), 8000)
    assert emissions_to_text(out.emissions) == "CQ"
    assert out.n_frames == 4 and out.confidence == pytest.approx(0.95, abs=1e-3)
    assert session.seen[0].shape[1] == 1 and session.seen[0].shape[3] == 65


def test_model_pads_clip_shorter_than_fft_length():
    session = FakeSession(lattice([None]))
    model = DeepCwModel(meta=META, session=session)
    model.log_probs(np.zeros(100, dtype=np.float32), 8000)      # không được ném ValueError
    assert session.seen[0].shape[2] >= 1


def test_model_reports_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_deepcw"):
        DeepCwModel(tmp_path / "model.onnx")
    (tmp_path / "model.onnx.json").write_text(json.dumps(META), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="fetch_deepcw"):
        DeepCwModel(tmp_path / "model.onnx").load()


def test_read_wav_mono(tmp_path):
    from morsedesk.api import Encoder
    from morsedesk.audio.io import save_audio

    p = tmp_path / "cq.wav"
    save_audio(p, Encoder("en").to_audio("CQ", wpm=25), 8000)
    rate, audio = read_wav_mono(p)
    assert rate == 8000 and audio.dtype == np.float32 and audio.ndim == 1
    assert float(np.max(np.abs(audio))) <= 1.0


def test_bench_pretrained_reuses_module_without_copy():
    from tools import bench_pretrained

    assert bench_pretrained.Remapper is deepcw.Remapper
    assert bench_pretrained.audio_to_spectrogram is deepcw.audio_to_spectrogram
    assert bench_pretrained.read_wav_mono is deepcw.read_wav_mono
    assert bench_pretrained.resample_to is deepcw.resample_to


def test_fetch_deepcw_copies_local_dir(tmp_path):
    from tools import fetch_deepcw

    src = tmp_path / "src"
    src.mkdir()
    (src / "model.onnx").write_bytes(b"onnx-bytes")
    (src / "model.onnx.json").write_text(json.dumps(META), encoding="utf-8")
    out = tmp_path / "out"
    assert fetch_deepcw.main(["--src", str(src), "--out", str(out), "--no-verify"]) == 0
    assert (out / "model.onnx").read_bytes() == b"onnx-bytes"
    assert json.loads((out / "model.onnx.json").read_text(encoding="utf-8"))["blank_index"] == 41


def test_fetch_deepcw_rejects_wrong_checksum(tmp_path, capsys):
    from tools import fetch_deepcw

    src = tmp_path / "src"
    src.mkdir()
    (src / "model.onnx").write_bytes(b"sai noi dung")
    (src / "model.onnx.json").write_text(json.dumps(META), encoding="utf-8")
    out = tmp_path / "out"
    assert fetch_deepcw.main(["--src", str(src), "--out", str(out)]) == 2
    assert "sha256" in capsys.readouterr().err
    assert not (out / "model.onnx").exists()


def test_check_models_knows_deepcw_engine(tmp_path, monkeypatch):
    from morsedesk.app import startup

    monkeypatch.setattr(startup, "DEEPCW_MODEL_PATH", tmp_path / "model.onnx")
    monkeypatch.setattr(startup, "DEEPCW_META_PATH", tmp_path / "model.onnx.json")
    missing = startup.check_models(None, tmp_path / "lm", engine="deepcw")
    assert [p.name for p in missing[:2]] == ["model.onnx", "model.onnx.json"]
    assert "fetch_deepcw" in startup.missing_models_message(missing)
