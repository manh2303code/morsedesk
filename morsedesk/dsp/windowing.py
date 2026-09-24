"""Chia dải khung thành cửa sổ chồng nhau (dùng chung cho đặc trưng theo cửa sổ và gộp log-prob)."""

from __future__ import annotations

# 12 s / 2 s, đi từ 4 s / 3 s qua hai lần đo trên toàn T1 (500 clip): 4 s/3 s cho 17,96 %,
# 8 s/2 s cho 11,52 %, 12 s/2 s cho 10,87 %. Cửa sổ 10, 12 và 16 s cho KẾT QUẢ GIỐNG HỆT nhau
# vì clip T1 dài 4-12 s nên lọt trọn vào một cửa sổ — tức phần thắng cuối không đến từ "cửa sổ
# dài hơn" mà từ việc THÔI CHIA NHỎ những clip vốn đã đủ ngắn. Đó cũng là ca dùng thật hay gặp
# nhất: một bản tin vài giây.
#
# Trên T2 bản ghi thật (7-37 phút) thì 8 s và 12 s ra từng chữ số giống nhau (4,47 %), nên con
# số này KHÔNG chọn theo clip dài; nó chỉ phải không làm hại clip dài, và đã đo: bản ghi 37 phút
# hết 183,9 giây thay vì 169,4 và đỉnh bộ nhớ 643 MB thay vì 603 MB.
#
# Vì sao cửa sổ dài giúp: BiGRU đọc hai chiều nên mỗi khung được quyết định bằng cả quá khứ lẫn
# tương lai TRONG CÙNG cửa sổ; cắt ngắn là cắt mất ngữ cảnh đó.
WINDOW_FRAMES = 2400      # 12 s ở 200 khung/s (chế độ file)
STEP_FRAMES = 400         # 2 s, chồng 10 s
LIVE_WINDOW_FRAMES = 400  # 2 s (chế độ live)
LIVE_STEP_FRAMES = 200    # 1 s
# Đệm nhiễu nền ở mép cửa sổ GIÁP CỬA SỔ KHÁC khi GIẢI MÃ, chỉ cửa sổ có nhịp phím
# (frontend.repad_window; không dùng lúc huấn luyện). Model chỉ từng học clip có khoảng lặng ở hai
# đầu, và AGC khởi động từ 0,5 s đầu cửa sổ. Cửa sổ nằm giữa một bản tin dài thì
# dày tín hiệu từ đầu tới cuối và bắt đầu giữa một ký tự: đo 24/09 trên bản tin ~2 phút, 26/60 cửa
# sổ ra RỖNG hoàn toàn và CER greedy 56 %; đệm 0,5 s: 0/60 cửa sổ rỗng, 5,8 %. Số chẵn (stride 2).
WINDOW_PAD_FRAMES = 100   # 0,5 s


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
