"""Tải corpus LM từ nguồn giấy phép rộng (public domain, CC BY, MIT, Apache-2.0).

Ghi corpus/raw/<lang>/*.txt và corpus/raw/<lang>/SOURCES.json (tên, URL, license, số dòng).
Chỉ chạy trên máy dev có mạng; không dùng trong runtime.
"""

from __future__ import annotations

import argparse
import http.client
import io
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from morsedesk.data.text import TextSampler
from morsedesk.lm.profile import load_profile
from morsedesk.textio import force_utf8_streams

UA = {"User-Agent": "morsedesk-corpus-fetch/0.1 (+offline morse decoder research)"}
LANG_PROFILE = {"en": "en", "ru": "ru", "kk": "kk-cyrl-ru"}
GUTENBERG_TOP = "https://www.gutenberg.org/browse/scores/top"
GUTENBERG_RU = "https://www.gutenberg.org/browse/languages/ru"
GUTENBERG_TXT = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
HF_PARQUET_API = "https://huggingface.co/api/datasets/{repo}/parquet/{config}/{split}"
HF_TREE_API = "https://huggingface.co/api/datasets/{repo}/tree/main"
HF_RESOLVE = "https://huggingface.co/datasets/{repo}/resolve/main/{path}"
_ID_RE = re.compile(r'href="/ebooks/(\d+)"')
_START_RE = re.compile(r"\*\*\* ?START OF[^\n]*\*\*\*")
_END_RE = re.compile(r"\*\*\* ?END OF[^\n]*\*\*\*")


def _get(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def gutenberg_ids_from_html(html: str) -> list[int]:
    seen: list[int] = []
    for m in _ID_RE.finditer(html):
        i = int(m.group(1))
        if i not in seen:
            seen.append(i)
    return seen


def strip_gutenberg(text: str) -> str:
    s = _START_RE.search(text)
    e = _END_RE.search(text)
    if s and e and e.start() > s.end():
        return text[s.end():e.start()]
    return text


def detokenize(tokens: list[str]) -> str:
    out = ""
    for tok in tokens:
        if tok in {",", ".", "!", "?", ":", ";", ")"} or not out:
            out += tok
        elif out.endswith("("):
            out += tok
        else:
            out += " " + tok
    return out


def fetch_gutenberg(ids: list[int], out_dir: Path, sleep_s: float, sources: list) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for i in ids:
        dest = out_dir / f"gutenberg_{i}.txt"
        if dest.exists():
            sources.append({"name": f"Project Gutenberg #{i}", "url": GUTENBERG_TXT.format(id=i),
                             "license": "Public domain (Project Gutenberg License)",
                             "lines": dest.read_text(encoding="utf-8").count("\n")})
            n += 1
            continue
        try:
            text = _get(GUTENBERG_TXT.format(id=i)).decode("utf-8", errors="replace")
        except _NET_ERRORS as e:  # nguồn lẻ lỗi không chặn cả lô
            print(f"bỏ qua Gutenberg {i}: {e}")
            continue
        body = strip_gutenberg(text)
        dest.write_text(body, encoding="utf-8")
        sources.append({"name": f"Project Gutenberg #{i}", "url": GUTENBERG_TXT.format(id=i),
                         "license": "Public domain (Project Gutenberg License)", "lines": body.count("\n")})
        n += 1
        time.sleep(sleep_s)
    return n


def fetch_parquet_urls(repo: str, config: str = "default", split: str = "train") -> list[str]:
    return json.loads(_get(HF_PARQUET_API.format(repo=repo, config=config, split=split)))


def parquet_column_lines(url: str, column: str, join_tokens: bool = False) -> list[str]:
    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(_get(url, timeout=600.0)), columns=[column])
    values = table.column(column).to_pylist()
    if join_tokens:
        return [detokenize([str(t) for t in v]) for v in values if v]
    return [str(v) for v in values if v]


def write_ham_lines(profile_id: str, n: int, out: Path, seed: int = 0) -> int:
    """Radiogram tự sinh (HAM_TEMPLATES, callsign ngẫu nhiên) đã chuyển tự sang profile."""
    profiles = {pid: load_profile(pid) for pid in {"en", profile_id}}
    sampler = TextSampler(profiles, ham_ratio=1.0, random_ratio=0.0)
    rng = np.random.default_rng(seed)
    lines = [sampler.sample(profile_id, rng) for _ in range(n)]
    return _write_lines(out, lines)


def _write_lines(path: Path, lines: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


_NET_ERRORS = (OSError, urllib.error.URLError, http.client.HTTPException, ValueError, KeyError)  # IncompleteRead là HTTPException


def fetch_lang(lang: str, out_dir: Path, limit_books: int, sleep_s: float, ham_lines: int = 20000) -> None:
    dest = out_dir / lang
    dest.mkdir(parents=True, exist_ok=True)
    sources: list[dict] = []
    try:
        if lang == "en":
            ids = gutenberg_ids_from_html(_get(GUTENBERG_TOP).decode("utf-8", errors="replace"))[:limit_books]
            fetch_gutenberg(ids, dest, sleep_s, sources)
            try:
                lines: list[str] = []
                for url in fetch_parquet_urls("michaellin/morse-translate-transcribe-100k"):
                    lines += parquet_column_lines(url, "english")
                n = _write_lines(dest / "morse_100k_english.txt", lines)
                sources.append({"name": "michaellin/morse-translate-transcribe-100k (english)",
                                 "url": "https://huggingface.co/datasets/michaellin/morse-translate-transcribe-100k",
                                 "license": "Apache-2.0", "lines": n})
            except _NET_ERRORS as e:  # nguồn lẻ lỗi không chặn cả ngôn ngữ
                print(f"bỏ qua morse-translate-transcribe-100k: {e}")
        elif lang == "ru":
            ids = gutenberg_ids_from_html(_get(GUTENBERG_RU).decode("utf-8", errors="replace"))[:limit_books]
            fetch_gutenberg(ids, dest, sleep_s, sources)
        elif lang == "kk":
            try:
                lines = []
                for url in fetch_parquet_urls("yeshpanovrustem/kaznerd"):
                    lines += parquet_column_lines(url, "tokens", join_tokens=True)
                n = _write_lines(dest / "kaznerd.txt", lines)
                sources.append({"name": "KazNERD (yeshpanovrustem/kaznerd)",
                                 "url": "https://huggingface.co/datasets/yeshpanovrustem/kaznerd",
                                 "license": "CC BY 4.0", "lines": n})
            except _NET_ERRORS as e:  # nguồn lẻ lỗi không chặn cả ngôn ngữ
                print(f"bỏ qua KazNERD: {e}")
            try:
                tree = json.loads(_get(HF_TREE_API.format(repo="issai/Kazakh_Speech_Corpus_2")))
                texts = [t for t in tree if t.get("type") == "file"
                         and t["path"].lower().endswith((".txt", ".tsv", ".csv")) and t.get("size", 0) < 50_000_000]
                for t in texts:
                    data = _get(HF_RESOLVE.format(repo="issai/Kazakh_Speech_Corpus_2", path=t["path"]), 600.0)
                    (dest / ("ksc2_" + Path(t["path"]).name)).write_bytes(data)
                    sources.append({"name": f"KSC2 {t['path']}", "license": "MIT",
                                     "url": HF_RESOLVE.format(repo="issai/Kazakh_Speech_Corpus_2", path=t["path"]),
                                     "lines": data.count(b"\n")})
            except _NET_ERRORS as e:
                print(f"KSC2: không tải được phần text ({e}); dùng KazNERD")
        else:
            raise SystemExit(f"ngôn ngữ lạ: {lang}")
        if ham_lines > 0:
            n = write_ham_lines(LANG_PROFILE[lang], ham_lines, dest / "ham_synthetic.txt")
            sources.append({"name": "Radiogram tự sinh từ HAM_TEMPLATES của dự án",
                             "url": "", "license": "Tự tạo", "lines": n})
    finally:
        # luôn ghi SOURCES.json để phản ánh đúng những gì đã tải được, kể cả khi có nguồn lỗi
        (dest / "SOURCES.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{lang}: {len(sources)} nguồn -> {dest}")


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Tải corpus LM")
    ap.add_argument("--lang", required=True, choices=["en", "ru", "kk"])
    ap.add_argument("--out", type=Path, default=Path("corpus/raw"))
    ap.add_argument("--limit-books", type=int, default=40)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--ham-lines", type=int, default=20000, help="số radiogram tự sinh thêm vào corpus")
    a = ap.parse_args(argv)
    fetch_lang(a.lang, a.out, a.limit_books, a.sleep, a.ham_lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
