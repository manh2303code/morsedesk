"""Sinh .ts bằng pyside6-lupdate, điền bản dịch từ translations.json, biên dịch .qm bằng pyside6-lrelease.

Dùng: uv run python tools/build_i18n.py            # sinh lại .ts/.qm
      uv run python tools/build_i18n.py --check    # chỉ kiểm bảng dịch có đủ chuỗi tr() không (không cần Qt tools)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET  # .ts do pyside6-lupdate của chính dự án sinh (đầu vào tin cậy, không cần defusedxml)
from pathlib import Path

from morsedesk.textio import force_utf8_streams

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "morsedesk" / "app"
I18N_DIR = APP_DIR / "i18n"
LANGS = ("ru", "kk")
SOURCES = sorted(p for p in APP_DIR.rglob("*.py"))
_TR_RE = re.compile(r'self\.tr\("((?:[^"\\]|\\.)*)"\)')


def tr_literals(paths: list[Path]) -> set[str]:
    """Trích mọi chuỗi nguồn `self.tr("...")` (double-quote) trong các file `paths`."""
    out: set[str] = set()
    for p in paths:
        for m in _TR_RE.finditer(p.read_text(encoding="utf-8")):
            out.add(m.group(1).encode("utf-8").decode("unicode_escape") if "\\" in m.group(1) else m.group(1))
    return out


def fill_ts(ts_path: Path, table: dict[str, str]) -> int:
    """Điền `<translation>` cho mỗi `<message>` theo `<source>` khớp khóa trong `table`.

    Xóa thuộc tính `type="unfinished"` khi có bản dịch; giữ lại (đặt lại) khi không có.
    Trả về số message còn `unfinished` sau khi điền.
    """
    tree = ET.parse(ts_path)
    left = 0
    for msg in tree.getroot().iter("message"):
        src = msg.findtext("source") or ""
        tr = msg.find("translation")
        if tr is None:
            tr = ET.SubElement(msg, "translation")
        if src in table:
            tr.text = table[src]
            tr.attrib.pop("type", None)
        else:
            tr.set("type", "unfinished")
            left += 1
    tree.write(ts_path, encoding="utf-8", xml_declaration=True)
    text = ts_path.read_text(encoding="utf-8")
    if "<!DOCTYPE TS>" not in text:
        text = text.replace("?>", "?>\n<!DOCTYPE TS>", 1)
        ts_path.write_text(text, encoding="utf-8")
    return left


def _tool(name: str) -> str:
    """Tìm binary Qt (`pyside6-lupdate`/`pyside6-lrelease`) trên PATH hoặc cạnh python hiện tại."""
    exe = shutil.which(name) or shutil.which(name + ".exe")
    if exe is None:
        scripts = Path(sys.executable).parent
        for cand in (scripts / name, scripts / f"{name}.exe"):
            if cand.exists():
                return str(cand)
        raise SystemExit(f"không tìm thấy {name}; cài extra gui: uv sync --all-extras")
    return exe


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Dựng bản dịch Qt cho GUI")
    ap.add_argument("--check", action="store_true", help="chỉ kiểm bảng dịch đủ chuỗi")
    a = ap.parse_args(argv)
    table = json.loads((I18N_DIR / "translations.json").read_text(encoding="utf-8"))
    literals = tr_literals(SOURCES)
    missing = {lang: sorted(s for s in literals if s not in table[lang]) for lang in LANGS}
    for lang, miss in missing.items():
        for s in miss:
            print(f"{lang}: thiếu {s!r}")
    if a.check:
        return 1 if any(missing.values()) else 0
    ts_files = [I18N_DIR / f"morsedesk_{lang}.ts" for lang in LANGS]
    subprocess.run(
        [_tool("pyside6-lupdate"), *map(str, SOURCES), "-no-obsolete", "-ts", *map(str, ts_files)],
        check=True,
    )
    for lang, ts in zip(LANGS, ts_files, strict=True):
        left = fill_ts(ts, table[lang])
        subprocess.run([_tool("pyside6-lrelease"), str(ts), "-qm", str(ts.with_suffix(".qm"))], check=True)
        print(f"{lang}: {ts.name} -> {ts.with_suffix('.qm').name}, chưa dịch {left}")
    return 1 if any(missing.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
