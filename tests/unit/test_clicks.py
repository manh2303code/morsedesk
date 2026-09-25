"""Tiếng click của phím điện báo (không có tone): nhận ra, và KHÔNG bịa chữ (spec §7).

Bản ghi thật của người dùng (25/09, "Morse code key typing — Russian training — 1930s") từng ra
"TENE УО ТЕКЕТАРТТА … MORE EEL TO ЕЕ НЕ" — chữ vô nghĩa lẫn hai bảng chữ. Ở đây dựng tiếng click
nhân tạo đúng kiểu đó: mỗi phần tử Morse = một click lúc nhấn + một click nhỏ hơn lúc nhả.
"""

from __future__ import annotations

import numpy as np
import pytest

from morsedesk.api import Decoder, Encoder
from morsedesk.dsp.clicks import CLICK_PEAKY_MIN, CLICK_RATE_MIN, click_features, is_key_clicks
from morsedesk.dsp.tone import estimate_tone
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.warnings import WarningCode

SR = 8000


def key_click_audio(text: str = "CQ CQ DE R1ABC PSE K QRL QTH MOSCOW", wpm: float = 25.0, seed: int = 0,
                    ring_ms: float = 15.0, reverb_ms: float = 80.0, bg: float = 0.004) -> np.ndarray:
    """Tiếng phím cơ học: click nhấn (cộng hưởng ~1,1 và 2,6 kHz + tiếng nảy 8 ms sau), click nhả
    nhỏ hơn, vang phòng, ồn nền. KHÔNG có tone. Bỏ cổng click thì model bịa chữ trên chính âm thanh
    này ("TWATAWE TWATAW…", đo 25/09) — test dưới mới có nghĩa."""
    rng = np.random.default_rng(seed)
    elements = tokens_to_elements(Encoder("en").to_tokens(text), TimingParams(wpm=wpm))
    x = rng.normal(0, bg, int((sum(e.duration for e in elements) + 1.0) * SR))
    n = int(0.05 * SR)
    tt = np.arange(n) / SR

    def clack(amp: float, f1: float, f2: float) -> np.ndarray:
        env = np.exp(-tt / (ring_ms / 1000))
        return amp * env * (np.sin(2 * np.pi * f1 * tt) + 0.6 * np.sin(2 * np.pi * f2 * tt) + 0.8 * rng.normal(0, 1, n))

    t = 0.5
    for e in elements:
        if e.on:
            for at, c in ((t, clack(0.4, 1100, 2600)), (t + 0.008, clack(0.12, 1100, 2600)),
                          (t + e.duration, clack(0.2, 900, 2200))):
                i = int(at * SR)
                m = min(n, len(x) - i)
                x[i:i + m] += c[:m]
        t += e.duration
    k = int(reverb_ms / 1000 * SR)
    ir = rng.normal(0, 1, k) * np.exp(-np.arange(k) / (0.02 * SR))
    ir[0] = 1.0
    x = np.convolve(x, 0.3 * ir)[: len(x)]
    return (x / np.max(np.abs(x)) * 0.5).astype(np.float32)


@pytest.mark.parametrize("kw", [{}, {"ring_ms": 25.0}, {"reverb_ms": 150.0}, {"wpm": 30.0}, {"bg": 0.01}])
def test_key_clicks_are_recognised(kw):
    x = key_click_audio(**kw)
    rate, peaky = click_features(x, SR)
    assert rate >= CLICK_RATE_MIN and peaky >= CLICK_PEAKY_MIN, (rate, peaky)
    # cộng hưởng của phím làm bộ dò tone tưởng có tone: vẫn phải nhận ra là click
    est = estimate_tone(x)
    assert is_key_clicks(x, SR, f0_hz=est.f0_hz if est.has_signal else None)


@pytest.mark.parametrize("kind", ["silence", "white", "tone_morse"])
def test_non_click_audio_is_not_called_clicks(kind):
    rng = np.random.default_rng(1)
    if kind == "silence":
        x = np.zeros(SR * 10, dtype=np.float32)
    elif kind == "white":
        x = rng.normal(0, 0.05, SR * 10).astype(np.float32)
    else:
        # Morse tone bình thường, nhiễu vừa phải: trường hợp chủ yếu của app (cổng chỉ áp khi không
        # dò được tone, nhưng bản thân bộ nhận diện cũng không được nhầm nó với click)
        x = Encoder("en").to_audio("CQ CQ DE R1ABC PSE K", wpm=20, snr_db=10.0, seed=2)
    est = estimate_tone(x)
    assert not is_key_clicks(x, SR, f0_hz=est.f0_hz if est.has_signal else None), kind


def test_decoder_says_key_clicks_instead_of_inventing_text():
    from pathlib import Path

    if not Path("models/acoustic.onnx").exists():
        pytest.skip("cần models/acoustic.onnx")
    r = Decoder("auto" if Path("models/lm/en.bin").exists() else "en", engine="onnx",
                lm=Path("models/lm/en.bin").exists()).decode_array(key_click_audio(), SR)
    assert r.text == "" and r.words == []
    assert [w.code for w in r.warning_codes] == [WarningCode.NO_SIGNAL.value, WarningCode.KEY_CLICKS.value]
