"""Dựng ảnh README từ HTML (docs/readme/src) bằng Edge/Chrome headless -> docs/readme/img/{trang}-{lang}-{theme}.png.

    uv run python docs/readme/render.py                       # mọi trang x en/ru/kk x sáng/tối
    uv run python docs/readme/render.py hero --lang ru --theme dark

Chữ ba ngôn ngữ ở src/strings.js; nét tay dùng seed cố định nên dựng lại ra đúng một hình.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC, IMG = HERE / "src", HERE / "img"
PAGES = {"hero": 600, "repo": 740, "pipeline": 700, "results": 720}   # cao (px CSS); rộng 1200
SCALE = 1.5
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def browser() -> str:
    for b in BROWSERS:
        if Path(b).is_file() or shutil.which(b):
            return b
    sys.exit("không tìm thấy Edge/Chrome")


def render(page: str, lang: str, theme: str, exe: str, profile: str) -> Path:
    out = IMG / f"{page}-{lang}-{theme}.png"
    url = (SRC / f"{page}.html").as_uri() + f"?lang={lang}&theme={theme}"
    cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           f"--user-data-dir={profile}", f"--force-device-scale-factor={SCALE}",
           f"--window-size=1200,{PAGES[page]}", "--virtual-time-budget=6000",
           f"--screenshot={out}", url]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*", default=list(PAGES))
    ap.add_argument("--lang", default="en,ru,kk")
    ap.add_argument("--theme", default="light,dark")
    a = ap.parse_args()
    IMG.mkdir(parents=True, exist_ok=True)
    exe = browser()
    with tempfile.TemporaryDirectory() as profile:
        for page in a.pages:
            for lang in a.lang.split(","):
                for theme in a.theme.split(","):
                    p = render(page, lang, theme, exe, profile)
                    print(f"{p.relative_to(HERE.parents[1])}  {os.path.getsize(p) // 1024} KB", flush=True)


if __name__ == "__main__":
    main()
