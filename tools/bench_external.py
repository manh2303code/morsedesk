"""Đo CER của công cụ ngoài (multimon-ng, pycw, DeepCW engine...) trên một manifest JSONL.

Mỗi file được chuyển sang WAV 8 kHz mono tạm (nhiều công cụ không đọc MP3), rồi chạy
lệnh mẫu có {path}; stdout là văn bản giải mã.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from morsedesk.audio.io import load_audio, save_audio
from morsedesk.metrics import cer
from morsedesk.textio import force_utf8_streams


def read_manifest(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_manifest(manifest: Path, cmd_template: str, strip_prefix: str = "", to_wav: bool = True,
                 timeout_s: float = 300.0) -> dict:
    rows_out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, row in enumerate(read_manifest(manifest)):
            src = Path(row["path"])
            if to_wav:
                x, sr = load_audio(src)
                wav = Path(tmp) / f"{i}.wav"
                save_audio(wav, x, sr)
            else:
                wav = src
            # Tách token TRƯỚC rồi mới thay {path}: nếu thay path (có thể chứa khoảng
            # trắng) vào chuỗi mẫu rồi mới shlex.split thì đường dẫn sẽ bị tách thành
            # nhiều token. posix=False trên Windows giữ dấu ngoặc kép nguyên trong token
            # (để tách đúng theo khoảng trắng) nhưng subprocess.run trên Windows cần argv
            # không còn dấu ngoặc kép bao ngoài, nếu không list2cmdline sẽ escape chúng
            # thành literal và CreateProcess không tìm thấy file (WinError 2). Bóc dấu
            # ngoặc kép bao ngoài từng token sau khi thay path.
            tokens = shlex.split(cmd_template, posix=(os.name != "nt"))
            cmd = [t.replace("{path}", str(wav)) for t in tokens]
            if os.name == "nt":
                cmd = [t[1:-1] if len(t) >= 2 and t[0] == t[-1] == '"' else t for t in cmd]
            t0 = time.time()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                # Cô lập lỗi từng file: một công cụ ngoài bị thiếu, treo, hoặc lỗi hệ
                # điều hành không được làm hỏng cả lượt đo; ghi nhận như một hyp rỗng
                # (CER = 1.0 với ref không rỗng) và tiếp tục file kế tiếp.
                rows_out.append({
                    "path": row["path"], "ref": row["text"], "hyp": "",
                    "cer": cer(row["text"], ""), "seconds": time.time() - t0,
                    "returncode": None, "stderr": "", "error": f"{type(e).__name__}: {e}",
                })
                continue
            lines = []
            for line in proc.stdout.splitlines():
                if strip_prefix and line.startswith(strip_prefix):
                    line = line[len(strip_prefix):]
                lines.append(line.strip())
            hyp = " ".join(ln for ln in lines if ln)
            rows_out.append({
                "path": row["path"], "ref": row["text"], "hyp": hyp,
                "cer": cer(row["text"], hyp), "seconds": time.time() - t0,
                "returncode": proc.returncode, "stderr": proc.stderr[-500:], "error": None,
            })
    mean = sum(r["cer"] for r in rows_out) / max(1, len(rows_out))
    return {"name": cmd_template.split()[0], "n": len(rows_out), "mean_cer": mean, "rows": rows_out}


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Đo công cụ giải mã ngoài trên manifest")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--cmd", required=True, help='ví dụ: "multimon-ng -a MORSE_CW -t wav {path}"')
    ap.add_argument("--name", required=True)
    ap.add_argument("--strip-prefix", default="")
    ap.add_argument("--no-wav", action="store_true", help="đưa file gốc, không chuyển WAV 8 kHz")
    ap.add_argument("--out-dir", type=Path, default=Path("bench_results"))
    a = ap.parse_args(argv)
    result = run_manifest(a.manifest, a.cmd, a.strip_prefix, to_wav=not a.no_wav)
    result["name"] = a.name
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"external_{a.name}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    n_err = sum(1 for r in result["rows"] if r.get("error"))
    print(f"{a.name}: n={result['n']} CER trung bình={result['mean_cer']:.3f} lỗi={n_err} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
