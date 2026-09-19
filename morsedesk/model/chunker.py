"""Cửa sổ trượt cho mô hình ONNX: chạy model trên từng cửa sổ chồng nhau và gộp log-prob,
mỗi khung đầu ra lấy từ cửa sổ có tâm gần nó nhất."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import HOP
from morsedesk.dsp.frontend import compute_features_windowed
from morsedesk.dsp.windowing import (  # noqa: F401  (re-export cho import cũ)
    LIVE_STEP_FRAMES,
    LIVE_WINDOW_FRAMES,
    STEP_FRAMES,
    WINDOW_FRAMES,
    frame_windows,
)


def _merge_pieces(pieces: list[tuple[int, int, np.ndarray]], n_frames: int, stride: int,
                  n_classes: int) -> np.ndarray:
    """pieces: (khung đầu vào bắt đầu, kết thúc, log-prob [T_w', C]) của từng cửa sổ."""
    t_out = (n_frames - 1) // stride + 1 if n_frames > 0 else 0
    out = np.zeros((t_out, n_classes), dtype=np.float32)
    best = np.full(t_out, np.inf)
    filled = np.zeros(t_out, dtype=bool)
    for s, e, lp in pieces:
        g = s // stride + np.arange(lp.shape[0])
        valid = g < t_out
        g, lp = g[valid], lp[valid]
        center = (s + e) / 2.0
        dist = np.abs(g * stride + stride / 2.0 - center)
        better = dist < best[g]
        out[g[better]] = lp[better]
        best[g[better]] = dist[better]
        filled[g[better]] = True
    if not filled.all():
        out[~filled] = np.log(1e-6)
        out[~filled, 0] = 0.0
    return out


def run_chunked(model, feats: np.ndarray, window: int = WINDOW_FRAMES, step: int = STEP_FRAMES) -> np.ndarray:
    """Đặc trưng đã tính cho cả clip (chế độ 'clip'). model: time_stride, output_length, __call__, meta['vocab']."""
    n = feats.shape[0]
    pieces = [(s, e, model(feats[s:e])) for s, e in frame_windows(n, window, step)]
    return _merge_pieces(pieces, n, int(model.time_stride), len(model.meta["vocab"]))


def run_chunked_audio(model, x: np.ndarray, f0_hint: float | None = None, window: int = WINDOW_FRAMES,
                      step: int = STEP_FRAMES) -> tuple[np.ndarray, int]:
    """Chế độ 'window': đặc trưng và tone tính riêng từng cửa sổ. Trả (log-prob gộp, số khung đầu vào)."""
    n_frames = len(x) // HOP
    pieces = [(w.start_frame, w.end_frame, model(w.feats))
              for w in compute_features_windowed(x, f0_hint, window_frames=window, step_frames=step)]
    return _merge_pieces(pieces, n_frames, int(model.time_stride), len(model.meta["vocab"])), n_frames
