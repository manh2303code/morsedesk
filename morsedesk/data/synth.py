"""SynthGenerator: sinh cặp (audio, nhãn) on-the-fly, tái lập theo seed."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.data.channel import (
    ChannelParams, apply_channel, ffmpeg_available, sample_channel_params,
)
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine, sample_keyer_params
from morsedesk.data.text import BUILTIN_WORDS, TextSampler
from morsedesk.encode.synth import elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import Element, elements_to_segments, tokens_to_elements, total_seconds
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.vocab import SPACE, VOCAB

AMPLITUDE = 0.8
MAX_SAMPLE_ROUNDS = 50


def split_words(tokens: list[str]) -> list[list[str]]:
    """Tách danh sách token trên SPACE thành các từ, bỏ qua từ rỗng."""
    words: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok == SPACE:
            if current:
                words.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        words.append(current)
    return words


def rescale_elements(elements: list[Element], target_seconds: float) -> list[Element]:
    """Co giãn đều mọi phần tử để tổng thời lượng bằng target_seconds (giữ nguyên hình dạng jitter/drift)."""
    total = total_seconds(elements)
    if total <= 0 or target_seconds <= 0:
        return elements
    k = target_seconds / total
    return [Element(e.on, e.duration * k) for e in elements]


@dataclass
class Example:
    audio: np.ndarray
    labels: list[int]
    tokens: list[str]
    text: str
    profile_id: str
    keyer: KeyerParams
    channel: ChannelParams
    f0_hz: float
    sample_rate: int

    @property
    def seconds(self) -> float:
        return len(self.audio) / self.sample_rate


@dataclass
class SynthConfig:
    profile_ids: tuple[str, ...] = ("en", "ru", "kk-cyrl-ru")
    min_seconds: float = 4.0
    max_seconds: float = 12.0
    pad_min_s: float = 0.2
    pad_max_s: float = 0.8
    corpus: dict[str, Path] | None = None
    mp3_enabled: bool = True


class SynthGenerator:
    def __init__(self, cfg: SynthConfig = SynthConfig()) -> None:
        self.cfg = cfg
        ids = set(cfg.profile_ids) | {"en"}
        self.profiles: dict[str, Profile] = {pid: load_profile(pid) for pid in ids}
        self.text = TextSampler(self.profiles, cfg.corpus)
        self._mp3 = cfg.mp3_enabled and ffmpeg_available()

    @staticmethod
    def tokens_duration(tokens: list[str], keyer: KeyerParams) -> float:
        return total_seconds(tokens_to_elements(tokens, keyer.timing()))

    def _sample_tokens(self, profile: Profile, keyer: KeyerParams, rng: np.random.Generator,
                       target_s: float) -> list[str]:
        """Ghép từng từ cho tới khi đạt target_s, không bao giờ vượt max_seconds.

        Chỉ thêm từ nào còn vừa trần; dừng khi đã đạt target_s, hoặc khi không còn từ vừa
        mà thời lượng đã >= min_seconds. Sinh tối đa MAX_SAMPLE_ROUNDS đoạn văn bản.

        Bất biến: nếu vòng lặp thêm được ít nhất một từ thì thời lượng <= max_seconds; và
        thời lượng >= min_seconds trừ khi hết MAX_SAMPLE_ROUNDS mà không tìm được từ nào vừa
        (trên thực tế gần như không xảy ra).
        """
        tokens: list[str] = []
        queue: list[list[str]] = []
        rounds = 0
        while rounds < MAX_SAMPLE_ROUNDS:
            if not queue:
                rounds += 1
                queue = split_words(text_to_tokens(self.text.sample(profile.id, rng), profile))
                continue
            word = queue.pop(0)
            cand = tokens + ([SPACE] if tokens else []) + word
            d = self.tokens_duration(cand, keyer)
            if d <= self.cfg.max_seconds:
                tokens = cand
                if d >= target_s:
                    break
            elif self.tokens_duration(tokens, keyer) >= self.cfg.min_seconds:
                break
        if not tokens:
            tokens = self._shortest_builtin_word(profile, keyer)
        return tokens

    def _shortest_builtin_word(self, profile: Profile, keyer: KeyerParams) -> list[str]:
        """Từ ngắn nhất (theo thời lượng) trong BUILTIN_WORDS của profile, dùng khi không tìm
        được từ nào vừa trần trong _sample_tokens."""
        words = [text_to_tokens(w, profile) for w in BUILTIN_WORDS[profile.id]]
        return min(words, key=lambda w: self.tokens_duration(w, keyer))

    def _random_morse(self, n: int, f0: float, rng: np.random.Generator) -> np.ndarray:
        """Tín hiệu Morse ngẫu nhiên tiếng Anh dùng làm QRM."""
        en = self.profiles["en"]
        keyer = machine(float(rng.uniform(15.0, 35.0)))
        tokens = self._sample_tokens(en, keyer, rng, n / SAMPLE_RATE)
        audio = elements_to_audio(tokens_to_elements(tokens, keyer.timing()), f0, SAMPLE_RATE, AMPLITUDE)
        reps = int(np.ceil(n / max(1, len(audio))))
        return np.tile(audio, reps)[:n]

    def generate(
        self,
        seed: int,
        profile_id: str | None = None,
        keyer: KeyerParams | None = None,
        channel: ChannelParams | None = None,
    ) -> Example:
        rng = np.random.default_rng(seed)
        pid = profile_id or self.cfg.profile_ids[int(rng.integers(len(self.cfg.profile_ids)))]
        profile = self.profiles[pid]
        keyer = keyer or sample_keyer_params(rng)
        channel = channel or sample_channel_params(rng)
        if channel.mp3_kbps and not self._mp3:
            channel = replace(channel, mp3_kbps=None)

        target = float(rng.uniform(self.cfg.min_seconds, self.cfg.max_seconds))
        tokens = self._sample_tokens(profile, keyer, rng, target)
        nominal = tokens_to_elements(tokens, keyer.timing())
        elements = rescale_elements(apply_keyer(nominal, keyer, rng), total_seconds(nominal))
        n_sig = elements_to_segments(elements, SAMPLE_RATE)[-1][2]
        t = np.arange(n_sig) / SAMPLE_RATE
        freq = channel.tone_hz + channel.tone_drift_hz_per_s * t
        signal = elements_to_audio(elements, freq, SAMPLE_RATE, AMPLITUDE)

        pad_a = np.zeros(int(rng.uniform(self.cfg.pad_min_s, self.cfg.pad_max_s) * SAMPLE_RATE), np.float32)
        pad_b = np.zeros(int(rng.uniform(self.cfg.pad_min_s, self.cfg.pad_max_s) * SAMPLE_RATE), np.float32)
        x = np.concatenate([pad_a, signal, pad_b])
        audio = apply_channel(x, channel, rng, SAMPLE_RATE, tone_power(AMPLITUDE), self._random_morse)

        return Example(
            audio=audio,
            labels=[VOCAB.id(tok) for tok in tokens],
            tokens=tokens,
            text=profile.render(tokens),
            profile_id=pid,
            keyer=keyer,
            channel=channel,
            f0_hz=channel.tone_hz,
            sample_rate=SAMPLE_RATE,
        )
