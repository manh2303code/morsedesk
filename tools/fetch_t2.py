"""Gom bản ghi Morse thật thành bộ T2 trong `testdata/private/t2/` (gitignored).

Mỗi nguồn là một thư mục con `<root>/<source>/` chứa cặp `<tên>.<đuôi audio>` + `<tên>.txt`
(đáp án) và một `_meta.json` ghi source/profile/license. `build` gộp mọi thư mục con thành
`manifest.jsonl` đúng khuôn T1 (`path`, `text`, `profile`, `wpm`, `source`, `license`).

    # 1. trang liệt kê file (ARRL W1AW code practice): quét link audio + text cùng tên
    uv run python tools/fetch_t2.py page --source arrl --profile en \
        --index-url https://www.arrl.org/code-practice-files

    # 2. Wikimedia Commons theo category (API ổn định, giấy phép tự do)
    uv run python tools/fetch_t2.py commons --source commons --profile en \
        --category "Morse code sound files" --limit 30

    # 3. file đã tải tay (SRAA, QSO thu tay): chép vào đúng chỗ; đáp án tự chép vào .txt cùng tên
    uv run python tools/fetch_t2.py local --source sraa --profile en --dir <thư mục>

    # 4. bù chỗ trống tiếng Nga/Kazakh: ebook2cw nếu có trên PATH, không thì Encoder của dự án
    uv run python tools/fetch_t2.py synth --source ebook2cw --profile ru --n 20

    uv run python tools/fetch_t2.py build
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio
from morsedesk.data.text import TextSampler
from morsedesk.lm.profile import load_profile
from morsedesk.textio import force_utf8_streams
from tools.make_t2_manifest import AUDIO_EXT, build_manifest, write_jsonl

DEFAULT_ROOT = Path("testdata/private/t2")
UA = "MorseDesk-T2/1.0 (offline research)"
LICENSES = {
    "arrl": "ARRL W1AW code practice — dùng nội bộ, không phân phối",
    "commons": "Wikimedia Commons — giấy phép tự do, xem <tên>.license.txt",
    "sraa": "tự thu / tự chép đáp án",
    "ebook2cw": "tổng hợp (không phải bản ghi thật)",
}
_HREF_RE = re.compile(r'href="([^"#?]+)"', re.IGNORECASE)


def _suffix(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).suffix.lower()


def _stem(url: str) -> str:
    return Path(urllib.parse.urlparse(url).path).stem


def _normalised_stem(stem: str) -> str:
    """Stem bỏ hậu tố tốc độ, để ghép audio với file đáp án đặt tên khác nhau.

    Trang thật của ARRL đặt audio là `260303_20WPM.mp3` nhưng đáp án là `260303_20.txt`. Khớp
    stem y hệt thì bỏ sót toàn bộ 11 cặp (đo được khi chạy thật ngày 22/09).
    """
    return re.sub(r"(?i)wpm$", "", stem).rstrip("_-")


def discover_pairs(html: str, base_url: str) -> list[tuple[str, str | None]]:
    """(URL audio, URL text đi kèm hoặc None) từ một trang liệt kê file.

    Ưu tiên file text trùng stem tuyệt đối; chỉ khi không có mới suy theo stem đã bỏ hậu tố
    tốc độ, để một trang đặt tên cẩn thận không bị ghép nhầm.
    """
    links = [urllib.parse.urljoin(base_url, h) for h in _HREF_RE.findall(html)]
    texts = {_stem(u): u for u in links if _suffix(u) == ".txt"}
    loose: dict[str, str] = {}
    for stem, url in texts.items():
        loose.setdefault(_normalised_stem(stem), url)
    return [(u, texts.get(_stem(u)) or loose.get(_normalised_stem(_stem(u))))
            for u in links if _suffix(u) in AUDIO_EXT]


def fetch_url(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)


def write_meta(directory: Path, source: str, profile_id: str, license_id: str,
               synthetic: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "_meta.json").write_text(
        json.dumps({"source": source, "profile": profile_id, "license": license_id,
                    "synthetic": synthetic}, ensure_ascii=False, indent=2), encoding="utf-8")


def build_all(root: Path, out: Path) -> list[dict]:
    rows: list[dict] = []
    for meta_path in sorted(Path(root).glob("*/_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        part = build_manifest(meta_path.parent, meta["source"], meta["profile"], meta["license"])
        for r in part:
            r["synthetic"] = bool(meta.get("synthetic", False))
        rows += part
    write_jsonl(rows, out)
    return rows


def cmd_page(a: argparse.Namespace) -> int:
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES.get(a.source, "unknown"))
    req = urllib.request.Request(a.index_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        html = r.read().decode("utf-8", errors="replace")
    pairs = discover_pairs(html, a.index_url)
    errors: list[dict] = []
    kept = 0
    for audio_url, text_url in pairs[: a.limit]:
        if text_url is None:
            errors.append({"url": audio_url, "reason": "không có file .txt cùng tên"})
            continue
        try:                                   # một URL hỏng không được làm hỏng cả lượt
            fetch_url(audio_url, directory / f"{_stem(audio_url)}{_suffix(audio_url)}")
            fetch_url(text_url, directory / f"{_stem(audio_url)}.txt")
            kept += 1
        except OSError as e:
            errors.append({"url": audio_url, "reason": f"{type(e).__name__}: {e}"})
    (directory / "_errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(f"{kept}/{len(pairs)} cặp -> {directory} ({len(errors)} lỗi, xem _errors.json)")
    return 0 if kept else 1


def cmd_commons(a: argparse.Namespace) -> int:
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES.get(a.source, "unknown"))
    query = {"action": "query", "format": "json", "generator": "categorymembers",
             "gcmtitle": f"Category:{a.category}", "gcmlimit": str(a.limit), "gcmtype": "file",
             "prop": "imageinfo", "iiprop": "url|extmetadata"}
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    kept = 0
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        src = info.get("url")
        if not src or _suffix(src) not in AUDIO_EXT:
            continue
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", _stem(src))[:60]
        try:
            fetch_url(src, directory / f"{stem}{_suffix(src)}")
        except OSError as e:
            print(f"bỏ qua {src}: {e}", file=sys.stderr)
            continue
        lic = ((info.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "?")
        (directory / f"{stem}.license.txt").write_text(f"{src}\n{lic}\n", encoding="utf-8")
        kept += 1
    print(f"{kept} file -> {directory}. CHÉP ĐÁP ÁN TAY vào <tên>.txt rồi chạy `build`.")
    return 0 if kept else 1


def cmd_local(a: argparse.Namespace) -> int:
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES.get(a.source, "unknown"))
    n = 0
    for p in sorted(Path(a.dir).iterdir()):
        if p.suffix.lower() in AUDIO_EXT or p.suffix.lower() == ".txt":
            shutil.copyfile(p, directory / p.name)
            n += p.suffix.lower() in AUDIO_EXT
    print(f"{n} file audio -> {directory}")
    return 0 if n else 1


def cmd_synth(a: argparse.Namespace) -> int:
    """ebook2cw nếu có trên PATH; không thì Encoder của dự án. Luôn đánh dấu synthetic=True."""
    directory = Path(a.root) / a.source
    write_meta(directory, a.source, a.profile, a.license or LICENSES["ebook2cw"], synthetic=True)
    profile = load_profile(a.profile)
    # phải có cả "en": TextSampler._ham dựng radiogram bằng bảng Latin rồi mới chuyển tự sang
    # profile đích; thiếu "en" thì bản tin ru/kk bị lọc sạch chữ và chỉ còn số.
    sampler = TextSampler({a.profile: profile, "en": load_profile("en")})
    rng = np.random.default_rng(a.seed)
    encoder = Encoder(profile)
    tool = shutil.which("ebook2cw")
    wpms = [12.0, 18.0, 25.0, 35.0]
    for i in range(a.n):
        text = sampler.sample(a.profile, rng, n_words=(8, 16))
        wpm = wpms[i % len(wpms)]
        stem = f"{a.source}_{i:03d}_{int(wpm)}WPM"
        (directory / f"{stem}.txt").write_text(text, encoding="utf-8")
        made = False
        if tool:
            try:
                subprocess.run([tool, "-w", str(int(wpm)), "-f", "700",
                                "-o", str(directory / stem), str(directory / f"{stem}.txt")],
                               check=True, capture_output=True, timeout=120)
                for produced in sorted(directory.glob(f"{stem}*.mp3")):
                    produced.rename(directory / f"{stem}.mp3")
                    made = True
                    break
            except (subprocess.SubprocessError, OSError) as e:
                print(f"ebook2cw thất bại ({e}), dùng Encoder", file=sys.stderr)
        if not made:
            x = encoder.to_audio(text, wpm=wpm, tone_hz=700.0,
                                 snr_db=float(rng.uniform(6.0, 20.0)), seed=a.seed + i, strict=False)
            save_audio(directory / f"{stem}.wav", x, 8000)
    print(f"{a.n} clip -> {directory} (ebook2cw={'có' if tool else 'không, dùng Encoder'})")
    return 0


def cmd_build(a: argparse.Namespace) -> int:
    rows = build_all(Path(a.root), Path(a.out))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    print(f"{len(rows)} mục -> {a.out}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0 if rows else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Dựng bộ test T2 từ bản ghi thật")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--source", required=True)
        p.add_argument("--profile", default="en")
        p.add_argument("--license", default=None)

    page = sub.add_parser("page", help="quét một trang liệt kê file audio + text")
    common(page)
    page.add_argument("--index-url", required=True)
    page.add_argument("--limit", type=int, default=50)
    page.set_defaults(func=cmd_page)

    commons = sub.add_parser("commons", help="tải theo category của Wikimedia Commons")
    common(commons)
    commons.add_argument("--category", required=True)
    commons.add_argument("--limit", type=int, default=30)
    commons.set_defaults(func=cmd_commons)

    local = sub.add_parser("local", help="chép file đã tải tay vào đúng chỗ")
    common(local)
    local.add_argument("--dir", type=Path, required=True)
    local.set_defaults(func=cmd_local)

    synth = sub.add_parser("synth", help="sinh bù bằng ebook2cw hoặc Encoder")
    common(synth)
    synth.add_argument("--n", type=int, default=20)
    synth.add_argument("--seed", type=int, default=1)
    synth.set_defaults(func=cmd_synth)

    build = sub.add_parser("build", help="gộp mọi thư mục con thành manifest.jsonl")
    build.add_argument("--out", type=Path, default=None)
    build.set_defaults(func=cmd_build)
    return ap


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    a = build_parser().parse_args(argv)
    if a.cmd == "build" and a.out is None:
        a.out = Path(a.root) / "manifest.jsonl"
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
