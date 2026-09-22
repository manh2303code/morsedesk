"""Chọn profile cho văn bản sắp mã hóa — tất định, không đoán.

Khác hẳn bài toán nhận diện ngôn ngữ lúc GIẢI MÃ (ở đó chỉ có tín hiệu nhiễu và phải dựa vào mô
hình ngôn ngữ). Ở chiều mã hóa, văn bản nằm ngay trước mắt, nên câu hỏi duy nhất là bảng nào
chứa đủ ký tự — trả lời được chắc chắn.

Ba sự thật đo được về ba bảng, và chúng là lý do quy tắc này an toàn:
- `kk-cyrl-ru` là **siêu tập** của `ru`: 60 ký tự chung có mẫu giống hệt, cộng 9 chữ riêng
  (Ә Ғ Қ Ң Ө Ұ Ү Һ І); `ru` không có ký tự nào mà `kk` thiếu;
- số và dấu câu (`0-9 . , ? / = + - : ; ( ) " ' @` ...) có mẫu giống hệt ở cả ba;
- `en` và `ru` không chia nhau chữ cái nào.

Hệ quả: khi nhiều profile cùng phủ được văn bản, chúng sinh ra **đúng cùng một chuỗi Morse**,
nên chọn cái nào cũng cho cùng tín hiệu. Đó là điều làm cho "tự động" ở đây là chính xác chứ
không phải may rủi.
"""

import pytest

from morsedesk.api import Encoder
from morsedesk.encode.detect import UNSUPPORTED, detect_profile, profiles_covering


@pytest.mark.parametrize("text,expected", [
    ("CQ CQ DE R1ABC K", "en"),
    ("599 TU 73", "en"),
    ("ПРИВЕТ МИР", "ru"),
    ("ВСЕМ ВСЕМ ДЕ Р1АБВ К", "ru"),
    ("СӘЛЕМ ӘЛЕМ", "kk-cyrl-ru"),
    ("ҚҰРМЕТТІ ДОС", "kk-cyrl-ru"),
])
def test_detects_the_expected_profile(text, expected):
    assert detect_profile(text) == expected


def test_digits_alone_are_covered_by_every_profile():
    """Số có mẫu giống hệt ở ba bảng nên profile nào cũng cho cùng tín hiệu."""
    assert set(profiles_covering("73")) == {"en", "ru", "kk-cyrl-ru"}
    assert detect_profile("73") == "en"          # chọn ổn định, không phụ thuộc thứ tự từ điển


def test_mixed_scripts_have_no_profile():
    assert detect_profile("HELLO МИР") is UNSUPPORTED
    assert profiles_covering("HELLO МИР") == []


def test_empty_text_has_no_profile():
    assert detect_profile("") is UNSUPPORTED
    assert detect_profile("   ") is UNSUPPORTED


def test_kazakh_letters_force_kazakh():
    for ch in "ӘҒҚҢӨҰҮҺІ":
        assert detect_profile(f"ТЕСТ {ch}") == "kk-cyrl-ru", ch


def test_every_covering_profile_gives_the_same_morse():
    """Điểm mấu chốt: khi nhiều profile cùng phủ được, tín hiệu đầu ra phải giống hệt nhau."""
    for text in ("73", "ПРИВЕТ МИР", "599", "МИР 73"):
        outputs = {Encoder(pid).to_morse_string(text) for pid in profiles_covering(text)}
        assert len(outputs) == 1, (text, outputs)


def test_lowercase_is_accepted():
    assert detect_profile("cq de k") == "en"
    assert detect_profile("привет") == "ru"
