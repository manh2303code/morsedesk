"""Giao diện ổn định cho GUI và CLI. GUI/CLI chỉ dùng Encoder, Decoder, DecodeResult."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio, resample
from morsedesk.constants import FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.dsp.baseline import BaselineDecoder, Symbol
from morsedesk.dsp.clicks import is_key_clicks
from morsedesk.dsp.dither import dither_to_ceiling
from morsedesk.dsp.frontend import (
    Window,
    compute_features,
    compute_features_windowed,
    mix_envelope,
    repad_window,
    window_cfg,
)
from morsedesk.dsp.selection import dsp_is_complete, dsp_keeps_words, dsp_result_usable, prefer_dsp
from morsedesk.dsp.tone import ToneEstimate, estimate_tone, fallback_tone_hz
from morsedesk.dsp.windowing import WINDOW_PAD_FRAMES
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.keyed import MIN_SNR_DB as KEYED_MIN_SNR_DB
from morsedesk.keyed import (
    NOT_MORSE_MAX_CONF,
    NOT_MORSE_MIN_S_WEAK,
    not_morse_clip,
    read_keying,
    reconcile,
    speechlike,
)
from morsedesk.lm.beam import BeamParams, Hypothesis, beam_search
from morsedesk.lm.langid import LangIdResult, detect, detect_tokens, split_segments
from morsedesk.lm.ngram import CharNGramLM
from morsedesk.lm.profile import Profile, list_profiles, load_profile
from morsedesk.lm.store import LMStore
from morsedesk.model.ctc import greedy_decode_with_frames
from morsedesk.model.protocol import AcousticModel
from morsedesk.model.vocab import SPACE, UNK, VOCAB
from morsedesk.numbers import analyze, letters_of, normalize_groups
from morsedesk.progress import STAGE_ACOUSTIC, STAGE_LANGUAGE, DecodeProgress, StageProgress
from morsedesk.traffic import traffic_words
from morsedesk.warnings import DecodeWarning, WarningCode, warn

LOW_CONFIDENCE = 0.6
FALLBACK_CONFIDENCE = 0.5
# Dưới mức này thì coi như không có Morse (spec §7). Chọn trên bộ DEV (seed 500000), xác nhận trên
# T1, đo 23/09 với E9 + cửa sổ 12 s:
# - 120 lần chạy đầu vào KHÔNG có Morse (nhiễu trắng/xung/lọc dải, sóng mang, 5-60 s): độ tin cậy
#   trung bình cả clip tối đa 0,113 -> ở 0,15 không lần nào lọt;
# - dev: không clip thật nào dưới 0,15 (CER +0,00); T1: 3 clip, đều `qsb` 0-3 dB vốn đã sai
#   86-92 % (CER +0,09). Ở 0,20 bắt đầu cắt clip thật trên cả hai bộ.
# Giới hạn đã biết: tín hiệu đánh phím TUẦN HOÀN hoàn hảo (vd. nhiễu điều biên đều 4 Hz) ra
# "EEEE..." với độ tin cậy ~0,99 — về mặt đường bao nó chính là Morse chữ E, không cổng nào tách được.
MIN_CLIP_CONFIDENCE = 0.15
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
    # (chữ, giây) của từng chữ trong từ — để tách/ghép nhóm số và để chế độ nghe chốt được từng chữ
    # của một "từ" dài hơn bộ đệm (dãy số liền). Không xuất ra JSON.
    chars: list = field(default_factory=list, compare=False, repr=False)
    # Xác suất của dấu cách ĐỨNG TRƯỚC từ này (1.0 nếu không biết): khoảng cách từ thật gần như luôn
    # ~1,0; dấu cách chèn nhầm giữa nhóm số gõ tay thì lưỡng lự — dùng khi ghép lại nhóm vỡ.
    space_p: float = field(default=1.0, compare=False, repr=False)


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
        d = asdict(self)
        for w in d["words"]:
            w.pop("chars", None)
        return json.dumps(d, ensure_ascii=False, indent=2)


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

    times: list[float] = []

    def flush() -> None:
        if cur:
            words.append(Word("".join(cur), start / frame_rate, end / frame_rate, confidence,
                              list(zip(cur, times, strict=True))))
            cur.clear()
            times.clear()

    for i, s in enumerate(symbols):
        if s.token == SPACE:
            flush()
            continue
        if not cur:
            start = s.start_frame
        end = s.end_frame
        cur.append(letters[i] if letters is not None else profile.render([s.token]))
        times.append(s.start_frame / frame_rate)
    flush()
    return words


def segment_profile(seg, file_profile_id: str) -> str:
    """Bảng chữ để VIẾT một đoạn: luôn là ngôn ngữ của cả file, không phải lựa chọn riêng của đoạn.

    Một bản tin thật không đổi ngôn ngữ giữa chừng. Nhưng Morse Latin và Kirin dùng chung mẫu
    (`.- -... -.-.` vừa là ABC vừa là АБЦ), nên một đoạn ngắn nhiễu nặng có thể được mô hình ngôn
    ngữ Nga chấm nhỉnh hơn dù cả file rõ là tiếng Anh — trước đây ra `CQ CQ DE R АБЦ РА А ILS`.
    Lựa chọn riêng của từng đoạn chỉ còn dùng để BỎ PHIẾU chọn ngôn ngữ cả file. Beam của mọi
    profile đã chạy sẵn trên mọi đoạn, nên việc này không tốn thêm gì.
    """
    return file_profile_id if file_profile_id in seg.best else seg.profile_id


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
    times: list[float] = []
    start = 0
    space_p, pending_space = 1.0, 1.0
    for tok, letter, f, p in list(items) + [(SPACE, " ", end_frame, 1.0)]:
        if tok == SPACE:
            if cur:
                conf = float(np.exp(np.mean(np.log(np.maximum(probs, 1e-6)))))
                words.append(Word("".join(cur), start / frame_rate, f / frame_rate, conf,
                                  list(zip(cur, times, strict=True)), space_p))
                cur, probs, times = [], [], []
            pending_space = float(p)
            continue
        if not cur:
            space_p = pending_space
            start = f
        cur.append(letter)
        probs.append(p)
        times.append(f / frame_rate)
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


def numbers_words(words: list[Word], profile: Profile) -> list[Word] | None:
    """Điện số (morsedesk/numbers.py): số viết tắt -> số, ghép/tách nhóm độ dài cố định. None nếu
    bản tin không phải điện số (không đổi gì)."""
    groups = [letters_of(w.text) for w in words]
    new_groups, sources, ctx = normalize_groups(groups, profile)
    if not ctx.numeric or (new_groups == groups):
        return None
    out: list[Word] = []
    offsets: dict[tuple[int, ...], int] = {}
    for letters, src in zip(new_groups, sources, strict=True):
        key = tuple(src)
        base = [t for k in src for _, t in words[k].chars] or [words[src[0]].start_s] * sum(
            len(groups[k]) for k in src)
        off = offsets.get(key, 0)
        times = base[off:off + len(letters)]
        offsets[key] = off + len(letters)
        if len(times) < len(letters):
            times = times + [times[-1] if times else words[src[0]].start_s] * (len(letters) - len(times))
        start = times[0] if off else words[src[0]].start_s
        last = off + len(letters) >= len(base)
        end = words[src[-1]].end_s if last else times[-1]
        conf = min(words[k].confidence for k in src)
        out.append(Word("".join(letters), start, end, conf, list(zip(letters, times, strict=True))))
    return out


def apply_keying(result: DecodeResult, x8: np.ndarray, profile: Profile) -> DecodeResult:
    """Đối chiếu với âm thanh (morsedesk/keyed.py): bỏ từ đọc ra từ giọng nói/nhạc; khi tín hiệu sạch thì
    đối chiếu từng ký tự với nhịp phím đo được (sửa ký tự, chèn ký tự bỏ sót, dấu cách)."""
    f0 = float(result.tone_hz)
    words = result.words
    env = keyed = None
    if max(w.confidence for w in words) < NOT_MORSE_MAX_CONF and len(x8) / SAMPLE_RATE >= NOT_MORSE_MIN_S_WEAK:
        env = mix_envelope(x8, f0)
        keyed = read_keying(x8, env, f0)
        if not_morse_clip(words, keyed, profile, len(x8) / SAMPLE_RATE):
            codes = list(result.warning_codes) + [warn(WarningCode.NO_SIGNAL)]
            return replace(result, words=[], text="", warnings=[w.vi() for w in codes], warning_codes=codes)
    if (result.snr_db or 0.0) >= KEYED_MIN_SNR_DB:
        if keyed is None:
            keyed = read_keying(x8, mix_envelope(x8, f0), f0)
        if keyed.stable:                        # fading: đáy fading cũng "kém chắc, không thuần tone"
            drop = speechlike(words, x8, f0)
            if any(drop):
                words = [w for w, d in zip(words, drop, strict=True) if not d]
            rec = reconcile(words, keyed, profile) if words else None
            if rec is not None:
                words = rec
    if words is result.words:
        return result
    return replace(result, words=words, text=" ".join(w.text for w in words))


def apply_traffic(result: DecodeResult, profile: Profile) -> DecodeResult:
    """Điện văn mạng (morsedesk/traffic.py): chia lại nhóm thân điện sau RMKS, số viết tắt -> số."""
    words = traffic_words(result.words, profile)
    if words is None:
        return result
    return replace(result, text=" ".join(w.text for w in words), words=words)


def apply_numbers(result: DecodeResult, profile: Profile) -> DecodeResult:
    words = numbers_words(result.words, profile)
    if words is None:
        return result
    return replace(result, text=" ".join(w.text for w in words), words=words)


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
        skip_silent_windows: bool = False, numbers: bool = True, keyed: bool = True,
    ) -> None:
        """lm_store: dùng chung LM giữa nhiều Decoder (GUI); khi có thì bỏ qua lm_dir.

        numbers: xử lý điện số (morsedesk/numbers.py — số viết tắt, nhóm độ dài cố định). Chế độ nghe
        tắt nó ở đây và làm ở StreamDecoder với ngữ cảnh cả phiên (bộ đệm ~9 s quá ít nhóm).

        keyed: đối chiếu với nhịp phím đo được (morsedesk/keyed.py). Chế độ nghe TẮT: StreamDecoder nhận
        ký tự đã chốt bằng mốc thời gian của mô hình, mà đối chiếu đổi mốc và bộ đệm cắt ngang ký tự ở hai
        đầu — đo 27/09: chữ số nhân đôi (`00000` -> `000000`), số ở chế độ nghe 0,0 -> 11,8 % lỗi.

        skip_silent_windows: cửa sổ không dò ra tone thì ép thành blank thay vì chạy mô hình.
        Chặn được chuyện mô hình đọc nhiễu nền thành chữ (30 giây nhiễu trắng thuần ra `WE ARE`),
        nhưng trên T1 nó làm CER xấu từ 9,70 % lên 13,28 % vì clip SNR thấp cũng bị vạ lây.
        Chỉ bật ở chế độ nghe trực tiếp.
        """
        self.auto = isinstance(profile, str) and profile == "auto"
        self.profile: Profile | None = None if self.auto else _resolve_profile(profile)
        self.engine = engine
        self.fallback = fallback
        self.lm_enabled = bool(lm)
        self.skip_silent_windows = bool(skip_silent_windows)
        self.numbers = bool(numbers)
        self.keyed = bool(keyed)
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
        self._auto_requested = self.auto

    def pin_language(self, profile_id: str | None) -> bool:
        """Khóa một bộ giải mã `auto` vào một ngôn ngữ (None = mở khóa, về lại `auto`).

        Dùng cho chế độ nghe: mỗi lần giải mã chỉ thấy vài giây gần nhất nên tự chọn ngôn ngữ LẠI
        mỗi lần, và dòng chữ đã chốt có thể lẫn hai bảng chữ. Khi phiên nghe đã đủ chắc chắn, khóa
        lại cho cả phần còn lại. Trả False nếu không áp dụng (bộ giải mã không phải `auto`, hoặc
        profile lạ).
        """
        if not self._auto_requested:
            return False
        if profile_id is None:
            self.auto, self.profile = True, None
            return True
        if profile_id not in self._profiles:
            return False
        self.auto, self.profile = False, self._profiles[profile_id]
        return True

    @property
    def pinned_language(self) -> str | None:
        return self.profile.id if self._auto_requested and not self.auto else None

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
                     progress: DecodeProgress | None = None, continued: bool = False) -> DecodeResult:
        """`continued`: `x` nối tiếp âm thanh đã có trước nó (bộ đệm chế độ nghe sau khi cắt phần đầu),
        nên mép đầu là mép TRONG — đệm nhiễu nền như mép giáp cửa sổ khác (frontend.repad_window)."""
        result = self._decode_array(x, sample_rate, progress, continued)
        if self.keyed and result.words and result.tone_hz:
            x8 = x if sample_rate == SAMPLE_RATE else resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
            profile = self._profiles.get(result.language) or self.profile or next(iter(self._profiles.values()))
            result = apply_keying(result, x8, profile)
        if self.numbers and result.words:
            profile = self._profiles.get(result.language) or self.profile or next(iter(self._profiles.values()))
            result = apply_numbers(apply_traffic(result, profile), profile)
        return result

    def _decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE,
                      progress: DecodeProgress | None = None, continued: bool = False) -> DecodeResult:
        """Ước lượng tone toàn clip chỉ là gợi ý ở chế độ 'window': clip dài chủ yếu là nhiễu vẫn
        giải mã được nếu có cửa sổ 4 s nào dò ra tone (spec §3.1)."""
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        est = estimate_tone(x)
        tone_hz = est.f0_hz if est.has_signal else None
        if self.engine != "deepcw" and is_key_clicks(x, f0_hz=tone_hz):
            # Chỉ có tiếng click (phím điện báo — hoặc nhiễu xung/sét), không có tone: đoán tone rồi
            # giải thì ra chữ vô nghĩa, mỗi lần một ngôn ngữ (dsp/clicks.py). Nói thật thay vì bịa chữ;
            # vẫn báo NO_SIGNAL vì nhiễu xung thuần cũng rơi vào đây (test §7 qrn).
            return self._empty([warn(WarningCode.NO_SIGNAL), warn(WarningCode.KEY_CLICKS)])
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
        # Tiến trình theo tầng, đúng tỉ trọng thời gian đo được (xem morsedesk/progress.py).
        acoustic = StageProgress(progress, *STAGE_ACOUSTIC) if progress is not None else None
        language = StageProgress(progress, *STAGE_LANGUAGE) if progress is not None else None
        # chế độ 'clip' gọi đúng hai đối số: test thay `_log_probs` bằng hàm hai tham số
        logp, n_in = (self._log_probs(x_model, tone_hz, progress=acoustic) if windows is None
                      else self._log_probs(x_model, tone_hz, windows, progress=acoustic, continued=continued))
        result = self._decode_onnx(x, logp, n_in, tone_hz, snr_db, warnings, progress=language)
        if language is not None:
            language.finish()                   # 100 % chỉ khi KẾT QUẢ CUỐI đã sẵn sàng
        return result

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
                   progress: DecodeProgress | None = None, continued: bool = False) -> tuple[np.ndarray, int]:
        """Nơi duy nhất biến âm thanh thành log-prob. `windows`: đặc trưng cửa sổ đã tính sẵn."""
        from morsedesk.model.chunker import run_chunked, run_chunked_audio, run_chunked_windows

        if getattr(self._model, "feature_mode", "clip") == "window":
            if windows is None:
                return run_chunked_audio(self._model, x, f0_hint=f0_hz, cfg=self.feature_cfg,
                                         progress=progress)
            n_frames = len(x) // HOP
            cfg = self.feature_cfg

            def pad(w: Window) -> Window:
                return repad_window(x, w, n_frames, WINDOW_PAD_FRAMES, cfg, inner_start=continued)

            return run_chunked_windows(self._model, windows, n_frames, progress,
                                       skip_silent=self.skip_silent_windows, pad=pad), n_frames
        feats = compute_features(x, f0_hz)
        return run_chunked(self._model, feats, progress=progress), len(feats)

    def _beam_words(self, logp: np.ndarray, stride: int, n_in: int, progress=None):
        if not self.auto:
            hyp = beam_search(logp, self.profile, self._lms[self.profile.id], self.beam_params,
                              progress=progress)[0]
            emissions = _strip_spaces([(tok, f * stride, p) for tok, f, p in hyp.emissions])
            return hypothesis_to_words(hyp, FRAME_RATE, stride, n_in), emissions, self.profile, {}
        segments = len(split_segments(logp, blank_id=self.beam_params.blank_id))
        staged = progress is not None and hasattr(progress, "sub") and segments > 1
        vote = progress.sub(0, segments, segments + 1) if staged else progress
        res = detect(logp, self._profiles, self._lms, self.beam_params, progress=vote)
        pid = res.profile_id
        voted = [seg for seg in res.segments if seg.profile_id is not None]
        if len(res.segments) == 1 and voted:
            # Một đoạn: beam của ngôn ngữ đã chọn chính là lượt giải cả lưới, dùng luôn.
            hyp = voted[0].best[segment_profile(voted[0], pid)]
        elif voted:
            # Nhiều đoạn (âm thanh > 30 s): các đoạn cắt đều, chỗ cắt rơi giữa nhóm chữ/số, ghép lại
            # là đẻ ra dấu cách sai ("40788 70729" -> "4078 8 7 0729"; đo 26/09 trên nhóm số gõ tay:
            # 84 % nhóm đúng so với 97 % khi biết trước ngôn ngữ). Các đoạn chỉ để BỎ PHIẾU chọn
            # ngôn ngữ; văn bản giải lại cả lưới một lượt bằng ngôn ngữ đã chọn.
            last = progress.sub(segments, segments + 1, segments + 1) if staged else None
            hyp = beam_search(logp, self._profiles[pid], self._lms[pid], self.beam_params, progress=last)[0]
        else:
            return [], [], self._profiles[pid], res.scores
        emissions = _strip_spaces([(tok, f * stride, p) for tok, f, p in hyp.emissions])
        return hypothesis_to_words(hyp, FRAME_RATE, stride, n_in), emissions, self._profiles[pid], res.scores

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
                     warnings: list[DecodeWarning], progress=None) -> DecodeResult:
        stride = int(self._model.time_stride)
        if self.lm_enabled:
            words, emissions, profile, scores = self._beam_words(logp, stride, n_in, progress)
            if words and analyze([letters_of(w.text) for w in words], profile).numeric:
                # Điện số: LM văn bản không biết gì về dãy số ngẫu nhiên, chỉ kéo mẫu mô hình đã
                # nghe về ký tự "hay gặp" hơn — đo 27/09: nhóm `(737)` ra `9737)` 21/202 lần với
                # LM, 4/202 khi đọc thẳng từ mô hình. Ngôn ngữ vẫn do LM chọn ở trên.
                emissions = _strip_spaces([(VOCAB.token(i), f * stride, p)
                                           for i, f, p in greedy_decode_with_frames(logp, VOCAB.blank_id)])
                words = emissions_to_words(emissions, profile, FRAME_RATE, n_in)
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
        # Bộ DSP nay chạy cho MỌI clip, không chỉ khi tín hiệu sạch: chi phí timing của nó là
        # phép đo cần có để quyết định, và nhánh "timing khớp gần hoàn hảo" hoạt động ở cả mức
        # nhiễu bình thường. Giá phải trả là khoảng một phần năm thời gian giải mã; đổi lại
        # 101/461 clip T1 chuyển sang đường tốt hơn và CER giảm 0,78 điểm.
        if self.fallback:
            dsp = self._baseline_tokens(x, tone_hz)
            usable = dsp_result_usable(dsp.tokens, profile)
            # Mẫu mơ hồ (bảng Kazakh giải `.-` ra А hoặc Ә) không buộc phải bỏ đường DSP: giữ
            # phân đoạn chính xác mà tín hiệu sạch cho không, rồi để mô hình ngôn ngữ chọn chữ.
            # Chỉ khi không có LM mới phải nhường hẳn cho mô hình âm thanh.
            dsp_letters = self._letters_for_tokens(list(dsp.tokens), profile) if usable else None
            ambiguous = (dsp_letters is None
                         and any(len(profile.map.get(tok, ())) > 1 for tok in dsp.tokens))
            if usable and prefer_dsp(snr_db, dsp.cost, ambiguous):
                dsp_conf = float(np.exp(-dsp.cost)) if np.isfinite(dsp.cost) else 0.0
                dsp_words = symbols_to_words(dsp.symbols, profile, FRAME_RATE, dsp_conf, dsp_letters)
                model_text = " ".join(w.text for w in words)
                # DSP ngắn hẳn mô hình = nó đã bỏ sót cả đoạn (fading). Chỉ đổi sang mô hình khi mô
                # hình đủ tin cậy; nếu không, cổng bên dưới sẽ trả RỖNG — tệ hơn giữ kết quả DSP.
                dsp_text = " ".join(w.text for w in dsp_words)
                keep_dsp = ((dsp_is_complete(dsp_text, model_text) and dsp_keeps_words(dsp_text, model_text))
                            or confidence < MIN_CLIP_CONFIDENCE)
            else:
                keep_dsp = False
            if keep_dsp:
                lang = profile.id if (not self.auto or scores) else ""
                return DecodeResult(
                    " ".join(w.text for w in dsp_words), dsp_words, dsp.wpm, tone_hz, snr_db,
                    lang, scores, [w.vi() for w in warnings], "onnx",
                    " ".join(w.text for w in words), warning_codes=list(warnings),
                    decoded_by="dsp")
        # Spec §7: không có Morse thì kết quả rỗng, không bịa chữ. Nhiễu trắng, sóng mang không
        # đánh phím, nhiễu xung đều ra "chữ" — mô hình ngôn ngữ còn gọt chúng thành thứ trông rất
        # thật (`SEE`, `73`, `CAR`) — nhưng với độ tin cậy rất thấp. Chỉ áp cho đường MÔ HÌNH:
        # đường DSP phía trên đã chỉ được chọn khi timing khớp gần hoàn hảo. Giữ tone và SNR đo
        # được: "nghe thấy một tone ở 700 Hz nhưng không đọc ra Morse" khác hẳn "không có gì".
        if confidence < MIN_CLIP_CONFIDENCE:
            warnings.append(warn(WarningCode.NO_SIGNAL))
            lang = profile.id if (not self.auto or scores) else ""
            return DecodeResult("", [], None, tone_hz, snr_db, lang, scores,
                                [w.vi() for w in warnings], "onnx", None,
                                warning_codes=list(warnings))
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
