"""Số trong điện Morse: số viết tắt và nhóm độ dài cố định — xử lý như người chép điện.

Người dùng 26/09: "khả năng giải mã số học cực kỳ kém ... thường xuyên là các chuỗi số dài và ngẫu
nhiên". Đo trên bản ghi THẬT của trạm số (M01/M12/M14, bản chép Priyom; tools/real_numbers_eval.py):
app sai 25 % chữ số, chỉ 42 % nhóm đúng trọn, trong khi trên số tổng hợp chỉ sai 0,2 %. Hai lý do
chính KHÔNG nằm ở việc nghe:

1. **Số viết tắt (cut numbers).** Điện số, điện quân sự và điện thi đấu thường đánh 0 bằng một gạch
   dài (mẫu của T), và trong thi đấu cả bộ: 1 = A, 2 = U, 3 = V, 5 = E, 7 = B, 8 = D, 9 = N, 0 = T
   (4 và 6 giữ nguyên). Mô hình nghe đúng gạch dài nhưng không thể biết đó là 0 — `15304` ra
   `153T4`. Chỉ ngữ cảnh mới phân biệt được.
2. **Nhóm độ dài cố định.** Điện số gồm nhóm 5 chữ số; khi người gõ để khoảng lặng giữa hai chữ số
   hơi dài thì nhóm vỡ đôi (`40788` -> `4078 8`), khi đánh các nhóm sát nhau thì dính liền.

Cả hai CHỈ được áp khi bản tin rõ là điện số (`numeric_context`): hô hiệu `UA9AB`, nhóm mã chữ-số của
đề thi SRR (`Д088А`) hay văn bản thường không bị đụng tới. Làm theo MẪU chấm gạch nên đúng cho cả
bảng Latin lẫn Kirin (`Т` Nga cũng là `-`).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from morsedesk.model.vocab import DIGITS

# Số viết tắt theo mẫu (quy ước thi đấu ARRL/IARU; 0 = T dùng rộng rãi nhất, kể cả trạm số).
CUT_PATTERNS: dict[str, str] = {
    "-": "0", "-.": "9", ".-": "1", "..-": "2", "...-": "3", ".": "5", "-...": "7", "-..": "8",
}
DIGIT_OF_PATTERN: dict[str, str] = {p: d for d, p in DIGITS.items()}
MIN_NUMERIC_GROUPS = 3          # dưới ngần này nhóm có số thì không đủ bằng chứng là điện số
NUMERIC_SHARE = 0.5             # ... và phải là ít nhất nửa số nhóm có chữ/số của bản tin
MAX_ALPHA_SHARE = 0.25          # nhóm có số mà lẫn chữ KHÔNG viết tắt được: quá ngần này là nhóm mã
FIXED_LEN_SHARE = 0.5           # một độ dài chiếm ngần này nhóm số thuần = điện nhóm cố định
MIN_FIXED_GROUPS = 4
STRONG_SHARE = 0.8              # tỉ lệ nhóm đúng độ dài cố định để coi là điện nhóm số thuần

_PROSIGN = re.compile(r"<[A-Z]+>")


@dataclass
class NumericContext:
    numeric: bool
    group_len: int | None        # độ dài nhóm cố định (5 với điện số), None nếu không có
    strong: bool = False         # gần như mọi nhóm đúng độ dài cố định: nhóm chỉ gồm chữ viết tắt cũng là số


def letters_of(text: str) -> list[str]:
    """Tách văn bản một từ thành chữ; prosign `<SK>` là một chữ."""
    out, i = [], 0
    while i < len(text):
        m = _PROSIGN.match(text, i)
        if m:
            out.append(m.group(0))
            i = m.end()
        else:
            out.append(text[i])
            i += 1
    return out


def _patterns(letters: list[str], profile) -> list[str | None]:
    return [profile.letter_to_pattern.get(ch) for ch in letters]


def _is_alpha(ch: str) -> bool:
    return len(ch) == 1 and ch.isalpha()


def analyze(groups: list[list[str]], profile) -> NumericContext:
    """Bản tin có phải điện số không, và nhóm có độ dài cố định không. `groups`: chữ của từng nhóm."""
    counted = [g for g in groups if any(_is_alpha(c) or c.isdigit() for c in g)]
    numeric = [g for g in counted if any(c.isdigit() for c in g)]
    if len(numeric) < MIN_NUMERIC_GROUPS or len(numeric) < NUMERIC_SHARE * len(counted):
        return NumericContext(False, None)
    alpha = 0
    for g in numeric:
        pats = _patterns(g, profile)
        if any(_is_alpha(c) and p not in CUT_PATTERNS for c, p in zip(g, pats, strict=True)):
            alpha += 1
    if alpha > MAX_ALPHA_SHARE * len(numeric):
        return NumericContext(False, None)
    pure = [len(g) for g in numeric if all(c.isdigit() for c in g)]
    cut_like = [g for g in numeric
                if all(c.isdigit() or (_is_alpha(c) and p in CUT_PATTERNS) for c, p in zip(g, _patterns(g, profile), strict=True))]
    if len(pure) < MIN_FIXED_GROUPS and len(cut_like) >= STRONG_SHARE * len(counted):
        # bộ viết tắt đầy đủ (thi đấu): nhóm số gần như không còn nhóm thuần chữ số — tính độ dài theo
        # nhóm chỉ gồm chữ số + chữ viết tắt được (đo 27/09: `N4TD6 TNT6U A4NBV …` không được đổi), CHỈ khi
        # chúng chiếm gần hết bản tin — số có định dạng (`5NN 708`, `UN2`) không phải điện nhóm số
        pure = [len(g) for g in cut_like]
    group_len = None
    if len(pure) >= MIN_FIXED_GROUPS:
        length, n = Counter(pure).most_common(1)[0]
        if n >= FIXED_LEN_SHARE * len(pure) and length >= 3:
            group_len = length
    strong = group_len is not None and sum(1 for g in counted if len(g) == group_len) >= STRONG_SHARE * len(counted)
    return NumericContext(True, group_len, strong)


def expand_cut(group: list[str], profile, ctx: NumericContext) -> list[str]:
    """Nhóm có chữ số trong điện số: chữ viết tắt -> số. Nhóm lẫn chữ KHÁC (nhiễu, hô hiệu) giữ nguyên.

    - Nhóm đúng độ dài cố định của điện, không dấu câu: đổi cả bộ viết tắt (`TT32T`, `AUV4E`).
    - Ngoài ra chỉ đổi `T` (0, gạch dài) và chỉ khi chữ số không ít hơn chữ viết tắt (`153T4`, `3T`).
      Các chữ khác ngoài nhóm số cố định là chữ thật: `5NN`, hô hiệu `UA9T`, lưới `EB84`.
    - Dấu câu: ngoài điện nhóm cố định nó là ĐỊNH DẠNG — `42.6735N/512.9889E` là Bắc/Đông, `T=05`
      không phải `0=05` (đo 27/09, tools/numeric_eval.py kind=formatted) — nên giữ nguyên cả nhóm.
      Trong điện nhóm cố định nó là rác do nghe nhầm một chữ số (`'8T115` ở M01), `T` vẫn là 0.
    """
    pats = _patterns(group, profile)
    cut, n_digit, punct = [], 0, False
    for i, (c, p) in enumerate(zip(group, pats, strict=True)):
        if c.isdigit():
            n_digit += 1
        elif _is_alpha(c) and p in CUT_PATTERNS:
            cut.append(i)
        elif _is_alpha(c) or len(c) > 1:
            return group            # chữ không viết tắt được, hoặc prosign
        else:
            punct = True
    if not cut or (n_digit == 0 and not (ctx.strong and len(group) == ctx.group_len and not punct)):
        return group                # nhóm TOÀN chữ viết tắt chỉ đổi trong điện nhóm số thuần (`EETVT` = 55030)
    fixed = ctx.group_len is not None
    if fixed and len(group) == ctx.group_len and not punct:
        pass
    elif (n_digit < len(cut) or any(CUT_PATTERNS[pats[i]] != "0" for i in cut)
          or (punct and not fixed)):
        return group
    out = list(group)
    for i in cut:
        out[i] = CUT_PATTERNS[pats[i]]
    return out


def repair_groups(groups: list[list[str]], ctx: NumericContext) -> list[list[int]]:
    """Chỉ số các mảnh gộp thành một nhóm, cho điện nhóm cố định độ dài L.

    Ghép một CỤM mảnh số ngắn hơn L khi (a) cụm nằm GIỮA hai nhóm số đủ L chữ và (b) các mảnh ghép
    khít thành từng nhóm đúng L (`4078 8 7 0729` giữa hai nhóm đủ -> `40788 70729`). Phần đầu/cuối
    điện (`284 39 284 39 =`) không nằm giữa hai nhóm đủ nên không bị đụng, dù 3 + 2 cũng bằng 5.
    Độ chắc của dấu cách không dùng được để phân biệt: đo 27/09, dấu cách chèn nhầm ở chỗ ngắt dài
    của người gõ tay có xác suất 0,36–0,996, lẫn hẳn vào dấu cách thật (0,51–1,0).
    """
    L = ctx.group_len
    n = len(groups)

    def short_digits(k: int) -> bool:
        return 0 < len(groups[k]) < (L or 0) and all(c.isdigit() for c in groups[k])

    def full(k: int) -> bool:
        return 0 <= k < n and len(groups[k]) == L and all(c.isdigit() for c in groups[k])

    plan: list[list[int]] = []
    i = 0
    while i < n:
        if L and short_digits(i):
            j = i
            while j < n and short_digits(j):
                j += 1
            tiles: list[list[int]] = []
            cur, total, ok = [], 0, full(i - 1) and full(j)
            for k in range(i, j) if ok else []:
                cur.append(k)
                total += len(groups[k])
                if total == L:
                    tiles.append(cur)
                    cur, total = [], 0
                elif total > L:
                    ok = False
                    break
            if ok and not cur and all(len(t) > 1 for t in tiles):
                plan += tiles
            else:
                plan += [[k] for k in range(i, j)]
            i = j
            continue
        plan.append([i])
        i += 1
    return plan


def normalize_groups(groups: list[list[str]], profile) -> tuple[list[list[str]], list[list[int]], NumericContext]:
    """Toàn bộ xử lý trên danh sách nhóm (chữ). Trả (nhóm mới, nguồn của từng nhóm mới, ngữ cảnh).

    Nguồn: chỉ số các nhóm cũ ghép thành nhóm mới; nhóm tách từ một khối dính có cùng nguồn.
    """
    ctx = analyze(groups, profile)
    if not ctx.numeric:
        return groups, [[i] for i in range(len(groups))], ctx
    expanded = [expand_cut(g, profile, ctx) for g in groups]
    if ctx.group_len is None:
        # tính lại độ dài nhóm SAU khi đổi `T` (`7568T` mới thành nhóm số thuần 5 chữ số), rồi đổi
        # nốt các chữ viết tắt khác của nhóm đúng độ dài đó
        ctx = analyze(expanded, profile)
        if not ctx.numeric:
            return expanded, [[i] for i in range(len(groups))], ctx
        expanded = [expand_cut(g, profile, ctx) for g in expanded]
    out: list[list[str]] = []
    sources: list[list[int]] = []
    for idx in repair_groups(expanded, ctx):
        merged = [c for k in idx for c in expanded[k]]
        L = ctx.group_len
        if L and len(idx) == 1 and len(merged) > L and len(merged) % L == 0 and all(c.isdigit() for c in merged):
            for s in range(0, len(merged), L):          # khối dính k*L chữ số -> k nhóm
                out.append(merged[s:s + L])
                sources.append(idx)
            continue
        out.append(merged)
        sources.append(idx)
    return out, sources, ctx
