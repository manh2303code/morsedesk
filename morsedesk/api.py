"""Giao diện ổn định cho GUI và CLI. GUI/CLI chỉ dùng Encoder, Decoder, DecodeResult."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio, resample
from morsedesk.constants import FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.dsp.baseline import BaselineDecoder, Symbol
from morsedesk.dsp.dither import dither_to_ceiling
from morsedesk.dsp.frontend import (
    Window,
    compute_features,
    compute_features_windowed,
    mix_envelope,
    window_cfg,
)
from morsedesk.dsp.selection import SNR_OUT_OF_RANGE_DB, prefer_dsp
from morsedesk.dsp.tone import ToneEstimate, estimate_tone, fallback_tone_hz
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
from morsedesk.progress import DecodeProgress
from morsedesk.warnings import DecodeWarning, WarningCode, warn

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
    # Song song với `warnings`: cùng thứ tự, cùng số phần tử. `warnings` là tiếng Việt cho CLI và
    # log; `warning_codes` là mã ổn định để giao diện dịch sang en/ru/kk (CP-10).
    warning_codes: list[DecodeWarning] = field(default_factory=list)
    # Đường thực sự sinh ra `text`: "model" như thường lệ, hoặc "dsp" khi tín hiệu sạch hơn dải
    # huấn luyện và bộ giải mã DSP đo được tốt hơn hẳn (xem morsedesk/dsp/selection.py).
    decoded_by: str = "model"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _finite_snr(v: float | None) -> bool:
    return v is not None and math.isfinite(float(v))


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
        # tau AGC lấy từ metadata model (mặc định 1,0 cho baseline/deepcw hoặc model cũ không khai báo)
        self.feature_cfg = window_cfg(float(getattr(self._model, "agc_tau_s", 1.0)))

    @staticmethod
    def lm_available(lm_dir: Path | None = None) -> bool:
        """Có đủ file LM cho mọi profile chưa (GUI/CLI hỏi trước khi bật auto hoặc engine onnx)."""
        store = LMStore(lm_dir)
        return all(store.available(pid) for pid in list_profiles())

    def _empty(self, warnings: list[DecodeWarning]) -> DecodeResult:
        lang = self.profile.id if self.profile is not None else ""
        return DecodeResult("", [], None, None, None, lang, {}, [w.vi() for w in warnings],
                            self.engine, warning_codes=list(warnings))

    def _windowed(self) -> bool:
        return self.engine == "onnx" and getattr(self._model, "feature_mode", "clip") == "window"

    def decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE,
                     progress: DecodeProgress | None = None) -> DecodeResult:
        """Ước lượng tone toàn clip chỉ là gợi ý ở chế độ 'window': clip dài chủ yếu là nhiễu vẫn
        giải mã được nếu có cửa sổ 4 s nào dò ra tone (spec §3.1)."""
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        est = estimate_tone(x)
        tone_hz = est.f0_hz if est.has_signal else None
        # Mô hình âm thanh chỉ từng thấy SNR -6..25 dB. Bản ghi thật của ARRL W1AW đo 61,7 dB và
        # mô hình trả về rác trên chính loại bản ghi đó, trong khi thêm nhiễu cho bẩn đi thì nó
        # đọc được ngay (CER 89,8 % -> 28,9 % trên clip đầu của T2). Chỉ đường mô hình dùng bản
        # đã trộn nhiễu; bộ giải mã DSP dự phòng và mọi số báo cáo vẫn theo tín hiệu gốc, và
        # không clip nào của T1 vượt trần nên bộ đo cũ không đổi.
        x_model = (dither_to_ceiling(x, est.snr_db if est.has_signal else None)
                   if self.engine == "onnx" else x)
        windows: list[Window] | None = None
        if self._windowed():
            windows = compute_features_windowed(x_model, tone_hz, cfg=self.feature_cfg)
            if tone_hz is None:                     # toàn clip không dò ra tone -> cửa sổ có tín hiệu đầu tiên
                signal = next((w for w in windows if w.has_signal), None)
                tone_hz = signal.f0_hz if signal is not None else None
        # Engine `deepcw` nghe cả dải 400-1200 Hz và không dùng ước lượng tone, nên không được
        # chặn nó ở đây: đo được 15/167 clip `en` của T1 (SNR 0-3 dB, phần lớn qsb) bị cổng này
        # trả rỗng dù DeepCW giải mã được, làm CER xấu từ 22,9 % lên 27,2 %.
        guessed_tone = False
        if tone_hz is None and self.engine == "onnx":
            # Model âm thanh được huấn luyện trên đúng loại nhiễu này; bỏ cuộc là chắc chắn sai
            # (CER 1,0), còn đoán tone theo đỉnh phổ đo được 74,8 % trên đúng nhóm clip đó.
            # 29/500 clip vùng gate của T1 rơi vào đây, tương đương 1,46 điểm CER.
            tone_hz = fallback_tone_hz(x_model)
            guessed_tone = tone_hz is not None
            if guessed_tone and windows is not None:
                # dựng lại đặc trưng theo tone đoán; giữ nguyên cfg (đặc biệt agc_tau_s) như lần tính đầu
                windows = compute_features_windowed(x_model, tone_hz, cfg=self.feature_cfg)
        if tone_hz is None and self.engine != "deepcw":
            return self._empty([warn(WarningCode.NO_SIGNAL)])
        warnings = self._tone_warnings(est)
        if guessed_tone:
            warnings.append(warn(WarningCode.GUESSED_TONE))
        snr_db = est.snr_db if est.has_signal else None
        if self.engine in ("baseline", "deepcw"):
            # Hai engine này không chia cửa sổ nên chỉ có một bước; vẫn gọi `step` để bên gọi
            # hủy được trước khi vào đoạn tính nặng.
            if progress is not None:
                progress.step(1, 1)
            if self.engine == "baseline":
                return self._decode_baseline(x, tone_hz, snr_db, warnings)
            return self._decode_deepcw(x, tone_hz, snr_db, warnings)
        # chế độ 'clip' gọi đúng hai đối số: test thay `_log_probs` bằng hàm hai tham số
        logp, n_in = (self._log_probs(x_model, tone_hz, progress=progress) if windows is None
                      else self._log_probs(x_model, tone_hz, windows, progress=progress))
        return self._decode_onnx(x, logp, n_in, tone_hz, snr_db, warnings)

    @staticmethod
    def _tone_warnings(est: ToneEstimate) -> list[DecodeWarning]:
        if not est.has_signal or est.second_peak_hz is None:
            return []
        return [warn(WarningCode.SECOND_TONE, second_hz=est.second_peak_hz, tracked_hz=est.f0_hz)]

    def _baseline_tokens(self, x: np.ndarray, f0_hz: float):
        return self._baseline.decode_envelope(mix_envelope(x, f0_hz))

    def _decode_baseline(self, x, tone_hz: float, snr_db: float | None,
                         warnings: list[DecodeWarning]) -> DecodeResult:
        res = self._baseline_tokens(x, tone_hz)
        profile, scores, letters = self.profile, {}, None
        if self.auto:                               # cùng thuật toán langid với engine onnx (spec §2.4)
            det = detect_tokens(res.tokens, self._profiles, self._lms, self.beam_params)
            profile, scores = self._profiles[det.profile_id], det.scores
            letters = beam_letters(res.tokens, det.profile_id, det)
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append(warn(WarningCode.LOW_CONFIDENCE))
        words = symbols_to_words(res.symbols, profile, FRAME_RATE, confidence, letters)
        # auto mà không giải mã được token nào (scores rỗng) -> language rỗng, vẫn dùng profile đầu để hiển thị
        lang = profile.id if (not self.auto or scores) else ""
        return DecodeResult(" ".join(w.text for w in words), words, res.wpm, tone_hz, snr_db,
                            lang, scores, [w.vi() for w in warnings], "baseline",
                            warning_codes=list(warnings))

    def _log_probs(self, x: np.ndarray, f0_hz: float, windows: list[Window] | None = None,
                   progress: DecodeProgress | None = None) -> tuple[np.ndarray, int]:
        """Nơi duy nhất biến âm thanh thành log-prob. `windows`: đặc trưng cửa sổ đã tính sẵn."""
        from morsedesk.model.chunker import run_chunked, run_chunked_audio, run_chunked_windows

        if getattr(self._model, "feature_mode", "clip") == "window":
            if windows is None:
                return run_chunked_audio(self._model, x, f0_hint=f0_hz, cfg=self.feature_cfg,
                                         progress=progress)
            n_frames = len(x) // HOP
            return run_chunked_windows(self._model, windows, n_frames, progress), n_frames
        feats = compute_features(x, f0_hz)
        return run_chunked(self._model, feats, progress=progress), len(feats)

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

    def _decode_deepcw(self, x: np.ndarray, tone_hz: float | None, snr_db: float | None,
                       warnings: list[DecodeWarning]) -> DecodeResult:
        """`tone_hz` có thể là None: DeepCW không cần tone, chỉ fallback DSP và báo cáo mới cần.

        Không dò được tone mà model cũng không ra chữ nào thì mới coi là không có tín hiệu, giữ
        đúng spec §7 "không bịa chữ".
        """
        words, emissions, frame_rate = self._deepcw_words(x)
        if not words and tone_hz is None:
            return self._empty([warn(WarningCode.NO_SIGNAL)])
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append(warn(WarningCode.LOW_CONFIDENCE_WITH_DSP))
            if self.fallback and tone_hz is not None:   # bộ giải mã DSP bắt buộc phải có tone
                fallback_text = self.profile.render(self._baseline_tokens(x, tone_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append(warn(WarningCode.LOW_CONFIDENCE))
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, frame_rate), tone_hz, snr_db,
                            self.profile.id, {}, [w.vi() for w in warnings], "deepcw",
                            fallback_text, warning_codes=list(warnings))

    def _letters_for_tokens(self, tokens: list[str], profile: Profile) -> list[str] | None:
        """Chữ do mô hình ngôn ngữ chọn cho từng token; None khi không dùng được.

        Dùng khi lấy phân đoạn của bộ DSP trên tín hiệu sạch: bộ DSP chỉ biết mẫu chấm gạch, còn
        việc chọn giữa А và Ә là của LM. Trả None nếu không bật LM, không có LM cho profile này,
        hoặc chuỗi token mà beam đi qua không khớp — khi đó bên gọi tự quyết.
        """
        if not tokens or not self.lm_enabled:
            return None
        lm = self._lms.get(profile.id)
        if lm is None:
            return None
        det = detect_tokens(tokens, {profile.id: profile}, {profile.id: lm}, self.beam_params)
        return beam_letters(tokens, profile.id, det)

    def _decode_onnx(self, x, logp: np.ndarray, n_in: int, tone_hz: float, snr_db: float | None,
                     warnings: list[DecodeWarning]) -> DecodeResult:
        stride = int(self._model.time_stride)
        if self.lm_enabled:
            words, emissions, profile, scores = self._beam_words(logp, stride, n_in)
        else:
            profile, scores = self.profile, {}
            emissions = _strip_spaces([(VOCAB.token(i), f * stride, p)
                                       for i, f, p in greedy_decode_with_frames(logp, VOCAB.blank_id)])
            words = emissions_to_words(emissions, profile, FRAME_RATE, n_in)
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        # Tín hiệu sạch hơn dải huấn luyện: bộ DSP đo được TỐT HƠN HẲN mô hình trên đúng loại
        # này (T2 bản ghi thật: DSP 4,0 % so với mô hình 24,2 %), nên nếu timing cũng khớp thì
        # lấy kết quả của nó và để kết quả mô hình xuống dòng dự phòng. Chỉ chạy bộ DSP khi SNR
        # đã vượt ngưỡng, để clip bình thường không phải trả thêm chi phí nào.
        if self.fallback and _finite_snr(snr_db) and float(snr_db) > SNR_OUT_OF_RANGE_DB:
            dsp = self._baseline_tokens(x, tone_hz)
            # Mẫu mơ hồ (bảng Kazakh giải `.-` ra А hoặc Ә) không buộc phải bỏ đường DSP: giữ
            # phân đoạn chính xác mà tín hiệu sạch cho không, rồi để mô hình ngôn ngữ chọn chữ.
            # Chỉ khi không có LM mới phải nhường hẳn cho mô hình âm thanh.
            dsp_letters = self._letters_for_tokens(list(dsp.tokens), profile)
            ambiguous = (dsp_letters is None
                         and any(len(profile.map.get(tok, ())) > 1 for tok in dsp.tokens))
            if prefer_dsp(snr_db, dsp.cost, ambiguous):
                dsp_conf = float(np.exp(-dsp.cost)) if np.isfinite(dsp.cost) else 0.0
                dsp_words = symbols_to_words(dsp.symbols, profile, FRAME_RATE, dsp_conf, dsp_letters)
                lang = profile.id if (not self.auto or scores) else ""
                return DecodeResult(
                    " ".join(w.text for w in dsp_words), dsp_words, dsp.wpm, tone_hz, snr_db,
                    lang, scores, [w.vi() for w in warnings], "onnx",
                    " ".join(w.text for w in words), warning_codes=list(warnings),
                    decoded_by="dsp")
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append(warn(WarningCode.LOW_CONFIDENCE_WITH_DSP))
            if self.fallback:
                fallback_text = profile.render(self._baseline_tokens(x, tone_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append(warn(WarningCode.LOW_CONFIDENCE))
        # auto mà detect() không ra điểm cho profile nào (scores rỗng) -> language rỗng
        lang = profile.id if (not self.auto or scores) else ""
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, FRAME_RATE), tone_hz, snr_db,
                            lang, scores, [w.vi() for w in warnings], "onnx", fallback_text,
                            warning_codes=list(warnings))

    def decode_file(self, path: str | Path, progress: DecodeProgress | None = None) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr, progress=progress)
