"""Chạy mô hình âm thanh ONNX trên CPU, kiểm metadata và parity với golden."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort

from morsedesk.constants import FEAT_DIM, HOP, SAMPLE_RATE
from morsedesk.model.vocab import VOCAB


class OnnxAcousticModel:
    def __init__(self, model_path: Path, meta_path: Path | None = None) -> None:
        model_path = Path(model_path)
        meta_path = Path(meta_path) if meta_path else model_path.with_suffix(".json")
        if not model_path.exists():
            raise FileNotFoundError(f"không tìm thấy model: {model_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"không tìm thấy metadata: {meta_path}")
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if self.meta.get("vocab") != VOCAB.tokens:
            raise ValueError("từ vựng trong metadata model không khớp phần mềm; cần xuất lại model")
        for field, expected in (("feat_dim", FEAT_DIM), ("sample_rate", SAMPLE_RATE), ("hop", HOP)):
            if self.meta.get(field) != expected:
                raise ValueError(
                    f"{field} trong metadata model ({self.meta.get(field)}) không khớp phần mềm "
                    f"({expected}); cần xuất lại model"
                )
        so = ort.SessionOptions()
        # Chạy song song nhiều tiến trình (morsedesk/parallel.py) thì mỗi tiến trình MỘT luồng.
        so.intra_op_num_threads = (int(os.environ.get("MORSEDESK_ORT_THREADS", "0") or 0)
                                   or max(1, (os.cpu_count() or 2) // 2))
        self.session = ort.InferenceSession(str(model_path), so, providers=["CPUExecutionProvider"])
        self.input_name = self.meta["input_name"]
        self.output_name = self.meta["output_name"]
        self.time_stride = int(self.meta["time_stride"])
        self.feature_mode = str(self.meta.get("feature_mode", "clip"))
        self.hidden = (self.meta.get("config") or {}).get("hidden")
        self.agc_tau_s = float((self.meta.get("config") or {}).get("agc_tau_s", 1.0))

    def output_length(self, t: int) -> int:
        return (t - 1) // self.time_stride + 1

    def __call__(self, feats: np.ndarray) -> np.ndarray:
        x = np.ascontiguousarray(feats, dtype=np.float32)[None]
        return self.session.run([self.output_name], {self.input_name: x})[0][0]


def check_parity(model: OnnxAcousticModel, golden_path: Path, atol: float = 1e-4) -> float:
    data = np.load(golden_path)
    n = len([k for k in data.files if k.startswith("x")])
    max_err = 0.0
    for i in range(n):
        y = model(data[f"x{i}"])
        err = float(np.max(np.abs(y - data[f"y{i}"])))
        max_err = max(max_err, err)
    if max_err > atol:
        raise AssertionError(f"parity ONNX/torch lệch {max_err:.2e} > {atol:.0e}")
    return max_err
