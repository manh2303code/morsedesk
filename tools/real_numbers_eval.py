"""Đo SỐ trên bản ghi THẬT (manifest JSONL: path, text, profile, source): CER, lỗi chữ số, nhóm đúng trọn.

Bộ T5 (testdata/private/t5, gitignored — dùng nội bộ): trạm số M01/M12/M14 thu trên sóng thật, bản
chép của Priyom. Trạm số dùng SỐ VIẾT TẮT (0 = T, một gạch dài) — thứ mà bộ đo tổng hợp không có.
Thêm cột `ggmorse` (bộ giải của ggerganov, chạy trong WSL) nếu có `--ggmorse <đường dẫn binary WSL>`.

    uv run python tools/real_numbers_eval.py [--manifest testdata/private/t5/manifest.jsonl]
        [--configs app,auto,model+LM,model,live] [--ggmorse /mnt/c/.../ggmorse-wav]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.numeric_eval as ne  # noqa: E402
from morsedesk.audio.io import load_audio  # noqa: E402
from morsedesk.parallel import default_workers, map_parallel  # noqa: E402
from tools.numeric_eval import _decoder, live_decode, score  # noqa: E402


def wsl_path(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    return f"/mnt/{s[0].lower()}{s[2:]}"


def ggmorse(binary: str, path: Path) -> str:
    cmd = ["wsl.exe", "-d", "Ubuntu-26.04", "--", binary, wsl_path(path)]
    out = subprocess.run(cmd, capture_output=True, timeout=1800)
    lines = [ln for ln in out.stdout.decode("utf-8", "replace").splitlines() if "	" in ln]
    return lines[0].split("	", 1)[1].strip() if lines else ""


def run_one(job: tuple) -> dict:
    row, configs, model = job
    ne._MODEL = model
    x, sr = load_audio(row["path"])
    out = {"source": row["source"], "file": Path(row["path"]).name, "ref": row["text"], "seconds": len(x) / sr}
    for name in configs:
        dec = _decoder(row["profile"], name)
        t0 = time.perf_counter()
        if name.startswith("live"):
            hyp, lang = live_decode(dec, x)
        else:
            r = dec.decode_array(x, sr)
            hyp, lang = r.text, r.language
        out[name] = {"hyp": hyp, "language": lang, "seconds": time.perf_counter() - t0, **score(row["text"], hyp)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="testdata/private/t5/manifest.jsonl")
    ap.add_argument("--configs", default="app,auto,model+LM,model,live")
    ap.add_argument("--model", default=None)
    ap.add_argument("--ggmorse", default=None, help="đường dẫn WSL tới ggmorse-wav")
    ap.add_argument("--out", default="runs/t5_numbers")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    rows = [json.loads(ln) for ln in Path(a.manifest).read_text(encoding="utf-8").splitlines() if ln.strip()]
    configs = tuple(c for c in a.configs.split(",") if c)
    res = map_parallel(run_one, [(r, configs, a.model) for r in rows],
                       a.workers if a.workers is not None else default_workers())
    if a.ggmorse:
        for r, row in zip(res, rows, strict=True):
            hyp = ggmorse(a.ggmorse, Path(row["path"]))
            r["ggmorse"] = {"hyp": hyp, **score(row["text"], hyp)}
        configs = configs + ("ggmorse",)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'file':44s}" + "".join(f"{c:>20s}" for c in configs))
    for r in res:
        print(f"{r['file'][:44]:44s}" + "".join(
            f"{100 * r[c]['der']:7.1f}% {100 * r[c]['groups_ok'] / max(1, r[c]['groups']):6.1f}%  " for c in configs))
    for c in configs:
        der = sum(r[c]["digit_errors"] for r in res) / max(1, sum(r[c]["digits"] for r in res))
        gok = sum(r[c]["groups_ok"] for r in res) / max(1, sum(r[c]["groups"] for r in res))
        cer = sum(r[c]["cer"] * len(r["ref"]) for r in res) / sum(len(r["ref"]) for r in res)
        print(f"TỔNG {c:10s} lỗi chữ số {100 * der:6.2f} %   nhóm đúng {100 * gok:6.2f} %   CER {100 * cer:6.2f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
