"""Hằng số dùng chung cho toàn bộ pipeline âm thanh."""

SAMPLE_RATE = 8000          # Hz, mọi xử lý nội bộ ở tần số này
HOP = 40                    # mẫu mỗi khung -> 200 khung/giây
FRAME_RATE = SAMPLE_RATE // HOP
N_FFT = 256                 # cỡ STFT, bin = 31.25 Hz
FEAT_DIM = 11               # 1 envelope AGC + 1 đạo hàm + 9 bin phổ
TONE_MIN_HZ = 300.0
TONE_MAX_HZ = 1500.0

assert SAMPLE_RATE % HOP == 0
assert FRAME_RATE == 200
