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
from morsedesk.lm.beam import BeamParams, Hypothesis, beam_search
from morsedesk.lm.langid import detect
from morsedesk.lm.ngram import CharNGramLM
from morsedesk.lm.profile import Profile, list_profiles, load_profile
from morsedesk.lm.store import LMStore
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
        raise ValueError("profile 'auto' chỉ dùng cho Decoder")
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


def _group_words(items: list[tuple[str, str, int, float]], frame_rate: int, end_frame: int) -> list[Word]:
    """items: (token, chữ hiển thị, khung đầu vào, xác suất). Tách từ tại SPACE; tin cậy = trung bình nhân."""
    words: list[Word] = []
    cur: list[str] = []
    probs: list[float] = []
    start = 0
    for tok, letter, f, p in list(items) + [(SPACE, " ", end_frame, 1.0)]:
        if tok == SPACE:
            if cur:
                conf = float(np.exp(np.mean(np.log(np.maximum(probs, 1e-6)))))
                words.append(Word("".join(cur), start / frame_rate, f / frame_rate, conf))
                cur, probs = [], []
            continue
        if not cur:
            start = f
        cur.append(letter)
        probs.append(p)
    return words


def emissions_to_words(
    emissions: list[tuple[str, int, float]], profile: Profile, frame_rate: int, end_frame: int
) -> list[Word]:
    return _group_words([(tok, profile.render([tok]), f, p) for tok, f, p in emissions], frame_rate, end_frame)


def hypothesis_to_words(hyp: Hypothesis, frame_rate: int, stride: int, end_frame: int, offset: int = 0) -> list[Word]:
    """Từ từ giả thuyết beam: chữ đã chọn theo LM; khung token = (offset + khung ra) * stride."""
    items = [(tok, letter, (offset + f) * stride, p)
             for tok, letter, f, p in zip(hyp.tokens, hyp.letters, hyp.frames, hyp.probs, strict=True)]
    return _group_words(items, frame_rate, end_frame)


def _strip_spaces(emissions: list[tuple[str, int, float]]) -> list[tuple[str, int, float]]:
    i, j = 0, len(emissions)
    while i < j and emissions[i][0] == SPACE:
        i += 1
    while j > i and emissions[j - 1][0] == SPACE:
        j -= 1
    return emissions[i:j]


class Decoder:
    def __init__(
        self, profile: str | Profile = "en", engine: str = "baseline", model_path: Path | None = None,
        fallback: bool = True, lm: bool = True, beam: int = 64, lm_dir: Path | None = None,
        acoustic_model=None,
    ) -> None:
        self.auto = isinstance(profile, str) and profile == "auto"
        self.profile: Profile | None = None if self.auto else _resolve_profile(profile)
        self.engine = engine
        self.fallback = fallback
        self.lm_enabled = bool(lm)
        self.beam_params = BeamParams(beam=int(beam))
        self._baseline = BaselineDecoder()
        self._model = acoustic_model
        if engine == "onnx":
            if self._model is None:
                from morsedesk.model.onnx_runner import OnnxAcousticModel

                self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
                self._model = OnnxAcousticModel(self.model_path)
        elif engine != "baseline":
            raise NotImplementedError(f"engine chưa hỗ trợ: {engine}")
        if self.auto and not self.lm_enabled:
            raise ValueError("profile 'auto' cần mô hình ngôn ngữ; bỏ --no-lm hoặc chọn profile cụ thể")
        self._store = LMStore(lm_dir)
        if self.profile is not None:
            self._store.register(self.profile)
        self.candidates: list[str] = list_profiles() if self.auto else [self.profile.id]
        self._profiles: dict[str, Profile] = {pid: self._store.get_profile(pid) for pid in self.candidates}
        self._lms: dict[str, CharNGramLM] = {}
        if self.lm_enabled and (self.auto or engine == "onnx"):
            for pid in self.candidates:
                self._lms[pid] = self._store.get(pid)   # thiếu file -> FileNotFoundError nêu đường dẫn

    def _empty(self, warnings: list[str]) -> DecodeResult:
        lang = self.profile.id if self.profile is not None else ""
        return DecodeResult("", [], None, None, None, lang, {}, warnings, self.engine)

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

    def _pick_profile_for_tokens(self, tokens: list[str]) -> tuple[Profile, dict[str, float]]:
        """Chế độ auto với engine baseline: chấm văn bản render qua từng profile bằng LM."""
        if not self.auto:
            return self.profile, {}
        if not tokens:
            return self._profiles[self.candidates[0]], {}
        scores = {}
        for pid in self.candidates:
            text = self._profiles[pid].render(tokens)
            scores[pid] = self._lms[pid].sentence_logprob(text) / (len(text) + 1)
        best = max(scores, key=scores.get)
        return self._profiles[best], scores

    def _decode_baseline(self, x, est, warnings: list[str]) -> DecodeResult:
        res = self._baseline_tokens(x, est.f0_hz)
        profile, scores = self._pick_profile_for_tokens(res.tokens)
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        words = symbols_to_words(res.symbols, profile, FRAME_RATE, confidence)
        # auto mà không giải mã được token nào (scores rỗng) -> language rỗng, vẫn dùng profile đầu để hiển thị
        lang = profile.id if (not self.auto or scores) else ""
        return DecodeResult(" ".join(w.text for w in words), words, res.wpm, est.f0_hz, est.snr_db,
                            lang, scores, warnings, "baseline")

    def _log_probs(self, x: np.ndarray, f0_hz: float) -> tuple[np.ndarray, int]:
        from morsedesk.model.chunker import run_chunked, run_chunked_audio

        if getattr(self._model, "feature_mode", "clip") == "window":
            return run_chunked_audio(self._model, x, f0_hint=f0_hz)
        feats = compute_features(x, f0_hz)
        return run_chunked(self._model, feats), len(feats)

    def _beam_words(self, logp: np.ndarray, stride: int, n_in: int):
        if not self.auto:
            hyp = beam_search(logp, self.profile, self._lms[self.profile.id], self.beam_params)[0]
            emissions = _strip_spaces([(tok, f * stride, p) for tok, f, p in hyp.emissions])
            return hypothesis_to_words(hyp, FRAME_RATE, stride, n_in), emissions, self.profile, {}
        res = detect(logp, self._profiles, self._lms, self.beam_params)
        words: list[Word] = []
        emissions: list[tuple[str, int, float]] = []
        for seg in res.segments:
            if seg.profile_id is None:
                continue
            hyp = seg.best[seg.profile_id]
            end_in = min(n_in, seg.end * stride)
            words += hypothesis_to_words(hyp, FRAME_RATE, stride, end_in, offset=seg.start)
            emissions += [(tok, (seg.start + f) * stride, p) for tok, f, p in hyp.emissions]
        return words, _strip_spaces(emissions), self._profiles[res.profile_id], res.scores

    def _decode_onnx(self, x, est, warnings: list[str]) -> DecodeResult:
        logp, n_in = self._log_probs(x, est.f0_hz)
        stride = int(self._model.time_stride)
        if self.lm_enabled:
            words, emissions, profile, scores = self._beam_words(logp, stride, n_in)
        else:
            profile, scores = self.profile, {}
            emissions = _strip_spaces([(VOCAB.token(i), f * stride, p)
                                       for i, f, p in greedy_decode_with_frames(logp, VOCAB.blank_id)])
            words = emissions_to_words(emissions, profile, FRAME_RATE, n_in)
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append("độ tin cậy thấp, kèm kết quả bộ giải mã DSP")
            if self.fallback:
                fallback_text = profile.render(self._baseline_tokens(x, est.f0_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        # auto mà detect() không ra điểm cho profile nào (scores rỗng) -> language rỗng
        lang = profile.id if (not self.auto or scores) else ""
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, FRAME_RATE), est.f0_hz, est.snr_db,
                            lang, scores, warnings, "onnx", fallback_text)

    def decode_file(self, path: str | Path) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr)
