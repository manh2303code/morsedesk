"""Prefix beam search CTC trên lưới 65 lớp mẫu; rẽ nhánh chữ theo profile, chấm bằng LM ký tự.

Tiền tố = (chuỗi token đã phát, chuỗi chữ đã chọn). Mỗi khung chỉ xét blank cộng tối đa
`topk_per_frame` lớp có xác suất >= `min_prob`. Khung không có lớp nào đạt ngưỡng đi đường tắt
chỉ-blank (không sinh tiền tố mới), nhờ đó chi phí tỉ lệ với số token chứ không phải số khung.

Khi `lm=None`, tìm kiếm thuần âm thanh: không cộng điểm LM, không phạt `unk_logp`, không cộng
`beta` (thưởng theo từ) hay `lexicon_bonus` (thưởng từ trong lexicon) — chỉ điểm âm học quyết
định thứ hạng. `n_words` vẫn được đếm bình thường trong mọi trường hợp.
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
    # Quét lại cùng char_bonus trên T1 (200 clip qsb+clean): tại cb=1,25 thì alpha 0,15 -> 33,85 %;
    # 0,20 -> 32,99; 0,30 -> 32,21; 0,45 -> 33,16. Giá trị 0,2 cũ tinh chỉnh khi chưa có char_bonus;
    # thưởng ký tự làm beam dám phát ký tự hơn nên LM cũng đáng tin hơn (spec gốc 0,6 vẫn quá cao).
    alpha: float = 0.3
    beta: float = 1.0    # thưởng mỗi từ; 1.0 tốt hơn 0.5 trên T1 v2
    lexicon_bonus: float = 1.0
    # Thưởng mỗi KÝ TỰ phát ra (khác `beta` là thưởng mỗi TỪ). Đo 22/09 trên T1: 74 % lỗi của
    # model là XÓA ký tự và chỉ 1 % là chèn thừa (riêng kênh qsb: xóa 43,5 % so với thay 11,0 %),
    # nghĩa là beam đang quá dè dặt khi tín hiệu fade. Thưởng theo từ không chạm tới lỗi xóa bên
    # trong từ. Đây là "character insertion bonus" của Deep Speech 2 (công thức 12) cho mô hình
    # mức ký tự. 0.0 = giữ nguyên hành vi cũ.
    # Quét trên T1 (200 clip qsb+clean): 0,0 -> 35,73 %; 0,75 -> 34,06; 1,0 -> 33,25;
    # 1,25 -> 32,99; 1,5 -> 33,38; 2,0 -> 35,20; 3,0 -> 43,26; 5,0 -> 94,99 (chèn thừa tràn lan).
    # Trên toàn T1: gate 23,85 % -> 21,58 %, mọi kênh đều tốt lên.
    char_bonus: float = 1.25
    topk_per_frame: int = 8
    unk_logp: float = math.log(1e-4)
    min_prob: float = 1e-3
    space_id: int = VOCAB.space_id
    blank_id: int = VOCAB.blank_id
    # Dấu cách ngay sau . ? ! (có thể qua một dấu ngoặc kép) = hết câu: chấm P(</s>) rồi mở ngữ cảnh
    # mới từ <s>. Corpus LM là MỘT CÂU MỘT DÒNG, nên LM chưa từng thấy ". " — P(" " | "…X.") ≈ e^-10
    # (en) … e^-15 (ru), nhân alpha là phạt 3–4,6 nat mỗi dấu chấm giữa bản tin; beam né bằng cách
    # đổi dấu chấm thành chữ (IMAGINE. -> IMAGINER, ЖЕНЩИНА. -> ЖЕНЩИНАЯ) hoặc nuốt dấu cách.
    # (research-lm-2026-09-24.md §2.4). Đo 25/09 (so ghép cặp): 54 bản tin 2 phút app 3,87 -> 3,69 %
    # [-0,31; -0,08], 11 tốt / 0 xấu; model+LM 4,36 -> 4,01, 20 / 0; dev, dev-OOV, T2 không đổi.
    sentence_breaks: bool = True


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


class _Chars:
    """Một mắt xích của chuỗi ký tự: (cha, token, chữ hiển thị) và một `uid` duy nhất.

    Trước đây mỗi tiền tố giữ cả `tuple` token lẫn `tuple` chữ, và khóa của từ điển beam là cặp
    tuple đó. Mỗi lần mở rộng vì thế phải sao chép và băm lại TOÀN BỘ chuỗi, nên chi phí tăng
    theo bình phương độ dài: đo trên bản ghi thật, 240 giây tốn gấp hơn ba lần 120 giây, và bản
    tin 3 746 ký tự thì không chạy nổi. Ở đây chuỗi là danh sách liên kết chia sẻ phần đuôi, và
    khóa chỉ là một số nguyên, nên mở rộng chỉ tốn hằng số.

    Hai chuỗi ký tự giống nhau luôn cho cùng một `_Chars` nhờ `_Trie`, nên `uid` định danh đúng
    tiền tố chứ không chỉ đối tượng.
    """

    __slots__ = ("parent", "tok", "letter", "depth", "uid")

    def __init__(self, parent: _Chars | None, tok: str, letter: str, uid: int) -> None:
        self.parent = parent
        self.tok = tok
        self.letter = letter
        self.depth = (parent.depth + 1) if parent is not None else 0
        self.uid = uid

    def tokens(self) -> tuple[str, ...]:
        out: list[str] = []
        node: _Chars | None = self
        while node is not None and node.parent is not None:
            out.append(node.tok)
            node = node.parent
        out.reverse()
        return tuple(out)

    def letters(self) -> tuple[str, ...]:
        out: list[str] = []
        node: _Chars | None = self
        while node is not None and node.parent is not None:
            out.append(node.letter)
            node = node.parent
        out.reverse()
        return tuple(out)


class _Trie:
    """Cấp `_Chars` duy nhất cho mỗi chuỗi, để khóa beam là một số nguyên."""

    __slots__ = ("root", "_kids", "_next")

    def __init__(self) -> None:
        self.root = _Chars(None, "", "", 0)
        self._kids: dict[tuple[int, str, str], _Chars] = {}
        self._next = 1

    def child(self, parent: _Chars, tok: str, letter: str) -> _Chars:
        key = (parent.uid, tok, letter)
        node = self._kids.get(key)
        if node is None:
            node = _Chars(parent, tok, letter, self._next)
            self._next += 1
            self._kids[key] = node
        return node


class _Marks:
    """Khung và xác suất của từng ký tự, tách khỏi `_Chars`.

    Phải tách vì cùng một chuỗi ký tự có thể đến từ hai đường trong cùng một khung và thuật toán
    giữ khung của đóng góp nặng hơn; `_Chars` thì chia sẻ giữa mọi chuỗi con nên không được sửa.
    Đổi một mắt xích ở đây chỉ là gán lại con trỏ, vẫn hằng số.
    """

    __slots__ = ("parent", "frame", "prob")

    def __init__(self, parent: _Marks | None, frame: int, prob: float) -> None:
        self.parent = parent
        self.frame = frame
        self.prob = prob

    @staticmethod
    def unpack(marks: _Marks | None) -> tuple[tuple[int, ...], tuple[float, ...]]:
        frames: list[int] = []
        probs: list[float] = []
        node = marks
        while node is not None:
            frames.append(node.frame)
            probs.append(node.prob)
            node = node.parent
        frames.reverse()
        probs.reverse()
        return tuple(frames), tuple(probs)


class _Prefix:
    __slots__ = ("chars", "marks", "p_b", "p_nb",
                 "lm_ctx", "lm_logp", "bonus", "n_words", "word")

    def __init__(self, chars: _Chars) -> None:
        self.chars = chars
        self.marks: _Marks | None = None
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
        c = _Prefix(self.chars)
        c.marks = self.marks
        c.lm_ctx, c.lm_logp, c.bonus, c.n_words, c.word = (
            self.lm_ctx, self.lm_logp, self.bonus, self.n_words, self.word)
        return c


REPORT_EVERY = 100     # khung đầu ra (1 s âm thanh) giữa hai lần báo tiến trình của beam


class BeamState:
    """Trạng thái beam search nối tiếp qua nhiều khối `log_probs`.

    `n_shortcut` là bộ đếm chẩn đoán (diagnostic): số khung đã đi đường tắt chỉ-blank trong
    `_advance` (không lớp nào đạt `min_prob` nên không sinh tiền tố mới). Không ảnh hưởng tới
    điểm số hay kết quả giải mã, chỉ để quan sát đường tắt có phát huy tác dụng hay không.
    """

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
        self._enders = {self.alphabet.index[c] for c in ".?!" if c in self.alphabet.index}
        self._quote = self.alphabet.index.get('"')
        self.t = 0
        self.n_shortcut = 0
        self._lm_cache: dict[tuple[tuple[int, ...], tuple[int, ...]], dict[int, float]] = {}
        self.trie = _Trie()
        root = _Prefix(self.trie.root)
        root.p_b = 0.0
        root.lm_ctx = (self.alphabet.bos_id,)
        self.beams: dict[int, _Prefix] = {self.trie.root.uid: root}

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
        ext = _Prefix(self.trie.child(pre.chars, tok, display))
        ext.marks = _Marks(pre.marks, frame, prob)
        ext.lm_ctx, ext.lm_logp, ext.bonus, ext.n_words, ext.word = (
            pre.lm_ctx, pre.lm_logp, pre.bonus, pre.n_words, pre.word)
        if lm_id is None:                                   # `#` hoặc prosign: phạt, không đổi context
            if self.lm is not None:
                ext.lm_logp += p.unk_logp
            return ext
        if self.lm is not None:
            if tok == SPACE and self.params.sentence_breaks and self._ends_sentence(pre.lm_ctx):
                ext.lm_logp += float(self.lm.score(pre.lm_ctx, self.alphabet.eos_id))
                ext.lm_ctx = (self.alphabet.bos_id,)
            else:
                ext.lm_logp += lm_scores[lm_id]
                ext.lm_ctx = (pre.lm_ctx + (lm_id,))[-self.ctx_len:] if self.ctx_len else ()
        if tok == SPACE:
            if pre.word:                                    # kết thúc một từ (rỗng: prosign/# vừa qua)
                ext.n_words += 1
                if self.lm is not None:                     # thuần âm thanh: không thưởng từ/lexicon
                    ext.bonus += p.beta
                    if pre.word in self.lexicon:
                        ext.bonus += p.lexicon_bonus
            ext.word = ""
        else:
            ext.word = pre.word + display
            if self.lm is not None:         # thuần âm thanh: không cộng thưởng nào, như beta
                ext.bonus += p.char_bonus   # bù xu hướng xóa ký tự khi tín hiệu yếu
        return ext

    def _ends_sentence(self, ctx: tuple[int, ...]) -> bool:
        if not ctx:
            return False
        if ctx[-1] in self._enders:
            return True
        return len(ctx) >= 2 and ctx[-1] == self._quote and ctx[-2] in self._enders

    # ---- một khung ----
    def _advance(self, lp: np.ndarray) -> None:
        p = self.params
        lp_blank = float(lp[p.blank_id])
        k = min(p.topk_per_frame + 1, len(lp))
        cand = np.argpartition(-lp, k - 1)[:k]
        thresh = math.log(p.min_prob) if p.min_prob > 0.0 else NEG_INF   # 0.0: tắt đường tắt (test)
        classes = [int(c) for c in cand if int(c) != p.blank_id and lp[c] >= thresh]
        if not classes:                                     # đường tắt chỉ-blank
            self.n_shortcut += 1
            for pre in self.beams.values():
                pre.p_b = _lse(pre.p_b, pre.p_nb) + lp_blank
                pre.p_nb = NEG_INF
            return
        classes.sort(key=lambda c: -float(lp[c]))
        classes = classes[: p.topk_per_frame]
        nxt: dict[int, _Prefix] = {}
        for key, pre in self.beams.items():
            carried = _lse(pre.p_b, pre.p_nb) + lp_blank
            same = nxt.get(key)
            if same is None:
                same = pre.clone_reset()
                nxt[key] = same
            elif carried > _lse(same.p_b, same.p_nb):
                # tiền tố này đã được một tiền tố ngắn hơn mở rộng tới trong cùng khung:
                # giữ khung/xác suất của đóng góp nặng hơn (xem chú thích ở nhánh mở rộng)
                same.marks = pre.marks
            same.p_b = _lse(same.p_b, carried)
            last = pre.chars.tok if pre.chars.parent is not None else None
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
                    node = self.trie.child(pre.chars, tok, display)
                    ext = nxt.get(node.uid)
                    if ext is None:
                        ext = self._extend(pre, tok, display, lm_id, lm_scores, self.t, math.exp(lp_c))
                        nxt[node.uid] = ext
                    elif p_new > _lse(ext.p_b, ext.p_nb):
                        # Cùng một tiền tố đến từ hai đường trong một khung: bản sao "đứng yên"
                        # của chính tiền tố đó và bản mở rộng từ tiền tố ngắn hơn. Giữ khung/xác
                        # suất của đóng góp nặng hơn phần đã gộp, thay vì của đường tạo ra trước.
                        # (lm_logp, bonus, n_words chỉ phụ thuộc chuỗi chữ nên hai đường giống nhau)
                        ext.marks = _Marks(pre.marks, self.t, math.exp(lp_c))
                    ext.p_nb = _lse(ext.p_nb, p_new)
        ranked = sorted(nxt.values(), key=lambda h: h.total(p.alpha), reverse=True)[: p.beam]
        self.beams = {h.chars.uid: h for h in ranked}

    def step(self, log_probs: np.ndarray, progress=None) -> BeamState:
        """`progress`: đối tượng có `step(done, total)` (DecodeProgress/StageProgress), gọi mỗi
        REPORT_EVERY khung. Beam là phần chiếm ~91 % thời gian giải mã, nên nếu không báo từ đây
        thì thanh tiến trình đứng im gần hết thời gian — và nút Hủy cũng không có tác dụng."""
        lp = np.asarray(log_probs, dtype=np.float32)
        if lp.ndim != 2 or lp.shape[1] != len(VOCAB):
            raise ValueError(f"log_probs phải có dạng [T, {len(VOCAB)}], nhận {lp.shape}")
        n = len(lp)
        for i, row in enumerate(lp, 1):
            self._advance(row)
            self.t += 1
            if progress is not None and (i % REPORT_EVERY == 0 or i == n):
                progress.step(i, n)
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
                if self.lm is not None:                     # thuần âm thanh: không thưởng từ/lexicon
                    bonus += p.beta + (p.lexicon_bonus if pre.word in self.lexicon else 0.0)
            frames, probs = _Marks.unpack(pre.marks)
            out.append(Hypothesis(pre.chars.tokens(), pre.chars.letters(), frames, probs,
                                  acoustic, lm_logp,
                                  acoustic + p.alpha * lm_logp + bonus, n_words))
        out.sort(key=lambda h: h.score, reverse=True)
        return out


def beam_search(log_probs: np.ndarray, profile: Profile, lm: CharNGramLM | None = None,
                params: BeamParams | None = None, progress=None) -> list[Hypothesis]:
    return BeamState(profile, lm, params).step(log_probs, progress).hypotheses()
