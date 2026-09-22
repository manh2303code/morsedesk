"""`morsedesk decode --progress` in tiến trình ra stderr, và `decode_file` chuyển tiếp nó."""

import numpy as np
import pytest

from morsedesk.api import Decoder
from morsedesk.audio.io import save_audio
from morsedesk.cli import main
from morsedesk.progress import DecodeProgress
from tests.helpers import make_morse


@pytest.fixture
def clip(tmp_path):
    x, _ = make_morse("CQ DE R1ABC K", profile_id="en", wpm=20)
    path = tmp_path / "clip.wav"
    save_audio(path, np.tile(x, 2), 8000)
    return path


def test_decode_file_forwards_progress(clip):
    seen: list[tuple[int, int]] = []
    Decoder("en", engine="baseline").decode_file(
        clip, progress=DecodeProgress(on_step=lambda d, t: seen.append((d, t)))
    )
    assert seen


def test_cli_progress_goes_to_stderr_not_stdout(clip, capsys):
    assert main(["decode", str(clip), "--engine", "baseline", "--progress"]) == 0
    out = capsys.readouterr()
    assert "%" in out.err
    assert "%" not in out.out                    # stdout chỉ chứa văn bản giải mã


def test_cli_without_flag_stays_quiet(clip, capsys):
    assert main(["decode", str(clip), "--engine", "baseline"]) == 0
    assert "%" not in capsys.readouterr().err
