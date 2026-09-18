"""Giao diện ổn định cho GUI và CLI. GUI/CLI chỉ dùng Encoder, Decoder, DecodeResult."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio, resample
from morsedesk.constants import FRAME_RATE, SAMPLE_RATE
from morsedesk.dsp.baseline import BaselineDecoder, Symbol
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.vocab import SPACE

LOW_CONFIDENCE = 0.6


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


class Decoder:
    def __init__(
        self, profile: str | Profile = "en", engine: str = "baseline", model_path: Path | None = None
    ) -> None:
        self.profile = _resolve_profile(profile)
        self.engine = engine
        self.model_path = model_path
        if engine != "baseline":
            raise NotImplementedError(f"engine chưa hỗ trợ: {engine}")
        self._baseline = BaselineDecoder()

    def _empty(self, warnings: list[str]) -> DecodeResult:
        return DecodeResult("", [], None, None, None, self.profile.id, {}, warnings, self.engine)

    def decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> DecodeResult:
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        res, est = self._baseline.decode_audio(x)
        if not est.has_signal or est.f0_hz is None:
            return self._empty(["không có tín hiệu Morse trong đoạn âm thanh"])
        warnings: list[str] = []
        if est.second_peak_hz is not None:
            warnings.append(
                f"phát hiện tone thứ hai tại {est.second_peak_hz:.0f} Hz, đang bám {est.f0_hz:.0f} Hz"
            )
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        words = symbols_to_words(res.symbols, self.profile, FRAME_RATE, confidence)
        return DecodeResult(
            text=" ".join(w.text for w in words),
            words=words,
            wpm=res.wpm,
            tone_hz=est.f0_hz,
            snr_db=est.snr_db,
            language=self.profile.id,
            language_scores={},
            warnings=warnings,
            engine=self.engine,
        )

    def decode_file(self, path: str | Path) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr)
