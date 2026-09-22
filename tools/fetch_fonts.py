"""Tải font DejaVu Sans và Noto Sans vào `morsedesk/app/fonts/` (CP-11).

Thư mục không nằm trong repo vì là file nhị phân lớn; AppImage đóng gói nó theo. Chạy một lần:

    uv run python tools/fetch_fonts.py
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

from morsedesk.app.fonts import FONT_DIR
from morsedesk.textio import force_utf8_streams

UA = "MorseDesk-fonts/1.0 (offline research)"
DEJAVU_ZIP = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
DEJAVU_WANT = ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf")
NOTO_TTF = ("https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoSans/hinted/ttf/"
            "NotoSans-Regular.ttf")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main() -> int:
    force_utf8_streams()
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(fetch(DEJAVU_ZIP))) as z:
            for name in z.namelist():
                base = Path(name).name
                if base in DEJAVU_WANT:
                    (FONT_DIR / base).write_bytes(z.read(name))
                    written.append(base)
        (FONT_DIR / "NotoSans-Regular.ttf").write_bytes(fetch(NOTO_TTF))
        written.append("NotoSans-Regular.ttf")
    except OSError as e:
        print(f"lỗi tải font: {e}", file=sys.stderr)
        return 2
    total = sum((FONT_DIR / n).stat().st_size for n in written)
    print(f"{len(written)} font -> {FONT_DIR} ({total / 1e6:.1f} MB): {', '.join(sorted(written))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
