"""Xuất checkpoint PyTorch sang ONNX opset 17 kèm metadata JSON và file golden để kiểm parity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from morsedesk.constants import FEAT_DIM, FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.model.vocab import VOCAB
from morsedesk.textio import force_utf8_streams
from tools.net_torch import CONFIG_DEFAULT, MorseNet

OPSET = 17


def _onnx_export(model: torch.nn.Module, dummy: torch.Tensor, out: Path) -> None:
    kwargs = dict(
        input_names=["features"], output_names=["log_probs"],
        dynamic_axes={"features": {0: "batch", 1: "time"}, "log_probs": {0: "batch", 1: "time"}},
        opset_version=OPSET,
    )
    try:
        torch.onnx.export(model, dummy, str(out), dynamo=False, **kwargs)
    except TypeError:  # torch cũ không có tham số dynamo
        torch.onnx.export(model, dummy, str(out), **kwargs)


def export(checkpoint: Path, out_onnx: Path, version: str = "0.1.0", n_golden: int = 20) -> tuple[Path, Path]:
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    config = dict(ckpt.get("config", CONFIG_DEFAULT))
    model = MorseNet(config["feat_dim"], config["n_classes"], config["hidden"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    out_onnx.parent.mkdir(parents=True, exist_ok=True)
    _onnx_export(model, torch.zeros(1, 800, config["feat_dim"]), out_onnx)

    meta = {
        "version": version, "sample_rate": SAMPLE_RATE, "hop": HOP, "frame_rate": FRAME_RATE,
        "feat_dim": FEAT_DIM, "vocab": VOCAB.tokens, "blank_id": VOCAB.blank_id,
        "space_id": VOCAB.space_id, "unk_id": VOCAB.unk_id, "input_name": "features",
        "output_name": "log_probs", "time_stride": 2, "opset": OPSET,
        "train_step": ckpt.get("step"), "val_ter": ckpt.get("val_ter"), "config": config,
        "feature_mode": config.get("feature_mode", "clip"),
    }
    meta_path = out_onnx.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    rng = np.random.default_rng(0)
    golden = {}
    with torch.no_grad():
        for i in range(n_golden):
            t = int(rng.integers(200, 1600))
            x = rng.normal(size=(t, config["feat_dim"])).astype(np.float32)
            y = model(torch.from_numpy(x)[None])[0].numpy()
            golden[f"x{i}"], golden[f"y{i}"] = x, y
    golden_path = out_onnx.with_suffix(".golden.npz")
    np.savez(golden_path, **golden)
    return meta_path, golden_path


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Xuất ONNX")
    ap.add_argument("--checkpoint", type=Path, default=Path("runs/v1/best.pt"))
    ap.add_argument("--out", type=Path, default=Path("models/acoustic.onnx"))
    ap.add_argument("--version", default="0.1.0")
    a = ap.parse_args(argv)
    meta, golden = export(a.checkpoint, a.out, a.version)
    print(f"đã ghi {a.out}, {meta}, {golden}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
