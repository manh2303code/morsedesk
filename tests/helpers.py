"""Tiện ích dùng chung cho test: tạo audio Morse tổng hợp."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.profile import load_profile


def make_morse(
    text: str,
    profile_id: str = "en",
    wpm: float = 20.0,
    farnsworth_wpm: float | None = None,
    tone_hz: float = 700.0,
    snr_db: float | None = None,
    seed: int = 0,
    pad_s: float = 0.3,
    amplitude: float = 0.8,
) -> tuple[np.ndarray, list[str]]:
    profile = load_profile(profile_id)
    tokens = text_to_tokens(text, profile)
    elements = tokens_to_elements(tokens, TimingParams(wpm=wpm, farnsworth_wpm=farnsworth_wpm))
    audio = elements_to_audio(elements, tone_hz=tone_hz, amplitude=amplitude)
    pad = np.zeros(int(pad_s * SAMPLE_RATE), dtype=np.float32)
    audio = np.concatenate([pad, audio, pad])
    if snr_db is not None:
        audio = add_noise(audio, snr_db, tone_power(amplitude), rng=np.random.default_rng(seed))
    return audio, tokens
