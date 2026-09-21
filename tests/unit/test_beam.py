import math

import numpy as np
import pytest

from morsedesk.encode.text import text_to_tokens
from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.beam import BeamParams, BeamState, Hypothesis, beam_search, class_options
from morsedesk.lm.ngram import train_small
from morsedesk.lm.profile import load_profile
from morsedesk.model.ctc import greedy_decode
from morsedesk.model.vocab import SPACE, VOCAB
from tests.helpers import lattice_from_tokens

EN, RU, KK = load_profile("en"), load_profile("ru"), load_profile("kk-cyrl-ru")


def tiny_lm(profile, lines, order=4):
    return train_small(lines, LMAlphabet.for_profile(profile), order=order)


def test_class_options_letters_unk_prosign():
    opts = class_options(KK, LMAlphabet.for_profile(KK))
    assert opts[VOCAB.blank_id] == []
    assert opts[VOCAB.space_id][0][0] == " " and opts[VOCAB.space_id][0][1] == 3
    assert [o[0] for o in opts[VOCAB.id(".-")]] == ["А", "Ә"]
    assert all(o[1] is not None for o in opts[VOCAB.id(".-")])
    assert opts[VOCAB.id("...-.-")] == [("<SK>", None)]           # prosign
    assert opts[VOCAB.unk_id] == [("#", None)]
    en_opts = class_options(EN, LMAlphabet.for_profile(EN))
    assert en_opts[VOCAB.id("----")] == [("#", None)]             # Ш không có trong en


def test_one_hot_lattice_decodes_exactly():
    tokens = text_to_tokens("CQ DE K", EN)
    hyps = beam_search(lattice_from_tokens(tokens), EN, None)
    assert isinstance(hyps[0], Hypothesis)
    assert hyps[0].text == "CQ DE K"
    assert hyps[0].tokens == tuple(tokens)
    assert hyps[0].n_words == 3 and hyps[0].n_chars == len(tokens)
    assert len(hyps[0].emissions) == len(tokens)
    assert all(0.85 < p <= 1.0 for _, _, p in hyps[0].emissions)
    assert hyps[0].frames[0] == 3                                 # sau `lead` khung blank
    assert hyps[0].lm_logp == 0.0


def test_beam_one_without_lm_equals_greedy():
    rng = np.random.default_rng(0)
    for _ in range(20):
        n = int(rng.integers(3, 12))
        toks = [VOCAB.token(int(i)) for i in rng.integers(1, len(VOCAB), size=n)]
        lat = lattice_from_tokens(toks, gap=int(rng.integers(1, 5)), peak=0.75)
        lat = lat + rng.normal(0, 0.05, size=lat.shape).astype(np.float32)
        lat = lat - np.logaddexp.reduce(lat, axis=1, keepdims=True)
        hyp = beam_search(lat, EN, None, BeamParams(beam=1))[0]
        greedy = [VOCAB.token(i) for i in greedy_decode(lat)]
        assert list(hyp.tokens) == greedy


def test_lm_resolves_ambiguous_frame():
    lm = tiny_lm(EN, ["CQ CQ DE K", "DE K", "CQ DE K K", "K K K"])
    tokens = text_to_tokens("DE K", EN)
    lat = lattice_from_tokens(tokens)
    t = list(np.where(lat.argmax(1) == VOCAB.id("-.-"))[0])[0]   # khung phát K
    row = np.full(len(VOCAB), np.log(0.02 / (len(VOCAB) - 2)), dtype=np.float32)
    row[VOCAB.id("-.--")] = np.log(0.55)                          # Y hơi cao hơn
    row[VOCAB.id("-.-")] = np.log(0.43)                           # K
    lat[t] = row
    assert beam_search(lat, EN, None)[0].text == "DE Y"           # thuần âm thanh chọn Y
    assert beam_search(lat, EN, lm)[0].text == "DE K"             # LM kéo về K


def test_no_lm_has_no_bonus():
    lat = lattice_from_tokens(text_to_tokens("CQ DE", EN))
    h = beam_search(lat, EN, None)[0]
    assert h.lm_logp == 0.0
    assert h.n_words == 2
    assert math.isclose(h.score, h.acoustic_logp)
    boosted = beam_search(lat, EN, None, BeamParams(beta=5.0, lexicon_bonus=5.0))[0]
    assert boosted.text == h.text
    assert math.isclose(boosted.score, h.score)


def test_kazakh_one_to_many_branching():
    tokens = text_to_tokens("ӘЛЕМ", KK)
    lat = lattice_from_tokens(tokens)
    assert beam_search(lat, KK, None)[0].text == "АЛЕМ"           # không LM: chữ đầu tiên
    lm_kk = tiny_lm(KK, ["СӘЛЕМ ӘЛЕМ", "ӘЛЕМ", "ӘЛЕМ СӘЛЕМ"])
    hyps = beam_search(lat, KK, lm_kk)
    assert hyps[0].text == "ӘЛЕМ"
    texts = [h.text for h in hyps]
    assert "АЛЕМ" in texts                                        # nhánh thay thế vẫn trong beam
    lm_ru = tiny_lm(RU, ["ПРИВЕТ МИР", "АЛЕМ"])
    assert beam_search(lat, RU, lm_ru)[0].text == "АЛЕМ"          # profile ru không có Ә


def test_unknown_pattern_and_prosign_render_without_lm_context():
    lm = tiny_lm(EN, ["73 DE K", "SK"])
    tokens = ["--...", "...--", SPACE, "...-.-", SPACE, "----"]   # 73 <SK> Ш(#)
    hyps = beam_search(lattice_from_tokens(tokens), EN, lm)
    assert hyps[0].text == "73 <SK> #"
    p = BeamParams()
    assert hyps[0].lm_logp < 2 * p.unk_logp                       # hai lần phạt unk + điểm chữ


def test_word_bonus_and_lexicon_bonus_change_score():
    tokens = text_to_tokens("CQ DE", EN)
    lat = lattice_from_tokens(tokens)
    lm = tiny_lm(EN, ["CQ DE K"])
    base = beam_search(lat, EN, lm, BeamParams(beta=0.0, lexicon_bonus=0.0))[0]
    boosted = beam_search(lat, EN, lm, BeamParams(beta=0.5, lexicon_bonus=1.0))[0]
    assert boosted.text == base.text == "CQ DE"
    assert math.isclose(boosted.score - base.score, 2 * 0.5 + 2 * 1.0, abs_tol=1e-5)  # CQ, DE đều trong lexicon


def test_step_in_two_halves_matches_single_pass():
    tokens = text_to_tokens("THE QUICK BROWN FOX", EN)
    lat = lattice_from_tokens(tokens)
    lm = tiny_lm(EN, ["THE QUICK BROWN FOX", "THE FOX"])
    one = beam_search(lat, EN, lm)
    st = BeamState(EN, lm).step(lat[:37]).step(lat[37:])
    two = st.hypotheses()
    assert st.t == len(lat)
    assert [h.text for h in one[:5]] == [h.text for h in two[:5]]
    assert math.isclose(one[0].score, two[0].score, rel_tol=1e-6)
    assert one[0].frames == two[0].frames


def test_lm_alphabet_mismatch_raises():
    lm_ru = tiny_lm(RU, ["ПРИВЕТ"])
    # "Е" ở đây là chữ Kirin (U+0415), không phải Latin "E": profile kk-cyrl-ru không
    # hỗ trợ Latin "E" nên text_to_tokens sẽ báo lỗi ký tự trước khi tới beam_search.
    with pytest.raises(ValueError, match="bảng chữ"):
        beam_search(lattice_from_tokens(text_to_tokens("Е", KK)), KK, lm_ru)


def test_empty_and_blank_only_lattices():
    assert beam_search(np.zeros((0, len(VOCAB)), np.float32), EN, None)[0].text == ""
    blank_only = lattice_from_tokens([], gap=0, lead=50)
    h = beam_search(blank_only, EN, None)[0]
    assert h.text == "" and h.n_chars == 0 and h.acoustic_logp > math.log(0.9) * 50 - 1e-3


def test_blank_shortcut_fires_on_confident_lattice():
    tokens = text_to_tokens("CQ DE K", EN)
    lat99 = lattice_from_tokens(tokens, gap=20, peak=0.99)
    st = BeamState(EN, None).step(lat99)
    assert st.n_shortcut >= 0.8 * len(lat99)
    assert st.hypotheses()[0].text == "CQ DE K"
    # đường tắt là xấp xỉ: trên lưới này nó không đổi kết quả giải mã so với không có đường tắt
    no_shortcut = beam_search(lat99, EN, None, BeamParams(min_prob=0.0))[0]
    assert no_shortcut.text == st.hypotheses()[0].text
    assert no_shortcut.frames == st.hypotheses()[0].frames
    lat90 = lattice_from_tokens(tokens, gap=20, peak=0.9)                 # peak=0.9: dưới ngưỡng crossover
    assert BeamState(EN, None).step(lat90).n_shortcut == 0


def _row(peaks: dict[int, float]) -> np.ndarray:
    rest = (1.0 - sum(peaks.values())) / (len(VOCAB) - len(peaks))
    r = np.full(len(VOCAB), rest)
    for c, p in peaks.items():
        r[c] = p
    return np.log(r).astype(np.float32)


def test_merged_prefix_keeps_frames_of_heavier_path():
    """Tiền tố "E" tới từ hai đường trong cùng khung 2: đứng yên (phát ở khung 0, 0,50) và
    mở rộng từ tiền tố rỗng (phát ở khung 2, 0,94). Đường nặng hơn quyết định khung/xác suất."""
    e = VOCAB.id(".")
    lat = np.stack([
        _row({e: 0.50, VOCAB.blank_id: 0.49}),
        _row({VOCAB.blank_id: 0.99}),
        _row({e: 0.94, VOCAB.blank_id: 0.05}),
        _row({VOCAB.blank_id: 0.99}),
    ])
    h = beam_search(lat, EN, None)[0]
    assert h.text == "E" and h.frames == (2,) and math.isclose(h.probs[0], 0.94, abs_tol=1e-3)
    flipped = np.stack([lat[2], lat[1], lat[0], lat[3]])       # đỉnh mạnh ở khung 0
    h2 = beam_search(flipped, EN, None)[0]
    assert h2.text == "E" and h2.frames == (0,) and math.isclose(h2.probs[0], 0.94, abs_tol=1e-3)


def test_step_rejects_wrong_class_count():
    with pytest.raises(ValueError, match="65"):
        beam_search(np.zeros((4, 5), np.float32), EN, None)
    with pytest.raises(ValueError, match="65"):
        beam_search(np.zeros(len(VOCAB), np.float32), EN, None)


def test_prosign_does_not_close_word():
    tokens = ["--...", "...--", SPACE, "...-.-", SPACE]                  # 73 <SK>
    lm = tiny_lm(EN, ["73 DE K"])
    h = beam_search(lattice_from_tokens(tokens), EN, lm)[0]
    assert h.text == "73 <SK> "                                         # dấu cách cuối vẫn render " "
    assert h.n_words == 1                                                # prosign không đóng từ rỗng
    p = BeamParams()
    assert math.isclose(h.score - h.acoustic_logp - p.alpha * h.lm_logp, p.beta + p.lexicon_bonus)
