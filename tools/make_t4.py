"""Bộ đo T4: bản ghi Morse THẬT tải từ internet, có đáp án nguyên văn (không do dự án tự sinh).

Nguồn và cách kiểm từng cặp (audio, đáp án): .superpowers/sdd/research-real-audio-2026-09-24.md.
Mọi cặp dưới đây đã được giải thử bằng MorseDesk để chắc đáp án khớp audio. Chép audio từ thư mục
tải thử (`--probe`) vào testdata/private/t4/<nguồn>/ (gitignored — dùng nội bộ, KHÔNG phân phối lại)
và viết manifest.jsonl cho `morsedesk.cli bench`. Báo CER TÁCH theo nguồn (`by_source`), không gộp.

    uv run python tools/make_t4.py [--probe <thư mục tải thử>] [--out testdata/private/t4]

Lần đầu dự án có số đo tiếng Nga KHÔNG tự sinh (đề thi SRR). Tiếng Kazakh: không tìm được bản ghi
thật nào có đáp án (9 chữ Kazakh dùng chung mẫu với chữ Nga nên phần NGHE đo bằng SRR được; phần
chọn Қ/К chỉ đo được ở tầng LM).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from morsedesk.textio import force_utf8_streams  # noqa: E402
from tools.make_t2_manifest import clean_reference, original_reference, write_jsonl  # noqa: E402

DEFAULT_PROBE = Path.home() / "AppData/Local/Temp/claude/realaudio_probe"

# (nguồn, profile, kiểu gõ, kênh, audio, đáp án, mào đầu, đuôi) — đường dẫn tương đối với --probe.
# Mào đầu/đuôi: thứ audio CÓ phát mà file đáp án không ghi (SRR mở bằng "ЖЖЖ =", kết bằng "+").
PAIRS: list[tuple[str, str, str, str, str, str, str, str]] = [
    *[("srr_ru", "ru", "machine", "clean", f"ru/srr_exam_{i:02d}.wav", f"ru/srr_exam_{i:02d}.txt",
       "ЖЖЖ =", "+") for i in range(1, 26)],
    # Đáp án chép tay từ màn hình video: bài 1–2 lệch 5–11 chữ quanh Ю, chưa nghe lại — tách nguồn riêng.
    *[("fedyai_ru_unverified", "ru", "machine", "clean", f"ru/fedyai_letters50_text{i}.wav",
       f"ru/fedyai_letters50_text{i}.txt", "ЖЖЖ =", "") for i in (1, 2, 3)],
    ("arrl_archive", "en", "machine", "clean", "en_arrl/131211_05WPM.mp3", "en_arrl/131211_05.txt", "", ""),
    ("arrl_archive", "en", "machine", "clean", "en_arrl/190813_30WPM.mp3", "en_arrl/190813_30.txt", "", ""),
    ("arrl_archive", "en", "machine", "clean", "en_arrl/260304_075WPM.mp3", "en_arrl/260304_07_5.txt", "", ""),
    ("vk6flab", "en", "machine", "clean", "en_other/foundations_vk6flab/20110522.mp3",
     "en_other/foundations_vk6flab/20110522.txt", "", ""),
    ("vk6flab", "en", "machine", "clean", "en_other/foundations_vk6flab/20240407.mp3",
     "en_other/foundations_vk6flab/20240407.txt", "", ""),
    ("k7qo", "en", "machine", "clean", "en_other/k7qo/040.MP3", "en_other/k7qo/040.txt", "", ""),
    ("k7qo", "en", "machine", "clean", "en_other/k7qo/305.MP3", "en_other/k7qo/305.txt", "", ""),
    *[("skcc_wotw", "en", "machine", "clean", f"en_other/skcc/wotw_01110{i}.mp3",
       f"en_other/skcc/wotw_01110{i}.txt", "", "") for i in (1, 2, 3)],
    # Gõ TAY, thu từ sóng VLF thật (17,2 kHz, QRN nặng); đáp án = bản chép theo tai của SRAA (giữ cả
    # lỗi gõ thật như SAQQ, ANNIVER4RY), không phải văn bản công bố.
    ("saq_onair_hand", "en", "hand", "onair", "en_onair/saq/sraa_SAQ_2016-07-03_0900.mp3",
     "en_onair/saq/text_sraa_SAQ_2016-07-03_0900_units.txt", "", ""),
    ("saq_onair_hand", "en", "hand", "onair", "en_onair/saq/sraa_SAQ_2022-11-16.mp3",
     "en_onair/saq/text_sraa_SAQ_2022-11-16_units.txt", "", ""),
]

LICENSE = {
    "srr_ru": "SRR (Союз радиолюбителей России) đề thi — dùng nội bộ",
    "fedyai_ru_unverified": "YouTube Fedyai — dùng nội bộ",
    "arrl_archive": "ARRL W1AW code practice — dùng nội bộ, không phân phối",
    "vk6flab": "Foundations of Amateur Radio (VK6FLAB) — dùng nội bộ",
    "k7qo": "K7QO Code Course — dùng nội bộ",
    "skcc_wotw": "SKCC Learning Center — dùng nội bộ",
    "saq_onair_hand": "SRAA archive.org CC BY-NC 3.0",
}

_WPM_RE = re.compile(r"_(\d+)WPM", re.IGNORECASE)


def read_answer(path: Path) -> str:
    """Đáp án ARRL cũ ghi prosign bằng byte Windows-1252: 0x89 = BT (phát `=`), 0x83 = AS (`&`).
    Đọc utf-8 `errors="replace"` (như make_t2_manifest) làm MẤT cả hai, rồi `=`/`&` mà model giải ra
    bị tính là chèn thừa (~1,7 điểm CER ở file 5 WPM)."""
    data = path.read_bytes().replace(b"\x89", b" = ").replace(b"\x83", b" & ")
    return data.decode("utf-8", errors="replace").replace("�", " ")


def parse_wpm(name: str) -> float | None:
    """ARRL đặt 7,5 WPM là `_075WPM` (`parse_wpm` của make_t2_manifest đọc thành 75)."""
    m = _WPM_RE.search(name)
    if not m:
        return None
    digits = m.group(1)
    return int(digits) / 10 if digits.startswith("0") and len(digits) == 3 else float(digits)


def build(probe: Path, out: Path) -> list[dict]:
    rows = []
    for source, profile, keying, channel, audio, answer, head, tail in PAIRS:
        src_audio, src_text = probe / audio, probe / answer
        if not src_audio.exists() or not src_text.exists():
            print(f"thiếu, bỏ qua: {audio}")
            continue
        dst = out / source / src_audio.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src_audio, dst)
        raw = read_answer(src_text).strip()
        framed = " ".join(p for p in (head, raw, tail) if p)
        rows.append({
            "path": str(dst.resolve()),
            "text": clean_reference(framed, profile),
            "text_original": original_reference(framed, profile),
            "raw_text": raw,
            "source": source,
            "license": LICENSE[source],
            "wpm": parse_wpm(src_audio.name),
            "profile": profile,
            "keying": keying,
            "channel": channel,
            "synthetic": False,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Dựng bộ đo T4 (bản ghi thật có đáp án)")
    ap.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    ap.add_argument("--out", type=Path, default=Path("testdata/private/t4"))
    a = ap.parse_args(argv)
    rows = build(a.probe, a.out)
    write_jsonl(rows, a.out / "manifest.jsonl")
    by: dict[str, int] = {}
    for r in rows:
        by[r["source"]] = by.get(r["source"], 0) + 1
    print(f"{len(rows)} file -> {a.out / 'manifest.jsonl'}  {json.dumps(by, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
