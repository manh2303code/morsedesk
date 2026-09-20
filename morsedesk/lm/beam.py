"""Prefix beam search CTC trên lưới 65 lớp mẫu; rẽ nhánh chữ theo profile, chấm bằng LM ký tự.

Tiền tố = (chuỗi token đã phát, chuỗi chữ đã chọn). Mỗi khung chỉ xét blank cộng tối đa
`topk_per_frame` lớp có xác suất >= `min_prob`. Khung không có lớp nào đạt ngưỡng đi đường tắt
chỉ-blank (không sinh tiền tố mới), nhờ đó chi phí tỉ lệ với số token chứ không phải số khung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import CharNGramLM
from morsedesk.lm.profile import UNK_DISPLAY, Profile
from morsedesk.model.vocab import SPACE, UNK, VOCAB

NEG_INF = -math.inf


def _lse(a: float, b: float) -> float:
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    m = a if a > b else b
    return m + math.log(math.exp(a - m) + math.exp(b - m))


@dataclass(frozen=True)
class BeamParams:
    beam: int = 64
    alpha: float = 0.6
    beta: float = 0.5
    lexicon_bonus: float = 1.0
    topk_per_frame: int = 8
    unk_logp: float = math.log(1e-4)
    min_prob: float = 1e-3
    space_id: int = VOCAB.space_id
    blank_id: int = VOCAB.blank_id


@dataclass
class Hypothesis:
    tokens: tuple[str, ...]
    letters: tuple[str, ...]
    frames: tuple[int, ...]
    probs: tuple[float, ...]
    acoustic_logp: float
    lm_logp: float
    score: float
    n_words: int

    @property
    def text(self) -> str:
        return "".join(self.letters)

    @property
    def n_chars(self) -> int:
        return len(self.tokens)

    @property
    def emissions(self) -> list[tuple[str, int, float]]:
        return list(zip(self.tokens, self.frames, self.probs, strict=True))


def class_options(profile: Profile, alphabet: LMAlphabet) -> list[list[tuple[str, int | None]]]:
    """Với mỗi id lớp: danh sách (chuỗi hiển thị, id LM). id LM = None cho `#` và prosign."""
    out: list[list[tuple[str, int | None]]] = []
    for c, tok in enumerate(VOCAB.tokens):
        if c == VOCAB.blank_id:
            out.append([])
        elif c == VOCAB.space_id:
            out.append([(" ", alphabet.space_id)])
        elif c == VOCAB.unk_id:
            out.append([(UNK_DISPLAY, None)])
        elif tok in profile.map:
            out.append([(ch, alphabet.index[ch]) for ch in profile.decode_options(tok)])
        else:
            opts = profile.decode_options(tok)
            out.append([(UNK_DISPLAY if opts[0] == UNK else opts[0], None)])
    return out


class _Prefix:
    __slots__ = ("tokens", "letters", "frames", "probs", "p_b", "p_nb",
                 "lm_ctx", "lm_logp", "bonus", "n_words", "word")

    def __init__(self) -> None:
        self.tokens: tuple[str, ...] = ()
        self.letters: tuple[str, ...] = ()
        self.frames: tuple[int, ...] = ()
        self.probs: tuple[float, ...] = ()
        self.p_b = NEG_INF
        self.p_nb = NEG_INF
        self.lm_ctx: tuple[int, ...] = ()
        self.lm_logp = 0.0
        self.bonus = 0.0
        self.n_words = 0
        self.word = ""

    def total(self, alpha: float) -> float:
        return _lse(self.p_b, self.p_nb) + alpha * self.lm_logp + self.bonus

    def clone_reset(self) -> _Prefix:
        c = _Prefix()
        c.tokens, c.letters, c.frames, c.probs = self.tokens, self.letters, self.frames, self.probs
        c.lm_ctx, c.lm_logp, c.bonus, c.n_words, c.word = (
            self.lm_ctx, self.lm_logp, self.bonus, self.n_words, self.word)
        return c


class BeamState:
    def __init__(self, profile: Profile, lm: CharNGramLM | None = None, params: BeamParams | None = None) -> None:
        self.profile = profile
        self.lm = lm
        self.params = params or BeamParams()
        expected = LMAlphabet.for_profile(profile)
        if lm is not None and lm.alphabet.symbols != expected.symbols:
            raise ValueError(f"bảng chữ của LM không khớp profile {profile.id}")
        self.alphabet = lm.alphabet if lm is not None else expected
        self.options = class_options(profile, self.alphabet)
        self.lexicon = set(profile.lexicon_bonus)
        self.ctx_len = max(0, lm.order - 1) if lm is not None else 0
        self.t = 0
        self._lm_cache: dict[tuple[tuple[int, ...], tuple[int, ...]], dict[int, float]] = {}
        root = _Prefix()
        root.p_b = 0.0
        root.lm_ctx = (self.alphabet.bos_id,)
        self.beams: dict[tuple[tuple[str, ...], tuple[str, ...]], _Prefix] = {((), ()): root}

    # ---- LM ----
    def _lm_scores(self, pre: _Prefix, classes: list[int]) -> dict[int, float]:
        if self.lm is None:
            return {}
        ids = sorted({lm_id for c in classes for _, lm_id in self.options[c] if lm_id is not None})
        if not ids:
            return {}
        key = (pre.lm_ctx, tuple(ids))
        hit = self._lm_cache.get(key)
        if hit is None:
            vals = self.lm.score_many(pre.lm_ctx, np.asarray(ids, dtype=np.int64))
            hit = {i: float(v) for i, v in zip(ids, vals, strict=True)}
            if len(self._lm_cache) > 50_000:
                self._lm_cache.clear()
            self._lm_cache[key] = hit
        return hit

    def _extend(self, pre: _Prefix, tok: str, display: str, lm_id: int | None,
                lm_scores: dict[int, float], frame: int, prob: float) -> _Prefix:
        p = self.params
        ext = _Prefix()
        ext.tokens = pre.tokens + (tok,)
        ext.letters = pre.letters + (display,)
        ext.frames = pre.frames + (frame,)
        ext.probs = pre.probs + (prob,)
        ext.lm_ctx, ext.lm_logp, ext.bonus, ext.n_words, ext.word = (
            pre.lm_ctx, pre.lm_logp, pre.bonus, pre.n_words, pre.word)
        if lm_id is None:                                   # `#` hoặc prosign: phạt, không đổi context
            if self.lm is not None:
                ext.lm_logp += p.unk_logp
            return ext
        if self.lm is not None:
            ext.lm_logp += lm_scores[lm_id]
            ext.lm_ctx = (pre.lm_ctx + (lm_id,))[-self.ctx_len:] if self.ctx_len else ()
        if tok == SPACE:
            if pre.tokens and pre.tokens[-1] != SPACE:      # kết thúc một từ
                ext.n_words += 1
                ext.bonus += p.beta
                if pre.word in self.lexicon:
                    ext.bonus += p.lexicon_bonus
            ext.word = ""
        else:
            ext.word = pre.word + display
        return ext

    # ---- một khung ----
    def _advance(self, lp: np.ndarray) -> None:
        p = self.params
        lp_blank = float(lp[p.blank_id])
        k = min(p.topk_per_frame + 1, len(lp))
        cand = np.argpartition(-lp, k - 1)[:k]
        thresh = math.log(p.min_prob)
        classes = [int(c) for c in cand if int(c) != p.blank_id and lp[c] >= thresh]
        if not classes:                                     # đường tắt chỉ-blank
            for pre in self.beams.values():
                pre.p_b = _lse(pre.p_b, pre.p_nb) + lp_blank
                pre.p_nb = NEG_INF
            return
        classes.sort(key=lambda c: -float(lp[c]))
        classes = classes[: p.topk_per_frame]
        nxt: dict[tuple[tuple[str, ...], tuple[str, ...]], _Prefix] = {}
        for key, pre in self.beams.items():
            same = nxt.get(key)
            if same is None:
                same = pre.clone_reset()
                nxt[key] = same
            same.p_b = _lse(same.p_b, _lse(pre.p_b, pre.p_nb) + lp_blank)
            last = pre.tokens[-1] if pre.tokens else None
            lm_scores = self._lm_scores(pre, classes)
            for c in classes:
                tok = VOCAB.token(c)
                lp_c = float(lp[c])
                if tok == last:
                    same.p_nb = _lse(same.p_nb, pre.p_nb + lp_c)
                    p_new = pre.p_b + lp_c
                else:
                    p_new = _lse(pre.p_b, pre.p_nb) + lp_c
                if p_new == NEG_INF:
                    continue
                for display, lm_id in self.options[c]:
                    new_key = (pre.tokens + (tok,), pre.letters + (display,))
                    ext = nxt.get(new_key)
                    if ext is None:
                        ext = self._extend(pre, tok, display, lm_id, lm_scores, self.t, math.exp(lp_c))
                        nxt[new_key] = ext
                    ext.p_nb = _lse(ext.p_nb, p_new)
        ranked = sorted(nxt.values(), key=lambda h: h.total(p.alpha), reverse=True)[: p.beam]
        self.beams = {(h.tokens, h.letters): h for h in ranked}

    def step(self, log_probs: np.ndarray) -> BeamState:
        for row in np.asarray(log_probs, dtype=np.float32):
            self._advance(row)
            self.t += 1
        return self

    def hypotheses(self) -> list[Hypothesis]:
        p = self.params
        out: list[Hypothesis] = []
        for pre in self.beams.values():
            acoustic = _lse(pre.p_b, pre.p_nb)
            lm_logp = pre.lm_logp
            bonus = pre.bonus
            n_words = pre.n_words
            if self.lm is not None:
                lm_logp += float(self.lm.score(pre.lm_ctx, self.alphabet.eos_id))
            if pre.word:                                    # từ cuối chưa đóng bằng khoảng trắng
                n_words += 1
                bonus += p.beta + (p.lexicon_bonus if pre.word in self.lexicon else 0.0)
            out.append(Hypothesis(pre.tokens, pre.letters, pre.frames, pre.probs, acoustic, lm_logp,
                                  acoustic + p.alpha * lm_logp + bonus, n_words))
        out.sort(key=lambda h: h.score, reverse=True)
        return out


def beam_search(log_probs: np.ndarray, profile: Profile, lm: CharNGramLM | None = None,
                params: BeamParams | None = None) -> list[Hypothesis]:
    return BeamState(profile, lm, params).step(log_probs).hypotheses()
