"""Cửa sổ trượt cho mô hình ONNX: chạy model trên từng cửa sổ chồng nhau và gộp log-prob,
mỗi khung đầu ra lấy từ cửa sổ có tâm gần nó nhất."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import HOP
from morsedesk.dsp.frontend import FrontendConfig, Window, compute_features_windowed
from morsedesk.dsp.windowing import (  # noqa: F401  (re-export cho import cũ)
    LIVE_STEP_FRAMES,
    LIVE_WINDOW_FRAMES,
    STEP_FRAMES,
    WINDOW_FRAMES,
    frame_windows,
)
from morsedesk.model.protocol import AcousticModel
from morsedesk.progress import DecodeProgress


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


def run_chunked(model: AcousticModel, feats: np.ndarray, window: int = WINDOW_FRAMES,
                step: int = STEP_FRAMES, progress: DecodeProgress | None = None) -> np.ndarray:
    """Đặc trưng đã tính cho cả clip (chế độ 'clip')."""
    n = feats.shape[0]
    bounds = list(frame_windows(n, window, step))
    pieces = []
    for i, (s, e) in enumerate(bounds, 1):
        pieces.append((s, e, model(feats[s:e])))
        if progress is not None:
            progress.step(i, len(bounds))
    return _merge_pieces(pieces, n, int(model.time_stride), len(model.meta["vocab"]))


def run_chunked_windows(model: AcousticModel, windows: list[Window], n_frames: int,
                        progress: DecodeProgress | None = None,
                        skip_silent: bool = False) -> np.ndarray:
    """Chế độ 'window' với đặc trưng đã tính sẵn (tránh tính lại khi bên gọi đã có cửa sổ).

    `skip_silent`: cửa sổ không dò ra tone thì KHÔNG chạy mô hình, mà ép thẳng thành blank.
    **Mặc định TẮT cho chế độ file** — đo trên toàn T1 cho 13,28 % so với 9,70 % khi để nguyên,
    vì nhiều clip SNR thấp có cửa sổ không dò nổi tone nhưng vẫn chứa tín hiệu thật, ép blank là
    mất chữ. **Bật cho chế độ nghe trực tiếp**, nơi phần lớn thời gian micro không có ai phát và
    cái giá của việc bịa ra chữ lớn hơn hẳn cái giá của việc bỏ sót.

    Vì sao cần: AGC chuẩn hóa từng cửa sổ, nên một cửa sổ chỉ có nhiễu nền bị kéo lên đúng mức
    biên độ của tín hiệu thật, và mô hình — vốn chưa bao giờ được dạy nói "ở đây không có gì" —
    đọc nhiễu đó thành chữ. Đo được: 30 giây nhiễu trắng thuần cho ra `WE ARE`, 12 giây cho
    `DE K`. Trên clip dài có nhiều khoảng lặng, những chữ ma đó ghép vào bản tin thật và nhân
    nó lên: một bản tin chứa đúng một `CQ` ra thành `CQ CQ CQ CQ DE R1ABC`, CER 84,6 %.

    `Window.has_signal` là phép đo sẵn có và đúng việc: nhiễu trắng thuần cho False ở mọi cửa
    sổ, bản tin thật cho True. Bỏ qua chúng còn nhanh hơn, vì mỗi cửa sổ bỏ qua là một lượt
    chạy mô hình tiết kiệm được.
    """
    pieces = []
    blank = None
    for i, w in enumerate(windows, 1):
        if skip_silent and not w.has_signal:
            t_out = int(model.output_length(w.feats.shape[0])) if hasattr(model, "output_length")                 else (w.feats.shape[0] - 1) // int(model.time_stride) + 1
            if blank is None or blank.shape[0] < t_out:
                blank = np.full((t_out, len(model.meta["vocab"])), np.log(1e-6), dtype=np.float32)
                blank[:, 0] = 0.0
            pieces.append((w.start_frame, w.end_frame, blank[:t_out]))
        else:
            pieces.append((w.start_frame, w.end_frame, model(w.feats)))
        if progress is not None:
            progress.step(i, len(windows))
    return _merge_pieces(pieces, n_frames, int(model.time_stride), len(model.meta["vocab"]))


def run_chunked_audio(model: AcousticModel, x: np.ndarray, f0_hint: float | None = None,
                      window: int = WINDOW_FRAMES, step: int = STEP_FRAMES,
                      cfg: FrontendConfig | None = None,
                      progress: DecodeProgress | None = None) -> tuple[np.ndarray, int]:
    """Chế độ 'window': đặc trưng và tone tính riêng từng cửa sổ. Trả (log-prob gộp, số khung đầu vào)."""
    n_frames = len(x) // HOP
    windows = compute_features_windowed(x, f0_hint, window_frames=window, step_frames=step, cfg=cfg)
    return run_chunked_windows(model, windows, n_frames, progress), n_frames
