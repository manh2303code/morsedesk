# MorseDesk tuần 5, nhánh A — chất lượng giải mã Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đưa DeepCW thành engine sản phẩm cho profile `en`, dựng bộ test thật T2 với bảng số đối chứng, gán nhãn giả bản ghi thật, chạy thang thí nghiệm E6–E10 nhắm ngưỡng gate 2 %, và giao bảng số theo từng ô dù gate đạt hay không.

**Architecture:** Lõi tiền xử lý đã kiểm chứng của `tools/bench_pretrained.py` (23,70 % CER trên T1 v2) được nâng thành `morsedesk/model/deepcw.py`; tool đo import lại từ đó, không giữ bản sao. `DeepCwModel` **không** khớp `AcousticModel` protocol (đặc trưng phổ 65 bin ở 3200 Hz, 42 lớp chữ Latin, thay vì 11 chiều ở 8000 Hz, 65 lớp mẫu chấm gạch) nên nó đứng **cạnh** protocol: `Decoder` rẽ nhánh riêng ở `_decode_deepcw`, dùng lại `_group_words`/`estimate_wpm_from_emissions` để trả về đúng `DecodeResult` như hai engine cũ. Beam ký tự (`morsedesk/model/deepcw_beam.py`) chạy thẳng trên hậu nghiệm chữ Latin của DeepCW với LM `en` sẵn có, không đi qua tầng mẫu chấm gạch. Bộ T2 và gán nhãn giả dùng chung khuôn manifest JSONL của T1. Thang thí nghiệm E6–E10 chỉ đổi **một biến mỗi lần** so với E3 và chạy trong WSL (0,52 s/bước so với 1,1–1,3 s/bước trên Windows).

**Tech Stack:** Python 3.11 (uv), numpy < 2, scipy, soundfile, onnxruntime (extra `runtime`); torch CPU + onnx (extra `train`); ffmpeg 8.0.1 trong WSL Ubuntu-26.04 và 9.0.1 trên Windows; WSL Ubuntu-26.04 16 nhân với uv riêng `~/.venv-morsedesk` cho huấn luyện.

## Global Constraints

- Nhánh `week5`. Lệnh `uv run ...` từ `C:\Users\Admin\morsedesk`. Không chạy `uv sync` trừ khi thêm phụ thuộc mới, và nếu thêm thì nêu rõ lý do.
- Lõi `morsedesk/*` ngoài `morsedesk/app/` KHÔNG import PySide6/pyqtgraph; `morsedesk/app/` không import torch.
- Giấy phép không còn là ràng buộc (phần mềm nội bộ, offline): dùng được DeepCW (AGPL), multimon-ng, HamNoise.
- Ngưỡng gate giữ nguyên **2 %** trên vùng SNR ≥ 0 dB và 10–35 WPM, mọi kênh và kiểu gõ. Không tự hạ ngưỡng; nếu không đạt thì giao bảng số theo từng ô.
- `models/deepcw/` gitignored như `models/acoustic.onnx`; `testdata/private/` gitignored.
- Ruff sạch: `uv run ruff check morsedesk tests tools` (line length 100, rules E F I B UP, E501 ignored).
- Mọi commit kết thúc bằng hai trailer, mỗi dòng một `-m` riêng, đúng nguyên văn: `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` và `Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV`. Dùng `git add <đường dẫn>`, không `git add -A`. Khi chain lệnh dùng `${PIPESTATUS[0]}`, đừng kết luận pass từ `| tail`.
- Windows console: `PYTHONUTF8=1` khi in tiếng Việt/Cyrillic.
- Test phải chạy được trên máy không có PortAudio (xem fixture `fake_sounddevice` ở `tests/app/conftest.py`) và không cần mạng; test nào cần model thật hoặc mạng thì đánh dấu `@pytest.mark.gate` hoặc `skipif`.

## Phạm vi

Kế hoạch này phủ **nhánh A** của `docs/superpowers/specs/2026-09-22-morsedesk-week5-6-design.md` mục 3.1, 3.2, 3.3, 3.4 và điều kiện ra ở mục 7 (các mục 2, 3, 4, 5). Chốt kiểm đóng lại: **CP-01, CP-02, CP-03, CP-13** (`docs/superpowers/2026-09-21-rasoat-yeu-cau.md`). Nhánh B (giao diện) và nhánh C (Linux) nằm ở kế hoạch khác.

## Bản đồ tệp

| Tệp | Trách nhiệm |
|---|---|
| `morsedesk/model/deepcw.py` | **mới** — lõi DeepCW: đọc WAV, resample poly, phổ 65 bin, CTC greedy có khung, `Remapper`, `DeepCwModel` |
| `morsedesk/model/deepcw_beam.py` | **mới** — beam ký tự CTC trên hậu nghiệm DeepCW, chấm bằng `CharNGramLM` của profile `en` |
| `tools/fetch_deepcw.py` | **mới** — chép hoặc tải `model.onnx` + `model.onnx.json` về `models/deepcw/`, kiểm sha256 |
| `tools/bench_pretrained.py` | bỏ phần lõi trùng lặp, import từ `morsedesk.model.deepcw` |
| `morsedesk/app/startup.py` | `check_models` biết engine `deepcw` |
| `morsedesk/api.py` | `Decoder(engine="deepcw")`, `_decode_deepcw`, `feature_cfg` theo metadata model |
| `morsedesk/cli.py` | `--engine deepcw` cho `decode` và `bench`; `--t2-gate` cho `bench` |
| `tools/fetch_t2.py` | **mới** — tải/gom bản ghi thật về `testdata/private/t2/`, dựng manifest gộp |
| `tools/make_t2_manifest.py` | thêm trường `license`, hàm `merge_manifests` |
| `morsedesk/bench.py` | `source_gate` (T2 không có cột `snr`), `by_source` trong summary |
| `tools/pseudo_label.py` | **mới** — cắt đoạn, chạy DeepCW, lọc theo độ tin cậy, ánh xạ Latin → mẫu → 65 lớp |
| `morsedesk/data/channel.py` | `ChannelSampling`, `HARD_QSB_SAMPLING`, tham số thứ hai cho `sample_channel_params` |
| `morsedesk/data/noise.py` | **mới** — `NoiseBank`, `add_real_noise` (nhiễu thật thay AWGN) |
| `morsedesk/data/synth.py` | `SynthConfig.channel_sampling`, `SynthConfig.noise_dir` |
| `morsedesk/dsp/frontend.py` | `window_cfg(agc_tau_s)` |
| `morsedesk/model/chunker.py` | `run_chunked_audio(..., cfg=)` |
| `morsedesk/model/onnx_runner.py` | thuộc tính `agc_tau_s` đọc từ metadata |
| `tools/train.py` | `--qsb-hard`, `--agc-tau`, `--noise-dir`, `--real-manifest`, `--real-ratio`, `MixedDataset` |
| `tools/fetch_hamnoise.py` | **mới** — tải HamNoise về `testdata/private/noise/` (WAV 8 kHz mono) |
| `scripts/wsl_train.sh` | **mới** — launcher foreground cho WSL, `OMP_NUM_THREADS=8` bắt buộc |
| `docs/research/03-model-experiments.md` | một dòng bảng cho mỗi E6–E10 + mục chi tiết |
| `docs/research/04-pretrained-baselines.md` | số DeepCW làm engine, beam+LM, bảng năm công cụ trên T1/T2 |
| `docs/research/02-baseline-numbers.md` | số T2 (CP-02), `language_acc` (CP-03), bảng gate cuối tuần |

---

### Task 1: Lõi DeepCW thành module sản phẩm (spec §3.1)

**Loại: code (TDD).**

**Files:**
- Create: `morsedesk/model/deepcw.py`
- Create: `tools/fetch_deepcw.py`
- Modify: `morsedesk/app/startup.py`
- Modify: `tools/bench_pretrained.py`
- Test: `tests/unit/test_deepcw.py`

**Interfaces:**
- Consumes: `morsedesk.data.text.translit_via_patterns(text, src: Profile, dst: Profile) -> str`; `morsedesk.lm.profile.load_profile(id) -> Profile`; `scipy.signal.resample_poly`.
- Produces (mọi task sau dùng đúng các tên này):
  - `deepcw.DEEPCW_DIR`, `deepcw.DEEPCW_MODEL_PATH = models/deepcw/model.onnx`, `deepcw.DEEPCW_META_PATH = models/deepcw/model.onnx.json`, `deepcw.MODEL_SHA256: str`, `deepcw.MODEL_BYTES: int`.
  - `deepcw.read_wav_mono(path) -> tuple[int, np.ndarray]`
  - `deepcw.resample_to(audio, src_rate, dst_rate) -> np.ndarray`
  - `deepcw.frequency_bin_range(rate, fft_length, min_hz, max_hz) -> tuple[int, int]`
  - `deepcw.audio_to_spectrogram(audio, meta: dict) -> np.ndarray [1, 1, T, 65]`
  - `deepcw.greedy_ctc_emissions(log_probs, chars: list[str], blank: int) -> list[tuple[str, int, float]]` — (chữ, khung đầu ra, xác suất)
  - `deepcw.emissions_to_text(emissions) -> str`
  - `deepcw.mean_frame_confidence(log_probs) -> float`
  - `deepcw.Remapper()` với `__call__(text, profile_id) -> str` và `reachable_chars(profile_id, vocab) -> set[str]`
  - `deepcw.DeepCwOutput(emissions, n_frames: int, frame_rate: float, confidence: float)` (dataclass frozen)
  - `deepcw.DeepCwModel(model_path=DEEPCW_MODEL_PATH, meta_path=None, session=None, meta=None)` với thuộc tính `meta`, `chars: list[str]`, `blank: int`, `sample_rate: int`, `hop_length: int`, `frame_rate: float`, và phương thức `load() -> DeepCwModel`, `log_probs(x, sample_rate) -> np.ndarray [T, 42]`, `decode_greedy(x, sample_rate) -> DeepCwOutput`.
  - `tools.fetch_deepcw.sha256_file(path) -> str`, `tools.fetch_deepcw.main(argv) -> int`.
  - `startup.check_models(model_path, lm_dir, engine)` nhận thêm `engine == "deepcw"`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_deepcw.py`:

```python
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
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw.py -q
```

Expected: lỗi thu thập `ModuleNotFoundError: No module named 'morsedesk.model.deepcw'`, `1 error`.

- [ ] **Step 3: Viết `morsedesk/model/deepcw.py`**

```python
"""Adapter model pretrain DeepCW (AGPL-3.0; phần mềm nội bộ, offline, không phát hành lại).

Lõi này nâng nguyên văn từ `tools/bench_pretrained.py` — bản đã kiểm chứng 23,70 % CER trên T1 v2
(`docs/research/04-pretrained-baselines.md`). Tiền xử lý bám đúng `model.onnx.json`:

- resample về `sample_rate` (3200 Hz) bằng `scipy.signal.resample_poly`; **không** nội suy tuyến
  tính như ví dụ gốc: đo được 28,98 % so với 23,70 % (§1.2 của tài liệu trên);
- STFT `fft_length` = 256 / `hop_length` = 48, cửa sổ Hann tuần hoàn, pad phản xạ `fft_length // 2`;
- lấy biên độ các bin trong 400–1200 Hz (65 bin), chuẩn hóa `log1p`;
- **không lọc dải quanh tone**: lọc dải oracle làm CER xấu đi còn 64–73 % vì model chuẩn hóa
  `log1p` tuyệt đối và trông chờ nền nhiễu trải khắp 65 bin (§2.2).

Bảng chữ DeepCW chỉ có A–Z, 0–9, `,` `.` `/` `?` và dấu cách nên engine chỉ dùng cho profile `en`;
`Remapper` chỉ phục vụ việc **đo** trên clip Cyrillic của T1.
"""

from __future__ import annotations

import json
import math
import os
import wave
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly as _resample_poly

from morsedesk.data.text import translit_via_patterns
from morsedesk.lm.profile import load_profile

DEEPCW_DIR = Path(__file__).resolve().parents[2] / "models" / "deepcw"
DEEPCW_MODEL_PATH = DEEPCW_DIR / "model.onnx"
DEEPCW_META_PATH = DEEPCW_DIR / "model.onnx.json"
MODEL_SHA256 = "ef120799457bca042d4690944f0faf93268eb4654e7f50f28784ad63bdc1fe02"
MODEL_BYTES = 15_139_839
FETCH_HINT = "chạy: uv run python tools/fetch_deepcw.py"


def read_wav_mono(path: str | Path) -> tuple[int, np.ndarray]:
    """Đọc WAV PCM -> (sample_rate, mono float32 trong [-1, 1])."""
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    if width == 1:
        audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        audio = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"độ rộng mẫu PCM không hỗ trợ: {width} byte")
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return rate, audio.astype(np.float32, copy=False)


def resample_to(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample đa pha có lọc chống chồng phổ (scipy). 8000 -> 3200 là up 2 / down 5."""
    audio = np.asarray(audio, dtype=np.float32)
    if src_rate == dst_rate or len(audio) == 0:
        return audio
    g = gcd(int(src_rate), int(dst_rate))
    return _resample_poly(audio, int(dst_rate) // g, int(src_rate) // g).astype(np.float32, copy=False)


def frequency_bin_range(rate: int, fft_length: int, min_hz: float, max_hz: float) -> tuple[int, int]:
    bin_hz = rate / fft_length
    return int(math.ceil(min_hz / bin_hz)), int(math.floor(max_hz / bin_hz)) + 1


def audio_to_spectrogram(audio: np.ndarray, meta: dict) -> np.ndarray:
    """Phổ [1, 1, time, freq] float32 cho model. Vector hóa nhưng cùng công thức với ví dụ gốc."""
    fft_length = int(meta["fft_length"])
    hop = int(meta["hop_length"])
    rate = int(meta["sample_rate"])
    bins = int(meta["spectrogram_frequency_bins"])
    if meta.get("normalization") != "log1p":
        raise ValueError(f"chuẩn hóa không hỗ trợ: {meta.get('normalization')}")
    if len(audio) < fft_length:
        raise ValueError(f"clip quá ngắn so với fft_length={fft_length}")
    start_bin, stop_bin = frequency_bin_range(
        rate, fft_length, float(meta["spectrogram_min_freq_hz"]), float(meta["spectrogram_max_freq_hz"])
    )
    if stop_bin - start_bin != bins:
        raise ValueError(f"metadata cần {bins} bin nhưng dải tính được có {stop_bin - start_bin}")
    padded = np.pad(audio, (fft_length // 2, fft_length // 2), mode="reflect")
    window = np.hanning(fft_length + 1)[:-1].astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(padded, fft_length)[::hop] * window
    spec = np.abs(np.fft.rfft(frames, n=fft_length, axis=1)[:, start_bin:stop_bin]).astype(np.float32)
    spec = np.log1p(spec, dtype=np.float32)
    return spec[np.newaxis, np.newaxis, :, :]


def _as_2d(log_probs: np.ndarray) -> np.ndarray:
    lp = np.asarray(log_probs, dtype=np.float32)
    return lp[0] if lp.ndim == 3 else lp


def greedy_ctc_emissions(log_probs: np.ndarray, chars: list[str], blank: int) -> list[tuple[str, int, float]]:
    """(chữ, khung đầu ra phát ra chữ, xác suất tại khung đó) — như `ctc.greedy_decode_with_frames`."""
    lp = _as_2d(log_probs)
    if lp.shape[0] == 0:
        return []
    ids = lp.argmax(axis=-1)
    out: list[tuple[str, int, float]] = []
    prev = -1
    for t, raw in enumerate(ids.tolist()):
        i = int(raw)
        if i != prev and i != blank:
            out.append((chars[i], t, float(np.exp(lp[t, i]))))
        prev = i
    return out


def emissions_to_text(emissions: list[tuple[str, int, float]]) -> str:
    return "".join(ch for ch, _, _ in emissions)


def mean_frame_confidence(log_probs: np.ndarray) -> float:
    """Trung bình xác suất lớn nhất mỗi khung — ngưỡng tin cậy cho gán nhãn giả (spec §3.3)."""
    lp = _as_2d(log_probs)
    if lp.shape[0] == 0:
        return 0.0
    return float(np.mean(np.exp(lp.max(axis=-1))))


class Remapper:
    """Chữ Latin của DeepCW -> mẫu chấm gạch -> chữ của profile đích (ru, kk-cyrl-ru)."""

    def __init__(self) -> None:
        self._src = load_profile("en")
        self._dst: dict[str, object] = {}

    def __call__(self, text: str, profile_id: str) -> str:
        if profile_id == "en" or not text:
            return text
        if profile_id not in self._dst:
            self._dst[profile_id] = load_profile(profile_id)
        return translit_via_patterns(text, self._src, self._dst[profile_id])

    def reachable_chars(self, profile_id: str, vocab: list[str]) -> set[str]:
        """Tập ký tự mà DeepCW có thể sinh ra sau remap, để ước lượng sàn lỗi không tránh được."""
        got = {" "}
        for ch in vocab:
            if not ch.strip():
                continue
            got.add(self(ch, profile_id))
        return got


@dataclass(frozen=True)
class DeepCwOutput:
    emissions: list[tuple[str, int, float]]
    n_frames: int
    frame_rate: float
    confidence: float


class DeepCwModel:
    """Model DeepCW nạp từ `models/deepcw/`.

    `session`/`meta` cho phép test bơm phiên và metadata giả, nên bộ test mặc định không cần
    file 15 MB và không cần onnxruntime.
    """

    def __init__(self, model_path: str | Path = DEEPCW_MODEL_PATH, meta_path: str | Path | None = None,
                 session=None, meta: dict | None = None) -> None:
        self.model_path = Path(model_path)
        self.meta_path = Path(meta_path) if meta_path is not None else Path(str(self.model_path) + ".json")
        if meta is None:
            if not self.meta_path.is_file():
                raise FileNotFoundError(f"không tìm thấy metadata DeepCW: {self.meta_path}; {FETCH_HINT}")
            meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        if meta.get("normalization") != "log1p":
            raise ValueError(f"chuẩn hóa không hỗ trợ: {meta.get('normalization')}")
        self.meta = meta
        self.chars: list[str] = list(meta["chars"])
        self.blank = int(meta["blank_index"])
        self.sample_rate = int(meta["sample_rate"])
        self.hop_length = int(meta["hop_length"])
        self.fft_length = int(meta["fft_length"])
        self.frame_rate = self.sample_rate / self.hop_length
        self._session = session

    def load(self) -> DeepCwModel:
        if self._session is None:
            if not self.model_path.is_file():
                raise FileNotFoundError(f"không tìm thấy model DeepCW: {self.model_path}; {FETCH_HINT}")
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.intra_op_num_threads = max(1, (os.cpu_count() or 2) // 2)
            self._session = ort.InferenceSession(str(self.model_path), so,
                                                 providers=["CPUExecutionProvider"])
        return self

    def log_probs(self, x: np.ndarray, sample_rate: int) -> np.ndarray:
        """Audio mono float32 -> log-prob [T, n_classes]."""
        self.load()
        audio = resample_to(np.asarray(x, dtype=np.float32), int(sample_rate), self.sample_rate)
        if len(audio) < self.fft_length:        # clip cực ngắn: đệm 0 thay vì ném lỗi cho người dùng
            audio = np.pad(audio, (0, self.fft_length - len(audio)))
        spec = audio_to_spectrogram(audio, self.meta)
        out = self._session.run([self.meta["onnx_output_name"]], {self.meta["onnx_input_name"]: spec})
        return np.asarray(out[0], dtype=np.float32)[0]

    def decode_greedy(self, x: np.ndarray, sample_rate: int) -> DeepCwOutput:
        lp = self.log_probs(x, sample_rate)
        return DeepCwOutput(greedy_ctc_emissions(lp, self.chars, self.blank), int(lp.shape[0]),
                            self.frame_rate, mean_frame_confidence(lp))
```

- [ ] **Step 4: Viết `tools/fetch_deepcw.py`**

```python
"""Chép hoặc tải model DeepCW về `models/deepcw/` (gitignored như `models/acoustic.onnx`).

Ưu tiên `--src` (thư mục đã có sẵn `model.onnx` + `model.onnx.json`), sau đó tới biến môi trường
`DEEPCW_SRC`, cuối cùng mới tải từ GitHub ở đúng commit đã đo. Luôn kiểm sha256 trừ khi `--no-verify`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from morsedesk.model.deepcw import DEEPCW_DIR, MODEL_BYTES, MODEL_SHA256
from morsedesk.textio import force_utf8_streams

COMMIT = "8e264d243bbd4467bd19f3f28292219405b47e0e"
BASE_URL = f"https://raw.githubusercontent.com/e04/deepcw-engine/{COMMIT}"
FILES = ("model.onnx", "model.onnx.json")
CLONE_HINT = (
    f"nếu tải hỏng (Git LFS hoặc chặn mạng), clone thủ công rồi chạy lại với --src:\n"
    f"  git clone https://github.com/e04/deepcw-engine <thư mục> && cd <thư mục> && git checkout {COMMIT}"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_one(name: str, src_dir: Path | None, dst_dir: Path) -> Path:
    dst = dst_dir / name
    if src_dir is not None:
        shutil.copyfile(src_dir / name, dst)
    else:
        url = f"{BASE_URL}/{name}"
        print(f"tải {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
    return dst


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Tải model DeepCW về models/deepcw/")
    ap.add_argument("--src", type=Path, default=None,
                    help="thư mục có sẵn model.onnx và model.onnx.json (mặc định: biến DEEPCW_SRC)")
    ap.add_argument("--out", type=Path, default=DEEPCW_DIR)
    ap.add_argument("--no-verify", action="store_true", help="bỏ kiểm sha256 (chỉ dùng trong test)")
    a = ap.parse_args(argv)

    src = a.src if a.src is not None else (Path(os.environ["DEEPCW_SRC"]) if os.environ.get("DEEPCW_SRC") else None)
    a.out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in FILES:
        try:
            written.append(fetch_one(name, src, a.out))
        except OSError as e:
            print(f"lỗi: không lấy được {name}: {e}\n{CLONE_HINT}", file=sys.stderr)
            for p in written:
                p.unlink(missing_ok=True)
            return 2
    model = a.out / "model.onnx"
    size = model.stat().st_size
    digest = sha256_file(model)
    if not a.no_verify and (digest != MODEL_SHA256 or size != MODEL_BYTES):
        print(f"lỗi: sha256 {digest} ({size} byte) khác bản đã đo {MODEL_SHA256} ({MODEL_BYTES} byte)\n"
              f"{CLONE_HINT}", file=sys.stderr)
        for p in written:
            p.unlink(missing_ok=True)
        return 2
    print(f"{model} {size} byte sha256 {digest[:12]}… OK")
    print(f"{a.out / 'model.onnx.json'} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Sửa `morsedesk/app/startup.py` cho engine `deepcw`**

Thay phần đầu của `check_models` và thêm import:

```python
from morsedesk.api import DEFAULT_MODEL_PATH
from morsedesk.lm.profile import list_profiles, load_profile
from morsedesk.lm.store import default_lm_dir, lm_file_for
from morsedesk.model.deepcw import DEEPCW_META_PATH, DEEPCW_MODEL_PATH


def check_models(model_path: Path | None, lm_dir: Path | None, engine: str = "onnx") -> list[Path]:
    """Danh sách file thiếu: model của engine rồi các .bin LM theo thứ tự profile."""
    missing: list[Path] = []
    # is_file() chứ không phải exists(): một thư mục tên `acoustic.onnx` từng lọt qua kiểm
    # tra, cửa sổ mở ra rồi mới chết ở lần giải mã đầu.
    if engine == "onnx":
        onnx = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        for p in (onnx, onnx.with_suffix(".json")):
            if not p.is_file():
                missing.append(p)
    elif engine == "deepcw":
        base = Path(model_path) if model_path else DEEPCW_MODEL_PATH
        meta = Path(str(base) + ".json") if model_path else DEEPCW_META_PATH
        for p in (base, meta):
            if not p.is_file():
                missing.append(p)
    lm_root = Path(lm_dir) if lm_dir else default_lm_dir()
    for pid in list_profiles():
        p = lm_file_for(load_profile(pid), lm_root)
        if not p.is_file():
            missing.append(p)
    return missing
```

và thêm một dòng vào `missing_models_message`, ngay sau dòng `Export the acoustic model: ...`:

```python
        "Fetch the DeepCW model (engine deepcw): uv run python tools/fetch_deepcw.py",
```

- [ ] **Step 6: Bỏ phần trùng lặp trong `tools/bench_pretrained.py`**

Xóa khỏi file: `read_wav_mono`, `resample_poly`, `frequency_bin_range`, `audio_to_spectrogram`, `greedy_ctc_decode`, `class Remapper`, các import `math`/`wave`/`load_profile`/`translit_via_patterns` nay không dùng nữa. Thêm import và sửa hai chỗ gọi:

```python
from morsedesk.bench import aggregate, gate, load_rows, pivot_snr_wpm
from morsedesk.metrics import cer, wer
from morsedesk.model.deepcw import (
    DEEPCW_MODEL_PATH,
    Remapper,
    audio_to_spectrogram,
    emissions_to_text,
    greedy_ctc_emissions,
    read_wav_mono,
    resample_to,
)
from morsedesk.textio import force_utf8_streams
```

`resample_linear` và `bandpass` **ở lại trong tool**: chúng là đối chứng đo đạc (`--resampler linear`, `--bandpass`), không phải mã sản phẩm. Sửa `decode_one`:

```python
def decode_one(session, meta: dict, path: Path, resampler: str,
               band: tuple[float, float] | None = None) -> str:
    rate, audio = read_wav_mono(path)
    if band is not None:
        audio = bandpass(audio, rate, band[0], band[1])
    target = int(meta["sample_rate"])
    audio = resample_to(audio, rate, target) if resampler == "poly" else resample_linear(audio, rate, target)
    spec = audio_to_spectrogram(audio, meta)
    out = session.run([meta["onnx_output_name"]], {meta["onnx_input_name"]: spec})
    return emissions_to_text(greedy_ctc_emissions(out[0], list(meta["chars"]), int(meta["blank_index"])))
```

và đổi mặc định của hai tham số dòng lệnh để không phải gõ đường dẫn scratchpad nữa:

```python
    ap.add_argument("--model", type=Path, default=DEEPCW_MODEL_PATH, help="mặc định models/deepcw/model.onnx")
    ap.add_argument("--metadata", type=Path, default=None, help="mặc định <model>.json")
```

và ngay sau `args = ap.parse_args(argv)`:

```python
    if args.metadata is None:
        args.metadata = Path(str(args.model) + ".json")
```

- [ ] **Step 7: Chạy test để thấy nó xanh**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw.py -q
```

Expected: `15 passed`.

- [ ] **Step 8: Tải model thật và chạy lại mốc 23,70 % để chứng minh refactor không đổi kết quả**

```bash
cd /c/Users/Admin/morsedesk && DEEPCW_SRC='C:/Users/Admin/AppData/Local/Temp/claude/C--Users-Admin/ad13b2e6-84b0-4677-9fa2-30e87d93ef22/scratchpad/deepcw-engine' uv run python tools/fetch_deepcw.py
```

Expected: `...models\deepcw\model.onnx 15139839 byte sha256 ef120799457b… OK`.

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/bench_pretrained.py --manifest testdata/generated/t1/manifest.jsonl --out-dir runs/bench_deepcw --resampler poly 2>&1 | tail -6
```

Expected: dòng cuối có `CER=23.70%` (sai lệch chấp nhận được ≤ 0,05 điểm do thứ tự phép cộng; nếu lệch nhiều hơn thì refactor đã làm sai tiền xử lý — dừng và so từng hàm với `git show HEAD:tools/bench_pretrained.py`).

- [ ] **Step 9: Ruff và bộ test mặc định**

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` rồi `320 passed` (319 cũ + 15 mới − 14 test cũ không đổi; con số chính xác không quan trọng, điều kiện là **0 failed**).

- [ ] **Step 10: Commit**

```bash
cd /c/Users/Admin/morsedesk && git add morsedesk/model/deepcw.py tools/fetch_deepcw.py morsedesk/app/startup.py tools/bench_pretrained.py tests/unit/test_deepcw.py
git commit -m "feat(model): lõi DeepCW thành module sản phẩm, bench_pretrained import lại" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: `git log -1 --format=%B` in đủ hai trailer.

---

### Task 2: `Decoder(profile="en", engine="deepcw")` và CLI (spec §3.1)

**Loại: code (TDD).**

**Files:**
- Modify: `morsedesk/api.py`
- Modify: `morsedesk/cli.py`
- Test: `tests/unit/test_deepcw_engine.py`
- Test: `tests/regression/test_t1.py` (thêm một test `@pytest.mark.gate`)

**Interfaces:**
- Consumes: `deepcw.DeepCwModel`, `deepcw.DEEPCW_MODEL_PATH`, `deepcw.DeepCwOutput` (Task 1); `api._group_words(items, frame_rate, end_frame) -> list[Word]` với `items = (token, chữ hiển thị, khung, xác suất)`; `api._strip_spaces`; `api.estimate_wpm_from_emissions(emissions, frame_rate)`.
- Produces:
  - `Decoder(profile="en", engine="deepcw", model_path=None, acoustic_model=None, ...)`; profile khác `en` hoặc `auto` → `ValueError`.
  - `Decoder._decode_deepcw(x, tone_hz, snr_db, warnings) -> DecodeResult` với `engine == "deepcw"`.
  - `Decoder._deepcw_words(x) -> tuple[list[Word], list[tuple[str, int, float]], float]` (từ, emissions theo **mẫu chấm gạch**, `frame_rate` của DeepCW).
  - `api.DEEPCW_LM: bool` — công tắc dùng beam+LM cho engine `deepcw`, Task 3 đặt giá trị cuối.
  - `estimate_wpm_from_emissions(emissions, frame_rate: float)` (chú thích kiểu nới từ `int` sang `float`).
  - CLI: `morsedesk decode --engine deepcw`, `morsedesk bench --engine deepcw`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_deepcw_engine.py`:

```python
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
    dec = Decoder("en", engine="deepcw", acoustic_model=FakeDeepCw(), lm=False)
    r = dec.decode_array(np.zeros(8000, dtype=np.float32), 8000)
    assert r.text == "" and r.words == [] and r.warnings


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
```

Thêm vào cuối `tests/regression/test_t1.py`:

```python
@pytest.mark.gate
@pytest.mark.skipif(not Path("models/deepcw/model.onnx").exists(),
                    reason="chưa có models/deepcw/model.onnx (tools/fetch_deepcw.py)")
def test_deepcw_engine_on_t1_en_subset():
    """Engine deepcw phải đạt lại mốc đã đo (22,86 % trên các clip profile en của T1 v2)."""
    manifest = Path("testdata/generated/t1/manifest.jsonl")
    if not manifest.exists():
        pytest.skip("chạy: uv run python tools/make_t1.py")
    rows = [r for r in bench.load_rows(manifest) if r.get("profile") == "en"]
    results = bench.evaluate(rows, engine="deepcw", lm=False)
    mean = sum(r["cer"] for r in results) / len(results)
    assert mean <= 0.25, f"CER deepcw trên {len(results)} clip en = {mean:.4f}, mốc đo được 0.2286"
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw_engine.py -q
```

Expected: `8 failed` với `NotImplementedError: engine chưa hỗ trợ: deepcw` (và hai test CLI báo `argument --engine: invalid choice: 'deepcw'`).

- [ ] **Step 3: Sửa `morsedesk/api.py`**

Thêm import và hằng số ở đầu file (cạnh `DEFAULT_MODEL_PATH`):

```python
from morsedesk.model.vocab import SPACE, UNK, VOCAB

LOW_CONFIDENCE = 0.6
FALLBACK_CONFIDENCE = 0.5
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "acoustic.onnx"
DEEPCW_PROFILE = "en"
# Beam ký tự + LM `en` trên hậu nghiệm DeepCW. Task 3 đo trước/sau và chốt giá trị này.
DEEPCW_LM = True
```

Trong `Decoder.__init__`, thay khối chọn engine:

```python
        if engine == "onnx":
            if self._model is None:
                from morsedesk.model.onnx_runner import OnnxAcousticModel

                self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
                self._model = OnnxAcousticModel(self.model_path)
        elif engine == "deepcw":
            # Kiểm profile TRƯỚC khi nạp model: người dùng chọn sai profile phải thấy lỗi ngay,
            # không phải chờ tải 15 MB rồi mới báo.
            if self.auto or self.profile is None or self.profile.id != DEEPCW_PROFILE:
                raise ValueError(
                    "engine 'deepcw' chỉ hỗ trợ profile 'en' (bảng chữ DeepCW chỉ có A–Z, 0–9, "
                    "',' '.' '/' '?' và dấu cách); dùng --profile en, hoặc --engine onnx cho ru/kk"
                )
            if self._model is None:
                from morsedesk.model.deepcw import DEEPCW_MODEL_PATH, DeepCwModel

                self.model_path = Path(model_path) if model_path else DEEPCW_MODEL_PATH
                self._model = DeepCwModel(self.model_path).load()
        elif engine != "baseline":
            raise NotImplementedError(f"engine chưa hỗ trợ: {engine}")
```

và mở rộng điều kiện nạp LM (dòng cuối `__init__`):

```python
        if self.lm_enabled and (self.auto or engine in ("onnx", "deepcw")):
            for pid in self.candidates:
                self._lms[pid] = self._store.get(pid)   # thiếu file -> FileNotFoundError nêu đường dẫn
```

Trong `decode_array`, ngay sau dòng `if self.engine == "baseline": return self._decode_baseline(...)`:

```python
        if self.engine == "deepcw":
            return self._decode_deepcw(x, tone_hz, snr_db, warnings)
```

Thêm hai phương thức, đặt ngay trước `_decode_onnx`:

```python
    def _deepcw_words(self, x: np.ndarray) -> tuple[list[Word], list[tuple[str, int, float]], float]:
        """Từ và emissions từ hậu nghiệm DeepCW.

        DeepCW phát ra **chữ Latin**, còn phần còn lại của hệ thống đếm nhịp theo **mẫu chấm
        gạch**, nên mỗi chữ được đổi ngược về mẫu qua `profile.letter_to_pattern` để dùng lại
        `_group_words` và `estimate_wpm_from_emissions` y như engine onnx.
        """
        out = self._model.decode_greedy(x, SAMPLE_RATE)
        items = [(SPACE if ch == " " else self.profile.letter_to_pattern.get(ch, UNK), ch, f, p)
                 for ch, f, p in out.emissions]
        words = _group_words(items, out.frame_rate, out.n_frames)
        emissions = _strip_spaces([(tok, f, p) for tok, _, f, p in items])
        return words, emissions, out.frame_rate

    def _decode_deepcw(self, x: np.ndarray, tone_hz: float, snr_db: float | None,
                       warnings: list[str]) -> DecodeResult:
        words, emissions, frame_rate = self._deepcw_words(x)
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append("độ tin cậy thấp, kèm kết quả bộ giải mã DSP")
            if self.fallback:
                fallback_text = self.profile.render(self._baseline_tokens(x, tone_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, frame_rate), tone_hz, snr_db,
                            self.profile.id, {}, warnings, "deepcw", fallback_text)
```

Nới chú thích kiểu của `estimate_wpm_from_emissions` (DeepCW có `frame_rate` không nguyên = 66,67):

```python
def estimate_wpm_from_emissions(emissions: list[tuple[str, int, float]], frame_rate: float) -> float | None:
```

- [ ] **Step 4: Sửa `morsedesk/cli.py`**

```python
    dec.add_argument("--engine", default="baseline", choices=["baseline", "onnx", "deepcw"])
```

```python
    b.add_argument("--engine", default="baseline", choices=["baseline", "onnx", "deepcw"])
```

trong `cmd_decode`:

```python
        dec = Decoder(a.profile, engine=a.engine,
                      model_path=a.model if a.engine in ("onnx", "deepcw") else None,
                      fallback=not a.no_fallback, lm=not a.no_lm, beam=a.beam, lm_dir=a.lm_dir)
```

trong `cmd_bench`:

```python
    model = a.model if a.engine in ("onnx", "deepcw") else None
```

- [ ] **Step 5: Chạy test để thấy nó xanh**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw_engine.py -q
```

Expected: `8 passed`.

- [ ] **Step 6: Chạy test gate của engine mới (cần model thật đã tải ở Task 1)**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run pytest tests/regression/test_t1.py::test_deepcw_engine_on_t1_en_subset -m gate -q
```

Expected: `1 passed` (mất ~15 s cho 167 clip).

- [ ] **Step 7: Kiểm bằng tay một clip**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk decode "testdata/generated/t1/+20db_25wpm_machine_clean_0.wav" --profile en --engine deepcw --no-lm
```

Expected: in ra văn bản Latin (ví dụ `TNX FER CALL UR`), không có traceback.

- [ ] **Step 8: Ruff, bộ test mặc định, commit**

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` và `0 failed`.

```bash
cd /c/Users/Admin/morsedesk && git add morsedesk/api.py morsedesk/cli.py tests/unit/test_deepcw_engine.py tests/regression/test_t1.py
git commit -m "feat(api): engine deepcw cho profile en, mở qua CLI decode/bench" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ.

---

### Task 3: Beam ký tự + LM `en` trên hậu nghiệm DeepCW (spec §3.1, đoạn cuối)

**Loại: code (TDD) + đo trước/sau, giữ hay bỏ theo số đo.**

**Files:**
- Create: `morsedesk/model/deepcw_beam.py`
- Modify: `morsedesk/api.py` (`_decode_deepcw` dùng beam khi `lm_enabled and DEEPCW_LM`)
- Modify: `docs/research/04-pretrained-baselines.md` (mục mới "5. DeepCW làm engine")
- Test: `tests/unit/test_deepcw_beam.py`

**Interfaces:**
- Consumes: `deepcw.DeepCwModel.log_probs(x, sample_rate) -> np.ndarray [T, 42]`, `.chars`, `.blank`, `.frame_rate` (Task 1); `Decoder._lms["en"] -> CharNGramLM` với `.alphabet: LMAlphabet`, `.order: int`, `.score(context, symbol) -> float` (mã sẵn có); `api._group_words`, `api._strip_spaces`, `api.DEEPCW_LM`, `api.DEEPCW_PROFILE` (Task 2).
- Produces:
  - `deepcw_beam.CharBeamParams(beam=32, alpha=0.3, beta=0.5, topk_per_frame=6, min_prob=1e-3, unk_logp=log(1e-4))`
  - `deepcw_beam.CharHypothesis(text, chars, frames, probs, acoustic_logp, lm_logp, score, n_words)` với thuộc tính `emissions -> list[tuple[str, int, float]]`
  - `deepcw_beam.char_beam_search(log_probs, chars: list[str], blank: int, lm=None, alphabet=None, params=None) -> CharHypothesis`

- [x] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_deepcw_beam.py`:

```python
import numpy as np
import pytest

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import train_small
from morsedesk.lm.profile import load_profile
from morsedesk.model.deepcw import emissions_to_text, greedy_ctc_emissions
from morsedesk.model.deepcw_beam import CharBeamParams, char_beam_search

CHARS = [",", ".", "/", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "?",
         *[chr(c) for c in range(ord("A"), ord("Z") + 1)], " "]
BLANK = 41
N_CLASSES = 42


def lattice(rows: list[int | None], peak: float = 0.95) -> np.ndarray:
    rest = np.log((1.0 - peak) / (N_CLASSES - 1))
    lp = np.full((len(rows), N_CLASSES), rest, dtype=np.float32)
    for t, c in enumerate(rows):
        lp[t, BLANK if c is None else c] = np.log(peak)
    return lp


def ids(text: str) -> list[int | None]:
    """'_' = blank; mọi ký tự khác tra trong bảng chữ DeepCW."""
    return [None if ch == "_" else CHARS.index(ch) for ch in text]


@pytest.fixture(scope="module")
def en_lm():
    alphabet = LMAlphabet.for_profile(load_profile("en"))
    return train_small(["CQ DE K", "CQ CQ DE K", "TNX FER CALL UR 599 K"], alphabet, order=4)


def test_beam_without_lm_matches_greedy():
    lp = lattice(ids("_CCQ__ _DDE_ K_"))
    greedy = emissions_to_text(greedy_ctc_emissions(lp, CHARS, BLANK))
    hyp = char_beam_search(lp, CHARS, BLANK, params=CharBeamParams(beam=64))
    assert greedy == "CQ DE K"
    assert hyp.text == greedy
    assert hyp.lm_logp == 0.0 and hyp.n_words == 3


def test_beam_keeps_frames_and_probs_aligned():
    lp = lattice(ids("_CCQ__ _DDE_ K_"))
    hyp = char_beam_search(lp, CHARS, BLANK, params=CharBeamParams(beam=64))
    assert len(hyp.chars) == len(hyp.frames) == len(hyp.probs) == len(hyp.text)
    assert list(hyp.frames) == sorted(hyp.frames)
    assert all(0.0 < p <= 1.0 for p in hyp.probs)
    assert [ch for ch, _, _ in hyp.emissions] == list(hyp.chars)


def test_beam_uses_lm_to_break_acoustic_tie(en_lm):
    """Khung cuối hòa đúng bằng giữa 'C' và 'K'; greedy lấy chỉ số nhỏ hơn, LM phải chọn 'K'."""
    lp = lattice(ids("_CCQ__ _DDE_ _"))
    tie = np.full(N_CLASSES, np.log(0.1 / (N_CLASSES - 2)), dtype=np.float32)
    tie[CHARS.index("C")] = np.log(0.45)
    tie[CHARS.index("K")] = np.log(0.45)
    lp = np.vstack([lp, tie[None, :]]).astype(np.float32)
    assert emissions_to_text(greedy_ctc_emissions(lp, CHARS, BLANK)) == "CQ DE C"
    hyp = char_beam_search(lp, CHARS, BLANK, lm=en_lm, params=CharBeamParams(beam=64, alpha=0.5))
    assert hyp.text == "CQ DE K"
    assert hyp.lm_logp < 0.0


def test_beam_handles_empty_lattice(en_lm):
    hyp = char_beam_search(np.zeros((0, N_CLASSES), dtype=np.float32), CHARS, BLANK, lm=en_lm)
    assert hyp.text == "" and hyp.chars == () and hyp.n_words == 0


def test_beam_accepts_batched_lattice():
    lp = lattice(ids("_CCQ_"))[None]
    assert char_beam_search(lp, CHARS, BLANK, params=CharBeamParams(beam=8)).text == "CQ"
```

- [x] **Step 2: Chạy test để thấy nó đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw_beam.py -q
```

Expected: lỗi thu thập `ModuleNotFoundError: No module named 'morsedesk.model.deepcw_beam'`, `1 error`.

- [x] **Step 3: Viết `morsedesk/model/deepcw_beam.py`**

```python
"""Beam ký tự CTC trên hậu nghiệm DeepCW, chấm bằng LM ký tự của profile `en`.

Bảng chữ của DeepCW **là chữ Latin**, nên beam ký tự áp thẳng LM `en` của dự án, không phải đi
qua tầng mẫu chấm gạch như `morsedesk/lm/beam.py` (module đó phải rẽ nhánh một mẫu → nhiều chữ
cho Cyrillic; ở đây không có nhánh nào).

Thuật toán là prefix beam search CTC chuẩn: mỗi tiền tố giữ (p_blank, p_nonblank); mỗi khung chỉ
xét `topk_per_frame` lớp có xác suất ≥ `min_prob`; khung không có lớp nào đạt ngưỡng đi đường tắt
chỉ-blank nên chi phí tỉ lệ với số ký tự chứ không phải số khung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import CharNGramLM

NEG_INF = -math.inf


def _lse(a: float, b: float) -> float:
    """log(exp(a) + exp(b)). Bản sao có chủ ý của `lm/beam.py` để không phụ thuộc tên riêng tư."""
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    m = a if a > b else b
    return m + math.log(math.exp(a - m) + math.exp(b - m))


@dataclass(frozen=True)
class CharBeamParams:
    beam: int = 32
    alpha: float = 0.3                  # trọng số LM
    beta: float = 0.5                   # thưởng mỗi từ đã đóng
    topk_per_frame: int = 6
    min_prob: float = 1e-3
    unk_logp: float = math.log(1e-4)    # chữ không có trong bảng chữ LM


@dataclass
class CharHypothesis:
    text: str
    chars: tuple[str, ...]
    frames: tuple[int, ...]
    probs: tuple[float, ...]
    acoustic_logp: float
    lm_logp: float
    score: float
    n_words: int

    @property
    def emissions(self) -> list[tuple[str, int, float]]:
        return list(zip(self.chars, self.frames, self.probs, strict=True))


class _Prefix:
    __slots__ = ("chars", "frames", "probs", "p_b", "p_nb", "lm_ctx", "lm_logp", "n_words", "word")

    def __init__(self) -> None:
        self.chars: tuple[str, ...] = ()
        self.frames: tuple[int, ...] = ()
        self.probs: tuple[float, ...] = ()
        self.p_b = NEG_INF
        self.p_nb = NEG_INF
        self.lm_ctx: tuple[int, ...] = ()
        self.lm_logp = 0.0
        self.n_words = 0
        self.word = ""

    def total(self, alpha: float, beta: float) -> float:
        return _lse(self.p_b, self.p_nb) + alpha * self.lm_logp + beta * self.n_words

    def clone_reset(self) -> _Prefix:
        c = _Prefix()
        c.chars, c.frames, c.probs = self.chars, self.frames, self.probs
        c.lm_ctx, c.lm_logp, c.n_words, c.word = self.lm_ctx, self.lm_logp, self.n_words, self.word
        return c


def _extend(pre: _Prefix, ch: str, frame: int, prob: float, lm: CharNGramLM | None,
            alphabet: LMAlphabet | None, params: CharBeamParams) -> _Prefix:
    ext = _Prefix()
    ext.chars = pre.chars + (ch,)
    ext.frames = pre.frames + (frame,)
    ext.probs = pre.probs + (prob,)
    ext.lm_ctx, ext.lm_logp, ext.n_words, ext.word = pre.lm_ctx, pre.lm_logp, pre.n_words, pre.word
    if lm is not None and alphabet is not None:
        sym = alphabet.index.get(ch)
        if sym is None:
            ext.lm_logp += params.unk_logp          # chữ lạ: phạt, không đổi ngữ cảnh
        else:
            ext.lm_logp += float(lm.score(pre.lm_ctx, sym))
            ext.lm_ctx = (pre.lm_ctx + (sym,))[-(lm.order - 1):] if lm.order > 1 else ()
    if ch == " ":
        if pre.word:                                 # đóng một từ (rỗng: hai dấu cách liền nhau)
            ext.n_words += 1
        ext.word = ""
    else:
        ext.word = pre.word + ch
    return ext


def char_beam_search(log_probs: np.ndarray, chars: list[str], blank: int,
                     lm: CharNGramLM | None = None, alphabet: LMAlphabet | None = None,
                     params: CharBeamParams | None = None) -> CharHypothesis:
    p = params or CharBeamParams()
    if lm is not None and alphabet is None:
        alphabet = lm.alphabet
    lp = np.asarray(log_probs, dtype=np.float32)
    if lp.ndim == 3:
        lp = lp[0]
    root = _Prefix()
    root.p_b = 0.0
    if lm is not None and alphabet is not None:
        root.lm_ctx = (alphabet.bos_id,)
    beams: dict[tuple[str, ...], _Prefix] = {(): root}
    thresh = math.log(p.min_prob) if p.min_prob > 0.0 else NEG_INF
    for t in range(int(lp.shape[0])):
        row = lp[t]
        lp_blank = float(row[blank])
        k = min(p.topk_per_frame + 1, int(row.shape[0]))
        cand = np.argpartition(-row, k - 1)[:k]
        classes = [int(c) for c in cand
                   if int(c) != blank and int(c) < len(chars) and float(row[c]) >= thresh]
        if not classes:                              # đường tắt chỉ-blank
            for pre in beams.values():
                pre.p_b = _lse(pre.p_b, pre.p_nb) + lp_blank
                pre.p_nb = NEG_INF
            continue
        classes.sort(key=lambda c: -float(row[c]))
        classes = classes[: p.topk_per_frame]
        nxt: dict[tuple[str, ...], _Prefix] = {}
        for key, pre in beams.items():
            carried = _lse(pre.p_b, pre.p_nb) + lp_blank
            same = nxt.get(key)
            if same is None:
                same = pre.clone_reset()
                nxt[key] = same
            elif carried > _lse(same.p_b, same.p_nb):
                # tiền tố này đã được một tiền tố ngắn hơn mở rộng tới trong cùng khung:
                # giữ khung/xác suất của đóng góp nặng hơn
                same.frames, same.probs = pre.frames, pre.probs
            same.p_b = _lse(same.p_b, carried)
            last = pre.chars[-1] if pre.chars else None
            for c in classes:
                ch = chars[c]
                lp_c = float(row[c])
                if ch == last:
                    same.p_nb = _lse(same.p_nb, pre.p_nb + lp_c)
                    p_new = pre.p_b + lp_c
                else:
                    p_new = _lse(pre.p_b, pre.p_nb) + lp_c
                if p_new == NEG_INF:
                    continue
                new_key = pre.chars + (ch,)
                ext = nxt.get(new_key)
                if ext is None:
                    ext = _extend(pre, ch, t, float(math.exp(lp_c)), lm, alphabet, p)
                    nxt[new_key] = ext
                elif p_new > _lse(ext.p_b, ext.p_nb):
                    ext.frames = pre.frames + (t,)
                    ext.probs = pre.probs + (float(math.exp(lp_c)),)
                ext.p_nb = _lse(ext.p_nb, p_new)
        ranked = sorted(nxt.items(), key=lambda kv: kv[1].total(p.alpha, p.beta), reverse=True)
        beams = dict(ranked[: p.beam])
    best: CharHypothesis | None = None
    for pre in beams.values():
        acoustic = _lse(pre.p_b, pre.p_nb)
        lm_logp = pre.lm_logp
        n_words = pre.n_words + (1 if pre.word else 0)
        if lm is not None and alphabet is not None:
            lm_logp += float(lm.score(pre.lm_ctx, alphabet.eos_id))
        score = acoustic + p.alpha * lm_logp + p.beta * n_words
        if best is None or score > best.score:
            best = CharHypothesis("".join(pre.chars), pre.chars, pre.frames, pre.probs,
                                  acoustic, lm_logp, score, n_words)
    return best if best is not None else CharHypothesis("", (), (), (), NEG_INF, 0.0, NEG_INF, 0)
```

- [x] **Step 4: Chạy test để thấy nó xanh**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw_beam.py -q
```

Expected: `5 passed`.

- [x] **Step 5: Nối beam vào `Decoder._decode_deepcw`**

Trong `morsedesk/api.py`, thay `_deepcw_words` (viết ở Task 2) bằng bản có nhánh beam; phần còn lại của `_decode_deepcw` giữ nguyên:

```python
    def _deepcw_words(self, x: np.ndarray) -> tuple[list[Word], list[tuple[str, int, float]], float]:
        """Từ và emissions từ hậu nghiệm DeepCW.

        DeepCW phát ra **chữ Latin**, còn phần còn lại của hệ thống đếm nhịp theo **mẫu chấm
        gạch**, nên mỗi chữ được đổi ngược về mẫu qua `profile.letter_to_pattern` để dùng lại
        `_group_words` và `estimate_wpm_from_emissions` y như engine onnx.
        """
        frame_rate = float(self._model.frame_rate)
        if self.lm_enabled and DEEPCW_LM:
            from morsedesk.model.deepcw_beam import CharBeamParams, char_beam_search

            logp = self._model.log_probs(x, SAMPLE_RATE)
            hyp = char_beam_search(logp, self._model.chars, self._model.blank,
                                   self._lms[DEEPCW_PROFILE],
                                   params=CharBeamParams(beam=int(self.beam_params.beam)))
            raw = hyp.emissions
            n_frames = int(logp.shape[0])
        else:
            out = self._model.decode_greedy(x, SAMPLE_RATE)
            raw, n_frames = out.emissions, out.n_frames
        items = [(SPACE if ch == " " else self.profile.letter_to_pattern.get(ch, UNK), ch, f, p)
                 for ch, f, p in raw]
        words = _group_words(items, frame_rate, n_frames)
        emissions = _strip_spaces([(tok, f, p) for tok, _, f, p in items])
        return words, emissions, frame_rate
```

`Decoder("en", engine="deepcw")` mặc định `lm=True` nên nó cần `models/lm/en.bin` — đúng như engine `onnx`. Test của Task 2 dùng `lm=False` nên không đổi.

- [x] **Step 6: Chạy lại toàn bộ test liên quan**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_deepcw.py tests/unit/test_deepcw_beam.py tests/unit/test_deepcw_engine.py -q
```

Expected: `28 passed`.

- [x] **Step 7: Đo trước/sau trên tập con `en` của T1**

```bash
cd /c/Users/Admin/morsedesk && grep '"profile": "en"' testdata/generated/t1/manifest.jsonl > testdata/generated/t1/manifest_en.jsonl && wc -l testdata/generated/t1/manifest_en.jsonl
```

Expected: `167 testdata/generated/t1/manifest_en.jsonl`.

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/generated/t1/manifest_en.jsonl --engine deepcw --no-lm --out-dir runs/deepcw_t1 --gate --max-cer 0.02
```

Expected: `n=167 CER=22.86%` (± 0,05 điểm) và dòng gate `TRƯỢT`; ghi lại con số **greedy**.

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/generated/t1/manifest_en.jsonl --engine deepcw --out-dir runs/deepcw_t1 --gate --max-cer 0.02
```

Expected: một con số CER mới (beam + LM) và thời gian mỗi clip lớn hơn (greedy 0,019 s/clip). Ghi lại **cả hai** con số.

- [x] **Step 8: Quyết định giữ hay bỏ**

- Nếu `CER(beam+LM) < CER(greedy)`: giữ `DEEPCW_LM = True` trong `morsedesk/api.py`, không sửa gì.
- Nếu `CER(beam+LM) >= CER(greedy)`: sửa đúng một hằng số trong `morsedesk/api.py` thành

```python
# Beam ký tự + LM `en` trên hậu nghiệm DeepCW: ĐO ĐƯỢC XẤU HƠN GREEDY (xem
# docs/research/04-pretrained-baselines.md mục 5), giữ module làm đối chứng âm nhưng tắt mặc định.
DEEPCW_LM = False
```

Trong cả hai trường hợp, module `deepcw_beam.py` và test của nó **ở lại**.

- [x] **Step 9: Ghi số vào `docs/research/04-pretrained-baselines.md`**

Chèn trước mục "Giấy phép và phạm vi sử dụng" một mục mới; điền số đo thật từ Step 7 vào các ô `<...>`:

```markdown
## 5. DeepCW làm engine của MorseDesk (tuần 5)

Từ tuần 5 DeepCW không còn chỉ là thước đo: lõi tiền xử lý nằm ở `morsedesk/model/deepcw.py` và
`Decoder(profile="en", engine="deepcw")` dùng nó cho profile `en` (bảng chữ của nó chỉ có Latin).

| Cấu hình | n | CER T1 (chỉ profile `en`) | s/clip |
|---|---|---|---|
| greedy (mốc 2026-09-21) | 167 | <CER greedy> % | <s/clip> |
| beam ký tự + LM `en` (alpha 0,3, beta 0,5, beam 64) | 167 | <CER beam> % | <s/clip> |

Quyết định: <giữ / bỏ> beam+LM cho engine `deepcw` (`api.DEEPCW_LM = <True/False>`), vì <chênh
lệch đo được>. Lệnh tái lập ở `docs/superpowers/plans/2026-09-22-week5-quality.md` Task 3.
```

- [x] **Step 10: Ruff, test đầy đủ, commit**

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` và `0 failed`.

```bash
cd /c/Users/Admin/morsedesk && git add morsedesk/model/deepcw_beam.py morsedesk/api.py tests/unit/test_deepcw_beam.py docs/research/04-pretrained-baselines.md
git commit -m "feat(model): beam ky tu + LM en tren hau nghiem DeepCW, kem so do truoc/sau" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ. (Dòng subject có thể viết tiếng Việt có dấu; ví dụ trên bỏ dấu để tránh lỗi mã hóa console — nếu console đã `PYTHONUTF8=1` và `chcp 65001` thì dùng "beam ký tự + LM en trên hậu nghiệm DeepCW".)

---

### Task 4: Bộ T2 bản ghi thật, `bench` trên T2, bảng năm công cụ, `language_acc` (spec §3.2; CP-02, CP-13, CP-03)

**Loại: code (TDD) + đo.**

**Files:**
- Create: `tools/fetch_t2.py`
- Modify: `tools/make_t2_manifest.py`
- Modify: `morsedesk/bench.py`
- Modify: `morsedesk/cli.py`
- Modify: `docs/research/02-baseline-numbers.md`, `docs/research/04-pretrained-baselines.md`
- Test: `tests/unit/test_tools_t2.py` (mở rộng)

**Interfaces:**
- Consumes: `make_t2_manifest.build_manifest`, `write_jsonl`, `parse_wpm`, `clean_reference`, `AUDIO_EXT` (mã sẵn có); `bench.aggregate(results, key) -> dict[str, dict]`; `Decoder(engine="deepcw")` (Task 2); `bench_external.run_manifest(manifest, cmd_template, strip_prefix, to_wav, timeout_s) -> dict`; `TextSampler(profiles).sample(profile_id, rng, n_words)`.
- Produces:
  - `make_t2_manifest.build_manifest(audio_dir, source, profile_id, license_id="unknown") -> list[dict]`; mỗi hàng thêm khóa `"license"`.
  - `fetch_t2.discover_pairs(html: str, base_url: str) -> list[tuple[str, str | None]]`
  - `fetch_t2.write_meta(directory, source, profile_id, license_id) -> None` ghi `_meta.json`
  - `fetch_t2.build_all(root: Path, out: Path) -> list[dict]`
  - `fetch_t2.main(argv) -> int` với lệnh con `page`, `commons`, `local`, `synth`, `build`
  - `bench.T2_MAX_CER: dict[str, float]`, `bench.DEFAULT_T2_MAX_CER = 0.10`, `bench.source_gate(results, max_cer=None) -> dict[str, dict]` (mỗi mục `{"n","cer","wer","max_cer","ok"}`)
  - `bench.run(..., t2_gate: bool = False)`; summary thêm khóa `"by_source"` và `"source_gate"`
  - CLI: `morsedesk bench --t2-gate`
  - Dữ liệu: `testdata/private/t2/manifest.jsonl` với cột `path`, `text`, `raw_text`, `profile`, `wpm`, `source`, `license`, `synthetic`

- [x] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/unit/test_tools_t2.py` (và thêm `from pathlib import Path` ở đầu file):

```python
from morsedesk import bench
from tools import fetch_t2

INDEX_HTML = """
<html><body>
<a href="/files/morse/260303_5WPM.mp3">5 WPM</a>
<a href="/files/morse/260303_5WPM.txt">text</a>
<a href="/files/morse/260303_20WPM.mp3">20 WPM</a>
<a href="/files/morse/260303_20WPM.txt">text</a>
<a href="/files/morse/no_text_40WPM.mp3">40 WPM</a>
<a href="https://example.org/other.html">khác</a>
</body></html>
"""


def test_discover_pairs_matches_audio_with_same_stem_text():
    pairs = fetch_t2.discover_pairs(INDEX_HTML, "https://www.arrl.org/code-practice-files")
    assert len(pairs) == 3
    assert pairs[0] == ("https://www.arrl.org/files/morse/260303_5WPM.mp3",
                        "https://www.arrl.org/files/morse/260303_5WPM.txt")
    assert pairs[2][1] is None


def test_build_manifest_records_license(tmp_path):
    save_audio(tmp_path / "a_20WPM.wav", Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    (tmp_path / "a_20WPM.txt").write_text("CQ DE K", encoding="utf-8")
    rows = build_manifest(tmp_path, source="arrl", profile_id="en", license_id="ARRL nội bộ")
    assert rows[0]["license"] == "ARRL nội bộ"


def test_fetch_t2_local_then_build(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    save_audio(src / "qso_18WPM.wav", Encoder("en").to_audio("CQ DE K", wpm=18), 8000)
    (src / "qso_18WPM.txt").write_text("CQ DE K", encoding="utf-8")
    root = tmp_path / "t2"
    assert fetch_t2.main(["--root", str(root), "local", "--source", "sraa", "--profile", "en",
                          "--dir", str(src)]) == 0
    assert (root / "sraa" / "_meta.json").exists()
    assert fetch_t2.main(["--root", str(root), "build"]) == 0
    rows = bench.load_rows(root / "manifest.jsonl")
    assert len(rows) == 1
    assert rows[0]["source"] == "sraa" and rows[0]["wpm"] == 18.0 and rows[0]["text"] == "CQ DE K"
    assert rows[0]["license"] and Path(rows[0]["path"]).exists()
    assert rows[0]["synthetic"] is False


def test_fetch_t2_synth_falls_back_to_encoder(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_t2.shutil, "which", lambda name: None)   # không có ebook2cw
    root = tmp_path / "t2"
    assert fetch_t2.main(["--root", str(root), "synth", "--source", "ebook2cw", "--profile", "ru",
                          "--n", "2", "--seed", "3"]) == 0
    wavs = sorted((root / "ebook2cw").glob("*.wav"))
    assert len(wavs) == 2 and all(w.with_suffix(".txt").exists() for w in wavs)
    assert fetch_t2.main(["--root", str(root), "build"]) == 0
    rows = bench.load_rows(root / "manifest.jsonl")
    assert len(rows) == 2 and all(r["profile"] == "ru" and r["synthetic"] for r in rows)
    assert all(r["wpm"] is not None for r in rows)


def test_source_gate_uses_per_source_threshold():
    rows = [
        {"source": "arrl", "cer": 0.01, "wer": 0.02},
        {"source": "arrl", "cer": 0.01, "wer": 0.02},
        {"source": "sraa", "cer": 0.15, "wer": 0.30},
    ]
    g = bench.source_gate(rows)
    assert g["arrl"]["n"] == 2 and g["arrl"]["ok"] and g["arrl"]["max_cer"] == 0.02
    assert not g["sraa"]["ok"] and g["sraa"]["max_cer"] == 0.10
    assert bench.source_gate(rows, {"sraa": 0.2})["sraa"]["ok"]


def test_bench_run_reports_by_source_on_t2_shaped_manifest(tmp_path, capsys):
    src = tmp_path / "raw"
    src.mkdir()
    save_audio(src / "a_20WPM.wav", Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    (src / "a_20WPM.txt").write_text("CQ DE K", encoding="utf-8")
    manifest = tmp_path / "m.jsonl"
    write_jsonl(build_manifest(src, source="arrl", profile_id="en", license_id="x"), manifest)
    summary, ok = bench.run(manifest, "baseline", None, tmp_path / "r", None, False, 0.02,
                            t2_gate=True)
    assert summary["by_source"]["arrl"]["n"] == 1
    assert summary["source_gate"]["arrl"]["max_cer"] == 0.02
    assert "T2 arrl" in capsys.readouterr().out
    assert isinstance(ok, bool)
```

- [x] **Step 2: Chạy test để thấy nó đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_tools_t2.py -q
```

Expected: lỗi thu thập `ModuleNotFoundError: No module named 'tools.fetch_t2'`, `1 error`.

- [x] **Step 3: Sửa `tools/make_t2_manifest.py`**

```python
def build_manifest(audio_dir: Path, source: str, profile_id: str,
                   license_id: str = "unknown") -> list[dict]:
    rows = []
    for audio in sorted(p for p in Path(audio_dir).iterdir() if p.suffix.lower() in AUDIO_EXT):
        txt = audio.with_suffix(".txt")
        if not txt.exists():
            continue
        raw = txt.read_text(encoding="utf-8", errors="replace")
        rows.append({
            "path": str(audio.resolve()),
            "text": clean_reference(raw, profile_id),
            "raw_text": raw.strip(),
            "source": source,
            "license": license_id,
            "wpm": parse_wpm(audio.name),
            "profile": profile_id,
        })
    return rows
```

và hai dòng trong `main`:

```python
    ap.add_argument("--license", default="unknown", help="nhãn giấy phép/nguồn gốc ghi vào manifest")
```
```python
    rows = build_manifest(a.audio_dir, a.source, a.profile, a.license)
```

- [x] **Step 4: Viết `tools/fetch_t2.py`**

```python
"""Gom bản ghi Morse thật thành bộ T2 trong `testdata/private/t2/` (gitignored).

Mỗi nguồn là một thư mục con `<root>/<source>/` chứa cặp `<tên>.<đuôi audio>` + `<tên>.txt`
(đáp án) và một `_meta.json` ghi source/profile/license. `build` gộp mọi thư mục con thành
`manifest.jsonl` đúng khuôn T1 (`path`, `text`, `profile`, `wpm`, `source`, `license`).

    # 1. trang liệt kê file (ARRL W1AW code practice): quét link audio + text cùng tên
    uv run python tools/fetch_t2.py page --source arrl --profile en \
        --index-url https://www.arrl.org/code-practice-files

    # 2. Wikimedia Commons theo category (API ổn định, giấy phép tự do)
    uv run python tools/fetch_t2.py commons --source commons --profile en \
        --category "Morse code sound files" --limit 30

    # 3. file đã tải tay (SRAA, QSO thu tay): chép vào đúng chỗ; đáp án tự chép vào .txt cùng tên
    uv run python tools/fetch_t2.py local --source sraa --profile en --dir <thư mục>

    # 4. bù chỗ trống tiếng Nga/Kazakh: ebook2cw nếu có trên PATH, không thì Encoder của dự án
    uv run python tools/fetch_t2.py synth --source ebook2cw --profile ru --n 20

    uv run python tools/fetch_t2.py build
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio
from morsedesk.data.text import TextSampler
from morsedesk.lm.profile import load_profile
from morsedesk.textio import force_utf8_streams
from tools.make_t2_manifest import AUDIO_EXT, build_manifest, write_jsonl

DEFAULT_ROOT = Path("testdata/private/t2")
UA = "MorseDesk-T2/1.0 (offline research)"
LICENSES = {
    "arrl": "ARRL W1AW code practice — dùng nội bộ, không phân phối",
    "commons": "Wikimedia Commons — giấy phép tự do, xem <tên>.license.txt",
    "sraa": "tự thu / tự chép đáp án",
    "ebook2cw": "tổng hợp (không phải bản ghi thật)",
}
_HREF_RE = re.compile(r'href="([^"#?]+)"', re.IGNORECASE)


def _suffix(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).suffix.lower()


def _stem(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).stem


def discover_pairs(html: str, base_url: str) -> list[tuple[str, str | None]]:
    """(URL audio, URL text cùng stem hoặc None) từ một trang liệt kê file."""
    links = [urllib.parse.urljoin(base_url, h) for h in _HREF_RE.findall(html)]
    texts = {_stem(u): u for u in links if _suffix(u) == ".txt"}
    return [(u, texts.get(_stem(u))) for u in links if _suffix(u) in AUDIO_EXT]


def fetch_url(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)


def write_meta(directory: Path, source: str, profile_id: str, license_id: str,
               synthetic: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "_meta.json").write_text(
        json.dumps({"source": source, "profile": profile_id, "license": license_id,
                    "synthetic": synthetic}, ensure_ascii=False, indent=2), encoding="utf-8")


def build_all(root: Path, out: Path) -> list[dict]:
    rows: list[dict] = []
    for meta_path in sorted(Path(root).glob("*/_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        part = build_manifest(meta_path.parent, meta["source"], meta["profile"], meta["license"])
        for r in part:
            r["synthetic"] = bool(meta.get("synthetic", False))
        rows += part
    write_jsonl(rows, out)
    return rows


def cmd_page(a: argparse.Namespace) -> int:
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES.get(a.source, "unknown"))
    req = urllib.request.Request(a.index_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        html = r.read().decode("utf-8", errors="replace")
    pairs = discover_pairs(html, a.index_url)
    errors: list[dict] = []
    kept = 0
    for audio_url, text_url in pairs[: a.limit]:
        if text_url is None:
            errors.append({"url": audio_url, "reason": "không có file .txt cùng tên"})
            continue
        try:                                   # một URL hỏng không được làm hỏng cả lượt
            fetch_url(audio_url, directory / f"{_stem(audio_url)}{_suffix(audio_url)}")
            fetch_url(text_url, directory / f"{_stem(audio_url)}.txt")
            kept += 1
        except OSError as e:
            errors.append({"url": audio_url, "reason": f"{type(e).__name__}: {e}"})
    (directory / "_errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(f"{kept}/{len(pairs)} cặp -> {directory} ({len(errors)} lỗi, xem _errors.json)")
    return 0 if kept else 1


def cmd_commons(a: argparse.Namespace) -> int:
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES.get(a.source, "unknown"))
    query = {"action": "query", "format": "json", "generator": "categorymembers",
             "gcmtitle": f"Category:{a.category}", "gcmlimit": str(a.limit), "gcmtype": "file",
             "prop": "imageinfo", "iiprop": "url|extmetadata"}
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    kept = 0
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        src = info.get("url")
        if not src or _suffix(src) not in AUDIO_EXT:
            continue
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", _stem(src))[:60]
        try:
            fetch_url(src, directory / f"{stem}{_suffix(src)}")
        except OSError as e:
            print(f"bỏ qua {src}: {e}", file=sys.stderr)
            continue
        lic = ((info.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "?")
        (directory / f"{stem}.license.txt").write_text(f"{src}\n{lic}\n", encoding="utf-8")
        kept += 1
    print(f"{kept} file -> {directory}. CHÉP ĐÁP ÁN TAY vào <tên>.txt rồi chạy `build`.")
    return 0 if kept else 1


def cmd_local(a: argparse.Namespace) -> int:
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES.get(a.source, "unknown"))
    n = 0
    for p in sorted(Path(a.dir).iterdir()):
        if p.suffix.lower() in AUDIO_EXT or p.suffix.lower() == ".txt":
            shutil.copyfile(p, directory / p.name)
            n += p.suffix.lower() in AUDIO_EXT
    print(f"{n} file audio -> {directory}")
    return 0 if n else 1


def cmd_synth(a: argparse.Namespace) -> int:
    """ebook2cw nếu có trên PATH; không thì Encoder của dự án. Luôn đánh dấu synthetic=True."""
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES["ebook2cw"], synthetic=True)
    profile = load_profile(a.profile)
    # phải có cả "en": TextSampler._ham dựng radiogram bằng bảng Latin rồi mới chuyển tự sang
    # profile đích; thiếu "en" thì bản tin ru/kk bị lọc sạch chữ và chỉ còn số.
    sampler = TextSampler({a.profile: profile, "en": load_profile("en")})
    rng = np.random.default_rng(a.seed)
    encoder = Encoder(profile)
    tool = shutil.which("ebook2cw")
    wpms = [12.0, 18.0, 25.0, 35.0]
    for i in range(a.n):
        text = sampler.sample(a.profile, rng, n_words=(8, 16))
        wpm = wpms[i % len(wpms)]
        stem = f"{a.source}_{i:03d}_{int(wpm)}WPM"
        (directory / f"{stem}.txt").write_text(text, encoding="utf-8")
        made = False
        if tool:
            try:
                subprocess.run([tool, "-w", str(int(wpm)), "-f", "700",
                                "-o", str(directory / stem), str(directory / f"{stem}.txt")],
                               check=True, capture_output=True, timeout=120)
                for produced in sorted(directory.glob(f"{stem}*.mp3")):
                    produced.rename(directory / f"{stem}.mp3")
                    made = True
                    break
            except (subprocess.SubprocessError, OSError) as e:
                print(f"ebook2cw thất bại ({e}), dùng Encoder", file=sys.stderr)
        if not made:
            x = encoder.to_audio(text, wpm=wpm, tone_hz=700.0,
                                 snr_db=float(rng.uniform(6.0, 20.0)), seed=a.seed + i, strict=False)
            save_audio(directory / f"{stem}.wav", x, 8000)
    print(f"{a.n} clip -> {directory} (ebook2cw={'có' if tool else 'không, dùng Encoder'})")
    return 0


def cmd_build(a: argparse.Namespace) -> int:
    rows = build_all(Path(a.root), Path(a.out))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    print(f"{len(rows)} mục -> {a.out}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0 if rows else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Dựng bộ test T2 từ bản ghi thật")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--source", required=True)
        p.add_argument("--profile", default="en")
        p.add_argument("--license", default=None)

    page = sub.add_parser("page", help="quét một trang liệt kê file audio + text")
    common(page)
    page.add_argument("--index-url", required=True)
    page.add_argument("--limit", type=int, default=50)
    page.set_defaults(func=cmd_page)

    commons = sub.add_parser("commons", help="tải theo category của Wikimedia Commons")
    common(commons)
    commons.add_argument("--category", required=True)
    commons.add_argument("--limit", type=int, default=30)
    commons.set_defaults(func=cmd_commons)

    local = sub.add_parser("local", help="chép file đã tải tay vào đúng chỗ")
    common(local)
    local.add_argument("--dir", type=Path, required=True)
    local.set_defaults(func=cmd_local)

    synth = sub.add_parser("synth", help="sinh bù bằng ebook2cw hoặc Encoder")
    common(synth)
    synth.add_argument("--n", type=int, default=20)
    synth.add_argument("--seed", type=int, default=1)
    synth.set_defaults(func=cmd_synth)

    build = sub.add_parser("build", help="gộp mọi thư mục con thành manifest.jsonl")
    build.add_argument("--out", type=Path, default=None)
    build.set_defaults(func=cmd_build)
    return ap


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    a = build_parser().parse_args(argv)
    if a.cmd == "build" and a.out is None:
        a.out = Path(a.root) / "manifest.jsonl"
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 5: Sửa `morsedesk/bench.py`**

Thêm ngay sau `def language_accuracy(...)`:

```python
# Ngưỡng theo rà soát D4: ARRL < 2 %, QSO tay < 10 %. Manifest T2 không có cột `snr` nên
# `gate()` (lọc theo SNR/WPM) không dùng được cho T2; gate theo nguồn thay thế.
T2_MAX_CER = {"arrl": 0.02, "commons": 0.10, "sraa": 0.10, "qso": 0.10,
              "ebook2cw": 0.02, "ebook2cw_kk": 0.02}
DEFAULT_T2_MAX_CER = 0.10


def source_gate(results: list[dict], max_cer: dict[str, float] | None = None) -> dict[str, dict]:
    table = dict(T2_MAX_CER)
    table.update(max_cer or {})
    out: dict[str, dict] = {}
    for src, agg in aggregate(results, "source").items():
        limit = table.get(src, DEFAULT_T2_MAX_CER)
        out[src] = {"n": agg["n"], "cer": agg["cer"], "wer": agg["wer"],
                    "max_cer": limit, "ok": agg["cer"] <= limit}
    return out
```

Sửa chữ ký `run()` và ba chỗ trong thân hàm:

```python
def run(manifest: Path, engine: str, model_path: Path | None, out_dir: Path,
        limit: int | None, do_gate: bool, max_cer: float, profile_override: str | None = None,
        lm: bool = True, beam: int = 64, lm_dir: Path | None = None,
        t2_gate: bool = False) -> tuple[dict, bool]:
```

trong dict `summary`, thêm hai khóa ngay sau `"by_profile": aggregate(results, "profile"),`:

```python
        "by_source": aggregate(results, "source"),
        "source_gate": source_gate(results) if t2_gate else None,
```

và thay câu `return` cuối:

```python
    if t2_gate:
        for src, g in summary["source_gate"].items():
            print(f"T2 {src}: n={g['n']} CER={100 * g['cer']:.2f}% ngưỡng {100 * g['max_cer']:.2f}% "
                  f"{'ĐẠT' if g['ok'] else 'TRƯỢT'}")
        return summary, all(g["ok"] for g in summary["source_gate"].values())
    return summary, ok if do_gate else True
```

- [x] **Step 6: Sửa `morsedesk/cli.py`**

```python
    b.add_argument("--t2-gate", action="store_true",
                   help="gate theo nguồn cho bộ T2 (manifest T2 không có cột snr)")
```
```python
        _, ok = run(a.manifest, a.engine, model, a.out_dir, a.limit, a.gate, a.max_cer,
                    profile_override=a.profile_override, lm=not a.no_lm, beam=a.beam,
                    lm_dir=a.lm_dir, t2_gate=a.t2_gate)
```

- [x] **Step 7: Chạy test để thấy nó xanh**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_tools_t2.py -q
```

Expected: `13 passed`.

- [ ] **Step 8: Dựng bộ T2 thật**

Chạy bốn lệnh sau; lệnh nào lỗi mạng thì chép nguyên văn lỗi vào `docs/research/02-baseline-numbers.md` rồi đi tiếp (ba nguồn còn lại vẫn đủ đóng CP-02).

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_t2.py page --source arrl --profile en --index-url https://www.arrl.org/code-practice-files --limit 40
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_t2.py commons --source commons --profile en --category "Morse code sound files" --limit 30
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_t2.py synth --source ebook2cw --profile ru --n 20 --seed 11
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_t2.py synth --source ebook2cw_kk --profile kk-cyrl-ru --n 20 --seed 12
```

Nguồn `commons` phải **chép đáp án tay** vào `testdata/private/t2/commons/<tên>.txt` trước khi `build` (file không có `.txt` bị bỏ qua, đúng thiết kế). Với SRAA: tải 5 file tag CW về một thư mục tạm, tự chép đáp án ra `.txt` cùng tên, rồi

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_t2.py local --source sraa --profile en --dir <thư mục tạm>
```

Gộp:

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_t2.py build
```

Expected: ví dụ `84 mục -> testdata\private\t2\manifest.jsonl: arrl=39, commons=5, ebook2cw=20, ebook2cw_kk=20`. Điều kiện tối thiểu của CP-02: có ARRL nhiều tốc độ **và** ít nhất 20 clip không phải ARRL.

- [ ] **Step 9: Đo ba engine của mình trên T2 (CP-02)**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/private/t2/manifest.jsonl --engine baseline --out-dir runs/t2 --t2-gate
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/private/t2/manifest.jsonl --engine onnx --model models/acoustic.onnx --out-dir runs/t2 --t2-gate
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python -c "import json,pathlib; p=pathlib.Path('testdata/private/t2/manifest.jsonl'); rows=[json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]; en=[r for r in rows if r['profile']=='en']; pathlib.Path('testdata/private/t2/manifest_en.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+chr(10) for r in en),encoding='utf-8'); print(len(en))"
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/private/t2/manifest_en.jsonl --engine deepcw --out-dir runs/t2 --t2-gate
```

Expected: mỗi lệnh in bảng `by_source` và các dòng `T2 <nguồn>: ... ĐẠT/TRƯỢT`. Ghi lại cả ba bảng.

- [ ] **Step 10: Đo ba công cụ ngoài trên T1 và T2 (CP-13)**

`multimon-ng` (cài trong WSL, gọi từ Windows qua `wsl.exe`):

```bash
wsl.exe -d Ubuntu-26.04 -- bash -lc "sudo apt-get install -y multimon-ng && multimon-ng --help 2>&1 | head -3"
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/bench_external.py --manifest testdata/generated/t1/manifest_en.jsonl --name multimon-ng-t1 --strip-prefix "MORSE:" --cmd "wsl.exe -d Ubuntu-26.04 -- multimon-ng -a MORSE_CW -t wav {path}" --out-dir bench_results
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/bench_external.py --manifest testdata/private/t2/manifest_en.jsonl --name multimon-ng-t2 --strip-prefix "MORSE:" --cmd "wsl.exe -d Ubuntu-26.04 -- multimon-ng -a MORSE_CW -t wav {path}" --out-dir bench_results
```

`ggmorse` (build trong WSL, rồi chạy nhị phân giải mã tìm được ở `build/bin`):

```bash
wsl.exe -d Ubuntu-26.04 -- bash -lc "cd ~ && git clone --depth 1 https://github.com/ggerganov/ggmorse && cd ggmorse && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j8 && ls build/bin"
```

rồi hai lệnh `tools/bench_external.py` với `--name ggmorse-t1` / `ggmorse-t2` và
`--cmd "wsl.exe -d Ubuntu-26.04 -- /home/manh2303/ggmorse/build/bin/<tên nhị phân> {path}"`.

`pycw`:

```bash
cd /c/Users/Admin/morsedesk && uv run --with pycw python -c "import pycw; print([n for n in dir(pycw) if 'de' in n.lower()])"
```

`pycw` chỉ có phần **tạo mã**, không có bộ giải mã. Nếu lệnh trên xác nhận (danh sách rỗng), thay bằng `morse-audio-decoder` và ghi rõ việc thay thế:

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/bench_external.py --manifest testdata/generated/t1/manifest_en.jsonl --name morse-audio-decoder-t1 --cmd "uv run --with morse-audio-decoder python -m morse_audio_decoder {path}" --out-dir bench_results
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/bench_external.py --manifest testdata/private/t2/manifest_en.jsonl --name morse-audio-decoder-t2 --cmd "uv run --with morse-audio-decoder python -m morse_audio_decoder {path}" --out-dir bench_results
```

Công cụ nào không cài/không build được thì ghi **nguyên văn lỗi** vào bảng thay cho con số CER — CP-13 là "nên có", một dòng "không dùng được vì …" vẫn đóng được chốt kiểm, số bịa thì không.

- [ ] **Step 11: Đo `language_acc` trên T2 (CP-03)**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/private/t2/manifest.jsonl --engine onnx --model models/acoustic.onnx --profile-override auto --out-dir runs/t2 2>&1 | tail -3
```

Expected: một dòng `language_acc=<x>%`. Đây là con số CP-03 cần: T1 dùng radiogram ham chuyển tự trung lập ngôn ngữ nên 58,4 % không phản ánh năng lực thật, còn T2 có văn bản tự nhiên ba thứ tiếng.

- [ ] **Step 12: Ghi kết quả vào tài liệu**

Thêm vào `docs/research/02-baseline-numbers.md` mục `## Bộ T2 bản ghi thật (tuần 5)` gồm: thành phần T2 theo nguồn (số clip, dải WPM, giấy phép, cờ `synthetic`), bảng CER của `baseline` / `onnx` / `deepcw` theo nguồn kèm cột ĐẠT/TRƯỢT của `--t2-gate`, và mục con `### CP-03 language_acc` với con số ở Step 11, so với 58,4 % trên T1, cộng một câu khuyến nghị: đạt 95 % → CP-03 đóng; không đạt → nêu con số và đề nghị người dùng duyệt mức thấp hơn kèm lý do (radiogram trung lập ngôn ngữ).

Thêm vào `docs/research/04-pretrained-baselines.md` mục `## 6. Baseline công cụ ngoài trên T1 và T2 (CP-13)`:

```markdown
| Công cụ | Phiên bản / nguồn | CER T1 (en, n=167) | CER T2 (en, n=<n>) | Ghi chú |
|---|---|---|---|---|
| multimon-ng | <bản apt> | <x> % | <x> % | |
| ggmorse | <commit> | <x> % | <x> % | |
| pycw → morse-audio-decoder | <bản> | <x> % | <x> % | pycw không có bộ giải mã |
| DeepCW (engine) | commit 8e264d2 | <x> % | <x> % | |
| MorseDesk onnx (E3) | v0.2.0 | <x> % | <x> % | |
```

- [ ] **Step 13: Ruff, test đầy đủ, commit**

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` và `0 failed`.

```bash
cd /c/Users/Admin/morsedesk && git status --short testdata/ && git add tools/fetch_t2.py tools/make_t2_manifest.py morsedesk/bench.py morsedesk/cli.py tests/unit/test_tools_t2.py docs/research/02-baseline-numbers.md docs/research/04-pretrained-baselines.md
git commit -m "feat(bench): bo T2 ban ghi that, gate theo nguon, baseline nam cong cu" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: `git status --short testdata/` **không in gì** (đã gitignored); hai trailer hiện đủ.

---

### Task 5: `tools/pseudo_label.py` — gán nhãn giả bằng DeepCW (spec §3.3)

**Loại: code (TDD).**

**Files:**
- Create: `tools/pseudo_label.py`
- Test: `tests/unit/test_pseudo_label.py`

**Interfaces:**
- Consumes: `deepcw.DeepCwModel.decode_greedy(x, sr) -> DeepCwOutput(emissions, n_frames, frame_rate, confidence)`, `deepcw.emissions_to_text`, `deepcw.DEEPCW_MODEL_PATH` (Task 1); `morsedesk.audio.io.load_audio(path) -> (np.ndarray, int)`, `save_audio`, `SUPPORTED_EXT`; `Profile.letter_to_pattern: dict[str, str]`; `VOCAB.is_pattern`, `SPACE`.
- Produces:
  - `pseudo_label.PseudoConfig(seg_seconds=8.0, min_confidence=0.9, min_chars=3)`
  - `pseudo_label.text_to_pattern_tokens(text, profile) -> list[str] | None` (None nếu có chữ ngoài bảng 65 lớp)
  - `pseudo_label.label_segments(x, sample_rate, model, profile, cfg) -> list[dict]` mỗi mục `{"start_s","end_s","text","tokens","confidence"}`
  - `pseudo_label.load_model(path) -> DeepCwModel`
  - `pseudo_label.run(inputs, out_dir, model, profile, cfg, source) -> list[dict]` — ghi WAV vào `out_dir/clips/`, trả hàng manifest có khóa `path`, `text`, `tokens`, `profile`, `confidence`, `source`, `seconds`, `wpm` (=None), `origin`
  - `pseudo_label.main(argv) -> int`; manifest mặc định `testdata/private/pseudo/train.jsonl`
  - Khuôn hàng này là **đầu vào của E10** (Task 7): `tools/train.py --real-manifest` đọc `path` + `tokens`.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_pseudo_label.py`:

```python
from pathlib import Path

import numpy as np
import pytest

from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio
from morsedesk.lm.profile import load_profile
from morsedesk.model.deepcw import DeepCwOutput
from morsedesk.model.vocab import SPACE, VOCAB
from tools import pseudo_label
from tools.pseudo_label import PseudoConfig, label_segments, text_to_pattern_tokens

CHARS = [",", ".", "/", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "?",
         *[chr(c) for c in range(ord("A"), ord("Z") + 1)], " "]


class ScriptedModel:
    """Trả lần lượt (text, confidence) cho từng đoạn được gọi."""

    chars = CHARS
    blank = 41
    frame_rate = 3200 / 48

    def __init__(self, script: list[tuple[str, float]]) -> None:
        self.script = list(script)
        self.seen: list[int] = []

    def decode_greedy(self, x, sample_rate):
        self.seen.append(len(x))
        text, conf = self.script.pop(0)
        emissions = [(ch, 5 * i, conf) for i, ch in enumerate(text)]
        return DeepCwOutput(emissions, 5 * max(1, len(text)), self.frame_rate, conf)


def test_text_to_pattern_tokens_maps_latin_to_65_classes():
    en = load_profile("en")
    toks = text_to_pattern_tokens("CQ DE K", en)
    assert toks == ["-.-.", "--.-", SPACE, "-..", ".", SPACE, "-.-"]
    assert all(t == SPACE or VOCAB.is_pattern(t) for t in toks)
    assert [VOCAB.id(t) for t in toks]


def test_text_to_pattern_tokens_trims_and_rejects_unknown_chars():
    en = load_profile("en")
    assert text_to_pattern_tokens("  CQ  ", en) == ["-.-.", "--.-"]
    assert text_to_pattern_tokens("CQ Ж", en) is None
    assert text_to_pattern_tokens("   ", en) is None


def test_label_segments_filters_by_confidence_and_length():
    en = load_profile("en")
    model = ScriptedModel([("CQ DE K", 0.95), ("XY", 0.99), ("TEST TEST", 0.40)])
    x = np.zeros(8000 * 24, dtype=np.float32)          # 24 s -> 3 đoạn 8 s
    rows = label_segments(x, 8000, model, en,
                          PseudoConfig(seg_seconds=8.0, min_confidence=0.9, min_chars=3))
    assert len(rows) == 1                               # "XY" quá ngắn, "TEST TEST" tin cậy thấp
    assert rows[0]["text"] == "CQ DE K" and rows[0]["confidence"] == pytest.approx(0.95)
    assert rows[0]["start_s"] == 0.0 and rows[0]["end_s"] == 8.0
    assert rows[0]["tokens"][0] == "-.-."
    assert model.seen == [8000 * 8] * 3


def test_run_writes_clips_and_manifest_rows(tmp_path):
    src = tmp_path / "rec.wav"
    save_audio(src, Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    model = ScriptedModel([("CQ DE K", 0.95)])
    rows = pseudo_label.run([src], tmp_path / "out", model, load_profile("en"),
                            PseudoConfig(seg_seconds=30.0), source="t2-arrl")
    assert len(rows) == 1
    r = rows[0]
    assert Path(r["path"]).exists() and r["profile"] == "en" and r["source"] == "t2-arrl"
    assert r["wpm"] is None and r["seconds"] > 0 and r["tokens"]
    assert r["text"] == "CQ DE K" and Path(r["origin"]) == src.resolve()


def test_main_reports_when_nothing_passes_threshold(tmp_path, monkeypatch, capsys):
    src = tmp_path / "in"
    src.mkdir()
    save_audio(src / "a.wav", Encoder("en").to_audio("CQ", wpm=20), 8000)
    monkeypatch.setattr(pseudo_label, "load_model", lambda path: ScriptedModel([("CQ", 0.10)]))
    rc = pseudo_label.main(["--in", str(src), "--out-dir", str(tmp_path / "out"),
                            "--source", "x", "--min-confidence", "0.9"])
    assert rc == 1
    assert "0 đoạn" in capsys.readouterr().out
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_pseudo_label.py -q
```

Expected: lỗi thu thập `ModuleNotFoundError: No module named 'tools.pseudo_label'`, `1 error`.

- [ ] **Step 3: Viết `tools/pseudo_label.py`**

```python
"""Gán nhãn giả bằng DeepCW cho bản ghi thật KHÔNG có đáp án (spec §3.3).

Cắt mỗi bản ghi thành đoạn `--seg-seconds`, chạy DeepCW, giữ đoạn có độ tin cậy trung bình mỗi
khung ≥ `--min-confidence`, rồi ánh xạ **chữ Latin → mẫu chấm gạch → lớp trong bảng 65** bằng
chính `profile.letter_to_pattern`.

**Nhãn cứng, không chưng cất mềm.** Tần số khung hai bên khác nhau (DeepCW hop 48 @ 3200 Hz =
15 ms; MorseDesk hop 40 @ 8000 Hz = 5 ms) nên hậu nghiệm mềm phải nội suy theo thời gian và dễ
sai lệch; nhãn cứng đi đúng đường CTC sẵn có.

Cắt đoạn là bắt buộc chứ không phải tùy chọn: bản ghi ARRL dài vài phút, mà CTC cần chuỗi đầu vào
dài hơn chuỗi nhãn và `tools/train.py` chỉ quen clip 4–12 s.

    uv run python tools/pseudo_label.py --in testdata/private/t2/arrl --source t2-arrl
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from morsedesk.audio.io import SUPPORTED_EXT, load_audio, save_audio
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.deepcw import DEEPCW_MODEL_PATH, DeepCwModel, emissions_to_text
from morsedesk.model.vocab import SPACE, VOCAB
from morsedesk.textio import force_utf8_streams

DEFAULT_OUT = Path("testdata/private/pseudo")


@dataclass(frozen=True)
class PseudoConfig:
    seg_seconds: float = 8.0
    min_confidence: float = 0.9
    min_chars: int = 3


def text_to_pattern_tokens(text: str, profile: Profile) -> list[str] | None:
    """Chữ Latin của DeepCW -> token 65 lớp. None nếu có chữ nằm ngoài bảng."""
    out: list[str] = []
    for ch in text.strip().upper():
        if ch == " ":
            if out and out[-1] != SPACE:
                out.append(SPACE)
            continue
        pattern = profile.letter_to_pattern.get(ch)
        if pattern is None or not VOCAB.is_pattern(pattern):
            return None
        out.append(pattern)
    while out and out[-1] == SPACE:
        out.pop()
    return out or None


def label_segments(x: np.ndarray, sample_rate: int, model, profile: Profile,
                   cfg: PseudoConfig | None = None) -> list[dict]:
    cfg = cfg or PseudoConfig()
    n_seg = max(1, int(round(cfg.seg_seconds * sample_rate)))
    rows: list[dict] = []
    for start in range(0, max(1, len(x)), n_seg):
        seg = x[start:start + n_seg]
        if len(seg) < sample_rate:                  # bỏ mẩu cuối ngắn hơn 1 s
            continue
        out = model.decode_greedy(seg, sample_rate)
        text = emissions_to_text(out.emissions).strip()
        if out.confidence < cfg.min_confidence or len(text.replace(" ", "")) < cfg.min_chars:
            continue
        tokens = text_to_pattern_tokens(text, profile)
        if tokens is None:
            continue
        rows.append({"start_s": start / sample_rate, "end_s": (start + len(seg)) / sample_rate,
                     "text": text, "tokens": tokens, "confidence": float(out.confidence)})
    return rows


def load_model(path: Path) -> DeepCwModel:
    return DeepCwModel(path).load()


def iter_inputs(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in inputs:
        if p.is_dir():
            files += sorted(q for q in p.rglob("*") if q.suffix.lower() in SUPPORTED_EXT)
        elif p.suffix.lower() in SUPPORTED_EXT:
            files.append(p)
    return files


def run(inputs: list[Path], out_dir: Path, model, profile: Profile,
        cfg: PseudoConfig | None = None, source: str = "pseudo") -> list[dict]:
    cfg = cfg or PseudoConfig()
    clips = Path(out_dir) / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for path in iter_inputs([Path(p) for p in inputs]):
        x, sr = load_audio(path)
        for i, seg in enumerate(label_segments(x, sr, model, profile, cfg)):
            a, b = int(seg["start_s"] * sr), int(seg["end_s"] * sr)
            clip = clips / f"{path.stem}_{i:03d}.wav"
            save_audio(clip, x[a:b], sr)
            rows.append({"path": str(clip.resolve()), "text": seg["text"], "tokens": seg["tokens"],
                         "profile": profile.id, "confidence": seg["confidence"], "source": source,
                         "seconds": seg["end_s"] - seg["start_s"], "wpm": None,
                         "origin": str(path.resolve())})
    return rows


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Gán nhãn giả bản ghi thật bằng DeepCW")
    ap.add_argument("--in", dest="inputs", type=Path, nargs="+", required=True,
                    help="file hoặc thư mục bản ghi thật (không cần đáp án)")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--manifest", type=Path, default=None, help="mặc định <out-dir>/train.jsonl")
    ap.add_argument("--model", type=Path, default=DEEPCW_MODEL_PATH)
    ap.add_argument("--source", default="pseudo")
    ap.add_argument("--seg-seconds", type=float, default=8.0)
    ap.add_argument("--min-confidence", type=float, default=0.9)
    ap.add_argument("--min-chars", type=int, default=3)
    a = ap.parse_args(argv)

    cfg = PseudoConfig(a.seg_seconds, a.min_confidence, a.min_chars)
    rows = run(a.inputs, a.out_dir, load_model(a.model), load_profile("en"), cfg, a.source)
    manifest = a.manifest or (a.out_dir / "train.jsonl")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total_s = sum(r["seconds"] for r in rows)
    print(f"{len(rows)} đoạn giữ lại ({total_s / 60:.1f} phút, ngưỡng tin cậy {a.min_confidence}) "
          f"-> {manifest}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Chạy test để thấy nó xanh**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_pseudo_label.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Chạy thật trên bản ghi T2 (cần model DeepCW ở Task 1 và dữ liệu ở Task 4)**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/pseudo_label.py --in testdata/private/t2/arrl testdata/private/t2/commons testdata/private/t2/sraa --source t2-real --min-confidence 0.9
```

Expected: `<n> đoạn giữ lại (<x> phút, ngưỡng tin cậy 0.9) -> testdata\private\pseudo\train.jsonl`. Nếu `n == 0`: hạ ngưỡng xuống 0,8, chạy lại, và **ghi lại ngưỡng đã dùng** — E10 phải nêu đúng ngưỡng đó.

Kiểm chất lượng nhãn bằng mắt:

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python -c "import json,pathlib; rows=[json.loads(l) for l in pathlib.Path('testdata/private/pseudo/train.jsonl').read_text(encoding='utf-8').splitlines()[:5]]; [print(round(r['confidence'],3), round(r['seconds'],1), repr(r['text'][:60])) for r in rows]"
```

Expected: năm dòng văn bản đọc được (từ tiếng Anh, hô hiệu, số RST), không phải chuỗi ngẫu nhiên. Nếu là rác thì nâng ngưỡng lên 0,95 và chạy lại.

- [ ] **Step 6: Ruff, test đầy đủ, commit**

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` và `0 failed`.

```bash
cd /c/Users/Admin/morsedesk && git add tools/pseudo_label.py tests/unit/test_pseudo_label.py
git commit -m "feat(tools): gan nhan gia ban ghi that bang DeepCW, nhan cung 65 lop" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ.

---

### Task 6: Thí nghiệm E6 (tăng cường QSB) và E7 (AGC tau ngắn) (spec §3.4)

**Loại: thí nghiệm** — một run huấn luyện không có test thất bại. Hai cờ mới vẫn được viết theo TDD (Step 1–6); phần chạy thí nghiệm (Step 7 trở đi) đặc tả bằng lệnh, thời gian, tệp kết quả và tiêu chí nhận/loại.

**Files:**
- Create: `scripts/wsl_train.sh`
- Create: `tests/unit/test_channel_sampling.py`, `tests/unit/test_agc_tau.py`
- Modify: `morsedesk/data/channel.py`, `morsedesk/data/synth.py`, `morsedesk/dsp/frontend.py`, `morsedesk/model/chunker.py`, `morsedesk/model/onnx_runner.py`, `morsedesk/api.py`, `tools/train.py`
- Modify: `docs/research/03-model-experiments.md`

**Interfaces:**
- Consumes: `SynthGenerator(SynthConfig)`, `sample_channel_params(rng)`, `apply_channel`, `compute_features_windowed(x, f0_hint, sample_rate, window_frames, step_frames, cfg)`, `agc_log(env, frame_rate, tau_s, init_s)`, `export_onnx.export` ghi `meta["config"]`, `tools/eval_run.py::evaluate_run` + `markdown_row` (mã sẵn có).
- Produces:
  - `channel.ChannelSampling(qsb_prob=0.4, qsb_depth_db=(5.0, 30.0), qsb_period_s=(2.0, 20.0))` (frozen dataclass), `channel.DEFAULT_SAMPLING`, `channel.HARD_QSB_SAMPLING`
  - `channel.sample_channel_params(rng, sampling: ChannelSampling | None = None)` — mặc định giữ nguyên kết quả cũ từng bit
  - `synth.SynthConfig.channel_sampling: ChannelSampling | None = None`
  - `frontend.window_cfg(agc_tau_s: float = 1.0) -> FrontendConfig`; `WINDOW_CFG = window_cfg()`
  - `chunker.run_chunked_audio(model, x, f0_hint=None, window=WINDOW_FRAMES, step=STEP_FRAMES, cfg=None)`
  - `OnnxAcousticModel.agc_tau_s: float`
  - `Decoder.feature_cfg: FrontendConfig`
  - `train.sampling_for(qsb_hard: bool) -> ChannelSampling | None`; `train.example_features(ex, mode, agc_tau_s=1.0)`; cờ `--qsb-hard`, `--agc-tau`; `config` của checkpoint thêm khóa `qsb_hard: bool` và `agc_tau_s: float`
  - `scripts/wsl_train.sh <tên run> <cờ của tools/train.py...>`

- [ ] **Step 1: Viết test thất bại cho phân bố kênh**

Tạo `tests/unit/test_channel_sampling.py`:

```python
import numpy as np
import pytest

from morsedesk.data.channel import (
    DEFAULT_SAMPLING,
    HARD_QSB_SAMPLING,
    ChannelSampling,
    sample_channel_params,
)
from morsedesk.data.synth import SynthConfig, SynthGenerator


def test_default_sampling_is_bit_identical_to_old_behaviour():
    a = sample_channel_params(np.random.default_rng(7))
    b = sample_channel_params(np.random.default_rng(7), DEFAULT_SAMPLING)
    c = sample_channel_params(np.random.default_rng(7), ChannelSampling())
    assert a == b == c
    assert DEFAULT_SAMPLING == ChannelSampling(0.4, (5.0, 30.0), (2.0, 20.0))


def test_hard_qsb_narrows_period_and_raises_rate():
    rng = np.random.default_rng(0)
    rows = [sample_channel_params(rng, HARD_QSB_SAMPLING) for _ in range(400)]
    fading = [r for r in rows if r.qsb_depth_db > 0]
    assert 0.5 < len(fading) / len(rows) < 0.7        # ~60 % clip có QSB (mặc định 40 %)
    assert all(2.0 <= r.qsb_period_s <= 8.0 for r in rows)
    assert all(10.0 <= r.qsb_depth_db <= 24.0 for r in fading)


def test_synth_config_passes_sampling_through():
    gen = SynthGenerator(SynthConfig(channel_sampling=HARD_QSB_SAMPLING, mp3_enabled=False))
    for seed in range(5):
        ex = gen.generate(seed)
        assert 2.0 <= ex.channel.qsb_period_s <= 8.0


def test_train_sampling_for_flag():
    pytest.importorskip("torch")
    from tools import train

    assert train.sampling_for(True) is HARD_QSB_SAMPLING
    assert train.sampling_for(False) is None
```

- [ ] **Step 2: Viết test thất bại cho AGC tau**

Tạo `tests/unit/test_agc_tau.py`:

```python
import numpy as np
import pytest

from morsedesk.api import Decoder
from morsedesk.dsp.frontend import WINDOW_CFG, FrontendConfig, agc_log, window_cfg
from morsedesk.model.vocab import VOCAB


class WindowModel:
    """Model giả chế độ cửa sổ, khai báo agc_tau_s như metadata của model thật."""

    meta = {"vocab": VOCAB.tokens}
    time_stride = 2
    feature_mode = "window"

    def __init__(self, agc_tau_s: float) -> None:
        self.agc_tau_s = agc_tau_s

    def output_length(self, t: int) -> int:
        return (t - 1) // 2 + 1

    def __call__(self, feats: np.ndarray) -> np.ndarray:
        n = self.output_length(feats.shape[0])
        lp = np.full((n, len(VOCAB)), np.log(1e-6), dtype=np.float32)
        lp[:, VOCAB.blank_id] = 0.0
        return lp


def test_window_cfg_keeps_init_half_second():
    assert window_cfg() == WINDOW_CFG == FrontendConfig(agc_tau_s=1.0, agc_init_s=0.5)
    assert window_cfg(0.4) == FrontendConfig(agc_tau_s=0.4, agc_init_s=0.5)
    assert FrontendConfig().agc_init_s == 1.0


def test_short_tau_recovers_faster_after_level_change():
    env = np.concatenate([np.full(400, 1.0), np.full(400, 0.01), np.full(400, 1.0)])
    fast = agc_log(env, tau_s=0.3)
    slow = agc_log(env, tau_s=1.0)
    assert fast.shape == slow.shape == (1200,)
    assert abs(float(fast[-1])) < abs(float(slow[-1]))


def test_decoder_takes_agc_tau_from_model_metadata():
    dec = Decoder("en", engine="onnx", acoustic_model=WindowModel(0.4), lm=False)
    assert dec.feature_cfg.agc_tau_s == 0.4 and dec.feature_cfg.agc_init_s == 0.5
    base = Decoder("en", engine="baseline", lm=False)
    assert base.feature_cfg.agc_tau_s == 1.0


def test_onnx_runner_reads_agc_tau_from_config(tmp_path):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("torch")
    import json

    import torch

    from morsedesk.model.onnx_runner import OnnxAcousticModel
    from tools.export_onnx import export
    from tools.net_torch import CONFIG_DEFAULT, MorseNet

    ckpt = tmp_path / "best.pt"
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                "config": dict(CONFIG_DEFAULT, feature_mode="window", agc_tau_s=0.4)}, ckpt)
    onnx = tmp_path / "m.onnx"
    export(ckpt, onnx, version="test", n_golden=1)
    assert json.loads(onnx.with_suffix(".json").read_text(encoding="utf-8"))["config"]["agc_tau_s"] == 0.4
    assert OnnxAcousticModel(onnx).agc_tau_s == 0.4

    ckpt_old = tmp_path / "old.pt"          # checkpoint cũ không có khóa agc_tau_s -> mặc định 1.0
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                "config": dict(CONFIG_DEFAULT, feature_mode="window")}, ckpt_old)
    old = tmp_path / "old.onnx"
    export(ckpt_old, old, version="test", n_golden=1)
    assert OnnxAcousticModel(old).agc_tau_s == 1.0
```

- [ ] **Step 3: Chạy hai test để thấy chúng đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_channel_sampling.py tests/unit/test_agc_tau.py -q
```

Expected: `2 errors` khi thu thập — `ImportError: cannot import name 'ChannelSampling' from 'morsedesk.data.channel'` và `ImportError: cannot import name 'window_cfg' from 'morsedesk.dsp.frontend'`.

- [ ] **Step 4: Sửa `morsedesk/data/channel.py` và `morsedesk/data/synth.py`**

Trong `channel.py`, thêm ngay trước `sample_channel_params` và sửa hàm đó:

```python
@dataclass(frozen=True)
class ChannelSampling:
    """Tham số lấy mẫu kênh khi sinh dữ liệu huấn luyện. Mặc định = phân bố tuần 1–4."""

    qsb_prob: float = 0.4
    qsb_depth_db: tuple[float, float] = (5.0, 30.0)
    qsb_period_s: tuple[float, float] = (2.0, 20.0)


DEFAULT_SAMPLING = ChannelSampling()
# Ô qsb của T1 là depth đúng 20 dB, chu kỳ đúng 4 s (tools/make_t1.py). Phân bố mặc định hiếm khi
# rơi vào vùng đó (chu kỳ rải đều 2–20 s), nên E6 kéo phân bố về đúng độ khó của T1 và tăng tỉ lệ
# lấy mẫu QSB từ 40 % lên 60 %.
HARD_QSB_SAMPLING = ChannelSampling(qsb_prob=0.6, qsb_depth_db=(10.0, 24.0), qsb_period_s=(2.0, 8.0))


def sample_channel_params(rng: np.random.Generator,
                          sampling: ChannelSampling | None = None) -> ChannelParams:
    s = sampling or DEFAULT_SAMPLING
    qsb = rng.random() < s.qsb_prob
    qrm = rng.random() < 0.25
    return ChannelParams(
        tone_hz=float(rng.uniform(400.0, 1200.0)),
        tone_drift_hz_per_s=float(rng.uniform(-2.0, 2.0)),
        snr_db=float(rng.uniform(-6.0, 25.0)),
        qsb_depth_db=float(rng.uniform(*s.qsb_depth_db)) if qsb else 0.0,
        qsb_period_s=float(rng.uniform(*s.qsb_period_s)),
        qrm_offset_hz=float(rng.choice([-1.0, 1.0]) * rng.uniform(150.0, 600.0)) if qrm else 0.0,
        qrm_level_db=float(rng.uniform(3.0, 20.0)) if qrm else 0.0,
        qrm_kind=("morse" if rng.random() < 0.7 else "carrier") if qrm else "none",
        qrn_rate_per_s=float(rng.uniform(5.0, 50.0)) if rng.random() < 0.2 else 0.0,
        bandpass=True,
        gain=float(rng.uniform(0.1, 1.0)),
        clip=bool(rng.random() < 0.05),
        dc_offset=float(rng.uniform(-0.1, 0.1)) if rng.random() < 0.2 else 0.0,
        mp3_kbps=int(rng.choice([48, 64, 96, 128])) if rng.random() < 0.3 else None,
    )
```

Thứ tự các lần rút số ngẫu nhiên **không đổi**, nên với `sampling=None` kết quả trùng từng bit với bản cũ.

Trong `synth.py`: thêm import `ChannelSampling`, thêm trường vào `SynthConfig` và truyền xuống:

```python
from morsedesk.data.channel import (
    ChannelParams,
    ChannelSampling,
    apply_channel,
    ffmpeg_available,
    sample_channel_params,
)
```
```python
@dataclass
class SynthConfig:
    profile_ids: tuple[str, ...] = ("en", "ru", "kk-cyrl-ru")
    min_seconds: float = 4.0
    max_seconds: float = 12.0
    pad_min_s: float = 0.2
    pad_max_s: float = 0.8
    corpus: dict[str, Path] | None = None
    mp3_enabled: bool = True
    channel_sampling: ChannelSampling | None = None
```
```python
        channel = channel or sample_channel_params(rng, self.cfg.channel_sampling)
```

- [ ] **Step 5: Sửa `frontend.py`, `chunker.py`, `onnx_runner.py`, `api.py` cho AGC tau**

`morsedesk/dsp/frontend.py`, thay dòng `WINDOW_CFG = FrontendConfig(agc_init_s=0.5)`:

```python
def window_cfg(agc_tau_s: float = 1.0) -> FrontendConfig:
    """Cấu hình đặc trưng cho chế độ cửa sổ; `agc_tau_s` đến từ metadata của model đang dùng."""
    return FrontendConfig(agc_tau_s=agc_tau_s, agc_init_s=0.5)


WINDOW_CFG = window_cfg()
```

`morsedesk/model/chunker.py`:

```python
def run_chunked_audio(model: AcousticModel, x: np.ndarray, f0_hint: float | None = None,
                      window: int = WINDOW_FRAMES, step: int = STEP_FRAMES,
                      cfg: FrontendConfig | None = None) -> tuple[np.ndarray, int]:
    """Chế độ 'window': đặc trưng và tone tính riêng từng cửa sổ. Trả (log-prob gộp, số khung đầu vào)."""
    n_frames = len(x) // HOP
    windows = compute_features_windowed(x, f0_hint, window_frames=window, step_frames=step, cfg=cfg)
    return run_chunked_windows(model, windows, n_frames), n_frames
```

và đổi import đầu file thành `from morsedesk.dsp.frontend import FrontendConfig, Window, compute_features_windowed`.

`morsedesk/model/onnx_runner.py`, thêm sau dòng `self.feature_mode = ...`:

```python
        self.agc_tau_s = float((self.meta.get("config") or {}).get("agc_tau_s", 1.0))
```

`morsedesk/api.py`: thêm `window_cfg` vào import từ `morsedesk.dsp.frontend`, rồi thêm một dòng ở cuối `__init__` (sau khi `self._model` đã được đặt) và sửa hai chỗ dùng:

```python
        self.feature_cfg = window_cfg(float(getattr(self._model, "agc_tau_s", 1.0)))
```
```python
        if self._windowed():
            windows = compute_features_windowed(x, tone_hz, cfg=self.feature_cfg)
```
```python
            if windows is None:
                return run_chunked_audio(self._model, x, f0_hint=f0_hz, cfg=self.feature_cfg)
```

- [ ] **Step 6: Sửa `tools/train.py` (hai cờ mới) rồi chạy test**

Thêm import và hàm nhỏ:

```python
from morsedesk.data.channel import HARD_QSB_SAMPLING, ChannelSampling
from morsedesk.dsp.frontend import FrontendConfig, compute_features, compute_features_windowed, stitch_windows, window_cfg


def sampling_for(qsb_hard: bool) -> ChannelSampling | None:
    """None = phân bố mặc định tuần 1–4 (giữ nguyên hành vi cũ khi không truyền cờ)."""
    return HARD_QSB_SAMPLING if qsb_hard else None
```

`example_features` nhận thêm tau:

```python
def example_features(ex: Example, mode: str = DEFAULT_FEATURE_MODE, agc_tau_s: float = 1.0) -> np.ndarray:
    """Đặc trưng như lúc chạy thật. 'window': tone và chuẩn hóa theo cửa sổ, ghép theo khung, tone
    thật làm gợi ý khi cửa sổ không dò được; 'clip': tone toàn cục."""
    if mode == "window":
        n_frames = len(ex.audio) // HOP
        return stitch_windows(
            compute_features_windowed(ex.audio, f0_hint=ex.f0_hz, cfg=window_cfg(agc_tau_s)), n_frames)
    if mode != "clip":
        raise ValueError(f"feature_mode lạ: {mode}")
    est = estimate_tone(ex.audio)
    f0 = est.f0_hz if est.has_signal and est.f0_hz is not None else ex.f0_hz
    return compute_features(ex.audio, f0, cfg=FrontendConfig(agc_tau_s=agc_tau_s))
```

`SynthDataset` nhận thêm tau:

```python
class SynthDataset(IterableDataset):
    def __init__(self, gen: SynthGenerator, seed_start: int, n_items: int,
                 feature_mode: str = DEFAULT_FEATURE_MODE, agc_tau_s: float = 1.0) -> None:
        self.gen, self.seed_start, self.n_items = gen, seed_start, n_items
        self.feature_mode, self.agc_tau_s = feature_mode, agc_tau_s

    def __iter__(self):
        info = get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        for k in range(wid, self.n_items, nw):
            ex = self.gen.generate(self.seed_start + k)
            yield (torch.from_numpy(example_features(ex, self.feature_mode, self.agc_tau_s)),
                   torch.tensor(ex.labels, dtype=torch.long), ex.tokens)
```

Trong `main`, thêm hai cờ và bốn chỗ dùng:

```python
    ap.add_argument("--qsb-hard", action="store_true",
                    help="lấy mẫu QSB đúng độ khó ô qsb của T1 (E6): 60 %% clip, sâu 10–24 dB, chu kỳ 2–8 s")
    ap.add_argument("--agc-tau", type=float, default=1.0,
                    help="hằng số thời gian AGC (giây) dùng cả khi huấn luyện lẫn suy luận (E7)")
```
```python
    config = dict(CONFIG_DEFAULT, hidden=a.hidden, feature_mode=a.feature_mode,
                  qsb_hard=bool(a.qsb_hard), agc_tau_s=float(a.agc_tau))
```
```python
    gen = SynthGenerator(SynthConfig(mp3_enabled=not a.no_mp3, channel_sampling=sampling_for(a.qsb_hard)))
    val_items = []
    for i in range(a.val_clips):
        ex = gen.generate(VAL_SEED_BASE + i)
        val_items.append((torch.from_numpy(example_features(ex, a.feature_mode, a.agc_tau)), ex.tokens))

    ds = SynthDataset(gen, seed_start=a.seed * 1_000_000 + start_step * a.batch,
                      n_items=(a.steps - start_step) * a.batch, feature_mode=a.feature_mode,
                      agc_tau_s=a.agc_tau)
```

Chạy:

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_channel_sampling.py tests/unit/test_agc_tau.py -q
```

Expected: `8 passed`.

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` và `0 failed` (test cũ `tests/unit/test_data_synth.py`, `test_windowed.py`, `test_train_smoke.py` phải vẫn xanh — đó là bằng chứng mặc định không đổi).

- [ ] **Step 7: Viết `scripts/wsl_train.sh` và commit phần code**

```bash
#!/usr/bin/env bash
# Chạy một run huấn luyện trong WSL ở foreground. Gọi từ PowerShell:
#   Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash',
#     '/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','<tên run>','<cờ>...' -WindowStyle Hidden
#
# Vì sao foreground: `nohup` trong WSL bị giết cùng distro khi wsl.exe thoát (đã gặp ở E5);
# Start-Process giữ wsl.exe sống nên tiến trình huấn luyện sống theo.
# Vì sao OMP_NUM_THREADS=8: torch dùng đủ 16 hyperthread trên WSL2 gây thrash — micro-benchmark
# cho 27,6 s/bước với 16 thread so với 0,26 s/bước với 8 thread (E5). BẮT BUỘC, đừng bỏ.
set -euo pipefail
NAME="$1"; shift
cd /mnt/c/Users/Admin/morsedesk
export UV_PROJECT_ENVIRONMENT="$HOME/.venv-morsedesk"
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export PYTHONUTF8=1
mkdir -p "runs/$NAME"
exec "$HOME/.local/bin/uv" run python -m tools.train --name "$NAME" "$@" \
    >"runs/$NAME/train.log" 2>"runs/$NAME/train.err"
```

```bash
cd /c/Users/Admin/morsedesk && git add morsedesk/data/channel.py morsedesk/data/synth.py morsedesk/dsp/frontend.py morsedesk/model/chunker.py morsedesk/model/onnx_runner.py morsedesk/api.py tools/train.py scripts/wsl_train.sh tests/unit/test_channel_sampling.py tests/unit/test_agc_tau.py
git commit -m "feat(train): co --qsb-hard va --agc-tau, launcher WSL foreground" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ.

- [ ] **Step 8: Chạy E6 — tăng cường QSB đúng độ khó T1**

| Mục | Giá trị |
|---|---|
| Đổi so với run trước | **đúng một biến**: `--qsb-hard` thêm vào cấu hình E3 (cùng `--seed 13`, cùng `--no-mp3`, cùng cosine + warmup 500, cùng hidden 128) |
| Giả thuyết | Ô QSB là ~1/5 clip nhưng ~1/2 tổng lỗi; DeepCW hơn E3 15 điểm ở ô đó mà chưa từng thấy QSB lúc huấn luyện |
| Thời gian ước tính | ~4,5 h (0,52 s/bước × 30 000, đo ở E4/E5 trong WSL) |
| Tệp kết quả | `runs/E6/train.log`, `runs/E6/train.err`, `runs/E6/history.json`, `runs/E6/best.pt`, `runs/E6/args.json`; sau khi đo: `runs/E6/t1_summary.json`, `models/eval_E6.onnx` |

PowerShell (không dùng Bash tool: lệnh chạy 4,5 h, vượt trần 10 phút):

```powershell
New-Item -ItemType Directory -Force C:\Users\Admin\morsedesk\runs\E6 | Out-Null
Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash','/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','E6','--steps','30000','--batch','16','--lr','1e-3','--seed','13','--val-clips','200','--val-every','500','--hidden','128','--feature-mode','window','--lr-schedule','cosine','--warmup','500','--workers','8','--no-mp3','--qsb-hard' -WindowStyle Hidden
```

Theo dõi (sau ~2 phút, rồi mỗi 30 phút):

```powershell
Get-Content C:\Users\Admin\morsedesk\runs\E6\train.log -Tail 3; Get-Content C:\Users\Admin\morsedesk\runs\E6\train.err -Tail 3
```

Expected sau 2 phút: dòng dạng `step 50 loss 3.xxxx lr 1.00e-04 (26s)` → **0,5 s/bước**. Nếu thấy > 5 s/bước thì `OMP_NUM_THREADS` chưa có tác dụng: dừng tiến trình (`wsl.exe -d Ubuntu-26.04 -- pkill -f tools.train`), kiểm lại `scripts/wsl_train.sh`, chạy lại.

- [ ] **Step 9: Đo E6 và ghi một dòng bảng**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/eval_run.py --run runs/E6 --name E6
```

Expected: hai bảng pivot (greedy, beam+LM) và một dòng markdown 8 cột.

**Tiêu chí nhận/loại:** nhận E6 nếu `CER T1 greedy` **< 26,45 %** (mốc E3). Ghi riêng ô `qsb` (E3 = 62,34 %) — nếu tổng không giảm nhưng `qsb` giảm ≥ 5 điểm thì vẫn ghi nhận là chẩn đoán đúng, nhưng **mốc cho bước sau** luôn là run có CER tổng thấp nhất.

Dán vào bảng tổng hợp của `docs/research/03-model-experiments.md` một dòng, lấy 8 cột từ stdout và điền tay cột 2 (thay đổi) và cột 6 (giờ máy, đọc từ dòng cuối `train.log`):

```markdown
| E6 | E3 + `--qsb-hard` (QSB 60 %, 10–24 dB, 2–8 s) | 128 | window | <bước best> | <giờ> | <TER val> | <CER greedy> | <CER beam+LM> | <en / ru / kk> |
```

và một mục `### E6` với: lệnh nguyên văn ở Step 8, giờ bắt đầu–kết thúc, s/bước đọc từ log, đường cong TER (các mốc 3000/5000/10000/15000/20000/25000/30000), hai bảng pivot, CER theo kênh/kiểu gõ/profile, và một đoạn nhận xét trả lời đúng một câu hỏi: **ô `qsb` có giảm không, và giảm bao nhiêu điểm**.

- [ ] **Step 10: Chạy E7 — AGC tau ngắn**

| Mục | Giá trị |
|---|---|
| Đổi so với run trước | **đúng một biến**: `--agc-tau 0.4` thêm vào cấu hình của run tốt nhất hiện tại (giữ `--qsb-hard` nếu E6 được nhận ở Step 9, bỏ nếu E6 bị loại) |
| Giả thuyết | Chu kỳ fade 4 s của T1 trùng đúng độ dài cửa sổ 4 s nên chuẩn hóa theo cửa sổ vô hiệu; tau 0,4 s bám kịp fade |
| Thời gian ước tính | ~4,5 h |
| Tệp kết quả | `runs/E7/*` như E6, cộng `runs/E7/t1_summary.json`, `models/eval_E7.onnx` |

```powershell
New-Item -ItemType Directory -Force C:\Users\Admin\morsedesk\runs\E7 | Out-Null
Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash','/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','E7','--steps','30000','--batch','16','--lr','1e-3','--seed','13','--val-clips','200','--val-every','500','--hidden','128','--feature-mode','window','--lr-schedule','cosine','--warmup','500','--workers','8','--no-mp3','--qsb-hard','--agc-tau','0.4' -WindowStyle Hidden
```

(Bỏ `'--qsb-hard',` khỏi danh sách trên nếu E6 bị loại.)

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/eval_run.py --run runs/E7 --name E7
```

**Tiêu chí nhận/loại:** nhận E7 nếu `CER T1 greedy` thấp hơn run tốt nhất hiện tại (E3 26,45 % hoặc E6 nếu E6 đã được nhận). Chú ý `eval_run.py` xuất ONNX kèm `config.agc_tau_s = 0.4`, và `Decoder` đọc lại đúng giá trị đó lúc suy luận (Task 6 Step 5) — nếu CER tăng vọt lên > 60 % thì gần như chắc chắn đường suy luận **không** đọc được tau: kiểm `models/eval_E7.json` có `config.agc_tau_s` chưa.

Dòng bảng:

```markdown
| E7 | <run tốt nhất> + `--agc-tau 0.4` | 128 | window | <bước best> | <giờ> | <TER val> | <CER greedy> | <CER beam+LM> | <en / ru / kk> |
```

cộng mục `### E7` cùng cấu trúc như E6, nhận xét trả lời: **ô `qsb` và ô 0 dB có giảm không**.

- [ ] **Step 11: Commit tài liệu thí nghiệm**

```bash
cd /c/Users/Admin/morsedesk && git add docs/research/03-model-experiments.md
git commit -m "docs(research): ket qua E6 (QSB) va E7 (AGC tau 0.4) tren T1" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ. (`runs/` đã gitignored nên không có checkpoint nào lọt vào commit.)

---

### Task 7: Thí nghiệm E8 (nhiễu thật), E9 (model lớn hơn), E10 (dữ liệu thật gán nhãn giả) (spec §3.4)

**Loại: thí nghiệm** — phần code cho E8 và E10 viết theo TDD (Step 1–5), phần chạy đặc tả bằng lệnh và tiêu chí.

**Files:**
- Create: `morsedesk/data/noise.py`, `tools/fetch_hamnoise.py`
- Create: `tests/unit/test_noise_bank.py`, `tests/unit/test_train_mix.py`
- Modify: `morsedesk/data/channel.py` (`apply_channel(..., noise_bank=None)`), `morsedesk/data/synth.py` (`SynthConfig.noise_dir`), `tools/train.py` (`--noise-dir`, `--real-manifest`, `--real-ratio`, `features_from_audio`)
- Modify: `docs/research/03-model-experiments.md`

**Interfaces:**
- Consumes: `encode.synth.add_noise(x, snr_db, signal_power, sample_rate, band_hz=500.0, rng)` (quy ước SNR đo trong băng 500 Hz); `audio.io.load_audio`, `save_audio`; `pseudo_label` manifest với khóa `path` và `tokens` (Task 5); `train.example_features(ex, mode, agc_tau_s)`, `train.SynthDataset` (Task 6).
- Produces:
  - `noise.NoiseBank(root, sample_rate=SAMPLE_RATE)` với `.paths: list[Path]` và `.clip(n, rng) -> np.ndarray`
  - `noise.add_real_noise(x, snr_db, signal_power, bank, rng, sample_rate=SAMPLE_RATE, band_hz=500.0) -> np.ndarray`
  - `channel.apply_channel(x, p, rng, sample_rate, signal_power, qrm_factory=None, noise_bank=None)`
  - `synth.SynthConfig.noise_dir: Path | None = None`
  - `fetch_hamnoise.convert_dir(src: Path, dst: Path, sample_rate=8000) -> int`, `fetch_hamnoise.main(argv) -> int`
  - `train.features_from_audio(x, mode=DEFAULT_FEATURE_MODE, agc_tau_s=1.0) -> np.ndarray`
  - `train.load_real_rows(manifest: Path) -> list[dict]`
  - `train.SynthDataset(..., real_rows=None, real_ratio=0.0)`; cờ `--noise-dir`, `--real-manifest`, `--real-ratio`; `config` thêm khóa `real_ratio: float`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_noise_bank.py`:

```python
import numpy as np
import pytest

from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio
from morsedesk.data.channel import clean, apply_channel
from morsedesk.data.noise import NoiseBank, add_real_noise
from morsedesk.encode.synth import tone_power


@pytest.fixture
def bank_dir(tmp_path):
    rng = np.random.default_rng(0)
    for i in range(3):
        save_audio(tmp_path / f"n{i}.wav", rng.normal(0, 0.1, 8000 * 3).astype(np.float32), 8000)
    return tmp_path


def test_bank_lists_and_slices(bank_dir):
    bank = NoiseBank(bank_dir)
    assert len(bank.paths) == 3
    rng = np.random.default_rng(1)
    clip = bank.clip(8000, rng)
    assert clip.shape == (8000,) and clip.dtype == np.float32
    assert not np.allclose(clip, bank.clip(8000, rng))        # lấy đoạn khác nhau


def test_bank_tiles_when_source_shorter_than_request(bank_dir):
    bank = NoiseBank(bank_dir)
    assert bank.clip(8000 * 10, np.random.default_rng(2)).shape == (80000,)


def test_bank_reports_empty_dir(tmp_path):
    with pytest.raises(FileNotFoundError, match="wav"):
        NoiseBank(tmp_path)


def test_add_real_noise_hits_requested_snr(bank_dir):
    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    rng = np.random.default_rng(3)
    y = add_real_noise(x, 10.0, tone_power(0.8), NoiseBank(bank_dir), rng)
    added = y.astype(np.float64) - x.astype(np.float64)
    expected = tone_power(0.8) / (10.0 ** (10.0 / 10.0)) * (8000 / 2.0) / 500.0
    assert float(np.mean(added ** 2)) == pytest.approx(expected, rel=0.05)


def test_apply_channel_uses_bank_when_given(bank_dir):
    x = Encoder("en").to_audio("CQ", wpm=20)
    p = clean(10.0, 700.0)
    a = apply_channel(x, p, np.random.default_rng(4), 8000, tone_power(0.8))
    b = apply_channel(x, p, np.random.default_rng(4), 8000, tone_power(0.8),
                      noise_bank=NoiseBank(bank_dir))
    assert a.shape == b.shape and not np.allclose(a, b)


def test_fetch_hamnoise_converts_to_8k_mono(tmp_path):
    from morsedesk.audio.io import load_audio
    from tools import fetch_hamnoise

    src = tmp_path / "src"
    src.mkdir()
    save_audio(src / "a.wav", np.random.default_rng(5).normal(0, 0.1, 16000).astype(np.float32), 16000)
    (src / "readme.md").write_text("không phải audio", encoding="utf-8")
    dst = tmp_path / "dst"
    assert fetch_hamnoise.convert_dir(src, dst) == 1
    out = sorted(dst.glob("*.wav"))
    assert len(out) == 1
    x, sr = load_audio(out[0])
    assert sr == 8000 and len(x) == 8000
```

Tạo `tests/unit/test_train_mix.py`:

```python
import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from morsedesk.api import Encoder  # noqa: E402
from morsedesk.audio.io import save_audio  # noqa: E402
from morsedesk.constants import FEAT_DIM  # noqa: E402
from morsedesk.data.synth import SynthConfig, SynthGenerator  # noqa: E402
from morsedesk.model.vocab import VOCAB  # noqa: E402
from tools.train import SynthDataset, features_from_audio, load_real_rows  # noqa: E402


def write_real(tmp_path, n=2):
    manifest = tmp_path / "train.jsonl"
    rows = []
    for i in range(n):
        p = tmp_path / f"c{i}.wav"
        save_audio(p, Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
        rows.append({"path": str(p), "text": "CQ DE K", "profile": "en", "confidence": 0.95,
                     "tokens": ["-.-.", "--.-", "<space>", "-..", ".", "<space>", "-.-"]})
    manifest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                        encoding="utf-8")
    return manifest


def test_features_from_audio_shape_matches_feat_dim(tmp_path):
    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    feats = features_from_audio(x, "window")
    assert feats.shape[1] == FEAT_DIM and feats.shape[0] == len(x) // 40
    assert features_from_audio(x, "clip").shape == feats.shape


def test_load_real_rows_skips_missing_files_and_bad_tokens(tmp_path):
    manifest = write_real(tmp_path, n=2)
    extra = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    extra.append({"path": str(tmp_path / "khong-co.wav"), "tokens": ["-.-."]})
    extra.append({"path": extra[0]["path"], "tokens": ["khong-phai-mau"]})
    manifest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in extra),
                        encoding="utf-8")
    rows = load_real_rows(manifest)
    assert len(rows) == 2


def test_dataset_mixes_real_rows_at_requested_ratio(tmp_path):
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    rows = load_real_rows(write_real(tmp_path, n=2))
    ds = SynthDataset(gen, seed_start=5_000, n_items=40, feature_mode="window",
                      real_rows=rows, real_ratio=1.0)
    items = list(ds)
    assert len(items) == 40
    target = [VOCAB.id(t) for t in rows[0]["tokens"]]
    assert all(list(labels) == target for _, labels, _ in items)
    ds0 = SynthDataset(gen, seed_start=5_000, n_items=5, feature_mode="window",
                       real_rows=rows, real_ratio=0.0)
    assert all(feats.shape[1] == FEAT_DIM for feats, _, _ in ds0)
```

- [ ] **Step 2: Chạy test để thấy chúng đỏ**

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_noise_bank.py tests/unit/test_train_mix.py -q
```

Expected: `2 errors` — `ModuleNotFoundError: No module named 'morsedesk.data.noise'` và `ImportError: cannot import name 'features_from_audio' from 'tools.train'`.

- [ ] **Step 3: Viết `morsedesk/data/noise.py` và `tools/fetch_hamnoise.py`**

```python
"""Ngân hàng nhiễu sóng ngắn thật: chọn ngẫu nhiên một đoạn nền và trộn theo SNR mục tiêu.

Dùng cho thí nghiệm E8 (spec §3.4): thay AWGN tổng hợp bằng nhiễu băng sóng ngắn thật
(HamNoise). Mức trộn được chuẩn theo **tổng công suất** mà AWGN cùng SNR sẽ có
(`encode.synth.add_noise`), nên hai nhánh so được với nhau ở cùng một con số `snr_db`; nhiễu
thật phân bố năng lượng theo tần số khác hẳn AWGN, và đó chính là biến mà E8 muốn đo.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio
from morsedesk.constants import SAMPLE_RATE


class NoiseBank:
    def __init__(self, root: Path | str, sample_rate: int = SAMPLE_RATE) -> None:
        self.root = Path(root)
        self.sample_rate = sample_rate
        self.paths = sorted(p for p in self.root.glob("*.wav"))
        if not self.paths:
            raise FileNotFoundError(f"không có file .wav nào trong {self.root}")
        self._cache: dict[Path, np.ndarray] = {}

    def clip(self, n: int, rng: np.random.Generator) -> np.ndarray:
        path = self.paths[int(rng.integers(len(self.paths)))]
        if path not in self._cache:
            x, _ = load_audio(path, self.sample_rate)
            self._cache[path] = x
        src = self._cache[path]
        if len(src) < n:
            src = np.tile(src, int(np.ceil(n / max(1, len(src)))))
        start = int(rng.integers(0, max(1, len(src) - n + 1)))
        return np.asarray(src[start:start + n], dtype=np.float32)


def add_real_noise(x: np.ndarray, snr_db: float, signal_power: float, bank: NoiseBank,
                   rng: np.random.Generator, sample_rate: int = SAMPLE_RATE,
                   band_hz: float = 500.0) -> np.ndarray:
    """Trộn nhiễu thật ở tổng công suất bằng đúng AWGN cùng `snr_db` (xem docstring module)."""
    n = bank.clip(len(x), rng).astype(np.float64)
    p_noise_band = signal_power / (10.0 ** (snr_db / 10.0))
    sigma2 = p_noise_band * (sample_rate / 2.0) / band_hz
    power = float(np.mean(n ** 2))
    if power > 0.0:
        n = n * np.sqrt(sigma2 / power)
    return (x.astype(np.float64) + n).astype(np.float32)
```

```python
"""Tải nền nhiễu sóng ngắn thật (HamNoise) về `testdata/private/noise/` dạng WAV 8 kHz mono.

HamNoise (https://github.com/e04/HamNoise, cùng tác giả DeepCW) là nguồn nền nhiễu băng sóng
ngắn thật cho thí nghiệm E8. Repo có thể thay đổi bố cục, nên công cụ này **quét theo phần mở
rộng** thay vì bám đường dẫn cố định; nếu không tìm được file âm thanh nào thì trả mã 1 và E8
được ghi là "không chạy được vì thiếu dữ liệu" thay vì bịa số.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from morsedesk.audio.io import SUPPORTED_EXT, load_audio, save_audio
from morsedesk.textio import force_utf8_streams

REPO = "https://github.com/e04/HamNoise"
DEFAULT_OUT = Path("testdata/private/noise")


def convert_dir(src: Path, dst: Path, sample_rate: int = 8000) -> int:
    """Mọi file âm thanh trong `src` (đệ quy) -> WAV mono `sample_rate` trong `dst`. Trả số file."""
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(q for q in Path(src).rglob("*") if q.suffix.lower() in SUPPORTED_EXT):
        try:
            x, sr = load_audio(p, sample_rate)
        except Exception as e:                  # file hỏng không được làm hỏng cả lượt
            print(f"bỏ qua {p.name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        save_audio(dst / f"{n:03d}_{p.stem[:40]}.wav", x, sr)
        n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Tải HamNoise về testdata/private/noise/")
    ap.add_argument("--src", type=Path, default=None, help="thư mục đã clone sẵn (bỏ qua git clone)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    if a.src is not None:
        n = convert_dir(a.src, a.out)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                subprocess.run(["git", "clone", "--depth", "1", REPO, tmp + "/HamNoise"],
                               check=True, capture_output=True, timeout=600)
            except (subprocess.SubprocessError, OSError) as e:
                print(f"lỗi: không clone được {REPO}: {e}", file=sys.stderr)
                return 1
            n = convert_dir(Path(tmp) / "HamNoise", a.out)
    print(f"{n} file nhiễu -> {a.out}")
    if n == 0:
        print("không tìm thấy file âm thanh nào: E8 ghi là 'không chạy được vì thiếu dữ liệu'",
              file=sys.stderr)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Nối `noise_bank` vào `apply_channel` và `SynthConfig`**

`morsedesk/data/channel.py`: thêm tham số cuối cho `apply_channel` và thay đúng một dòng trong thân hàm:

```python
def apply_channel(
    x: np.ndarray,
    p: ChannelParams,
    rng: np.random.Generator,
    sample_rate: int = SAMPLE_RATE,
    signal_power: float = 0.32,
    qrm_factory: QrmFactory | None = None,
    noise_bank=None,
) -> np.ndarray:
```
```python
    if noise_bank is None:
        y = add_noise(y.astype(np.float32), p.snr_db, signal_power, sample_rate, rng=rng).astype(np.float64)
    else:
        from morsedesk.data.noise import add_real_noise

        y = add_real_noise(y.astype(np.float32), p.snr_db, signal_power, noise_bank, rng,
                           sample_rate).astype(np.float64)
```

`morsedesk/data/synth.py`: thêm trường, dựng bank một lần trong `__init__`, truyền vào `apply_channel`:

```python
    noise_dir: Path | None = None
```
```python
        self._mp3 = cfg.mp3_enabled and ffmpeg_available()
        if cfg.mp3_enabled and not self._mp3:
            logging.getLogger(__name__).warning("không có ffmpeg: bỏ tăng cường MP3")
        self.noise_bank = None
        if cfg.noise_dir is not None:
            from morsedesk.data.noise import NoiseBank

            self.noise_bank = NoiseBank(cfg.noise_dir)
```
```python
        audio = apply_channel(x, channel, rng, SAMPLE_RATE, tone_power(AMPLITUDE),
                              self._random_morse, self.noise_bank)
```

- [ ] **Step 5: Thêm trộn dữ liệu thật vào `tools/train.py` rồi chạy test**

Thêm import và hai hàm (đặt cạnh `example_features`):

```python
from morsedesk.audio.io import load_audio
from morsedesk.dsp.frontend import DEFAULT_F0_HZ


def features_from_audio(x: np.ndarray, mode: str = DEFAULT_FEATURE_MODE,
                        agc_tau_s: float = 1.0) -> np.ndarray:
    """Đặc trưng từ audio thật (không biết trước tone) — dùng cho dữ liệu đã gán nhãn giả."""
    if mode == "window":
        n_frames = len(x) // HOP
        return stitch_windows(
            compute_features_windowed(x, f0_hint=None, cfg=window_cfg(agc_tau_s)), n_frames)
    if mode != "clip":
        raise ValueError(f"feature_mode lạ: {mode}")
    est = estimate_tone(x)
    f0 = est.f0_hz if est.has_signal and est.f0_hz is not None else DEFAULT_F0_HZ
    return compute_features(x, f0, cfg=FrontendConfig(agc_tau_s=agc_tau_s))


def load_real_rows(manifest: Path) -> list[dict]:
    """Hàng của `tools/pseudo_label.py`; bỏ hàng thiếu file hoặc có token không thuộc bảng 65."""
    rows: list[dict] = []
    with open(manifest, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            toks = list(r.get("tokens") or [])
            if not toks or not Path(r["path"]).is_file():
                continue
            if any(t != SPACE and not VOCAB.is_pattern(t) for t in toks):
                continue
            rows.append(r)
    return rows
```

và `from morsedesk.model.vocab import SPACE, VOCAB` (module đang import `VOCAB`; thêm `SPACE`).

`SynthDataset` nhận thêm hai tham số (giữ nguyên phần còn lại của Task 6):

```python
class SynthDataset(IterableDataset):
    """Dữ liệu tổng hợp, có thể trộn dữ liệu thật đã gán nhãn giả theo tỉ lệ `real_ratio` (E10)."""

    def __init__(self, gen: SynthGenerator, seed_start: int, n_items: int,
                 feature_mode: str = DEFAULT_FEATURE_MODE, agc_tau_s: float = 1.0,
                 real_rows: list[dict] | None = None, real_ratio: float = 0.0) -> None:
        self.gen, self.seed_start, self.n_items = gen, seed_start, n_items
        self.feature_mode, self.agc_tau_s = feature_mode, agc_tau_s
        self.real_rows = list(real_rows or [])
        self.real_ratio = float(real_ratio) if self.real_rows else 0.0

    def __iter__(self):
        info = get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        for k in range(wid, self.n_items, nw):
            seed = self.seed_start + k
            rng = np.random.default_rng(seed)
            if self.real_ratio > 0.0 and rng.random() < self.real_ratio:
                row = self.real_rows[int(rng.integers(len(self.real_rows)))]
                x, _ = load_audio(row["path"])
                tokens = list(row["tokens"])
                yield (torch.from_numpy(features_from_audio(x, self.feature_mode, self.agc_tau_s)),
                       torch.tensor([VOCAB.id(t) for t in tokens], dtype=torch.long), tokens)
                continue
            ex = self.gen.generate(seed)
            yield (torch.from_numpy(example_features(ex, self.feature_mode, self.agc_tau_s)),
                   torch.tensor(ex.labels, dtype=torch.long), ex.tokens)
```

Trong `main`, thêm ba cờ và bốn chỗ dùng:

```python
    ap.add_argument("--noise-dir", type=Path, default=None,
                    help="thư mục WAV nhiễu thật thay AWGN tổng hợp (E8; tools/fetch_hamnoise.py)")
    ap.add_argument("--real-manifest", type=Path, default=None,
                    help="manifest dữ liệu thật đã gán nhãn giả (E10; tools/pseudo_label.py)")
    ap.add_argument("--real-ratio", type=float, default=0.25,
                    help="tỉ lệ mẫu lấy từ --real-manifest (chỉ có tác dụng khi có manifest)")
```
```python
    gen = SynthGenerator(SynthConfig(mp3_enabled=not a.no_mp3,
                                     channel_sampling=sampling_for(a.qsb_hard),
                                     noise_dir=a.noise_dir))
    real_rows = load_real_rows(a.real_manifest) if a.real_manifest else []
    real_ratio = a.real_ratio if real_rows else 0.0
    print(f"dữ liệu thật: {len(real_rows)} đoạn, tỉ lệ {real_ratio:.2f}")
```
```python
    config = dict(CONFIG_DEFAULT, hidden=a.hidden, feature_mode=a.feature_mode,
                  qsb_hard=bool(a.qsb_hard), agc_tau_s=float(a.agc_tau), real_ratio=float(real_ratio))
```
```python
    ds = SynthDataset(gen, seed_start=a.seed * 1_000_000 + start_step * a.batch,
                      n_items=(a.steps - start_step) * a.batch, feature_mode=a.feature_mode,
                      agc_tau_s=a.agc_tau, real_rows=real_rows, real_ratio=real_ratio)
```

Validation **luôn** là dữ liệu tổng hợp (`VAL_SEED_BASE`), không trộn dữ liệu thật: nếu không thì TER của E10 không so được với E6–E9.

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_noise_bank.py tests/unit/test_train_mix.py -q
```

Expected: `9 passed`.

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q
```

Expected: `All checks passed!` và `0 failed`.

```bash
cd /c/Users/Admin/morsedesk && git add morsedesk/data/noise.py morsedesk/data/channel.py morsedesk/data/synth.py tools/fetch_hamnoise.py tools/train.py tests/unit/test_noise_bank.py tests/unit/test_train_mix.py
git commit -m "feat(train): nhieu that HamNoise va tron du lieu that da gan nhan gia" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ.

- [ ] **Step 6: Chạy E8 — nhiễu thật thay AWGN**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/fetch_hamnoise.py
```

Expected: `<n> file nhiễu -> testdata\private\noise`. **Nếu `n == 0`**: E8 dừng tại đây; ghi vào `docs/research/03-model-experiments.md` một dòng `| E8 | … | — | không chạy được: HamNoise không có file âm thanh (mã 1 của tools/fetch_hamnoise.py, <ngày>) |` rồi sang Step 7. Không bịa số, không thay bằng nguồn nhiễu khác mà không ghi rõ.

| Mục | Giá trị |
|---|---|
| Đổi so với run trước | **đúng một biến**: `--noise-dir testdata/private/noise` thêm vào cấu hình của run tốt nhất sau E6/E7 |
| Giả thuyết | Nhiễu sóng ngắn thật khác AWGN về phân bố phổ và tính xung; model quen AWGN sẽ hụt trên bản ghi thật |
| Thời gian ước tính | ~5 h (đọc WAV nhiễu thêm khoảng 10 % mỗi bước) |
| Tệp kết quả | `runs/E8/*`, `runs/E8/t1_summary.json`, `models/eval_E8.onnx` |

```powershell
New-Item -ItemType Directory -Force C:\Users\Admin\morsedesk\runs\E8 | Out-Null
Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash','/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','E8','--steps','30000','--batch','16','--lr','1e-3','--seed','13','--val-clips','200','--val-every','500','--hidden','128','--feature-mode','window','--lr-schedule','cosine','--warmup','500','--workers','8','--no-mp3','--qsb-hard','--agc-tau','0.4','--noise-dir','testdata/private/noise' -WindowStyle Hidden
```

(Giữ `--qsb-hard` và `--agc-tau 0.4` chỉ khi E6 và E7 đã được nhận; bỏ cờ nào bị loại.)

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/eval_run.py --run runs/E8 --name E8
```

**Tiêu chí nhận/loại:** nhận nếu `CER T1 greedy` thấp hơn run tốt nhất hiện tại. E8 còn có một chỉ số thứ hai quan trọng hơn: **CER trên T2** (bản ghi thật, Task 4) — nếu T1 không đổi nhưng T2 giảm ≥ 2 điểm thì vẫn nhận, và ghi rõ lý do. Đo T2:

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/private/t2/manifest.jsonl --engine onnx --model models/eval_E8.onnx --out-dir runs/t2 --t2-gate
```

Dòng bảng:

```markdown
| E8 | <run trước> + `--noise-dir` (HamNoise, <n> file) | 128 | window | <bước best> | <giờ> | <TER val> | <CER greedy> | <CER beam+LM> | <en / ru / kk> |
```

- [ ] **Step 7: Chạy E9 — model lớn hơn**

| Mục | Giá trị |
|---|---|
| Đổi so với run trước | **đúng một biến**: `--hidden 192` (thay 128) trên cấu hình tốt nhất sau E6–E8 |
| Giả thuyết | E3 bão hòa ở TER 22 % từ bước 21500; DeepCW ~3,7 M tham số so với ~200 k của mình, và khoảng cách 10,8 điểm ở ô `clean` là khoảng cách năng lực |
| Thời gian ước tính | ~7 h (BiGRU 192 nặng hơn ~1,6×: ước 0,8 s/bước × 30 000) |
| Tệp kết quả | `runs/E9/*`, `runs/E9/t1_summary.json`, `models/eval_E9.onnx` |

```powershell
New-Item -ItemType Directory -Force C:\Users\Admin\morsedesk\runs\E9 | Out-Null
Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash','/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','E9','--steps','30000','--batch','16','--lr','1e-3','--seed','13','--val-clips','200','--val-every','500','--hidden','192','--feature-mode','window','--lr-schedule','cosine','--warmup','500','--workers','8','--no-mp3','--qsb-hard','--agc-tau','0.4' -WindowStyle Hidden
```

(Thêm `'--noise-dir','testdata/private/noise',` nếu E8 được nhận; bỏ cờ nào bị loại.)

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/eval_run.py --run runs/E9 --name E9
```

**Tiêu chí nhận/loại:** nhận nếu `CER T1 greedy` thấp hơn run tốt nhất hiện tại. Kiểm thêm tốc độ suy luận trong `t1_summary.json` (`greedy.mean_seconds`): nếu vượt **0,25 s/clip** thì ghi chú rủi ro cho chế độ live tuần 5 nhánh B (cửa sổ 2 s phải giải mã xong trong dưới 2 s).

Phương án "thêm khối Conv 2-D trên phổ trước BiGRU" nêu ở spec §3.4 **không làm trong tuần 5**: đầu vào hiện là 11 chiều đặc trưng thủ công (1 envelope AGC + 1 đạo hàm + 9 bin phổ), không phải phổ 2-D, nên một khối Conv 2-D đòi thay cả frontend, cả `FEAT_DIM`, cả định dạng ONNX và toàn bộ test theo cửa sổ — vượt khung một thí nghiệm một đêm. Ghi lại lựa chọn này trong mục `### E9`.

Dòng bảng:

```markdown
| E9 | <run trước> + `--hidden 192` | 192 | window | <bước best> | <giờ> | <TER val> | <CER greedy> | <CER beam+LM> | <en / ru / kk> |
```

- [ ] **Step 8: Chạy E10 — thêm dữ liệu thật đã gán nhãn giả**

| Mục | Giá trị |
|---|---|
| Đổi so với run trước | **đúng một biến**: `--real-manifest testdata/private/pseudo/train.jsonl --real-ratio 0.25` trên cấu hình tốt nhất sau E6–E9 |
| Giả thuyết | Khoảng cách tổng hợp ↔ thật chưa từng đo được; 25 % dữ liệu thật đủ để kéo phân bố mà không nhấn chìm dữ liệu tổng hợp |
| Thời gian ước tính | ~5–7,5 h (theo hidden của run nền; đọc WAV thật thêm ~10 %) |
| Tệp kết quả | `runs/E10/*`, `runs/E10/t1_summary.json`, `models/eval_E10.onnx` |
| Phụ thuộc | `testdata/private/pseudo/train.jsonl` từ Task 5 Step 5, **với đúng ngưỡng tin cậy đã ghi lại ở đó** |

```powershell
New-Item -ItemType Directory -Force C:\Users\Admin\morsedesk\runs\E10 | Out-Null
Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash','/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','E10','--steps','30000','--batch','16','--lr','1e-3','--seed','13','--val-clips','200','--val-every','500','--hidden','192','--feature-mode','window','--lr-schedule','cosine','--warmup','500','--workers','8','--no-mp3','--qsb-hard','--agc-tau','0.4','--real-manifest','testdata/private/pseudo/train.jsonl','--real-ratio','0.25' -WindowStyle Hidden
```

(Đặt `--hidden` bằng đúng giá trị của run nền; thêm/bỏ `--noise-dir` theo kết quả E8.)

Kiểm ngay sau 2 phút rằng dữ liệu thật thực sự được nạp:

```powershell
Select-String -Path C:\Users\Admin\morsedesk\runs\E10\train.log -Pattern "dữ liệu thật"
```

Expected: `dữ liệu thật: <n> đoạn, tỉ lệ 0.25` với `n > 0`. Nếu `n = 0` thì manifest sai đường dẫn — dừng và sửa trước khi để chạy tiếp 7 giờ.

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/eval_run.py --run runs/E10 --name E10
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run morsedesk bench --manifest testdata/private/t2/manifest.jsonl --engine onnx --model models/eval_E10.onnx --out-dir runs/t2 --t2-gate
```

**Tiêu chí nhận/loại:** nhận nếu `CER T1 greedy` thấp hơn E9, **hoặc** T1 không xấu đi quá 0,5 điểm trong khi T2 giảm ≥ 2 điểm (mục đích chính của E10 là thu hẹp khoảng cách tổng hợp ↔ thật). Ghi cả hai con số.

Dòng bảng:

```markdown
| E10 | E9 + dữ liệu thật gán nhãn giả (<n> đoạn, ngưỡng <c>, tỉ lệ 0,25) | <hidden> | window | <bước best> | <giờ> | <TER val> | <CER greedy> | <CER beam+LM> | <en / ru / kk> |
```

- [ ] **Step 9: Ghi mục chi tiết cho E8, E9, E10 và commit**

Mỗi mục (`### E8`, `### E9`, `### E10`) gồm: lệnh nguyên văn, giờ bắt đầu–kết thúc, s/bước, đường cong TER, hai bảng pivot, CER theo kênh/kiểu gõ/profile, CER trên T2 (E8 và E10), nhận xét một đoạn, và kết luận nhận/loại theo đúng tiêu chí ở trên.

```bash
cd /c/Users/Admin/morsedesk && git add docs/research/03-model-experiments.md
git commit -m "docs(research): ket qua E8 (nhieu that), E9 (hidden 192), E10 (du lieu that)" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: hai trailer hiện đủ.

---

### Task 8: Xuất model tốt nhất, chạy lại gate, giao bảng số theo từng ô (spec §7 mục 5; CP-01)

**Loại: đo và báo cáo.** Không có mã mới; nhiệm vụ là biến kết quả thành con số người dùng đọc được, dù gate xanh hay đỏ.

**Files:**
- Modify: `models/acoustic.json` (metadata mới, đã commit trong repo), `models/acoustic.onnx` (gitignored)
- Modify: `docs/research/02-baseline-numbers.md`, `docs/research/03-model-experiments.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: `runs/<best>/best.pt` và `runs/<best>/t1_summary.json` (Task 6–7); `tools/export_onnx.py --checkpoint --out --version`; `tests/regression/test_t1.py::test_t1_gate_onnx` và `test_t1_lm_not_worse_than_greedy_and_language_acc` (mã sẵn có); `bench.pivot_snr_wpm`, `bench.aggregate`; `testdata/private/t2/manifest.jsonl` (Task 4).
- Produces: `models/acoustic.onnx` v0.3.0 từ run tốt nhất; bảng gate theo từng ô trong `docs/research/02-baseline-numbers.md`.

- [ ] **Step 1: Chọn run tốt nhất và xuất ONNX**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python -c "import json,pathlib; [print(p.parent.name, round(100*json.loads(p.read_text(encoding='utf-8'))['greedy']['gate_cer'],2), round(100*(json.loads(p.read_text(encoding='utf-8'))['lm'] or {'gate_cer':float('nan')})['gate_cer'],2)) for p in sorted(pathlib.Path('runs').glob('*/t1_summary.json'))]"
```

Expected: một dòng cho mỗi run (`E3 26.45 25.27`, `E6 …`, …). Chọn run có `gate_cer` greedy thấp nhất; gọi là `<BEST>`.

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python tools/export_onnx.py --checkpoint runs/<BEST>/best.pt --out models/acoustic.onnx --version 0.3.0
```

Expected: ghi `models/acoustic.onnx`, `models/acoustic.json`, `models/acoustic.golden.npz`, in đường dẫn và sai số parity.

```bash
cd /c/Users/Admin/morsedesk && uv run pytest tests/unit/test_onnx_parity.py -q
```

Expected: `0 failed` (parity torch ↔ ONNX của model mới).

- [ ] **Step 2: Chạy lại gate**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run pytest -m gate -q
```

Ghi lại **nguyên văn** đầu ra. Hai kết cục đều hợp lệ:

- `X passed` → CP-01 đóng ở phần T1.
- `test_t1_gate_onnx` FAIL với `AssertionError: CER vùng gate = 0.xxxx trên 500 clip, ngưỡng 0.02` → gate vẫn đỏ. **Không** sửa ngưỡng trong test, **không** thu hẹp manifest. Đi tiếp Step 3; sản phẩm giao ra là bảng số.

Chạy riêng test roundtrip T0 (spec §7 và D2 của bản rà soát gộp vào CP-01):

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run pytest -m gate -q -k roundtrip
```

Ghi kết quả (đạt/không, và CER nếu không đạt).

- [ ] **Step 3: Dựng bảng số theo từng ô**

```bash
cd /c/Users/Admin/morsedesk && PYTHONUTF8=1 uv run python -c "
import json, pathlib
s = json.loads(pathlib.Path('runs/<BEST>/t1_summary.json').read_text(encoding='utf-8'))
for mode in ('greedy', 'lm'):
    d = s.get(mode)
    if not d:
        continue
    print('==', mode, 'gate_cer', round(100*d['gate_cer'], 2), 'n', d['n'])
    print(d['pivot'])
    for k in ('by_channel', 'by_keying', 'by_profile', 'by_snr', 'by_wpm'):
        print(k + ': ' + ', '.join(f'{a}={100*b:.2f}%' for a, b in d[k].items()))
"
```

Expected: hai khối (greedy và beam+LM), mỗi khối một bảng pivot SNR × WPM và năm dòng theo chiều.

- [ ] **Step 4: Viết mục kết luận tuần 5 vào `docs/research/02-baseline-numbers.md`**

Thêm mục `## Gate cuối tuần 5 (model <BEST>)` gồm đúng bảy phần:

1. Một câu: gate **ĐẠT** hay **KHÔNG ĐẠT**, kèm con số CER vùng gate và ngưỡng 2 % (không diễn giải lại ngưỡng).
2. Bảng pivot SNR × WPM của greedy và của beam+LM (dán từ Step 3).
3. Bảng CER theo kênh (`clean`, `mp3`, `qrn`, `qrm`, `qsb`) so với E3 và so với mốc DeepCW 23,70 % / 47,00 % ở ô `qsb`.
4. Bảng CER theo kiểu gõ và theo profile.
5. Bảng T2 theo nguồn (từ Task 4 Step 9, đo lại bằng `models/acoustic.onnx` mới).
6. `language_acc` mới nhất (CP-03) và kết quả T0 roundtrip (Step 2).
7. Khuyến nghị cho người dùng quyết, viết dưới dạng ba lựa chọn có số kèm theo: (a) giữ ngưỡng 2 % và chạy tiếp thang thí nghiệm ở tuần 6 với <ô còn kém nhất> là mục tiêu; (b) tách gate theo tầng như đề xuất ở `04-pretrained-baselines.md` mục 4.6 kèm số đo hiện tại của từng tầng; (c) thu hẹp phạm vi sản phẩm v1. **Không tự chọn thay người dùng, không tự sửa ngưỡng.**

Cập nhật mục "Kết luận và điều kiện ra" của `docs/research/03-model-experiments.md`: run được chọn, lý do, và tiến bộ theo mốc thời gian (v1 33,6 % → v1b 31,5 % → E3 26,5 % → <BEST> <x> %).

- [ ] **Step 5: Ghi sổ tiến độ**

Thêm vào cuối `.superpowers/sdd/progress.md` một khối `## Tuần 5 nhánh A (chất lượng)` liệt kê: 8 task đã xong kèm SHA commit, con số DeepCW engine, thành phần T2, kết quả E6–E10 một dòng mỗi cái, kết quả gate cuối và các chốt kiểm đã đóng (CP-01/02/03/13) hoặc lý do chưa đóng.

- [ ] **Step 6: Kiểm toàn bộ rồi commit**

```bash
cd /c/Users/Admin/morsedesk && uv run ruff check morsedesk tests tools && uv run pytest -q && uv run python tools/build_i18n.py --check
```

Expected: `All checks passed!`, `0 failed`, và i18n sạch (điều kiện ra tuần 5 mục 1).

```bash
cd /c/Users/Admin/morsedesk && git status --short && git add models/acoustic.json docs/research/02-baseline-numbers.md docs/research/03-model-experiments.md .superpowers/sdd/progress.md
git commit -m "docs(research): model v0.3.0, ket qua gate cuoi tuan 5 theo tung o" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
git log -1 --format=%B
```

Expected: `git status --short` không liệt kê `models/acoustic.onnx`, `runs/` hay `testdata/` (đều gitignored); hai trailer hiện đủ.

---

## Tự rà soát (đã chạy khi viết kế hoạch)

**1. Phủ spec.** Mục 3.1 → Task 1 (module + fetch + `check_models` + bench import lại), Task 2 (engine + CLI + chặn profile khác `en`), Task 3 (beam + LM, đo trước/sau). Mục 3.2 → Task 4 (bốn nguồn, manifest cùng khuôn T1, `bench` chạy được, năm công cụ đối chứng). Mục 3.3 → Task 5 (ngưỡng tin cậy, nhãn cứng, ánh xạ Latin → mẫu → 65 lớp, tỉ lệ thật/tổng hợp ghi vào `config.real_ratio` của run ở Task 7). Mục 3.4 → Task 6 (E6, E7) và Task 7 (E8, E9, E10). Mục 7 điều kiện ra: (1) ruff/pytest ở mọi task và i18n ở Task 8; (2) engine `deepcw` ở Task 2–3; (3) T2 ở Task 4; (4) E6–E10 ở Task 6–7; (5) gate ở Task 8. CP-01 → Task 8; CP-02 → Task 4; CP-03 → Task 4 Step 11; CP-13 → Task 4 Step 10.

**2. Chưa chuyển được thành task cụ thể.**

- *Khối Conv 2-D trên phổ trước BiGRU* (một nửa của E9): đầu vào hiện là 11 chiều đặc trưng thủ công chứ không phải phổ 2-D, nên nó kéo theo đổi `FEAT_DIM`, frontend, định dạng ONNX và toàn bộ test theo cửa sổ — lớn hơn một thí nghiệm một đêm. E9 chỉ chạy nhánh `--hidden 192`; lựa chọn này ghi rõ trong mục `### E9` (Task 7 Step 7).
- *Đường tải chính xác của ARRL/SRAA*: spec nêu tên nguồn chứ không nêu URL từng file, và trang có thể đổi. Task 4 dùng cách quét trang liệt kê (`page`) cộng đường vòng `local` cho file tải tay, kèm nhánh `synth` để không bao giờ kẹt — thay vì ghi một danh sách URL có thể sai ngay hôm sau.
- *HamNoise có thật sự chứa file âm thanh hay không*: chưa kiểm chứng được offline. Task 7 Step 6 đặt điều kiện dừng rõ ràng (`n == 0` → ghi "không chạy được vì thiếu dữ liệu") thay vì giả định.

**3. Nhất quán kiểu giữa các task.** `DeepCwOutput(emissions, n_frames, frame_rate, confidence)` định nghĩa ở Task 1, dùng nguyên vẹn ở Task 2 (`_deepcw_words`), Task 3 (nhánh greedy) và Task 5 (`label_segments`). `emissions` luôn là `list[tuple[str, int, float]]` = (chữ, khung, xác suất) ở phía DeepCW, và `list[tuple[str, int, float]]` = (mẫu chấm gạch, khung, xác suất) sau khi đổi trong `_deepcw_words` — hai nghĩa khác nhau nên tên biến trong `_deepcw_words` là `raw` (chữ) và `emissions` (mẫu). `frame_rate` là `float` ở mọi chỗ (3200/48 = 66,67), vì thế chú thích kiểu của `estimate_wpm_from_emissions` được nới ở Task 2. Khóa manifest T2 (`source`, `license`, `synthetic`) do Task 4 đặt và Task 4 Step 10 dùng lại; khóa manifest nhãn giả (`path`, `tokens`) do Task 5 đặt và Task 7 `load_real_rows` đọc đúng hai khóa đó. `window_cfg(agc_tau_s)` do Task 6 tạo, dùng ở `Decoder.feature_cfg`, `chunker.run_chunked_audio(cfg=)`, `train.example_features` và `train.features_from_audio` (Task 7) — cùng một hàm, không có bản sao.
