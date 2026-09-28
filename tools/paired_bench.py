"""So hai phiên bản MÃ trên cùng manifest, ghép cặp từng clip (bootstrap) — dùng đúng `morsedesk.bench.evaluate`.

    # 1) chạy và lưu kết quả từng clip (PYTHONPATH chọn phiên bản mã, vd. một git worktree của commit cũ)
    uv run python tools/paired_bench.py run MANIFEST OUT.json [--profile auto] [--workers 12] [--model X.onnx]
    # 2) so
    uv run python tools/paired_bench.py cmp BASE.json NEW.json

`bench` chỉ lưu số tổng; so hai cấu hình phải ghép cặp trên cùng clip (CLAUDE.md "Nhiễu đo").
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def cmd_run(a: argparse.Namespace) -> None:
    import morsedesk
    from morsedesk.bench import evaluate, load_rows

    rows = load_rows(Path(a.manifest))
    res = evaluate(rows, "onnx", Path(a.model) if a.model else None, None, a.profile, True, 64, None, a.workers)
    out = [{"path": r["path"], "ref": r["ref"], "hyp": r["hyp"], "cer": r["cer"],
            "channel": r.get("channel"), "snr": r.get("snr")} for r in res]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"code": str(Path(morsedesk.__file__).parent), "items": out},
                                      ensure_ascii=False), encoding="utf-8")
    print(f"{a.out}: {len(out)} clip, CER trung bình {100 * np.mean([r['cer'] for r in out]):.2f} %"
          f"  (mã: {Path(morsedesk.__file__).parent})")


def cmd_cmp(a: argparse.Namespace) -> None:
    base = {r["path"]: r for r in json.loads(Path(a.base).read_text(encoding="utf-8"))["items"]}
    new = {r["path"]: r for r in json.loads(Path(a.new).read_text(encoding="utf-8"))["items"]}
    keys = sorted(set(base) & set(new))
    b = np.array([base[k]["cer"] for k in keys])
    n = np.array([new[k]["cer"] for k in keys])
    d = n - b
    rng = np.random.default_rng(0)
    boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(5000)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"{len(keys)} clip: mốc {100 * b.mean():.2f} % -> mới {100 * n.mean():.2f} %  "
          f"(hiệu {100 * d.mean():+.2f}, KTC95 [{100 * lo:+.2f}; {100 * hi:+.2f}]) | "
          f"tốt hơn {int((d < -1e-9).sum())}, xấu hơn {int((d > 1e-9).sum())}")
    by = {}
    for k in keys:
        by.setdefault(base[k].get("channel") or "-", []).append(k)
    if len(by) > 1:
        for ch, ks in sorted(by.items()):
            bb = np.mean([base[k]["cer"] for k in ks])
            nn = np.mean([new[k]["cer"] for k in ks])
            print(f"   {ch:8s} {100 * bb:6.2f} -> {100 * nn:6.2f}")
    worst = sorted(keys, key=lambda k: new[k]["cer"] - base[k]["cer"], reverse=True)[:a.show]
    for k in worst:
        if new[k]["cer"] - base[k]["cer"] <= 0:
            break
        print(f"  xấu hơn {100 * (new[k]['cer'] - base[k]['cer']):+6.2f}  {Path(k).name}\n"
              f"     ref {base[k]['ref'][:90]}\n     cũ  {base[k]['hyp'][:90]}\n     mới {new[k]['hyp'][:90]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("manifest")
    r.add_argument("out")
    r.add_argument("--profile", default=None, help="ghi đè profile (vd. auto)")
    r.add_argument("--workers", type=int, default=None)
    r.add_argument("--model", default=None, help="ONNX model âm học (mặc định models/acoustic.onnx)")
    c = sub.add_parser("cmp")
    c.add_argument("base")
    c.add_argument("new")
    c.add_argument("--show", type=int, default=5)
    a = ap.parse_args()
    {"run": cmd_run, "cmp": cmd_cmp}[a.cmd](a)


if __name__ == "__main__":
    main()
