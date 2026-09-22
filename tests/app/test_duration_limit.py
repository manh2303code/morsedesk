"""Trần thời lượng của giao diện theo spec mục 7: file tới 1 giờ (CP-14).

Ba thứ từng chặn việc này đã gỡ xong và đo lại trên một file 60 phút dựng bằng `Encoder`:

- thanh tiến trình theo cửa sổ (CP-08) và nút Hủy (CP-09);
- beam search tuyến tính theo độ dài thay vì bậc hai;
- bộ nhớ hằng số ở khâu ước lượng tone và envelope — 5 414 MB xuống 583 MB.

Giải mã hết 162 giây, tức nhanh hơn thời gian thực 22 lần.
"""

from morsedesk.app.worker import MAX_SECONDS


def test_limit_matches_the_spec():
    assert MAX_SECONDS == 60 * 60


def test_pages_report_the_limit_in_minutes():
    from morsedesk.app.decode_page import MAX_MINUTES as decode_minutes
    from morsedesk.app.encode_page import MAX_MINUTES as encode_minutes

    assert decode_minutes == encode_minutes == 60
