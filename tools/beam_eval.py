"""Chấm một cấu hình beam search trên một manifest, lưu CER từng clip để so ghép cặp.

Dùng để CHỈNH trọng số beam (`alpha`, `char_bonus`, `beta`, `lexicon_bonus`...). Chấm y hệt bộ đo
chính thức — nguyên `bench.evaluate` và `bench.gate` — chỉ thay giá trị mặc định của `BeamParams`
mà `api.Decoder` dựng ra, nên dither, chọn đường DSP và chấm CER giống hệt lúc chạy thật.

Chỉnh trên bộ DEV, không bao giờ trên T1:

    uv run python tools/make_t1.py --out testdata/generated/t1dev --seed-base 500000
    uv run python tools/beam_eval.py testdata/generated/t1dev/manifest.jsonl runs/beam/base.json
    uv run python tools/beam_eval.py testdata/generated/t1dev/manifest.jsonl runs/beam/x.json \\
        alpha=0.3 char_bonus=1.75
    uv run python tools/paired_compare.py testdata/generated/t1dev/manifest.jsonl \\
        runs/beam/base.json runs/beam/*.json

Chạy nhiều cấu hình song song (mỗi lượt gần như đơn luồng, máy 16 nhân chạy được ~11 lượt):
`OMP_NUM_THREADS=1 xargs -P 11`. Lưu ý `langid.py` dựng `BeamParams()` riêng nên KHÔNG nhận
giá trị vá ở đây: khi đổi mặc định thật trong `morsedesk/lm/beam.py`, phải đo lại cả `auto`.
"""

from __future__ import annotations

import functools
import json
import sys
import time
from pathlib import Path

import morsedesk.api as api
from morsedesk import bench
from morsedesk.lm.beam import BeamParams
from morsedesk.textio import force_utf8_streams


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print(__doc__)
        return 2
    manifest, out = Path(args[0]), Path(args[1])
    overrides = {k: float(v) for k, v in (a.split("=", 1) for a in args[2:])}
    api.BeamParams = functools.partial(BeamParams, **overrides)

    t0 = time.time()
    rows = bench.load_rows(manifest)
    res = bench.evaluate(rows, engine="onnx", lm=True)
    _, gate_cer, n = bench.gate(res)
    summary = {
        "params": overrides, "manifest": str(manifest),
        "gate_cer": gate_cer, "n": n,
        "wer": sum(r["wer"] for r in res) / len(res),
        "by_channel": {k: v["cer"] for k, v in bench.aggregate(res, "channel_actual").items()},
        "by_profile": {k: v["cer"] for k, v in bench.aggregate(res, "profile").items()},
        "errors": sum(1 for r in res if r.get("error")),
        "seconds": time.time() - t0,
        "hyps": [r["hyp"] for r in res],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    ch = " ".join(f"{k}={100 * v:.2f}" for k, v in summary["by_channel"].items())
    print(f"{overrides} -> CER {100 * gate_cer:.2f}% | {ch} | lỗi {summary['errors']} | "
          f"{summary['seconds']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
