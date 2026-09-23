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
# Nhánh thứ hai, độc lập với SNR: timing khớp gần hoàn hảo tự nó đã là bằng chứng đủ. Đo trên
# 461 clip T1 có tín hiệu — chỉ mô hình 15,73 %; thêm nhánh này 14,95 % với 101 clip chuyển
# sang bộ DSP. Nới ngưỡng tới 0,05 thì xấu đi thành 18,48 %, nên nó phải nằm hẳn dưới mức đó.
# Ca lộ ra điều này: một clip SNR 12,8 dB mà bộ DSP đọc đúng nguyên văn còn mô hình sai 8 %.
DSP_TRUSTED_TIMING_COST = 0.02


def _finite(v: float | None) -> bool:
    return v is not None and math.isfinite(float(v))


def prefer_dsp(snr_db: float | None, timing_cost: float | None,
               has_ambiguous_tokens: bool = False) -> bool:
    """Có nên lấy kết quả của bộ giải mã DSP thay cho mô hình không.

    Hai nhánh độc lập dẫn tới cùng kết luận: timing khớp gần hoàn hảo (dưới
    `DSP_TRUSTED_TIMING_COST`), hoặc tín hiệu sạch hơn dải huấn luyện mà timing vẫn đủ khớp.

    `has_ambiguous_tokens`: kết quả DSP có chứa mẫu mà bảng của profile giải ra NHIỀU chữ không.
    Bảng Kazakh có 9 mẫu như vậy (`.-` là А hoặc Ә) và bảng Nga có một (`-..-` là Ь hoặc Ъ);
    chọn đúng giữa chúng là việc của mô hình ngôn ngữ, còn bộ DSP chỉ lấy lựa chọn đầu tiên. Gặp
    mẫu như thế thì dù tín hiệu sạch tới đâu cũng phải giữ đường mô hình.

    Thiếu bất kỳ phép đo nào thì trả False: mô hình là đường mặc định, và đổi đường dựa trên số
    liệu không có là cách chắc chắn nhất để làm hỏng những ca vốn đang chạy tốt.
    """
    if has_ambiguous_tokens or not _finite(timing_cost):
        return False
    cost = float(timing_cost)
    if cost < DSP_TRUSTED_TIMING_COST:
        return True
    return _finite(snr_db) and float(snr_db) > SNR_OUT_OF_RANGE_DB and cost < DSP_MAX_TIMING_COST


def dsp_result_usable(tokens, profile) -> bool:
    """Kết quả của bộ DSP có tra được bằng bảng của profile không.

    Trên clip nhiễu, phân đoạn sai đẻ ra những chuỗi như `.--..` hay `..-.-` mà không bảng nào
    có. Một kết quả chứa mẫu như vậy tự nó đã nói rằng bộ DSP đọc sai, nên giữ đường mô hình;
    đem chúng đi tra bảng thì vỡ với `KeyError` (đo trên T1 là 67/500 clip).
    """
    from morsedesk.model.vocab import SPACE

    return all(tok == SPACE or tok in profile.map for tok in tokens)


# Chi phí timing thấp nói rằng những đoạn bộ DSP ĐÃ đọc khớp lưới 1/3/7 dit — KHÔNG nói rằng nó đã
# đọc HẾT tín hiệu. Trên tín hiệu fading, bộ DSP (ngưỡng cố định) đọc hoàn hảo đoạn mạnh và bỏ trống
# đoạn chìm dưới ngưỡng, nên chi phí vẫn < 0,02 trong khi cả đoạn bản tin biến mất. Đo 23/09 với E9,
# cửa sổ 12 s: qsb@20 dB đi đường DSP 10 clip CER 72,5 %, đường mô hình 10 clip CER 11,5 % (dev).
# Kiểu hỏng là XÓA, nên văn bản của DSP ngắn hẳn văn bản của mô hình — dấu hiệu đó rẻ và đúng chỗ.
# Chọn trên bộ dev: 0,7 và 0,8 cho cùng kết quả, 0,9 và 0,95 tốt hơn một chút và y hệt nhau.
# Dev 12,25 -> 10,38 % [-2,94; -0,96], xác nhận T1 9,79 -> 8,99 % [-1,57; -0,18], T2 không đổi
# (không bản ghi thật nào bị chuyển). Quy tắc "chỉ tin DSP khi SNR > 30" thắng nhiều hơn trên dữ
# liệu tổng hợp nhưng làm T2 xấu từ 3,93 lên 12,64 % — lý do nhánh chi phí timing tồn tại.
DSP_MIN_LENGTH_RATIO = 0.9


def dsp_is_complete(dsp_text: str, model_text: str) -> bool:
    """Bộ DSP có đọc được gần hết những gì mô hình nghe thấy không (không tính dấu cách).

    Mô hình không có gì để so thì không có cơ sở nghi ngờ bộ DSP.
    """
    n_model = len(model_text.replace(" ", ""))
    return n_model == 0 or len(dsp_text.replace(" ", "")) >= DSP_MIN_LENGTH_RATIO * n_model
