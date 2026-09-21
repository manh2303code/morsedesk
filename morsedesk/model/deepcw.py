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
