"""Fixture cho test GUI: chạy offscreen, LM tí hon, WAV mẫu."""

import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from morsedesk.api import Encoder  # noqa: E402
from morsedesk.audio.io import save_audio  # noqa: E402
from morsedesk.lm.alphabet import LMAlphabet  # noqa: E402
from morsedesk.lm.ngram import save_bin, train_small  # noqa: E402
from morsedesk.lm.profile import load_profile  # noqa: E402


@pytest.fixture
def fake_sounddevice(monkeypatch):
    """Thay `sounddevice` bằng module giả trong `sys.modules`.

    Máy đích là Linux air-gap tối giản, có thể không có `libportaudio2`; khi đó
    `import sounddevice` ném `OSError` ngay. Test ở đây kiểm lớp bọc `Player` của mình chứ
    không kiểm PortAudio, nên phải chạy được ở cả hai nơi. Đã gặp thật: ba test này xanh
    trên Windows nhưng đỏ trên Ubuntu 26.04 vì thiếu libportaudio2.
    """
    mod = types.ModuleType("sounddevice")
    mod.calls = []

    class PortAudioError(Exception):
        pass

    mod.PortAudioError = PortAudioError
    mod.play = lambda x, sr, **kw: mod.calls.append(("play", len(x), sr))
    mod.stop = lambda: mod.calls.append(("stop",))
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return mod


CORPUS = {
    "en": ["CQ CQ DE K", "THE QUICK BROWN FOX", "HELLO WORLD", "CQ DE K", "SOS SOS"],
    "ru": ["ПРИВЕТ МИР", "ВСЕМ ПРИВЕТ", "ДОБРОЕ УТРО"],
    "kk-cyrl-ru": ["СӘЛЕМ ӘЛЕМ", "РАХМЕТ", "ҚАЙЫРЛЫ ТАҢ"],
}


@pytest.fixture(scope="session")
def tiny_lm_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("lm")
    for pid, lines in CORPUS.items():
        profile = load_profile(pid)
        save_bin(train_small(lines, LMAlphabet.for_profile(profile), order=4), d / profile.lm.split("/")[-1])
    return d


@pytest.fixture(scope="session")
def wav_cq(tmp_path_factory):
    p = tmp_path_factory.mktemp("wav") / "cq.wav"
    save_audio(p, Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    return p


@pytest.fixture(scope="session")
def wav_ru(tmp_path_factory):
    p = tmp_path_factory.mktemp("wav") / "ru.wav"
    save_audio(p, Encoder("ru").to_audio("ПРИВЕТ МИР", wpm=20), 8000)
    return p
