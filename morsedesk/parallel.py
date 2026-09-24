"""Chạy phép đo song song trên mọi lõi CPU (bench, thử nghiệm) — không dùng cho sản phẩm.

Giải mã một clip: beam search + LM chiếm ~93 % thời gian, mạng nơ-ron ~2 %. Beam search là thuật
toán rẽ nhánh, tra bảng từng khung — việc của CPU, không phải GPU. Thứ lãng phí thật là chạy từng
clip một trên MỘT lõi của máy 16 lõi; ở đây mỗi tiến trình con giải một clip, mỗi tiến trình chỉ
dùng một luồng (nếu không 14 tiến trình x 8 luồng ONNX tranh nhau và chậm hơn cả chạy tuần tự).

Kết quả giống hệt chạy tuần tự (mỗi clip vẫn đi đúng đường sản phẩm). Riêng số GIÂY mỗi clip thì
không tin được khi chạy song song — đo tốc độ nghiệm thu phải chạy `workers=1`.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

# Tiến trình con kế thừa môi trường lúc spawn: đặt TRƯỚC khi tạo pool để numpy/BLAS/ONNX của con
# chỉ dùng một luồng.
SINGLE_THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MORSEDESK_ORT_THREADS": "1",
}


def default_workers() -> int:
    """Chừa hai lõi cho hệ điều hành và giao diện."""
    return max(1, (os.cpu_count() or 2) - 2)


def map_parallel(fn: Callable[[T], R], items: Iterable[T], workers: int | None = None) -> list[R]:
    """`[fn(x) for x in items]`, giữ thứ tự, chia ra `workers` tiến trình (1 = tuần tự, như cũ).

    `fn` phải là hàm cấp module (pickle được). Mỗi tiến trình con tự dựng Decoder của nó một lần
    (xem bench._decoder) — tốn vài giây nạp LM, bù lại ngay khi có hơn vài chục clip.
    """
    items = list(items)
    workers = default_workers() if workers is None else int(workers)
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    saved = {k: os.environ.get(k) for k in SINGLE_THREAD_ENV}
    os.environ.update(SINGLE_THREAD_ENV)
    try:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=min(workers, len(items)), mp_context=ctx) as ex:
            return list(ex.map(fn, items, chunksize=1))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
