"""Ghép file âm thanh với file text đáp án cùng tên thành manifest JSONL cho bộ test T2.

Dùng cho ARRL W1AW (MP3 + .txt), Wikimedia Commons, SRAA, kho QSO... Text được lọc
qua profile để chỉ giữ ký tự bộ giải mã có thể sinh ra (đánh giá công bằng).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from morsedesk.encode.text import text_to_tokens
from morsedesk.lm.profile import load_profile

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".oga")
_WPM_RE = re.compile(r"_(\d+(?:\.\d+)?)WPM", re.IGNORECASE)


def parse_wpm(name: str) -> float | None:
    m = _WPM_RE.search(name)
    return float(m.group(1)) if m else None


def clean_reference(raw: str, profile_id: str) -> str:
    profile = load_profile(profile_id)
    return profile.render(text_to_tokens(raw, profile, strict=False))


def build_manifest(audio_dir: Path, source: str, profile_id: str) -> list[dict]:
    rows = []
    for audio in sorted(p for p in Path(audio_dir).iterdir() if p.suffix.lower() in AUDIO_EXT):
        txt = audio.with_suffix(".txt")
        if not txt.exists():
            continue
        raw = txt.read_text(encoding="utf-8", errors="replace")
        rows.append({
            "path": str(audio.resolve()),
            "text": clean_reference(raw, profile_id),
            "raw_text": raw.strip(),
            "source": source,
            "wpm": parse_wpm(audio.name),
            "profile": profile_id,
        })
    return rows


def write_jsonl(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tạo manifest T2 từ thư mục audio + txt")
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("--source", required=True, help="nhãn nguồn, ví dụ arrl, commons, sraa")
    ap.add_argument("--profile", default="en")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rows = build_manifest(a.audio_dir, a.source, a.profile)
    write_jsonl(rows, a.out)
    print(f"{len(rows)} mục -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
