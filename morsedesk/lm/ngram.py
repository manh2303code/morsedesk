"""LM ký tự n-gram kiểu ARPA (backoff) lưu bảng băm numpy; huấn luyện nhỏ thuần Python."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from morsedesk.lm.alphabet import SPACE_TOKEN, LMAlphabet

FNV_OFFSET = np.uint64(0xCBF29CE484222325)
FNV_PRIME = np.uint64(0x100000001B3)
LN10 = math.log(10.0)


def _fnv_step(h: np.uint64, byte: int) -> np.uint64:
    with np.errstate(over="ignore"):
        return (h ^ np.uint64(byte)) * FNV_PRIME


def fnv1a64(ids: Sequence[int]) -> int:
    h = FNV_OFFSET
    for i in ids:
        h = _fnv_step(h, int(i) & 0xFF)
        h = _fnv_step(h, (int(i) >> 8) & 0xFF)
    return int(h)


def extend_hash(h: np.uint64, ids: np.ndarray) -> np.ndarray:
    """Hash của (prefix có hash h) + mỗi id trong ids, vector hóa."""
    ids = np.asarray(ids, dtype=np.uint64)
    with np.errstate(over="ignore"):
        x = (np.uint64(h) ^ (ids & np.uint64(0xFF))) * FNV_PRIME
        x = (x ^ ((ids >> np.uint64(8)) & np.uint64(0xFF))) * FNV_PRIME
    return x


@dataclass
class NGramTable:
    hashes: np.ndarray
    logp: np.ndarray
    backoff: np.ndarray

    def lookup(self, key: int) -> int:
        i = int(np.searchsorted(self.hashes, np.uint64(key)))
        return i if i < len(self.hashes) and int(self.hashes[i]) == key else -1

    def lookup_many(self, keys: np.ndarray) -> np.ndarray:
        idx = np.searchsorted(self.hashes, keys)
        idx_c = np.minimum(idx, max(0, len(self.hashes) - 1))
        hit = (idx < len(self.hashes)) & (self.hashes[idx_c] == keys) if len(self.hashes) else np.zeros(len(keys), bool)
        return np.where(hit, idx_c, -1)


class CharNGramLM:
    def __init__(self, alphabet: LMAlphabet, order: int, tables: list[NGramTable]) -> None:
        if len(tables) != order:
            raise ValueError("số bảng phải bằng bậc")
        self.alphabet = alphabet
        self.order = order
        self.tables = tables
        self._cache: dict[tuple[tuple[int, ...], int], float] = {}

    # ---- chấm điểm ----
    def _backoff_weight(self, context: tuple[int, ...]) -> float:
        """Tổng backoff khi lùi từ context (bậc len(context)) xuống context[1:]."""
        k = len(context)
        if k == 0:
            return 0.0
        i = self.tables[k - 1].lookup(fnv1a64(context))
        return float(self.tables[k - 1].backoff[i]) if i >= 0 else 0.0

    def score(self, context: tuple[int, ...], symbol: int) -> float:
        ctx = tuple(context)[-(self.order - 1):] if self.order > 1 else ()
        key = (ctx, symbol)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        acc = 0.0
        while True:
            k = len(ctx) + 1
            i = self.tables[k - 1].lookup(fnv1a64(ctx + (symbol,)))
            if i >= 0:
                val = acc + float(self.tables[k - 1].logp[i])
                break
            if not ctx:
                val = acc + math.log(1e-7)  # ký hiệu chưa từng thấy ở bậc 1
                break
            acc += self._backoff_weight(ctx)
            ctx = ctx[1:]
        if len(self._cache) > 100_000:
            self._cache.clear()
        self._cache[key] = val
        return val

    def score_many(self, context: tuple[int, ...], symbols: np.ndarray) -> np.ndarray:
        symbols = np.asarray(symbols, dtype=np.int64)
        out = np.empty(len(symbols), dtype=np.float32)
        pending = np.ones(len(symbols), dtype=bool)
        acc = 0.0
        ctx = tuple(context)[-(self.order - 1):] if self.order > 1 else ()
        while True:
            k = len(ctx) + 1
            base = np.uint64(fnv1a64(ctx)) if ctx else FNV_OFFSET
            keys = extend_hash(base, symbols)
            idx = self.tables[k - 1].lookup_many(keys)
            found = pending & (idx >= 0)
            out[found] = acc + self.tables[k - 1].logp[idx[found]]
            pending &= ~found
            if not pending.any():
                break
            if not ctx:
                out[pending] = acc + math.log(1e-7)
                break
            acc += self._backoff_weight(ctx)
            ctx = ctx[1:]
        return out

    def sentence_logprob(self, text: str) -> float:
        ids = [self.alphabet.bos_id] + self.alphabet.encode(text) + [self.alphabet.eos_id]
        total = 0.0
        for i in range(1, len(ids)):
            total += self.score(tuple(ids[max(0, i - self.order + 1):i]), ids[i])
        return total

    def perplexity(self, lines: list[str]) -> float:
        non_blank = [ln for ln in lines if ln.strip()]
        if not non_blank:
            raise ValueError("không có dòng nào để tính perplexity")
        total_lp = 0.0
        n = 0
        for ln in non_blank:
            total_lp += self.sentence_logprob(ln)
            n += len(ln) + 1
        return math.exp(-total_lp / max(1, n))


# ---- huấn luyện nhỏ: Kneser-Ney nội suy đơn giản (absolute discounting) ----

def _ngram_counts(lines: list[str], alphabet: LMAlphabet, order: int) -> list[Counter]:
    counts: list[Counter] = [Counter() for _ in range(order)]
    for ln in lines:
        ids = [alphabet.bos_id] + alphabet.encode(ln) + [alphabet.eos_id]
        for i in range(1, len(ids)):
            for k in range(1, order + 1):
                if i - k + 1 < 0:
                    break
                counts[k - 1][tuple(ids[i - k + 1:i + 1])] += 1
    return counts


def train_small(lines: list[str], alphabet: LMAlphabet, order: int = 6, discount: float = 0.75) -> CharNGramLM:
    """Absolute discounting nội suy, xuất dạng backoff kiểu ARPA (entry đã nội suy, backoff = λ(h))."""
    lines = [ln for ln in lines if ln.strip()]
    counts = _ngram_counts(lines, alphabet, order)
    vocab_ids = list(range(1, len(alphabet)))  # không sinh <s>
    v = len(vocab_ids)
    probs: list[dict[tuple[int, ...], float]] = []
    backoffs: list[dict[tuple[int, ...], float]] = []

    # bậc 1
    total1 = sum(counts[0].values())
    n1plus = len(counts[0])
    lam1 = discount * n1plus / max(1, total1)
    p1 = {}
    for s in vocab_ids:
        c = counts[0].get((s,), 0)
        p1[(s,)] = max(c - discount, 0.0) / max(1, total1) + lam1 / v
    probs.append(p1)
    backoffs.append({})

    for k in range(2, order + 1):
        ctx_total: dict[tuple[int, ...], int] = defaultdict(int)
        ctx_types: dict[tuple[int, ...], int] = defaultdict(int)
        for ng, c in counts[k - 1].items():
            ctx_total[ng[:-1]] += c
            ctx_types[ng[:-1]] += 1
        pk: dict[tuple[int, ...], float] = {}
        bk: dict[tuple[int, ...], float] = {}
        lower = probs[k - 2]
        for ng, c in counts[k - 1].items():
            h = ng[:-1]
            lam = discount * ctx_types[h] / ctx_total[h]
            pk[ng] = max(c - discount, 0.0) / ctx_total[h] + lam * lower.get(ng[1:], 1.0 / v)
            bk[h] = lam
        probs.append(pk)
        backoffs.append(bk)

    tables = []
    ngrams_named: list[dict[tuple[int, ...], tuple[float, float]]] = []
    for k in range(1, order + 1):
        bo_map = backoffs[k] if k < order else {}
        named = {ng: (math.log(p), math.log(bo_map[ng]) if ng in bo_map else 0.0)
                 for ng, p in probs[k - 1].items()}
        ngrams_named.append(named)
        items = sorted(((fnv1a64(ng), lp, bo) for ng, (lp, bo) in named.items()), key=lambda t: t[0])
        tables.append(NGramTable(
            np.array([h for h, _, _ in items], dtype=np.uint64),
            np.array([lp for _, lp, _ in items], dtype=np.float32),
            np.array([bo for _, _, bo in items], dtype=np.float32),
        ))
    lm = CharNGramLM(alphabet, order, tables)
    lm._ngrams = ngrams_named  # tên n-gram, chỉ để save_arpa
    return lm


# ---- ARPA và nhị phân ----

def save_arpa(lm: CharNGramLM, path: Path) -> None:
    """Chỉ dùng cho LM nhỏ (cần tên n-gram): tái dựng từ bảng bằng cách liệt kê mọi tổ hợp là không khả thi,
    nên save_arpa yêu cầu lm có thuộc tính _ngrams (do train_small gán)."""
    ngrams = getattr(lm, "_ngrams", None)
    if ngrams is None:
        raise ValueError("save_arpa chỉ hỗ trợ LM từ train_small")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\\data\\\n")
        for k in range(1, lm.order + 1):
            f.write(f"ngram {k}={len(ngrams[k - 1])}\n")
        for k in range(1, lm.order + 1):
            f.write(f"\n\\{k}-grams:\n")
            for ng, (lp, bo) in ngrams[k - 1].items():
                words = " ".join(SPACE_TOKEN if s == lm.alphabet.space_id else lm.alphabet.symbols[s] for s in ng)
                line = f"{lp / LN10:.6f}\t{words}"
                if k < lm.order and bo != 0.0:
                    line += f"\t{bo / LN10:.6f}"
                f.write(line + "\n")
        f.write("\n\\end\\\n")


def load_arpa(path: Path, alphabet: LMAlphabet) -> CharNGramLM:
    order = 0
    per_order: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    section = 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("ngram "):
                order = max(order, int(line[6:].split("=")[0]))
                continue
            if line.endswith("-grams:"):
                section = int(line[1:].split("-")[0])
                continue
            if line in ("\\data\\", "\\end\\") or section == 0:
                continue
            parts = line.split("\t")
            lp = float(parts[0]) * LN10
            toks = parts[1].split(" ")
            ids = [alphabet.index.get(SPACE_TOKEN if t == SPACE_TOKEN else t, None) for t in toks]
            ids = [alphabet.space_id if t == SPACE_TOKEN else i for t, i in zip(toks, ids, strict=True)]
            if any(i is None for i in ids):
                continue  # ký hiệu ngoài bảng chữ (ví dụ <unk> của lmplz): bỏ
            bo = float(parts[2]) * LN10 if len(parts) > 2 else 0.0
            per_order[section].append((fnv1a64(ids), lp, bo))
    tables = []
    for k in range(1, order + 1):
        items = sorted(per_order.get(k, []), key=lambda t: t[0])
        tables.append(NGramTable(
            np.array([h for h, _, _ in items], dtype=np.uint64),
            np.array([lp for _, lp, _ in items], dtype=np.float32),
            np.array([bo for _, _, bo in items], dtype=np.float32),
        ))
    return CharNGramLM(alphabet, order, tables)


def save_bin(lm: CharNGramLM, path: Path) -> None:
    """Nhị phân numpy; bảng chữ lưu dạng chuỗi JSON (không pickle) để nạp an toàn."""
    arrays = {
        "order": np.array(lm.order),
        "symbols_json": np.array(json.dumps(lm.alphabet.symbols, ensure_ascii=False)),
    }
    for k, t in enumerate(lm.tables, start=1):
        arrays[f"h{k}"], arrays[f"p{k}"], arrays[f"b{k}"] = t.hashes, t.logp, t.backoff
    # np.savez tự thêm đuôi ".npz" nếu path là chuỗi/Path không có sẵn đuôi đó,
    # khiến load_bin(path) không tìm thấy file; mở sẵn file nhị phân để tránh việc này.
    with open(path, "wb") as f:
        np.savez(f, **arrays)


def load_bin(path: Path) -> CharNGramLM:
    z = np.load(path)  # không allow_pickle: chỉ mảng số và một chuỗi unicode
    order = int(z["order"])
    alphabet = LMAlphabet(json.loads(str(z["symbols_json"])))
    tables = [NGramTable(z[f"h{k}"], z[f"p{k}"], z[f"b{k}"]) for k in range(1, order + 1)]
    return CharNGramLM(alphabet, order, tables)
