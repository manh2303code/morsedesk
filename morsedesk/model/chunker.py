"""Cửa sổ trượt cho mô hình ONNX: chạy model trên từng cửa sổ chồng nhau và gộp log-prob,
mỗi khung đầu ra lấy từ cửa sổ có tâm gần nó nhất."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import HOP
from morsedesk.dsp.frontend import FrontendConfig, Window, compute_features_windowed, repad_window
from morsedesk.dsp.windowing import (  # noqa: F401  (re-export cho import cũ)
    LIVE_STEP_FRAMES,
    LIVE_WINDOW_FRAMES,
    STEP_FRAMES,
    WINDOW_FRAMES,
    WINDOW_PAD_FRAMES,
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
                        skip_silent: bool = False, pad=None) -> np.ndarray:
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

    `pad(window) -> Window`: cửa sổ CÓ TONE (`has_signal`) được chạy trên bản đệm nhiễu nền ở mép
    giáp cửa sổ khác (frontend.repad_window). Đo 24/09: cửa sổ 12 s nằm giữa một bản tin dài dày tín
    hiệu từ đầu tới cuối — thứ chưa từng có lúc huấn luyện — ra RỖNG 26/60 cửa sổ, bản tin 2 phút sai
    50 %; đệm thì 1,2 %. Chỉ cứu cửa sổ rỗng hẳn là chưa đủ (11,3 %: nhiều cửa sổ chỉ ra lác đác vài
    chữ). Cửa sổ KHÔNG có tone thì không đệm: đệm làm AGC khởi động từ nền yên và nhiễu xung thuần
    hóa thành chữ ('R R TU DE', test §7); sóng mang liên tục cũng không (repad_window tự trả nguyên
    cửa sổ). Clip <= 12 s là một cửa sổ không có mép trong — y hệt trước.
    """
    pieces = []
    blank = None
    stride = int(model.time_stride)
    for i, w in enumerate(windows, 1):
        if skip_silent and not w.has_signal:
            n_in = w.end_frame - w.start_frame
            t_out = int(model.output_length(n_in)) if hasattr(model, "output_length") \
                else (n_in - 1) // stride + 1
            if blank is None or blank.shape[0] < t_out:
                blank = np.full((t_out, len(model.meta["vocab"])), np.log(1e-6), dtype=np.float32)
                blank[:, 0] = 0.0
            pieces.append((w.start_frame, w.end_frame, blank[:t_out]))
        else:
            if pad is not None and w.has_signal:
                w = pad(w)
            pieces.append((w.start_frame, w.end_frame, _trimmed(model, w, stride)))
        if progress is not None:
            progress.step(i, len(windows))
    return _merge_pieces(pieces, n_frames, int(model.time_stride), len(model.meta["vocab"]))


def _trimmed(model: AcousticModel, w: Window, stride: int) -> np.ndarray:
    """Chạy model trên cửa sổ; bỏ đầu ra ứng với đoạn đệm ở mép giáp cửa sổ khác."""
    lp = model(w.feats)
    a, b = w.pad_head // stride, w.pad_tail // stride
    return lp[a: lp.shape[0] - b] if (a or b) else lp


def run_chunked_audio(model: AcousticModel, x: np.ndarray, f0_hint: float | None = None,
                      window: int = WINDOW_FRAMES, step: int = STEP_FRAMES,
                      cfg: FrontendConfig | None = None,
                      progress: DecodeProgress | None = None) -> tuple[np.ndarray, int]:
    """Chế độ 'window': đặc trưng và tone tính riêng từng cửa sổ. Trả (log-prob gộp, số khung đầu vào)."""
    n_frames = len(x) // HOP
    windows = compute_features_windowed(x, f0_hint, window_frames=window, step_frames=step, cfg=cfg)

    def pad(w: Window) -> Window:
        return repad_window(x, w, n_frames, WINDOW_PAD_FRAMES, cfg)

    return run_chunked_windows(model, windows, n_frames, progress, pad=pad), n_frames
