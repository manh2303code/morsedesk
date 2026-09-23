"""Báo tiến trình và hủy giữa chừng cho một lần giải mã (CP-08, CP-09).

Lõi không biết gì về Qt: nó chỉ gọi hai callback do bên gọi đưa vào. Giao diện bọc chúng thành
signal và một cờ; CLI có thể bỏ trống cả hai và mọi thứ chạy như cũ.

Engine `onnx` báo trên một thang cố định `PROGRESS_SCALE`, chia theo tầng đúng tỉ trọng thời gian
ĐO ĐƯỢC (clip 15,8 s, Core Ultra 9, 23/09): tone + đặc trưng + model âm thanh ~5 %, beam + mô hình
ngôn ngữ ~91 %, bộ DSP và hoàn tất ~3 %. Trước đây đơn vị là "cửa sổ đã chạy qua model", tức chỉ
phần 5 % đầu: thanh nhảy lên 100 % rồi đứng im suốt 91 % thời gian còn lại — người dùng tưởng máy
treo. Engine `baseline` không chia cửa sổ nên chỉ báo một bước.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

PROGRESS_SCALE = 1000
STAGE_ACOUSTIC = (0.00, 0.08)     # tone, đặc trưng, model âm thanh
STAGE_LANGUAGE = (0.08, 0.97)     # beam search + mô hình ngôn ngữ (+ nhận diện ngôn ngữ)


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


@dataclass(frozen=True)
class StageProgress:
    """Một tầng của lần giải mã, đổi tiến trình riêng (done/total) thành phần [lo, hi] của thang.

    Có cùng giao diện `step(done, total)` với `DecodeProgress`, nên truyền thẳng vào các vòng lặp
    đang nhận `DecodeProgress`. Kiểm hủy vẫn đi qua `parent.step`, nên hủy có hiệu lực ở MỌI tầng
    — trước đây trong lúc beam chạy (phần lâu nhất) nút Hủy không có tác dụng.
    """

    parent: DecodeProgress | None
    lo: float
    hi: float

    def step(self, done: int, total: int) -> None:
        if self.parent is None:
            return
        frac = min(1.0, max(0.0, done / total)) if total > 0 else 1.0
        value = round(PROGRESS_SCALE * (self.lo + (self.hi - self.lo) * frac))
        self.parent.step(max(1, value), PROGRESS_SCALE)

    def sub(self, start: int, end: int, total: int) -> StageProgress:
        """Phần [start, end] trong `total` đơn vị của tầng này (vd. một đoạn trong nhiều đoạn)."""
        if total <= 0:
            return self
        span = self.hi - self.lo
        return StageProgress(self.parent, self.lo + span * start / total, self.lo + span * end / total)

    def finish(self) -> None:
        if self.parent is not None:
            self.parent.step(PROGRESS_SCALE, PROGRESS_SCALE)
