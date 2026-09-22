"""Beam ký tự CTC trên hậu nghiệm DeepCW, chấm bằng LM ký tự của profile `en`.

Bảng chữ của DeepCW **là chữ Latin**, nên beam ký tự áp thẳng LM `en` của dự án, không phải đi
qua tầng mẫu chấm gạch như `morsedesk/lm/beam.py` (module đó phải rẽ nhánh một mẫu → nhiều chữ
cho Cyrillic; ở đây không có nhánh nào).

Thuật toán là prefix beam search CTC chuẩn: mỗi tiền tố giữ (p_blank, p_nonblank); mỗi khung chỉ
xét `topk_per_frame` lớp có xác suất ≥ `min_prob`; khung không có lớp nào đạt ngưỡng đi đường tắt
chỉ-blank nên chi phí tỉ lệ với số ký tự chứ không phải số khung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.ngram import CharNGramLM

NEG_INF = -math.inf


def _lse(a: float, b: float) -> float:
    """log(exp(a) + exp(b)). Bản sao có chủ ý của `lm/beam.py` để không phụ thuộc tên riêng tư."""
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    m = a if a > b else b
    return m + math.log(math.exp(a - m) + math.exp(b - m))


@dataclass(frozen=True)
class CharBeamParams:
    beam: int = 32
    alpha: float = 0.3                  # trọng số LM
    beta: float = 0.5                   # thưởng mỗi từ đã đóng
    topk_per_frame: int = 6
    min_prob: float = 1e-3
    unk_logp: float = math.log(1e-4)    # chữ không có trong bảng chữ LM


@dataclass
class CharHypothesis:
    text: str
    chars: tuple[str, ...]
    frames: tuple[int, ...]
    probs: tuple[float, ...]
    acoustic_logp: float
    lm_logp: float
    score: float
    n_words: int

    @property
    def emissions(self) -> list[tuple[str, int, float]]:
        return list(zip(self.chars, self.frames, self.probs, strict=True))


class _Prefix:
    __slots__ = ("chars", "frames", "probs", "p_b", "p_nb", "lm_ctx", "lm_logp", "n_words", "word")

    def __init__(self) -> None:
        self.chars: tuple[str, ...] = ()
        self.frames: tuple[int, ...] = ()
        self.probs: tuple[float, ...] = ()
        self.p_b = NEG_INF
        self.p_nb = NEG_INF
        self.lm_ctx: tuple[int, ...] = ()
        self.lm_logp = 0.0
        self.n_words = 0
        self.word = ""

    def total(self, alpha: float, beta: float) -> float:
        return _lse(self.p_b, self.p_nb) + alpha * self.lm_logp + beta * self.n_words

    def clone_reset(self) -> _Prefix:
        c = _Prefix()
        c.chars, c.frames, c.probs = self.chars, self.frames, self.probs
        c.lm_ctx, c.lm_logp, c.n_words, c.word = self.lm_ctx, self.lm_logp, self.n_words, self.word
        return c


def _extend(pre: _Prefix, ch: str, frame: int, prob: float, lm: CharNGramLM | None,
            alphabet: LMAlphabet | None, params: CharBeamParams) -> _Prefix:
    ext = _Prefix()
    ext.chars = pre.chars + (ch,)
    ext.frames = pre.frames + (frame,)
    ext.probs = pre.probs + (prob,)
    ext.lm_ctx, ext.lm_logp, ext.n_words, ext.word = pre.lm_ctx, pre.lm_logp, pre.n_words, pre.word
    if lm is not None and alphabet is not None:
        sym = alphabet.index.get(ch)
        if sym is None:
            ext.lm_logp += params.unk_logp          # chữ lạ: phạt, không đổi ngữ cảnh
        else:
            ext.lm_logp += float(lm.score(pre.lm_ctx, sym))
            ext.lm_ctx = (pre.lm_ctx + (sym,))[-(lm.order - 1):] if lm.order > 1 else ()
    if ch == " ":
        if pre.word:                                 # đóng một từ (rỗng: hai dấu cách liền nhau)
            ext.n_words += 1
        ext.word = ""
    else:
        ext.word = pre.word + ch
    return ext


def char_beam_search(log_probs: np.ndarray, chars: list[str], blank: int,
                     lm: CharNGramLM | None = None, alphabet: LMAlphabet | None = None,
                     params: CharBeamParams | None = None) -> CharHypothesis:
    p = params or CharBeamParams()
    if lm is not None and alphabet is None:
        alphabet = lm.alphabet
    lp = np.asarray(log_probs, dtype=np.float32)
    if lp.ndim == 3:
        lp = lp[0]
    root = _Prefix()
    root.p_b = 0.0
    if lm is not None and alphabet is not None:
        root.lm_ctx = (alphabet.bos_id,)
    beams: dict[tuple[str, ...], _Prefix] = {(): root}
    thresh = math.log(p.min_prob) if p.min_prob > 0.0 else NEG_INF
    for t in range(int(lp.shape[0])):
        row = lp[t]
        lp_blank = float(row[blank])
        k = min(p.topk_per_frame + 1, int(row.shape[0]))
        cand = np.argpartition(-row, k - 1)[:k]
        classes = [int(c) for c in cand
                   if int(c) != blank and int(c) < len(chars) and float(row[c]) >= thresh]
        if not classes:                              # đường tắt chỉ-blank
            for pre in beams.values():
                pre.p_b = _lse(pre.p_b, pre.p_nb) + lp_blank
                pre.p_nb = NEG_INF
            continue
        classes.sort(key=lambda c: -float(row[c]))
        classes = classes[: p.topk_per_frame]
        nxt: dict[tuple[str, ...], _Prefix] = {}
        for key, pre in beams.items():
            carried = _lse(pre.p_b, pre.p_nb) + lp_blank
            same = nxt.get(key)
            if same is None:
                same = pre.clone_reset()
                nxt[key] = same
            elif carried > _lse(same.p_b, same.p_nb):
                # tiền tố này đã được một tiền tố ngắn hơn mở rộng tới trong cùng khung:
                # giữ khung/xác suất của đóng góp nặng hơn
                same.frames, same.probs = pre.frames, pre.probs
            same.p_b = _lse(same.p_b, carried)
            last = pre.chars[-1] if pre.chars else None
            for c in classes:
                ch = chars[c]
                lp_c = float(row[c])
                if ch == last:
                    same.p_nb = _lse(same.p_nb, pre.p_nb + lp_c)
                    p_new = pre.p_b + lp_c
                else:
                    p_new = _lse(pre.p_b, pre.p_nb) + lp_c
                if p_new == NEG_INF:
                    continue
                new_key = pre.chars + (ch,)
                ext = nxt.get(new_key)
                if ext is None:
                    ext = _extend(pre, ch, t, float(math.exp(lp_c)), lm, alphabet, p)
                    nxt[new_key] = ext
                elif p_new > _lse(ext.p_b, ext.p_nb):
                    ext.frames = pre.frames + (t,)
                    ext.probs = pre.probs + (float(math.exp(lp_c)),)
                ext.p_nb = _lse(ext.p_nb, p_new)
        ranked = sorted(nxt.items(), key=lambda kv: kv[1].total(p.alpha, p.beta), reverse=True)
        beams = dict(ranked[: p.beam])
    best: CharHypothesis | None = None
    for pre in beams.values():
        acoustic = _lse(pre.p_b, pre.p_nb)
        lm_logp = pre.lm_logp
        n_words = pre.n_words + (1 if pre.word else 0)
        if lm is not None and alphabet is not None:
            lm_logp += float(lm.score(pre.lm_ctx, alphabet.eos_id))
        score = acoustic + p.alpha * lm_logp + p.beta * n_words
        if best is None or score > best.score:
            best = CharHypothesis("".join(pre.chars), pre.chars, pre.frames, pre.probs,
                                  acoustic, lm_logp, score, n_words)
    return best if best is not None else CharHypothesis("", (), (), (), NEG_INF, 0.0, NEG_INF, 0)