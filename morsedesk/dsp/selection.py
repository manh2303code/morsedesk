"""Khi nào tin bộ giải mã DSP hơn mô hình nơ-ron.

Không engine nào thắng ở mọi nơi, và hai đám đông đã đo tách bạch rõ:

| Bộ đo | SNR | CER mô hình | CER DSP |
|---|---|---|---|
| T1 tổng hợp (500 clip) | -6..22 dB | 20,21 % | 35,12 % |
| T2 bản ghi thật ARRL (10 bản) | 49..143 dB | 24,2 % | **4,0 %** |

Mô hình được huấn luyện trên -6..25 dB nên tín hiệu sạch hơn thế nằm ngoài phân bố của nó; còn
bộ DSP chỉ cần timing đều là đọc đúng, và bản tin máy gõ ở SNR cao là trường hợp dễ nhất của nó.

Hai điều kiện phải cùng đúng thì mới lấy kết quả DSP. Chỉ riêng SNR cao là chưa đủ: một bản tin
gõ tay lệch nhịp vẫn có thể rất sạch mà bộ DSP đọc sai, và chi phí timing chính là thứ phát hiện
điều đó — nó đo mức khớp giữa các đoạn bật/tắt với lưới 1/3/7 dit.

Ngưỡng đặt giữa hai đám đông đã đo, không chọn bừa: T1 cao nhất 22 dB còn T2 thấp nhất 49 dB;
chi phí timing trung vị của T2 là 0,0031 còn của T1 là 0,023–0,049.
"""

from __future__ import annotations

import math

# Ngưỡng SNR là thứ tách hai đám đông: T1 cao nhất 22 dB, T2 thấp nhất 49 dB. Nó cũng là lý do
# mọi clip của T1 đều đi đường mô hình như cũ, nên chỉ tín hiệu sạch mới chịu ảnh hưởng.
SNR_OUT_OF_RANGE_DB = 30.0
# Chi phí timing vì vậy KHÔNG phải để tách T1 với T2 nữa, mà là lưới an toàn cho trường hợp
# chưa có trong bộ đo: bản tin rất sạch nhưng gõ tay lệch nhịp, khi đó bộ DSP sẽ đọc sai còn mô
# hình thì không. Trên 10 bản ghi ARRL, chi phí nằm trong 0,0008-0,0523 (cao nhất là bản 5 WPM,
# nơi một dit dài 48 khung nên lượng tử hóa ranh giới nặng hơn); 0,06 giữ được cả mười mà vẫn
# loại những ca sai lệch log trung bình trên 24 %.
DSP_MAX_TIMING_COST = 0.06


def _finite(v: float | None) -> bool:
    return v is not None and math.isfinite(float(v))


def prefer_dsp(snr_db: float | None, timing_cost: float | None,
               has_ambiguous_tokens: bool = False) -> bool:
    """Có nên lấy kết quả của bộ giải mã DSP thay cho mô hình không.

    `has_ambiguous_tokens`: kết quả DSP có chứa mẫu mà bảng của profile giải ra NHIỀU chữ không.
    Bảng Kazakh có 9 mẫu như vậy (`.-` là А hoặc Ә) và bảng Nga có một (`-..-` là Ь hoặc Ъ);
    chọn đúng giữa chúng là việc của mô hình ngôn ngữ, còn bộ DSP chỉ lấy lựa chọn đầu tiên. Gặp
    mẫu như thế thì dù tín hiệu sạch tới đâu cũng phải giữ đường mô hình.

    Thiếu bất kỳ phép đo nào thì trả False: mô hình là đường mặc định, và đổi đường dựa trên số
    liệu không có là cách chắc chắn nhất để làm hỏng những ca vốn đang chạy tốt.
    """
    if has_ambiguous_tokens or not _finite(snr_db) or not _finite(timing_cost):
        return False
    return float(snr_db) > SNR_OUT_OF_RANGE_DB and float(timing_cost) < DSP_MAX_TIMING_COST
