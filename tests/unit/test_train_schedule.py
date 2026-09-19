import json
import math

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import tools.train as train  # noqa: E402
from morsedesk.constants import FEAT_DIM, HOP  # noqa: E402
from morsedesk.data.channel import clean  # noqa: E402
from morsedesk.data.keyer import machine  # noqa: E402
from morsedesk.data.synth import SynthConfig, SynthGenerator  # noqa: E402
from morsedesk.dsp.frontend import compute_features_windowed, stitch_windows  # noqa: E402
from tools.net_torch import CONFIG_DEFAULT, MorseNet  # noqa: E402


def test_lr_at_schedules():
    assert train.lr_at(1, 1e-3, 100, "constant", warmup=0) == 1e-3
    assert math.isclose(train.lr_at(5, 1e-3, 100, "cosine", warmup=10), 5e-4)      # warmup tuyến tính
    assert math.isclose(train.lr_at(10, 1e-3, 100, "cosine", warmup=10), 1e-3)
    mid = train.lr_at(55, 1e-3, 100, "cosine", warmup=10)
    assert math.isclose(mid, 1e-3 * (0.05 + 0.95 * 0.5), rel_tol=1e-6)              # giữa đoạn cosine
    assert math.isclose(train.lr_at(100, 1e-3, 100, "cosine", warmup=10), 5e-5)     # min_ratio 0.05
    assert train.lr_at(200, 1e-3, 100, "cosine") == 5e-5                              # sau total: giữ đáy
    assert train.lr_at(50, 1e-3, 100, "constant", warmup=10) == 1e-3
    with pytest.raises(ValueError):
        train.lr_at(1, 1e-3, 100, "linear")


def test_example_features_modes():
    gen = SynthGenerator(SynthConfig(min_seconds=5.0, max_seconds=6.0, mp3_enabled=False))
    ex = gen.generate(3, profile_id="en", keyer=machine(20), channel=clean(20.0))
    n = len(ex.audio) // HOP
    clip = train.example_features(ex, "clip")
    win = train.example_features(ex, "window")
    assert clip.shape == win.shape == (n, FEAT_DIM) and win.dtype == np.float32
    assert np.all(np.isfinite(win)) and not np.allclose(clip, win)
    expect = stitch_windows(compute_features_windowed(ex.audio, f0_hint=ex.f0_hz), n)
    assert np.allclose(win, expect)
    assert train.DEFAULT_FEATURE_MODE == "window" and train.FEATURE_MODES == ("clip", "window")
    with pytest.raises(ValueError):
        train.example_features(ex, "spectrogram")


COMMON = ["--batch", "2", "--val-clips", "2", "--val-every", "3", "--no-mp3", "--hidden", "32"]


def test_train_resume_restores_optimizer_and_step(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert train.main(["--name", "r", "--steps", "3", "--lr-schedule", "cosine", "--warmup", "1", *COMMON]) == 0
    last = train.load_ckpt(tmp_path / "runs/r/last.pt")
    assert last["step"] == 3 and "optimizer" in last
    assert last["config"] == {"feat_dim": 11, "n_classes": 65, "hidden": 32, "feature_mode": "window"}
    hist = json.loads((tmp_path / "runs/r/history.json").read_text(encoding="utf-8"))
    assert len(hist) == 1 and {"step", "loss", "val_ter", "lr", "elapsed_s"} <= set(hist[0])
    assert json.loads((tmp_path / "runs/r/args.json").read_text(encoding="utf-8"))["hidden"] == 32

    assert train.main(["--name", "r", "--steps", "6", "--lr-schedule", "cosine", "--warmup", "1",
                       "--resume", "runs/r/last.pt", *COMMON]) == 0
    out = capsys.readouterr().out
    assert "tiếp tục từ bước 3" in out
    last2 = train.load_ckpt(tmp_path / "runs/r/last.pt")
    assert last2["step"] == 6
    hist2 = json.loads((tmp_path / "runs/r/history.json").read_text(encoding="utf-8"))
    assert [h["step"] for h in hist2] == [3, 6]                                     # lịch sử được nối tiếp
    assert hist2[1]["lr"] == pytest.approx(0.05 * 1e-3)                             # cuối lịch cosine = min_ratio

    # checkpoint cũ (không optimizer): chỉ nạp trọng số, bước bắt đầu 0
    old = tmp_path / "old.pt"
    torch.save({"state_dict": MorseNet(11, 65, 32).state_dict(), "step": 99, "val_ter": 0.5,
                "config": dict(CONFIG_DEFAULT, hidden=32)}, old)
    assert train.main(["--name", "o", "--steps", "3", "--resume", str(old), *COMMON]) == 0
    assert "chỉ nạp trọng số" in capsys.readouterr().out
    assert train.load_ckpt(tmp_path / "runs/o/last.pt")["step"] == 3
    with pytest.raises(SystemExit):
        train.main(["--name", "bad", "--steps", "3", "--resume", str(old), "--batch", "2", "--val-clips", "1",
                    "--val-every", "3", "--no-mp3", "--hidden", "96"])
    with pytest.raises(SystemExit):
        train.main(["--name", "r", "--steps", "6", "--resume", "runs/r/last.pt", *COMMON])   # steps <= bước đã có


def test_export_uses_checkpoint_config(tmp_path, monkeypatch):
    pytest.importorskip("onnxruntime")
    from morsedesk.model.onnx_runner import OnnxAcousticModel, check_parity
    from tools.export_onnx import export

    monkeypatch.chdir(tmp_path)
    assert train.main(["--name", "e", "--steps", "3", *COMMON]) == 0
    onnx_path = tmp_path / "e.onnx"
    meta_path, golden = export(tmp_path / "runs/e/best.pt", onnx_path, version="t")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["config"]["hidden"] == 32 and meta["feature_mode"] == "window" and meta["train_step"] == 3
    m = OnnxAcousticModel(onnx_path)
    assert m.hidden == 32 and m.feature_mode == "window"
    assert check_parity(m, golden) < 1e-4
