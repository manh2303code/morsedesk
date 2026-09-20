import numpy as np

from morsedesk.encode.text import text_to_tokens
from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.beam import BeamParams
from morsedesk.lm.langid import MIN_MARGIN, LangIdResult, detect, split_segments
from morsedesk.lm.ngram import train_small
from morsedesk.lm.profile import load_profile
from morsedesk.model.vocab import VOCAB
from tests.helpers import lattice_from_tokens

PROFILES = {pid: load_profile(pid) for pid in ("en", "ru", "kk-cyrl-ru")}
CORPUS = {
    "en": ["CQ CQ DE K", "THE QUICK BROWN FOX", "HELLO WORLD", "GOOD MORNING"],
    "ru": ["ПРИВЕТ МИР", "ВСЕМ ПРИВЕТ", "ДОБРОЕ УТРО", "СПАСИБО"],
    "kk-cyrl-ru": ["СӘЛЕМ ӘЛЕМ", "РАХМЕТ", "ҚАЙЫРЛЫ ТАҢ", "ЖАҚСЫ"],
}
LMS = {pid: train_small(lines, LMAlphabet.for_profile(PROFILES[pid]), order=4) for pid, lines in CORPUS.items()}


def lat(text, pid, **kw):
    return lattice_from_tokens(text_to_tokens(text, PROFILES[pid]), **kw)


def test_split_segments_on_long_silence_and_max_frames():
    a = lat("CQ", "en", gap=2, lead=0)
    silence = lattice_from_tokens([], gap=0, lead=400)
    b = lat("DE", "en", gap=2, lead=0)
    full = np.concatenate([a, silence, b])
    segs = split_segments(full, silence_frames=300, max_frames=3000)
    assert len(segs) == 2 and segs[0][0] == 0 and segs[-1][1] == len(full)
    assert segs[0][1] == segs[1][0]
    assert len(a) < segs[0][1] < len(a) + 400                      # cắt bên trong khoảng lặng
    short = lattice_from_tokens([], gap=0, lead=100)
    assert split_segments(np.concatenate([a, short, b]), 300, 3000) == [(0, len(a) + 100 + len(b))]
    long_seg = lat("CQ", "en", gap=2, lead=0)
    long_seg = np.concatenate([long_seg] * 300)                    # không có khoảng lặng dài
    parts = split_segments(long_seg, 300, 1000)
    assert all(e - s <= 1000 for s, e in parts) and parts[0][0] == 0 and parts[-1][1] == len(long_seg)
    assert split_segments(np.zeros((0, len(VOCAB)), np.float32)) == []


def test_detect_picks_each_language():
    for text, pid in (("CQ CQ DE K", "en"), ("ПРИВЕТ МИР", "ru"), ("СӘЛЕМ ӘЛЕМ", "kk-cyrl-ru")):
        r = detect(lat(text, pid), PROFILES, LMS, BeamParams(beam=8))
        assert isinstance(r, LangIdResult)
        assert r.profile_id == pid, (text, r.scores)
        assert set(r.scores) == set(PROFILES) and r.scores[pid] == max(r.scores.values())
        assert len(r.segments) == 1 and r.segments[0].best[pid].text == text


def test_detect_per_segment_and_majority_by_chars():
    silence = lattice_from_tokens([], gap=0, lead=400)
    full = np.concatenate([lat("ПРИВЕТ МИР", "ru", lead=0), silence, lat("CQ", "en", lead=0)])
    r = detect(full, PROFILES, LMS, BeamParams(beam=8))
    assert [s.profile_id for s in r.segments] == ["ru", "en"]
    assert r.profile_id == "ru"                                    # nhiều ký tự hơn
    assert r.segments[1].start > r.segments[0].end - 1


def test_margin_keeps_previous_profile():
    silence = lattice_from_tokens([], gap=0, lead=400)
    full = np.concatenate([lat("ПРИВЕТ МИР", "ru", lead=0), silence, lat("E", "en", lead=0)])
    # "E" (.) một chữ: điểm ba profile gần nhau -> giữ ru của đoạn trước
    r = detect(full, PROFILES, LMS, BeamParams(beam=8), min_margin=10.0)
    assert [s.profile_id for s in r.segments] == ["ru", "ru"]
    assert MIN_MARGIN == 0.15


def test_detect_all_blank_returns_first_profile_without_scores():
    r = detect(lattice_from_tokens([], gap=0, lead=50), PROFILES, LMS, BeamParams(beam=4))
    assert r.profile_id == "en" and r.scores == {}
    assert r.segments[0].profile_id is None and r.segments[0].n_chars == 0
