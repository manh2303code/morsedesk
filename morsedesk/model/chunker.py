"""Cửa sổ trượt cho mô hình ONNX: chia đặc trưng thành cửa sổ chồng nhau và gộp log-prob,
mỗi khung đầu ra lấy từ cửa sổ có tâm gần nó nhất."""

from __future__ import annotations

import numpy as np

WINDOW_FRAMES = 800       # 4 s ở 200 khung/s (chế độ file)
STEP_FRAMES = 600         # 3 s, chồng 1 s
LIVE_WINDOW_FRAMES = 400  # 2 s (chế độ live)
LIVE_STEP_FRAMES = 200    # 1 s


def frame_windows(n_frames: int, window: int = WINDOW_FRAMES, step: int = STEP_FRAMES) -> list[tuple[int, int]]:
    if window % 2 or step % 2:
        raise ValueError("window và step phải là số chẵn để khớp stride 2 của mô hình")
    if n_frames <= window:
        return [(0, n_frames)]
    starts = list(range(0, n_frames - window, step))
    last = n_frames - window
    last -= last % 2
    if not starts or starts[-1] != last:
        starts.append(last)
    windows = [(s, s + window) for s in starts]
    # Cửa sổ cuối: làm tròn xuống số chẵn cho start có thể hụt 1 khung so với n_frames
    # (khi n_frames - window lẻ); kéo dài điểm cuối tới n_frames để không bỏ sót khung
    # cuối cùng (start luôn <= n_frames - window nên chỉ nới rộng, không bao giờ co lại).
    windows[-1] = (windows[-1][0], n_frames)
    return windows


def run_chunked(model, feats: np.ndarray, window: int = WINDOW_FRAMES, step: int = STEP_FRAMES) -> np.ndarray:
    """model: có time_stride, output_length(t), __call__(feats[T,F]) -> [T',C], meta['vocab']."""
    n = feats.shape[0]
    stride = int(model.time_stride)
    t_out = model.output_length(n)
    n_classes = len(model.meta["vocab"])
    out = np.zeros((t_out, n_classes), dtype=np.float32)
    best = np.full(t_out, np.inf)
    filled = np.zeros(t_out, dtype=bool)
    for s, e in frame_windows(n, window, step):
        lp = model(feats[s:e])
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
