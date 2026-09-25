"""Nhận ra tiếng CLICK của phím điện báo / máy gõ (sounder): Morse không có tone.

MorseDesk giải Morse phát bằng TONE (CW vô tuyến, âm luyện tập). Có loại bản ghi khác hẳn: tiếng
lách cách cơ học của phím — mỗi lần nhấn một click, mỗi lần nhả một click, phổ rải 0–3 kHz, không
có tone nào. Người dùng cho trang Nghe nghe một bản ghi như vậy ("Morse code key typing — Russian
training — 1930s", 25/09): bộ dò tone báo đúng là không có tín hiệu, nhưng đường đoán tone vẫn chạy
tiếp và model đọc tiếng click thành chữ vô nghĩa, mỗi lần một ngôn ngữ. Thà nói thật là "đây là
tiếng click, chưa giải được" (spec §7: không bịa chữ).

Hai số đo trên dải > 1,5 kHz, khung 2 ms: `rate` = số lần năng lượng nhảy gấp 4 trong một khung
(cách nhau >= 20 ms) mỗi giây; `peaky` = phân vị 99 / trung vị năng lượng. Đo 25/09 (1 080 clip
T1 + dev + T4 + T2 và bản ghi của người dùng):
- 78 clip KHÔNG dò được tone (tone thật chìm dưới nhiễu/fading): rate <= 0,14/s, peaky <= 1,7;
- bản ghi click của người dùng: rate 11,9/s, peaky 98;
- clip có tone sạch cũng có xung ở sườn phím (SRR: rate ~8/s, peaky ~110) — nên cổng CHỈ áp khi
  không dò được tone;
- click nhân tạo GIỐNG THẬT (cộng hưởng cơ học, nảy phím, vang phòng, tests/unit/test_clicks.py):
  rate 3,7–5,6/s, peaky 4,8–7,2 — và không có cổng thì model bịa ra "TWATAWE TWATAW…". Ngưỡng peaky
  đầu tiên (10) đặt theo một bản ghi đã bỏ sót chúng; nay 3, vẫn cách xa 1,7 của Morse không tone.
- cộng hưởng cơ học của phím (~1,1 kHz) làm bộ dò tone tưởng CÓ tone (SNR 21 dB). Khi đó phân biệt
  bằng `key_down_fraction` tại tone: tone Morse giữ năng lượng suốt chấm/gạch, click chỉ ngân vài
  chục ms. Click (7 biến thể + bản ghi thật): <= 0,123; 1 580 clip Morse (T1, dev, dev-OOV, T4, T2)
  lọt hai điều kiện kia chỉ có một (K7QO, bản thu studio có im lặng số): 0,204. Ngưỡng 0,15 nghiêng
  về phía an toàn cho Morse thật (bỏ sót click = như cũ; nhận nhầm Morse = mất chữ).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

from morsedesk.constants import SAMPLE_RATE

CLICK_RATE_MIN = 3.0        # xung/giây
CLICK_PEAKY_MIN = 3.0       # phân vị 99 / trung vị năng lượng dải cao
ANALYSE_S = 60.0            # chỉ cần một phút đầu
CLICK_KEYED_MAX = 0.15      # key_down_fraction tại tone: dưới mức này tone chỉ là tiếng ngân của click


def click_features(x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> tuple[float, float]:
    """(xung mỗi giây, độ nhọn) của năng lượng trên 1,5 kHz."""
    x = np.asarray(x, dtype=np.float64)[: int(ANALYSE_S * sample_rate)]
    hop = max(1, int(0.002 * sample_rate))
    n = len(x) // hop
    if n < 50 or sample_rate < 4000:
        return 0.0, 0.0
    h = sosfiltfilt(butter(4, 1500, "high", fs=sample_rate, output="sos"), x)
    e = np.sqrt(np.mean(h[: n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9
    frame_rate = sample_rate / hop
    rise = np.maximum(np.diff(np.log(e), prepend=np.log(e[0])), 0.0)
    peaks, _ = find_peaks(rise, height=np.log(4.0), distance=max(1, int(0.02 * frame_rate)))
    return len(peaks) / (n / frame_rate), float(np.percentile(e, 99) / np.median(e))


def is_key_clicks(x: np.ndarray, sample_rate: int = SAMPLE_RATE, f0_hz: float | None = None) -> bool:
    """Chuỗi click dày và nhọn. `f0_hz`: tone bộ dò tone thấy (None = không có) — khi có tone, còn
    phải là tone chỉ NGÂN sau từng click chứ không giữ suốt chấm/gạch (xem docstring module)."""
    rate, peaky = click_features(x, sample_rate)
    if rate < CLICK_RATE_MIN or peaky < CLICK_PEAKY_MIN:
        return False
    if f0_hz is None:
        return True
    from morsedesk.dsp.frontend import key_down_fraction
    seg = np.asarray(x, dtype=np.float32)[: int(ANALYSE_S * sample_rate)]
    return key_down_fraction(seg, f0_hz, sample_rate) < CLICK_KEYED_MAX
