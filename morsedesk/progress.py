"""Báo tiến trình và hủy giữa chừng cho một lần giải mã (CP-08, CP-09).

Lõi không biết gì về Qt: nó chỉ gọi hai callback do bên gọi đưa vào. Giao diện bọc chúng thành
signal và một cờ; CLI có thể bỏ trống cả hai và mọi thứ chạy như cũ.

Đơn vị tiến trình là **cửa sổ đặc trưng đã chạy qua mô hình**, vì đó là phần chiếm gần hết thời
gian của một lần giải mã file dài. Engine `baseline` không chia cửa sổ nên chỉ báo một bước.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


class DecodeCancelled(Exception):
    """Người dùng hủy giữa chừng. Không phải lỗi: bên gọi bắt và trở lại trạng thái rảnh."""


@dataclass(frozen=True)
class DecodeProgress:
    on_step: Callable[[int, int], None] | None = None
    should_cancel: Callable[[], bool] | None = None

    def step(self, done: int, total: int) -> None:
        """Báo đã xong `done`/`total` bước; ném `DecodeCancelled` nếu bên gọi xin hủy.

        Kiểm hủy TRƯỚC khi báo tiến trình: lần hủy cuối cùng không nên đẩy thanh tiến trình
        nhảy thêm một nấc rồi mới biến mất.
        """
        if self.should_cancel is not None and self.should_cancel():
            raise DecodeCancelled()
        if self.on_step is not None:
            self.on_step(int(done), int(total))
