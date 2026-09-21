"""Giao diện ổn định cho GUI và CLI. GUI/CLI chỉ dùng Encoder, Decoder, DecodeResult."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio, resample
from morsedesk.constants import FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.dsp.baseline import BaselineDecoder, Symbol
from morsedesk.dsp.frontend import Window, compute_features, compute_features_windowed, mix_envelope
from morsedesk.dsp.tone import ToneEstimate, estimate_tone
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.beam import BeamParams, Hypothesis, beam_search
from morsedesk.lm.langid import LangIdResult, detect, detect_tokens
from morsedesk.lm.ngram import CharNGramLM
from morsedesk.lm.profile import Profile, list_profiles, load_profile
from morsedesk.lm.store import LMStore
from morsedesk.model.ctc import greedy_decode_with_frames
from morsedesk.model.protocol import AcousticModel
from morsedesk.model.vocab import SPACE, UNK, VOCAB

LOW_CONFIDENCE = 0.6
FALLBACK_CONFIDENCE = 0.5
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "acoustic.onnx"
DEEPCW_PROFILE = "en"
# Beam ký tự + LM `en` trên hậu nghiệm DeepCW. Task 3 đo trước/sau và chốt giá trị này.
DEEPCW_LM = True


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
    symbols: list[Symbol], profile: Profile, frame_rate: int, confidence: float,
    letters: list[str] | None = None,
) -> list[Word]:
    """`letters`: chữ beam/LM đã chọn cho từng symbol (cùng độ dài); None -> chữ đầu của profile."""
    words: list[Word] = []
    cur: list[str] = []
    start = end = 0

    def flush() -> None:
        if cur:
            words.append(Word("".join(cur), start / frame_rate, end / frame_rate, confidence))
            cur.clear()

    for i, s in enumerate(symbols):
        if s.token == SPACE:
            flush()
            continue
        if not cur:
            start = s.start_frame
        end = s.end_frame
        cur.append(letters[i] if letters is not None else profile.render([s.token]))
    flush()
    return words


def beam_letters(tokens: list[str], profile_id: str, res: LangIdResult) -> list[str] | None:
    """Chữ beam đã chọn cho từng token của `res`; None nếu chuỗi token các đoạn không khớp `tokens`."""
    seq: list[str] = []
    letters: list[str] = []
    for seg in res.segments:
        hyp = seg.best.get(profile_id)
        if hyp is None:
            return None
        seq += list(hyp.tokens)
        letters += list(hyp.letters)
    return letters if seq == tokens else None


def pattern_units(token: str) -> float:
    """Số dit của một mẫu: dot 1, dash 3, khoảng trong chữ 1."""
    return sum(1.0 if c == "." else 3.0 for c in token) + (len(token) - 1)


def estimate_wpm_from_emissions(emissions: list[tuple[str, int, float]], frame_rate: float) -> float | None:
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
        acoustic_model: AcousticModel | None = None, lm_store: LMStore | None = None,
    ) -> None:
        """lm_store: dùng chung LM giữa nhiều Decoder (GUI); khi có thì bỏ qua lm_dir."""
        self.auto = isinstance(profile, str) and profile == "auto"
        self.profile: Profile | None = None if self.auto else _resolve_profile(profile)
        self.engine = engine
        self.fallback = fallback
        self.lm_enabled = bool(lm)
        self.beam_params = BeamParams(beam=int(beam))
        self._baseline = BaselineDecoder()
        self._model: AcousticModel | None = acoustic_model
        self.model_path: Path | None = None     # chỉ đặt khi tự nạp model ONNX từ đĩa
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
        if self.auto and not self.lm_enabled:
            raise ValueError("profile 'auto' cần mô hình ngôn ngữ; bỏ --no-lm hoặc chọn profile cụ thể")
        self._store = lm_store if lm_store is not None else LMStore(lm_dir)
        if self.profile is not None:
            self._store.register(self.profile)
        self.candidates: list[str] = list_profiles() if self.auto else [self.profile.id]
        self._profiles: dict[str, Profile] = {pid: self._store.get_profile(pid) for pid in self.candidates}
        self._lms: dict[str, CharNGramLM] = {}
        if self.lm_enabled and (self.auto or engine in ("onnx", "deepcw")):
            for pid in self.candidates:
                self._lms[pid] = self._store.get(pid)   # thiếu file -> FileNotFoundError nêu đường dẫn

    @staticmethod
    def lm_available(lm_dir: Path | None = None) -> bool:
        """Có đủ file LM cho mọi profile chưa (GUI/CLI hỏi trước khi bật auto hoặc engine onnx)."""
        store = LMStore(lm_dir)
        return all(store.available(pid) for pid in list_profiles())

    def _empty(self, warnings: list[str]) -> DecodeResult:
        lang = self.profile.id if self.profile is not None else ""
        return DecodeResult("", [], None, None, None, lang, {}, warnings, self.engine)

    def _windowed(self) -> bool:
        return self.engine == "onnx" and getattr(self._model, "feature_mode", "clip") == "window"

    def decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> DecodeResult:
        """Ước lượng tone toàn clip chỉ là gợi ý ở chế độ 'window': clip dài chủ yếu là nhiễu vẫn
        giải mã được nếu có cửa sổ 4 s nào dò ra tone (spec §3.1)."""
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        est = estimate_tone(x)
        tone_hz = est.f0_hz if est.has_signal else None
        windows: list[Window] | None = None
        if self._windowed():
            windows = compute_features_windowed(x, tone_hz)
            if tone_hz is None:                     # toàn clip không dò ra tone -> cửa sổ có tín hiệu đầu tiên
                signal = next((w for w in windows if w.has_signal), None)
                tone_hz = signal.f0_hz if signal is not None else None
        # Engine `deepcw` nghe cả dải 400-1200 Hz và không dùng ước lượng tone, nên không được
        # chặn nó ở đây: đo được 15/167 clip `en` của T1 (SNR 0-3 dB, phần lớn qsb) bị cổng này
        # trả rỗng dù DeepCW giải mã được, làm CER xấu từ 22,9 % lên 27,2 %.
        if tone_hz is None and self.engine != "deepcw":
            return self._empty(["không có tín hiệu Morse trong đoạn âm thanh"])
        warnings = self._tone_warnings(est)
        snr_db = est.snr_db if est.has_signal else None
        if self.engine == "baseline":
            return self._decode_baseline(x, tone_hz, snr_db, warnings)
        if self.engine == "deepcw":
            return self._decode_deepcw(x, tone_hz, snr_db, warnings)
        # chế độ 'clip' gọi đúng hai đối số: test thay `_log_probs` bằng hàm hai tham số
        logp, n_in = self._log_probs(x, tone_hz) if windows is None else self._log_probs(x, tone_hz, windows)
        return self._decode_onnx(x, logp, n_in, tone_hz, snr_db, warnings)

    @staticmethod
    def _tone_warnings(est: ToneEstimate) -> list[str]:
        if not est.has_signal or est.second_peak_hz is None:
            return []
        return [f"phát hiện tone thứ hai tại {est.second_peak_hz:.0f} Hz, đang bám {est.f0_hz:.0f} Hz"]

    def _baseline_tokens(self, x: np.ndarray, f0_hz: float):
        return self._baseline.decode_envelope(mix_envelope(x, f0_hz))

    def _decode_baseline(self, x, tone_hz: float, snr_db: float | None,
                         warnings: list[str]) -> DecodeResult:
        res = self._baseline_tokens(x, tone_hz)
        profile, scores, letters = self.profile, {}, None
        if self.auto:                               # cùng thuật toán langid với engine onnx (spec §2.4)
            det = detect_tokens(res.tokens, self._profiles, self._lms, self.beam_params)
            profile, scores = self._profiles[det.profile_id], det.scores
            letters = beam_letters(res.tokens, det.profile_id, det)
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        words = symbols_to_words(res.symbols, profile, FRAME_RATE, confidence, letters)
        # auto mà không giải mã được token nào (scores rỗng) -> language rỗng, vẫn dùng profile đầu để hiển thị
        lang = profile.id if (not self.auto or scores) else ""
        return DecodeResult(" ".join(w.text for w in words), words, res.wpm, tone_hz, snr_db,
                            lang, scores, warnings, "baseline")

    def _log_probs(self, x: np.ndarray, f0_hz: float,
                   windows: list[Window] | None = None) -> tuple[np.ndarray, int]:
        """Nơi duy nhất biến âm thanh thành log-prob. `windows`: đặc trưng cửa sổ đã tính sẵn."""
        from morsedesk.model.chunker import run_chunked, run_chunked_audio, run_chunked_windows

        if getattr(self._model, "feature_mode", "clip") == "window":
            if windows is None:
                return run_chunked_audio(self._model, x, f0_hint=f0_hz)
            n_frames = len(x) // HOP
            return run_chunked_windows(self._model, windows, n_frames), n_frames
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

    def _decode_deepcw(self, x: np.ndarray, tone_hz: float | None, snr_db: float | None,
                       warnings: list[str]) -> DecodeResult:
        """`tone_hz` có thể là None: DeepCW không cần tone, chỉ fallback DSP và báo cáo mới cần.

        Không dò được tone mà model cũng không ra chữ nào thì mới coi là không có tín hiệu, giữ
        đúng spec §7 "không bịa chữ".
        """
        words, emissions, frame_rate = self._deepcw_words(x)
        if not words and tone_hz is None:
            return self._empty(["không có tín hiệu Morse trong đoạn âm thanh"])
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append("độ tin cậy thấp, kèm kết quả bộ giải mã DSP")
            if self.fallback and tone_hz is not None:   # bộ giải mã DSP bắt buộc phải có tone
                fallback_text = self.profile.render(self._baseline_tokens(x, tone_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, frame_rate), tone_hz, snr_db,
                            self.profile.id, {}, warnings, "deepcw", fallback_text)

    def _decode_onnx(self, x, logp: np.ndarray, n_in: int, tone_hz: float, snr_db: float | None,
                     warnings: list[str]) -> DecodeResult:
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
                fallback_text = profile.render(self._baseline_tokens(x, tone_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        # auto mà detect() không ra điểm cho profile nào (scores rỗng) -> language rỗng
        lang = profile.id if (not self.auto or scores) else ""
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, FRAME_RATE), tone_hz, snr_db,
                            lang, scores, warnings, "onnx", fallback_text)

    def decode_file(self, path: str | Path) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr)
