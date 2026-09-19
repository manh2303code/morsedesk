import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("onnxruntime")

from morsedesk.model.onnx_runner import OnnxAcousticModel, check_parity  # noqa: E402
from morsedesk.model.vocab import VOCAB  # noqa: E402
from tools.export_onnx import export  # noqa: E402
from tools.net_torch import CONFIG_DEFAULT, MorseNet, output_length  # noqa: E402


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("onnx")
    torch.manual_seed(0)
    model = MorseNet(**CONFIG_DEFAULT)
    ckpt = tmp / "best.pt"
    torch.save({"state_dict": model.state_dict(), "step": 1, "val_ter": 0.5, "config": CONFIG_DEFAULT}, ckpt)
    onnx_path = tmp / "acoustic.onnx"
    meta_path, golden_path = export(ckpt, onnx_path, version="test")
    return onnx_path, meta_path, golden_path


def test_metadata(exported):
    _, meta_path, _ = exported
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["vocab"] == VOCAB.tokens
    assert meta["sample_rate"] == 8000 and meta["hop"] == 40 and meta["feat_dim"] == 11
    assert meta["time_stride"] == 2 and meta["opset"] == 17


def test_parity_within_1e4(exported):
    onnx_path, _, golden_path = exported
    model = OnnxAcousticModel(onnx_path)
    max_err = check_parity(model, golden_path, atol=1e-4)
    assert max_err <= 1e-4


def test_dynamic_length_and_shapes(exported):
    onnx_path, _, _ = exported
    model = OnnxAcousticModel(onnx_path)
    for t in (37, 200, 1601):
        y = model(np.random.default_rng(t).normal(size=(t, 11)).astype(np.float32))
        assert y.shape == (output_length(t), 65)
        assert np.allclose(np.exp(y).sum(-1), 1.0, atol=1e-3)


def test_vocab_mismatch_rejected(exported, tmp_path):
    onnx_path, meta_path, _ = exported
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vocab"] = meta["vocab"][::-1]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError):
        OnnxAcousticModel(onnx_path, bad)


def test_metadata_field_mismatch_rejected(exported, tmp_path):
    onnx_path, meta_path, _ = exported
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["sample_rate"] = 16000
    bad = tmp_path / "bad_sr.json"
    bad.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="sample_rate"):
        OnnxAcousticModel(onnx_path, bad)

