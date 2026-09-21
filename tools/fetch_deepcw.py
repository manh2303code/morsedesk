"""Chép hoặc tải model DeepCW về `models/deepcw/` (gitignored như `models/acoustic.onnx`).

Ưu tiên `--src` (thư mục đã có sẵn `model.onnx` + `model.onnx.json`), sau đó tới biến môi trường
`DEEPCW_SRC`, cuối cùng mới tải từ GitHub ở đúng commit đã đo. Luôn kiểm sha256 trừ khi `--no-verify`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from morsedesk.model.deepcw import DEEPCW_DIR, MODEL_BYTES, MODEL_SHA256
from morsedesk.textio import force_utf8_streams

COMMIT = "8e264d243bbd4467bd19f3f28292219405b47e0e"
BASE_URL = f"https://raw.githubusercontent.com/e04/deepcw-engine/{COMMIT}"
FILES = ("model.onnx", "model.onnx.json")
CLONE_HINT = (
    f"nếu tải hỏng (Git LFS hoặc chặn mạng), clone thủ công rồi chạy lại với --src:\n"
    f"  git clone https://github.com/e04/deepcw-engine <thư mục> && cd <thư mục> && git checkout {COMMIT}"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_one(name: str, src_dir: Path | None, dst_dir: Path) -> Path:
    dst = dst_dir / name
    if src_dir is not None:
        shutil.copyfile(src_dir / name, dst)
    else:
        url = f"{BASE_URL}/{name}"
        print(f"tải {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
    return dst


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Tải model DeepCW về models/deepcw/")
    ap.add_argument("--src", type=Path, default=None,
                    help="thư mục có sẵn model.onnx và model.onnx.json (mặc định: biến DEEPCW_SRC)")
    ap.add_argument("--out", type=Path, default=DEEPCW_DIR)
    ap.add_argument("--no-verify", action="store_true", help="bỏ kiểm sha256 (chỉ dùng trong test)")
    a = ap.parse_args(argv)

    src = a.src if a.src is not None else (Path(os.environ["DEEPCW_SRC"]) if os.environ.get("DEEPCW_SRC") else None)
    a.out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in FILES:
        try:
            written.append(fetch_one(name, src, a.out))
        except OSError as e:
            print(f"lỗi: không lấy được {name}: {e}\n{CLONE_HINT}", file=sys.stderr)
            for p in written:
                p.unlink(missing_ok=True)
            return 2
    model = a.out / "model.onnx"
    size = model.stat().st_size
    digest = sha256_file(model)
    if not a.no_verify and (digest != MODEL_SHA256 or size != MODEL_BYTES):
        print(f"lỗi: sha256 {digest} ({size} byte) khác bản đã đo {MODEL_SHA256} ({MODEL_BYTES} byte)\n"
              f"{CLONE_HINT}", file=sys.stderr)
        for p in written:
            p.unlink(missing_ok=True)
        return 2
    print(f"{model} {size} byte sha256 {digest[:12]}… OK")
    print(f"{a.out / 'model.onnx.json'} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
