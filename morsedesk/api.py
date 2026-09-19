"""Giao diện ổn định cho GUI và CLI. GUI/CLI chỉ dùng Encoder, Decoder, DecodeResult."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio, resample
from morsedesk.constants import FRAME_RATE, SAMPLE_RATE
from morsedesk.dsp.baseline import BaselineDecoder, Symbol
from morsedesk.dsp.frontend import compute_features, mix_envelope
from morsedesk.dsp.tone import estimate_tone
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.ctc import greedy_decode_with_frames
from morsedesk.model.vocab import SPACE, VOCAB

LOW_CONFIDENCE = 0.6
FALLBACK_CONFIDENCE = 0.5
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "acoustic.onnx"


@dataclass
class Word:
    text: str
    start_s: float
    end_s: float
    confidence: float


@dataclass
class DecodeResult:
    text: str
    words: list[Word]
    wpm: float | None
    tone_hz: float | None
    snr_db: float | None
    language: str
    language_scores: dict[str, float]
    warnings: list[str]
    engine: str
    fallback_text: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _resolve_profile(profile: str | Profile) -> Profile:
    if isinstance(profile, Profile):
        return profile
    if profile == "auto":
        raise NotImplementedError(
            "profile 'auto' cần mô hình ngôn ngữ (tuần 3); hãy chọn en, ru hoặc kk-cyrl-ru"
        )
    return load_profile(profile)


class Encoder:
    def __init__(self, profile: str | Profile = "en") -> None:
        self.profile = _resolve_profile(profile)

    def to_tokens(self, text: str, strict: bool = True) -> list[str]:
        return text_to_tokens(text, self.profile, strict=strict)

    def to_morse_string(self, text: str, strict: bool = True) -> str:
        return " ".join("/" if t == SPACE else t for t in self.to_tokens(text, strict))

    def to_audio(
        self,
        text: str,
        wpm: float = 20.0,
        farnsworth_wpm: float | None = None,
        weight: float = 3.0,
        tone_hz: float = 700.0,
        sample_rate: int = SAMPLE_RATE,
        snr_db: float | None = None,
        seed: int | None = None,
        pad_s: float = 0.3,
        amplitude: float = 0.8,
        strict: bool = True,
    ) -> np.ndarray:
        tokens = self.to_tokens(text, strict)
        elements = tokens_to_elements(tokens, TimingParams(wpm, farnsworth_wpm, weight))
        x = elements_to_audio(elements, tone_hz, sample_rate, amplitude)
        pad = np.zeros(int(pad_s * sample_rate), dtype=np.float32)
        x = np.concatenate([pad, x, pad])
        if snr_db is not None:
            x = add_noise(x, snr_db, tone_power(amplitude), sample_rate,
                          rng=np.random.default_rng(seed))
        return x


def symbols_to_words(
    symbols: list[Symbol], profile: Profile, frame_rate: int, confidence: float
) -> list[Word]:
    words: list[Word] = []
    cur: list[str] = []
    start = end = 0

    def flush() -> None:
        if cur:
            words.append(Word(profile.render(cur), start / frame_rate, end / frame_rate, confidence))
            cur.clear()

    for s in symbols:
        if s.token == SPACE:
            flush()
            continue
        if not cur:
            start = s.start_frame
        end = s.end_frame
        cur.append(s.token)
    flush()
    return words


def pattern_units(token: str) -> float:
    """Số dit của một mẫu: dot 1, dash 3, khoảng trong chữ 1."""
    return sum(1.0 if c == "." else 3.0 for c in token) + (len(token) - 1)


def estimate_wpm_from_emissions(emissions: list[tuple[str, int, float]], frame_rate: int) -> float | None:
    """emissions: (token, khung đầu vào lúc phát ra, xác suất). Chia số khung cho tổng dit lý thuyết."""
    items = [(t, f) for t, f, _ in emissions]
    if len([t for t, _ in items if t != SPACE]) < 2:
        return None
    units = 0.0
    for t, _ in items[:-1]:
        units += 4.0 if t == SPACE else pattern_units(t) + 3.0
    span = items[-1][1] - items[0][1]
    if units <= 0 or span <= 0:
        return None
    return 1.2 * frame_rate / (span / units)


def emissions_to_words(
    emissions: list[tuple[str, int, float]], profile: Profile, frame_rate: int, end_frame: int
) -> list[Word]:
    words: list[Word] = []
    cur: list[str] = []
    probs: list[float] = []
    start = 0
    for tok, f, p in list(emissions) + [(SPACE, end_frame, 1.0)]:
        if tok == SPACE:
            if cur:
                conf = float(np.exp(np.mean(np.log(np.maximum(probs, 1e-6)))))
                words.append(Word(profile.render(cur), start / frame_rate, f / frame_rate, conf))
                cur, probs = [], []
            continue
        if not cur:
            start = f
        cur.append(tok)
        probs.append(p)
    return words


class Decoder:
    def __init__(
        self, profile: str | Profile = "en", engine: str = "baseline", model_path: Path | None = None,
        fallback: bool = True,
    ) -> None:
        self.profile = _resolve_profile(profile)
        self.engine = engine
        self.fallback = fallback
        self._baseline = BaselineDecoder()
        self._model = None
        if engine == "onnx":
            from morsedesk.model.onnx_runner import OnnxAcousticModel

            self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
            self._model = OnnxAcousticModel(self.model_path)
        elif engine != "baseline":
            raise NotImplementedError(f"engine chưa hỗ trợ: {engine}")

    def _empty(self, warnings: list[str]) -> DecodeResult:
        return DecodeResult("", [], None, None, None, self.profile.id, {}, warnings, self.engine)

    def decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> DecodeResult:
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        est = estimate_tone(x)
        if not est.has_signal or est.f0_hz is None:
            return self._empty(["không có tín hiệu Morse trong đoạn âm thanh"])
        warnings: list[str] = []
        if est.second_peak_hz is not None:
            warnings.append(
                f"phát hiện tone thứ hai tại {est.second_peak_hz:.0f} Hz, đang bám {est.f0_hz:.0f} Hz"
            )
        if self.engine == "baseline":
            return self._decode_baseline(x, est, warnings)
        return self._decode_onnx(x, est, warnings)

    def _baseline_tokens(self, x: np.ndarray, f0_hz: float):
        return self._baseline.decode_envelope(mix_envelope(x, f0_hz))

    def _decode_baseline(self, x, est, warnings: list[str]) -> DecodeResult:
        res = self._baseline_tokens(x, est.f0_hz)
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        words = symbols_to_words(res.symbols, self.profile, FRAME_RATE, confidence)
        return DecodeResult(" ".join(w.text for w in words), words, res.wpm, est.f0_hz, est.snr_db,
                            self.profile.id, {}, warnings, "baseline")

    def _log_probs(self, x: np.ndarray, f0_hz: float) -> tuple[np.ndarray, int]:
        from morsedesk.model.chunker import run_chunked, run_chunked_audio

        if getattr(self._model, "feature_mode", "clip") == "window":
            return run_chunked_audio(self._model, x, f0_hint=f0_hz)
        feats = compute_features(x, f0_hz)
        return run_chunked(self._model, feats), len(feats)

    def _decode_onnx(self, x, est, warnings: list[str]) -> DecodeResult:
        logp, n_in = self._log_probs(x, est.f0_hz)
        stride = self._model.time_stride
        emissions = [(VOCAB.token(i), f * stride, p)
                     for i, f, p in greedy_decode_with_frames(logp, VOCAB.blank_id)]
        while emissions and emissions[0][0] == SPACE:
            emissions.pop(0)
        while emissions and emissions[-1][0] == SPACE:
            emissions.pop()
        words = emissions_to_words(emissions, self.profile, FRAME_RATE, n_in)
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append("độ tin cậy thấp, kèm kết quả bộ giải mã DSP")
            if self.fallback:
                fallback_text = self.profile.render(self._baseline_tokens(x, est.f0_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, FRAME_RATE), est.f0_hz, est.snr_db,
                            self.profile.id, {}, warnings, "onnx", fallback_text)

    def decode_file(self, path: str | Path) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr)
