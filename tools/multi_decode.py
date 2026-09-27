"""Giải một file bằng NHIỀU bộ giải mã độc lập — nguyên liệu cho vòng thẩm định đáp án (LLM as judge).

Bản ghi tải từ internet thường KHÔNG có bản chép. Đáp án tham chiếu được dựng bằng cách: các bộ giải
mã khác nhau (model mới/cũ, có/không LM, bộ cổ điển DSP, ggmorse) đọc cùng âm thanh; chỗ chúng đồng
ý là bằng chứng mạnh, chỗ chúng vênh nhau được đưa cho giám khảo (LLM) đọc ảnh đường bao
(tools/envelope_strips.py) để quyết. Mỗi từ kèm mốc thời gian để đối chiếu giữa các bộ.

    uv run python tools/multi_decode.py testdata/private/t6/*.mp3 --out runs/t6_multi
        [--ggmorse /mnt/c/.../ggmorse-wav]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from morsedesk.api import Decoder  # noqa: E402
from morsedesk.audio.io import load_audio  # noqa: E402
from morsedesk.parallel import default_workers, map_parallel  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
E17 = ROOT / "models" / "archive" / "acoustic-0.5.0-E17.onnx"
CONFIGS = ("app_auto", "app_ru", "app_en", "greedy", "dsp", "e17_ru")
_DEC: dict = {}


def decoder(name: str) -> Decoder:
    if name not in _DEC:
        _DEC[name] = {
            "app_auto": lambda: Decoder("auto", engine="onnx"),
            "app_ru": lambda: Decoder("ru", engine="onnx"),
            "app_en": lambda: Decoder("en", engine="onnx"),
            "greedy": lambda: Decoder("en", engine="onnx", lm=False, fallback=False, numbers=False),
            "dsp": lambda: Decoder("en", engine="baseline", lm=False, numbers=False),
            "e17_ru": lambda: Decoder("ru", engine="onnx", model_path=E17 if E17.exists() else None),
        }[name]()
    return _DEC[name]


def run_job(job: tuple[str, str]) -> dict:
    path, name = job
    x, sr = load_audio(path)
    r = decoder(name).decode_array(x, sr)
    return {"path": path, "config": name, "text": r.text, "language": r.language, "decoded_by": r.decoded_by,
            "wpm": r.wpm, "tone_hz": r.tone_hz, "snr_db": r.snr_db, "warnings": [w.code for w in r.warning_codes],
            "words": [{"text": w.text, "start": round(w.start_s, 3), "end": round(w.end_s, 3),
                       "conf": round(w.confidence, 3)} for w in r.words]}


def ggmorse(binary: str, path: str) -> str:
    """ggmorse-wav đọc WAV: đổi sang WAV 8 kHz mono trước."""
    with tempfile.TemporaryDirectory(dir=ROOT / "runs") as d:
        wav = Path(d) / "x.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "8000", str(wav)], check=True)
        s = str(wav.resolve()).replace("\\", "/")
        out = subprocess.run(["wsl.exe", "-d", "Ubuntu-26.04", "--", binary, f"/mnt/{s[0].lower()}{s[2:]}"],
                             capture_output=True, timeout=3600)
    lines = [ln for ln in out.stdout.decode("utf-8", "replace").splitlines() if "\t" in ln]
    return lines[0].split("\t", 1)[1].strip() if lines else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="runs/multi_decode")
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--ggmorse", default=None)
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    jobs = [(str(Path(f)), c) for f in a.files for c in a.configs.split(",") if c]
    rows = map_parallel(run_job, jobs, a.workers if a.workers is not None else default_workers())
    if a.ggmorse:
        for f in a.files:
            rows.append({"path": str(Path(f)), "config": "ggmorse", "text": ggmorse(a.ggmorse, f), "words": []})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in a.files:
        mine = {r["config"]: r for r in rows if r["path"] == str(Path(f))}
        (out / f"{Path(f).stem}.json").write_text(json.dumps(mine, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"== {Path(f).name}")
        for c, r in mine.items():
            print(f"  {c:9s} [{r.get('language', '')}/{r.get('decoded_by', '')}] {r['text'][:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
