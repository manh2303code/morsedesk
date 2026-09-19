import math

import pytest

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import save_arpa, save_bin, train_small
from morsedesk.lm.profile import load_profile
from morsedesk.lm.store import LMStore, default_lm_dir, lm_file_for
from tools.arpa_to_bin import convert


def _tiny_lm(profile_id):
    profile = load_profile(profile_id)
    alpha = LMAlphabet.for_profile(profile)
    lines = {"en": ["CQ DE K", "THE QUICK FOX"], "ru": ["ПРИВЕТ МИР"], "kk-cyrl-ru": ["СӘЛЕМ ӘЛЕМ"]}[profile_id]
    return train_small(lines, alpha, order=3), alpha


def test_default_dir_and_file_names():
    assert default_lm_dir().name == "lm" and default_lm_dir().parent.name == "models"
    assert lm_file_for(load_profile("en"), default_lm_dir()).name == "en.bin"
    assert lm_file_for(load_profile("kk-cyrl-ru"), default_lm_dir()).name == "kk.bin"


def test_store_loads_available_and_reports_missing(tmp_path):
    lm, _ = _tiny_lm("en")
    save_bin(lm, tmp_path / "en.bin")
    store = LMStore(tmp_path)
    assert store.available("en") and not store.available("ru")
    got = store.get("en")
    assert got.order == 3
    assert store.get("en") is got                      # cache
    with pytest.raises(FileNotFoundError, match="ru.bin"):
        store.get("ru")
    assert store.get_profile("en").id == "en"


def test_convert_arpa_to_bin_reports_stats(tmp_path):
    lm, alpha = _tiny_lm("kk-cyrl-ru")
    arpa = tmp_path / "kk.arpa"
    save_arpa(lm, arpa)
    hold = tmp_path / "kk.holdout.txt"
    hold.write_text("СӘЛЕМ\nӘЛЕМ\n", encoding="utf-8")
    stats = convert(arpa, "kk-cyrl-ru", tmp_path / "kk.bin", hold)
    assert (tmp_path / "kk.bin").exists()
    assert stats["ngrams_per_order"][0] > 0 and len(stats["ngrams_per_order"]) == 3
    assert stats["size_mb"] > 0 and math.isfinite(stats["perplexity"]) and stats["perplexity"] > 1
    store = LMStore(tmp_path)
    a = store.get("kk-cyrl-ru").alphabet
    assert a.symbols == alpha.symbols


def test_convert_empty_holdout_gives_none(tmp_path):
    lm, _ = _tiny_lm("en")
    arpa = tmp_path / "en.arpa"
    save_arpa(lm, arpa)

    empty_hold = tmp_path / "empty.holdout.txt"
    empty_hold.write_text("", encoding="utf-8")
    stats = convert(arpa, "en", tmp_path / "en1.bin", empty_hold)
    assert stats["perplexity"] is None

    blank_hold = tmp_path / "blank.holdout.txt"
    blank_hold.write_text("\n   \n\t\n", encoding="utf-8")
    stats = convert(arpa, "en", tmp_path / "en2.bin", blank_hold)
    assert stats["perplexity"] is None

    stats = convert(arpa, "en", tmp_path / "en3.bin")
    assert stats["perplexity"] is None


def test_register_custom_profile(tmp_path):
    from dataclasses import replace
    custom = replace(load_profile("en"), id="my-en", lm="lm/my.bin")
    lm, _ = _tiny_lm("en")
    save_bin(lm, tmp_path / "my.bin")
    store = LMStore(tmp_path)
    store.register(custom)
    assert store.available("my-en") and store.get("my-en").order == 3


def test_train_small_lm_tool(tmp_path):
    from tools.train_small_lm import build
    text = tmp_path / "en.txt"
    text.write_text("CQ DE K\nTHE FOX\n" * 20, encoding="utf-8")
    stats = build(text, "en", tmp_path / "en.bin", order=4, max_mb=1.0)
    assert stats["lines"] == 40 and (tmp_path / "en.bin").exists()
    assert LMStore(tmp_path).get("en").order == 4
