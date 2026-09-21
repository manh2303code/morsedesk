"""Giao diện tối thiểu của mô hình âm thanh mà `Decoder` và `chunker` cần.

Protocol cấu trúc (structural typing): `OnnxAcousticModel` và các model giả trong test khớp
mà không phải kế thừa. `feature_mode` có thể thiếu ở model cũ; bên gọi dùng
`getattr(model, "feature_mode", "clip")`.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class AcousticModel(Protocol):
    meta: dict
    time_stride: int
    feature_mode: str

    def output_length(self, t: int) -> int:
        """Số khung đầu ra cho `t` khung đầu vào."""
        ...

    def __call__(self, feats: np.ndarray) -> np.ndarray:
        """Đặc trưng [T, FEAT_DIM] -> log-prob [T', n_classes]."""
        ...
