"""Chọn bảng mã cho văn bản sắp mã hóa — tất định, không đoán.

Khác hẳn bài toán nhận diện ngôn ngữ lúc **giải mã**: ở đó chỉ có tín hiệu nhiễu và phải dựa vào
mô hình ngôn ngữ, nên kết quả là xác suất. Ở chiều **mã hóa**, văn bản nằm ngay trước mắt và câu
hỏi duy nhất là bảng nào chứa đủ ký tự — trả lời được chắc chắn.

Ba sự thật đo được về ba bảng của dự án, và chúng là lý do quy tắc này an toàn:

- `kk-cyrl-ru` là **siêu tập** của `ru`: 60 ký tự chung có mẫu giống hệt, cộng 9 chữ riêng
  (Ә Ғ Қ Ң Ө Ұ Ү Һ І). `ru` không có ký tự nào mà `kk` thiếu.
- Số và dấu câu có mẫu giống hệt ở cả ba bảng.
- `en` và `ru` không chia nhau chữ cái nào.

Hệ quả: khi nhiều profile cùng phủ được văn bản, chúng sinh ra **đúng cùng một chuỗi Morse**.
Nên "tự động" ở đây không phải là đoán rồi hy vọng: tín hiệu phát ra giống hệt nhau dù chọn
profile nào trong số đó. `tests/unit/test_profile_detect.py` canh chính điều này.
"""

from __future__ import annotations

from morsedesk.encode.text import normalize
from morsedesk.lm.profile import load_profile

# Thứ tự ưu tiên khi nhiều bảng cùng phủ được. Chỉ để kết quả ổn định giữa các lần chạy — mọi
# lựa chọn trong danh sách đều cho cùng chuỗi Morse.
PREFERENCE = ("en", "ru", "kk-cyrl-ru")

UNSUPPORTED = None      # không bảng nào phủ hết văn bản

_PROFILES: dict = {}


def _profile(pid: str):
    """Profile nạp MỘT lần. Trang Tạo mã gọi `detect_profile` ở mỗi phím gõ; `load_profile` đọc và
    phân tích lại hai file YAML mỗi lần — đo 25/09: 6 lần đọc đĩa mỗi phím, phần lớn độ trễ khi gõ."""
    if pid not in _PROFILES:
        _PROFILES[pid] = load_profile(pid)
    return _PROFILES[pid]


def profiles_covering(text: str) -> list[str]:
    """Các profile mã hóa được TOÀN BỘ văn bản, theo thứ tự ưu tiên.

    Văn bản rỗng trả danh sách rỗng: không có gì để mã hóa thì cũng không có gì để chọn.
    """
    out: list[str] = []
    for pid in PREFERENCE:
        profile = _profile(pid)
        norm = normalize(text, profile)
        if not norm:
            return []
        if all(ch == " " or ch in profile.letter_to_pattern for ch in norm):
            out.append(pid)
    return out


def detect_profile(text: str) -> str | None:
    """Profile nên dùng cho `text`, hoặc None nếu không bảng nào phủ hết.

    None nghĩa là văn bản trộn hệ chữ (ví dụ Latin lẫn Cyrillic) hoặc chứa ký tự ngoài mọi bảng
    — giao diện phải nói rõ ký tự nào, chứ không được âm thầm bỏ qua.
    """
    covering = profiles_covering(text)
    return covering[0] if covering else UNSUPPORTED
