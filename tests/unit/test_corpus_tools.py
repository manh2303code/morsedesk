import json

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.profile import load_profile
from tools import fetch_corpus
from tools.fetch_corpus import detokenize, gutenberg_ids_from_html, strip_gutenberg, write_ham_lines
from tools.normalize_corpus import normalize_line, normalize_paths, split_sentences

HTML = '<li><a href="/ebooks/1342">Pride</a></li><li><a href="/ebooks/84">Frank</a></li><a href="/ebooks/1342">dup</a>'


def test_gutenberg_ids_unique_in_order():
    assert gutenberg_ids_from_html(HTML) == [1342, 84]


def test_strip_gutenberg_markers():
    raw = "header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nbody line\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nfooter"
    assert strip_gutenberg(raw).strip() == "body line"
    assert strip_gutenberg("no markers here") == "no markers here"


def test_detokenize_punctuation():
    assert detokenize(["Сәлем", ",", "әлем", "!"]) == "Сәлем, әлем!"


def test_split_sentences():
    assert split_sentences("Hello there. How are you? Fine! ok") == ["Hello there.", "How are you?", "Fine!", "ok"]


def test_normalize_line_en_ru_kk():
    en, ru, kk = (load_profile(p) for p in ("en", "ru", "kk-cyrl-ru"))
    a_en, a_ru, a_kk = (LMAlphabet.for_profile(p) for p in (en, ru, kk))
    assert normalize_line("It’s “fine” — really…", en, a_en) == "IT'S \"FINE\" - REALLY..."
    assert normalize_line("Ёжик объём", ru, a_ru) == "ЕЖИК ОБЪЕМ"
    assert normalize_line("Сәлем, әлем!", kk, a_kk) == "СӘЛЕМ, ӘЛЕМ!"
    assert normalize_line("Привет мир", en, a_en) is None            # >5% ký tự lạ
    assert normalize_line("A", en, a_en) is None                     # quá ngắn
    assert normalize_line("CQ   DE\tK", en, a_en) == "CQ DE K"


def test_write_ham_lines_is_reproducible_and_encodable(tmp_path):
    from morsedesk.encode.text import text_to_tokens
    n = write_ham_lines("ru", 30, tmp_path / "ham.txt", seed=1)
    lines = (tmp_path / "ham.txt").read_text(encoding="utf-8").splitlines()
    assert n == 30 and len(lines) == 30 and all(lines)
    ru = load_profile("ru")
    for ln in lines:
        text_to_tokens(ln, ru)                                    # không ném UnsupportedCharacter
    assert any("ДЕ" in ln for ln in lines)                        # "DE" đã chuyển tự
    write_ham_lines("ru", 30, tmp_path / "ham2.txt", seed=1)
    assert (tmp_path / "ham2.txt").read_text(encoding="utf-8") == (tmp_path / "ham.txt").read_text(encoding="utf-8")


def test_normalize_paths_writes_plain_chars_holdout(tmp_path):
    src = tmp_path / "raw.txt"
    lines = [f"Line number {i} is here." for i in range(1000)] + ["Привет"]
    src.write_text("\n".join(lines), encoding="utf-8")
    plain, chars, hold = tmp_path / "en.txt", tmp_path / "en.chars.txt", tmp_path / "en.holdout.txt"
    stats = normalize_paths([src], "en", plain, chars, hold, holdout_every=500)
    p = plain.read_text(encoding="utf-8").splitlines()
    c = chars.read_text(encoding="utf-8").splitlines()
    h = hold.read_text(encoding="utf-8").splitlines()
    assert stats["lines_in"] == 1001 and stats["lines_out"] == len(p) and stats["holdout"] == len(h)
    assert len(p) + len(h) == 1000 and len(h) == 2
    assert c[0] == LMAlphabet.for_profile(load_profile("en")).to_tokens_line(p[0])
    assert "LINE NUMBER 0 IS HERE." in p
    assert isinstance(json.dumps(stats), str)


def test_normalize_paths_max_lines_caps_output(tmp_path):
    src = tmp_path / "raw.txt"
    lines = [f"Line number {i} is here." for i in range(50)]
    src.write_text("\n".join(lines), encoding="utf-8")
    plain, chars, hold = tmp_path / "en.txt", tmp_path / "en.chars.txt", tmp_path / "en.holdout.txt"
    stats = normalize_paths([src], "en", plain, chars, hold, holdout_every=1000, max_lines=5)
    assert stats["lines_out"] == 5
    assert len(plain.read_text(encoding="utf-8").splitlines()) == 5


def test_fetch_lang_survives_failing_source(tmp_path, monkeypatch):
    gutenberg_html = '<a href="/ebooks/1342">Pride</a><a href="/ebooks/84">Frank</a>'
    book_body = ("header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
                 "body line\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nfooter")

    def fake_get(url, timeout=60.0):
        if url == fetch_corpus.GUTENBERG_TOP:
            return gutenberg_html.encode("utf-8")
        if url.startswith("https://www.gutenberg.org/cache/epub/"):
            return book_body.encode("utf-8")
        raise OSError("offline")  # ví dụ HF parquet API

    monkeypatch.setattr(fetch_corpus, "_get", fake_get)
    fetch_corpus.fetch_lang("en", tmp_path, limit_books=2, sleep_s=0.0, ham_lines=5)

    en_dir = tmp_path / "en"
    sources = json.loads((en_dir / "SOURCES.json").read_text(encoding="utf-8"))
    assert len(sources) == 3
    assert (en_dir / "gutenberg_1342.txt").exists()
    assert (en_dir / "gutenberg_84.txt").exists()
    assert (en_dir / "ham_synthetic.txt").exists()


def test_fetch_gutenberg_skip_existing_keeps_source_entry(tmp_path, monkeypatch):
    (tmp_path / "gutenberg_1342.txt").write_text("one\ntwo\n", encoding="utf-8")

    def fail_get(url, timeout=60.0):
        raise OSError("should not be called")

    monkeypatch.setattr(fetch_corpus, "_get", fail_get)
    sources: list = []
    n = fetch_corpus.fetch_gutenberg([1342], tmp_path, sleep_s=0.0, sources=sources)
    assert n == 1
    assert len(sources) == 1
    assert sources[0]["lines"] == 2
    assert "Public domain" in sources[0]["license"]


def test_net_errors_cover_incomplete_read():
    import http.client

    from tools.fetch_corpus import _NET_ERRORS
    assert issubclass(http.client.IncompleteRead, _NET_ERRORS)
    assert issubclass(TimeoutError, _NET_ERRORS)
