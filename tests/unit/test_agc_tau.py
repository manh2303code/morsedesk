import numpy as np
import pytest

from morsedesk.api import Decoder
from morsedesk.dsp.frontend import WINDOW_CFG, FrontendConfig, agc_log, window_cfg
from morsedesk.model.vocab import VOCAB


class WindowModel:
    """Model giả chế độ cửa sổ, khai báo agc_tau_s như metadata của model thật."""

    meta = {"vocab": VOCAB.tokens}
    time_stride = 2
    feature_mode = "window"

    def __init__(self, agc_tau_s: float) -> None:
        self.agc_tau_s = agc_tau_s

    def output_length(self, t: int) -> int:
        return (t - 1) // 2 + 1

    def __call__(self, feats: np.ndarray) -> np.ndarray:
        n = self.output_length(feats.shape[0])
        lp = np.full((n, len(VOCAB)), np.log(1e-6), dtype=np.float32)
        lp[:, VOCAB.blank_id] = 0.0
        return lp


def test_window_cfg_keeps_init_half_second():
    assert window_cfg() == WINDOW_CFG == FrontendConfig(agc_tau_s=1.0, agc_init_s=0.5)
    assert window_cfg(0.4) == FrontendConfig(agc_tau_s=0.4, agc_init_s=0.5)
    assert FrontendConfig().agc_init_s == 1.0


def test_short_tau_recovers_faster_after_level_change():
    env = np.concatenate([np.full(400, 1.0), np.full(400, 0.01), np.full(400, 1.0)])
    fast = agc_log(env, tau_s=0.3)
    slow = agc_log(env, tau_s=1.0)
    assert fast.shape == slow.shape == (1200,)
    assert abs(float(fast[-1])) < abs(float(slow[-1]))


def test_decoder_takes_agc_tau_from_model_metadata():
    dec = Decoder("en", engine="onnx", acoustic_model=WindowModel(0.4), lm=False)
    assert dec.feature_cfg.agc_tau_s == 0.4 and dec.feature_cfg.agc_init_s == 0.5
    base = Decoder("en", engine="baseline", lm=False)
    assert base.feature_cfg.agc_tau_s == 1.0


def test_onnx_runner_reads_agc_tau_from_config(tmp_path):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("torch")
    import json

    import torch

    from morsedesk.model.onnx_runner import OnnxAcousticModel
    from tools.export_onnx import export
    from tools.net_torch import CONFIG_DEFAULT, MorseNet

    ckpt = tmp_path / "best.pt"
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                "config": dict(CONFIG_DEFAULT, feature_mode="window", agc_tau_s=0.4)}, ckpt)
    onnx = tmp_path / "m.onnx"
    export(ckpt, onnx, version="test", n_golden=1)
    assert json.loads(onnx.with_suffix(".json").read_text(encoding="utf-8"))["config"]["agc_tau_s"] == 0.4
    assert OnnxAcousticModel(onnx).agc_tau_s == 0.4

    ckpt_old = tmp_path / "old.pt"          # checkpoint cũ không có khóa agc_tau_s -> mặc định 1.0
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                "config": dict(CONFIG_DEFAULT, feature_mode="window")}, ckpt_old)
    old = tmp_path / "old.onnx"
    export(ckpt_old, old, version="test", n_golden=1)
    assert OnnxAcousticModel(old).agc_tau_s == 1.0
