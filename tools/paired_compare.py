"""So nhiều kết quả `beam_eval.py` với một mốc, bằng bootstrap GHÉP CẶP trên cùng các clip.

Vì sao ghép cặp: CER tổng của 500 clip có sai số chuẩn khoảng ±1 điểm, từng kênh (100 clip) tới
±0,5-2,8 điểm — nhưng đó là nhiễu giữa HAI BỘ clip khác nhau. Hai cấu hình chạy trên CÙNG các clip
thì phần lớn nhiễu đó triệt tiêu, nên hiệu của chúng đo được chính xác hơn nhiều.

Chỉ đổi mặc định khi khoảng tin cậy 95 % của hiệu nằm trọn dưới 0, VÀ kết quả lặp lại trên một
bộ khác bộ đã dùng để chọn. Thử nhiều cấu hình thì riêng may rủi cũng sinh ra một "người thắng":
đo 23/09, cấu hình tốt nhất trong 33 trên dev (-0,34 điểm) ra -0,01 trên T1.

    uv run python tools/paired_compare.py MANIFEST MOC.json KHAC1.json KHAC2.json ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from morsedesk import bench
from morsedesk.metrics import cer
from morsedesk.textio import force_utf8_streams


def per_clip(path: Path, refs: list[str]) -> tuple[dict, np.ndarray]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d["params"], np.array([cer(r, h) for r, h in zip(refs, d["hyps"], strict=True)])


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 3:
        print(__doc__)
        return 2
    rows = bench.load_rows(Path(args[0]))
    refs = [bench.reference_text(r, "onnx", True) for r in rows]
    _, base = per_clip(Path(args[1]), refs)
    idx = np.random.default_rng(0).integers(0, len(base), (5000, len(base)))
    out = []
    for f in args[2:]:
        params, c = per_clip(Path(f), refs)
        diff = c - base
        lo, hi = np.percentile(diff[idx].mean(axis=1), [2.5, 97.5])
        out.append((float(diff.mean()), float(lo), float(hi), params))
    print(f"mốc = {100 * base.mean():.2f} %. Hiệu âm = tốt hơn mốc.\n")
    for m, lo, hi, p in sorted(out, key=lambda t: t[0]):
        tag = ("TỐT HƠN chắc chắn" if hi < 0 else "XẤU HƠN chắc chắn" if lo > 0
               else "không phân biệt được")
        name = ", ".join(f"{k}={v:g}" for k, v in p.items()) or "(mặc định)"
        print(f"{name:44} {100 * m:+7.2f}   [{100 * lo:+.2f}, {100 * hi:+.2f}]   {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
