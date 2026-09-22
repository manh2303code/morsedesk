"""Chia dải khung thành cửa sổ chồng nhau (dùng chung cho đặc trưng theo cửa sổ và gộp log-prob)."""

from __future__ import annotations

# 8 s / 2 s chứ không phải 4 s / 3 s: đo trên toàn T1 (500 clip) cho CER 11,52 % so với
# 17,96 %, mọi kênh và mọi profile đều tốt lên, và mỗi clip còn nhanh hơn (0,368 s so với
# 0,492 s). T2 bản ghi thật cũng nhích từ 4,69 % xuống 4,47 % mà không ô nào xấu đi.
# Cửa sổ dài cho BiGRU nhiều ngữ cảnh hai chiều hơn; chồng lấn 6 s làm mỗi khung được
# nhiều cửa sổ bỏ phiếu, và `stitch_windows` luôn lấy cửa sổ có tâm gần khung nhất.
WINDOW_FRAMES = 1600      # 8 s ở 200 khung/s (chế độ file)
STEP_FRAMES = 400         # 2 s, chồng 6 s
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
    # Cửa sổ cuối: start làm tròn xuống số chẵn có thể hụt 1 khung so với n_frames; nới điểm cuối
    # tới n_frames để không bỏ sót khung cuối (start <= n_frames - window nên chỉ nới rộng).
    windows[-1] = (windows[-1][0], n_frames)
    return windows
