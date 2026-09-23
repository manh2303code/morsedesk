"""Chế độ tự kiểm của bản đóng gói: `MorseDesk.exe --self-test IN OUT`.

Bản `.exe` không có console, nên đây là cách duy nhất chứng minh một bản dựng MỚI giải mã được mà
không cần mở cửa sổ: thiếu model, LM, onnxruntime hay libsndfile trong gói đều lộ ra ở file OUT.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from morsedesk.api import DEFAULT_MODEL_PATH, Encoder
from morsedesk.audio.io import save_audio

ENTRY = Path("packaging/entry_gui.py")


def _entry():
    spec = importlib.util.spec_from_file_location("entry_gui", ENTRY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_self_test_reports_errors_to_the_file_instead_of_crashing(tmp_path):
    out = tmp_path / "out.json"
    assert _entry().self_test(str(tmp_path / "khong_co.wav"), str(out)) == 1
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["error"] and "khong_co.wav" in body["detail"]


def test_self_test_flag_needs_exactly_two_paths(monkeypatch):
    """Sai số tham số thì rơi về GUI như bình thường, không lặng lẽ tự kiểm nửa vời."""
    import sys

    mod = _entry()
    called = []
    monkeypatch.setattr(mod, "self_test", lambda *a: called.append(a) or 0)
    monkeypatch.setattr(sys, "argv", ["MorseDesk.exe", "--self-test", "a.wav", "b.json"])
    assert mod.main() == 0 and called == [("a.wav", "b.json")]


@pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="cần models/acoustic.onnx")
def test_self_test_decodes_with_the_bundled_models(tmp_path):
    wav, out = tmp_path / "ru.wav", tmp_path / "out.json"
    save_audio(wav, Encoder("ru").to_audio("ПРИВЕТ МИР КАК ДЕЛА", wpm=20), 8000)
    assert _entry().self_test(str(wav), str(out)) == 0
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["text"] == "ПРИВЕТ МИР КАК ДЕЛА" and body["language"] == "ru"
