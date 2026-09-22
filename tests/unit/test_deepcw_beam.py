import numpy as np
import pytest

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import train_small
from morsedesk.lm.profile import load_profile
from morsedesk.model.deepcw import emissions_to_text, greedy_ctc_emissions
from morsedesk.model.deepcw_beam import CharBeamParams, char_beam_search

CHARS = [",", ".", "/", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "?",
         *[chr(c) for c in range(ord("A"), ord("Z") + 1)], " "]
BLANK = 41
N_CLASSES = 42


def lattice(rows: list[int | None], peak: float = 0.95) -> np.ndarray:
    rest = np.log((1.0 - peak) / (N_CLASSES - 1))
    lp = np.full((len(rows), N_CLASSES), rest, dtype=np.float32)
    for t, c in enumerate(rows):
        lp[t, BLANK if c is None else c] = np.log(peak)
    return lp


def ids(text: str) -> list[int | None]:
    """'_' = blank; mọi ký tự khác tra trong bảng chữ DeepCW."""
    return [None if ch == "_" else CHARS.index(ch) for ch in text]


@pytest.fixture(scope="module")
def en_lm():
    alphabet = LMAlphabet.for_profile(load_profile("en"))
    return train_small(["CQ DE K", "CQ CQ DE K", "TNX FER CALL UR 599 K"], alphabet, order=4)


def test_beam_without_lm_matches_greedy():
    lp = lattice(ids("_CCQ__ _DDE_ K_"))
    greedy = emissions_to_text(greedy_ctc_emissions(lp, CHARS, BLANK))
    hyp = char_beam_search(lp, CHARS, BLANK, params=CharBeamParams(beam=64))
    assert greedy == "CQ DE K"
    assert hyp.text == greedy
    assert hyp.lm_logp == 0.0 and hyp.n_words == 3


def test_beam_keeps_frames_and_probs_aligned():
    lp = lattice(ids("_CCQ__ _DDE_ K_"))
    hyp = char_beam_search(lp, CHARS, BLANK, params=CharBeamParams(beam=64))
    assert len(hyp.chars) == len(hyp.frames) == len(hyp.probs) == len(hyp.text)
    assert list(hyp.frames) == sorted(hyp.frames)
    assert all(0.0 < p <= 1.0 for p in hyp.probs)
    assert [ch for ch, _, _ in hyp.emissions] == list(hyp.chars)


def test_beam_uses_lm_to_break_acoustic_tie(en_lm):
    """Khung cuối hòa đúng bằng giữa 'C' và 'K'; greedy lấy chỉ số nhỏ hơn, LM phải chọn 'K'."""
    lp = lattice(ids("_CCQ__ _DDE_ _"))
    tie = np.full(N_CLASSES, np.log(0.1 / (N_CLASSES - 2)), dtype=np.float32)
    tie[CHARS.index("C")] = np.log(0.45)
    tie[CHARS.index("K")] = np.log(0.45)
    lp = np.vstack([lp, tie[None, :]]).astype(np.float32)
    assert emissions_to_text(greedy_ctc_emissions(lp, CHARS, BLANK)) == "CQ DE C"
    hyp = char_beam_search(lp, CHARS, BLANK, lm=en_lm, params=CharBeamParams(beam=64, alpha=0.5))
    assert hyp.text == "CQ DE K"
    assert hyp.lm_logp < 0.0


def test_beam_handles_empty_lattice(en_lm):
    hyp = char_beam_search(np.zeros((0, N_CLASSES), dtype=np.float32), CHARS, BLANK, lm=en_lm)
    assert hyp.text == "" and hyp.chars == () and hyp.n_words == 0


def test_beam_accepts_batched_lattice():
    lp = lattice(ids("_CCQ_"))[None]
    assert char_beam_search(lp, CHARS, BLANK, params=CharBeamParams(beam=8)).text == "CQ"