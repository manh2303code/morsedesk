import json

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.profile import load_profile
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
