"""Điện văn mạng CW (định dạng M89/M95) — tầng cấu trúc sau giải mã (docs/research/06, bước 4).

Điện: `VV <hô hiệu> DE <hô hiệu>`, `HR MSG GA`, `NR .../CK ..` + nhóm giờ, `RMKS` + nhóm, `=`, THÂN gồm các nhóm
số độ dài cố định (4), `<AR>`. Số viết tắt A1 U2 V3 D8 N9 T0; `?` = nhóm vừa đánh hỏng, phát lại; 8 chấm = xóa.

Đo 28/09 trên T7 (3 file thật, bản chép nhân viên): ký tự đọc đúng tới 96 % nhưng chỉ 46/108 nhóm của bản chép
hiện ra ĐÚNG — các nhóm dính liền (`67A3TD3D6746` thay vì `6713 0838 6746`): người gửi để khoảng giữa nhóm ngắn
ngang khoảng giữa chữ (nhập nhằng thật, xem CLAUDE.md "Dấu cách giữa dãy số gõ tay"). Thân điện có cấu trúc
cứng nên chia lại được: quy hoạch động trên từng dãy ký tự số, nhóm đúng độ dài thì không tốn, lệch thì tốn
theo số ký tự lệch; dấu cách của mô hình là gợi ý (ranh giới trùng nó được thưởng, nằm trong nhóm thì phạt);
một từ ngắn mô hình đã tách riêng (mảnh rác trước `<AR>`) được giữ riêng với giá rẻ; phần cuối dãy ngay trước
`?`/xóa là lần đánh hỏng nên được ngắn.

`TO` giữa các nhóm RMKS (cả 3 file T7: `8981 TO 8836`, bản chép bỏ đi) là một từ, không phải số 0 + `O`. Dãy
số ĐỦ nhóm dính chữ lạ (`1345RNQSL`, `4236ST ?`) thì tách; dãy lẻ nhóm giữ chỗ nối (chữ lạ có thể là chữ số
đọc nhầm: `DN5S4`).

MÀO ĐẦU (trước RMKS, 28/09): người gửi để lặng giữa chữ 1,2–2 chấm, giữa từ 3–4 chấm và đánh liền chữ (`MSG` =
`--` `...` `--.` -> `7G`) nên âm thanh KHÔNG có ranh giới từ — nhân viên tách nhờ biết định dạng. Làm theo định
dạng: (1) cụm thủ tục khớp theo CHUỖI chấm-gạch bỏ qua ranh giới ký tự (`HR7GGA` = HR MSG GA, `HRWKNR` = HR WK NR);
(2) CK cuối trước RMKS đứng riêng, dãy số sau nó = CK / ngày / giờ / giờ, số CK đối chiếu với SỐ NHÓM thân đếm được
(`3116091419TT` -> `31 16 0914 1900`); (3) hô hiệu bỏ phiếu giữa các lần lặp (chuỗi 4 ký tự đứng riêng ít nhất
một lần và gặp ít nhất hai lần), `VV`/`DE` dính vào hô hiệu thì tách (`VV4ADJDE` -> `VV 4ADJ DE`).

CHỈ áp khi có mốc `RMKS` (theo MẪU: đúng cả khi bảng tự nhận là Kirin `РМКС`) và vùng sau nó gần như toàn số.
Hô hiệu, phần đầu điện, văn bản thường không bị đụng. Chế độ nghe chưa có tầng này (backlog).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace

from morsedesk.model.vocab import DIGITS

NET_CUT: dict[str, str] = {"-": "0", ".-": "1", "..-": "2", "...-": "3", "-..": "8", "-.": "9"}
DIGIT_OF: dict[str, str] = {p: d for d, p in DIGITS.items()}
RMKS = [".-.", "--", "-.-", "..."]
TO = ["-", "---"]
AR = ".-.-."
BT = "-...-"
QUERY = "..--.."
ERASE = "........"
HARD = {AR, BT, QUERY, ERASE}          # dấu cấu trúc: luôn đứng riêng
MIN_BODY_DIGITS = 12                   # ít hơn ngần này ký tự số sau RMKS thì không đủ bằng chứng
MIN_NUMERIC_SHARE = 0.8                # ... và ký tự số phải chiếm ngần này phần thân (trừ dấu cấu trúc)
DEFAULT_GROUP = 4
OFF_COST = 3.0                         # mỗi ký tự lệch độ dài nhóm
SOLO_COST = 2.5                        # từ ngắn mô hình đã tách riêng hai phía: giữ riêng giá này
BOTCHED_COST = 0.5                     # đoạn đánh hỏng ngay trước `?` / xóa
INNER_SPACE_COST = 2.0                 # dấu cách của mô hình nằm TRONG nhóm
BOUNDARY_BONUS = 1.0                   # ranh giới nhóm trùng dấu cách của mô hình


def digit_of(pattern: str | None) -> str | None:
    """Chữ số của một mẫu: số đủ, hoặc số viết tắt của điện mạng."""
    if pattern is None:
        return None
    return DIGIT_OF.get(pattern) or NET_CUT.get(pattern)


def body_span(patterns: list[str | None]) -> tuple[int, int] | None:
    """(đầu, cuối) vùng thân: sau mốc RMKS CUỐI CÙNG tới `<AR>` đầu tiên sau đó; None nếu không phải điện mạng."""
    start = None
    for i in range(len(patterns) - 3):
        if patterns[i:i + 4] == RMKS:
            start = i + 4
    if start is None:
        return None
    end = next((i for i in range(start, len(patterns)) if patterns[i] == AR), len(patterns))
    body = [p for p in patterns[start:end] if p not in HARD]
    n_num = sum(1 for p in body if digit_of(p) is not None)
    if n_num < MIN_BODY_DIGITS or n_num < MIN_NUMERIC_SHARE * len(body):
        return None
    return start, end


def group_length(runs: list[list[int]], spaces: list[bool]) -> int:
    """Độ dài nhóm: độ dài hay gặp nhất (3–6) của các từ số mô hình đã tách đúng; không rõ thì 4."""
    lens = []
    for run in runs:
        cut = [k for k in run if spaces[k]] + [run[-1] + 1]
        prev = run[0]
        for c in cut:
            if c > prev:
                lens.append(c - prev)
            prev = c
    lens = [n for n in lens if 3 <= n <= 6]
    if len(lens) >= 3:
        n, c = Counter(lens).most_common(1)[0]
        if c >= 3 and c >= 0.4 * len(lens):
            return n
    return DEFAULT_GROUP


def segment(n: int, spaces: list[bool], group: int, botched_tail: bool) -> list[int]:
    """Chỉ số bắt đầu các nhóm của một dãy n ký tự số; spaces[k]: mô hình có dấu cách trước ký tự k."""
    best = [float("inf")] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for e in range(1, n + 1):
        for size in range(1, group + 3):
            s = e - size
            if s < 0:
                break
            cost = 0.0 if size == group else OFF_COST * abs(size - group)
            solo = (s == 0 or spaces[s]) and (e == n or spaces[e]) and not any(spaces[s + 1:e])
            if solo and size < group:
                cost = min(cost, SOLO_COST)
            if e == n and botched_tail and size < group:
                cost = min(cost, BOTCHED_COST)
            cost += INNER_SPACE_COST * sum(1 for k in range(s + 1, e) if spaces[k])
            cost -= BOUNDARY_BONUS if (s == 0 or spaces[s]) else 0.0
            if best[s] + cost < best[e]:
                best[e], back[e] = best[s] + cost, s
    starts, e = [], n
    while e > 0:
        starts.append(back[e])
        e = back[e]
    return sorted(starts)


@dataclass
class Regrouped:
    letters: list[str]          # một ô = chữ của một ký tự gốc; có thể NHIỀU chữ (tách chữ đánh liền) hoặc rỗng
    spaces: list[bool]
    changed: bool
    ck: int | None = None       # số CK đọc được trong mào đầu
    groups: int | None = None   # số nhóm thân đếm được sau `=`


# Cụm thủ tục của mào đầu/phần kết, khớp theo chuỗi chấm-gạch (mẫu từng chữ theo bảng Latin, trùng mọi bảng).
PHRASES: list[list[list[str]]] = [
    [["....", ".-."], ["--", "...", "--."], ["--.", ".-"]],           # HR MSG GA
    [["....", ".-."], ["--", "...", "--."]],                          # HR MSG
    [["....", ".-."], [".--", "-.-"], ["-.", ".-."]],                 # HR WK NR
    [["--", "...", "--."], ["-.", ".-."]],                            # MSG NR
    [["--", "...", "--."], ["--.", ".-"]],                            # MSG GA
]
PHRASE_ELEMS = ["".join(p for word in ph for p in word) for ph in PHRASES]
CK = ["-.-.", "-.-"]
CALL_PREFIX = {("...-",), ("...-", "...-"), ("...-", "...-", "...-"), ("-..", ".")}   # V, VV, VVV, DE


def _first_rmks(patterns: list) -> int | None:
    return next((i for i in range(len(patterns) - 3) if patterns[i:i + 4] == RMKS), None)


def _words(idx: list[int], spaces: list[bool]) -> list[list[int]]:
    out: list[list[int]] = []
    for k in idx:
        if spaces[k] or not out:
            out.append([k])
        else:
            out[-1].append(k)
    return out


def _phrases(patterns: list, idx: list[int], render) -> dict[int, tuple[str, bool]]:
    """Khớp cụm thủ tục theo chuỗi chấm-gạch trên dãy ký tự `idx` (bỏ qua dấu cách). Trả {ký tự: (chữ mới,
    đầu từ?)}; ký tự bị gộp vào ký tự trước nhận chữ rỗng."""
    out: dict[int, tuple[str, bool]] = {}
    i = 0
    while i < len(idx):
        hit = None
        for ph in PHRASES:
            letters = [(p, j == 0) for word in ph for j, p in enumerate(word)]
            target = "".join(p for p, _ in letters)
            acc, j = "", i
            while j < len(idx) and len(acc) < len(target) and patterns[idx[j]]:
                acc += patterns[idx[j]]
                j += 1
            if acc == target:
                hit = (letters, j)
                break
        if hit is None:
            i += 1
            continue
        letters, j = hit
        lpos, pos = [], 0
        for p, _ in letters:
            lpos.append(pos)
            pos += len(p)
        pos = 0
        for q in range(i, j):
            lo, hi = pos, pos + len(patterns[idx[q]])
            pos = hi
            mine = [n for n, lp in enumerate(lpos) if lo <= lp < hi]
            out[idx[q]] = ("".join(render(letters[n][0]) for n in mine), bool(mine) and letters[mine[0]][1])
        i = j
    return out


def _header(patterns: list, out_l: list[str], out_s: list[bool], hdr_end: int, tail_from: int | None,
            groups: int | None, render) -> int | None:
    """Mào đầu [0, hdr_end) và phần kết [tail_from, hết): cụm thủ tục, CK + nhóm giờ, hô hiệu. Trả số CK."""
    regions = [list(range(0, hdr_end))]
    if tail_from is not None and tail_from < len(patterns):
        regions.append(list(range(tail_from, len(patterns))))
    for idx in regions:
        for k in idx:                                 # `<ERR>`, `=`, `<AR>` đứng riêng (`CYHMG<ERR>`); `?` ở
            if patterns[k] in HARD - {QUERY}:         # mào đầu/phần kết là dấu hỏi thật (`QSL?`), không tách
                out_s[k] = True
                if k + 1 < len(out_s):
                    out_s[k + 1] = True
        hits = _phrases(patterns, idx, render)
        for k, (text, word_start) in hits.items():
            out_l[k] = text
            if text:
                out_s[k] = word_start
        for k in hits:                                # chữ đầu tiên SAU một cụm thủ tục mở từ mới
            if k + 1 < len(out_s) and k + 1 not in hits:
                out_s[k + 1] = True
    # CK cuối cùng trước RMKS + dãy số theo sau: CK / ngày / giờ / giờ
    ck = None
    for i in reversed([i for i in range(hdr_end - 2) if patterns[i:i + 2] == CK]):
        run, q = [], i + 2
        while q < hdr_end and (digit_of(patterns[q]) is not None or patterns[q] is None):
            run.append(q)
            q += 1
        if len(run) < 3 or digit_of(patterns[run[0]]) is None:
            continue
        digits = "".join(digit_of(patterns[r]) or "?" for r in run)
        n = len(run)
        if groups is not None and digits.startswith(str(groups)) and n - len(str(groups)) in (0, 8, 10):
            cl = len(str(groups))
        elif n > 10:
            cl = n - 10
        elif n > 8:
            cl = n - 8
        else:
            cl = n
        rest = n - cl
        cuts = {0, cl} | ({cl + 2, cl + 6} if rest == 10 else {cl + 4} if rest == 8 else set())
        out_s[i], out_s[i + 1] = True, False
        for k, r in enumerate(run):
            out_s[r] = k in cuts
            out_l[r] = digit_of(patterns[r]) or out_l[r]
        if run[-1] + 1 < len(out_s):
            out_s[run[-1] + 1] = True
        ck = int(digits[:cl]) if digits[:cl].isdigit() else None
        break
    # hô hiệu: chuỗi 4 ký tự (theo mẫu) đứng riêng ít nhất một lần và gặp ít nhất hai lần trong mào đầu
    words = _words(list(range(0, hdr_end)), out_s)
    keys = [tuple(patterns[k] for k in w) for w in words]
    calls = set()
    for cand in {kw for kw in keys if len(kw) == 4 and all(kw)}:
        if cand in CALL_PREFIX or set(cand) <= {"...-"}:
            continue
        if sum(1 for kw in keys for st in range(len(kw) - 3) if kw[st:st + 4] == cand) >= 2:
            calls.add(cand)
    for w, kw in zip(words, keys, strict=True):
        if len(w) <= 4:
            continue
        for st in range(len(kw) - 3):
            if kw[st:st + 4] in calls:
                pre, post = kw[:st], kw[st + 4:]
                if (not pre or pre in CALL_PREFIX) and (not post or post in CALL_PREFIX or post in calls):
                    out_s[w[st]] = True
                    if st + 4 < len(w):
                        out_s[w[st + 4]] = True
                break
    return ck


def regroup(letters: list[str], patterns: list[str | None], spaces: list[bool], render=None) -> Regrouped:
    """Chia lại nhóm thân điện + mào đầu. `spaces[k]`: có dấu cách trước ký tự k. Trả ký tự (số viết tắt trong
    nhóm đủ độ dài đã đổi thành chữ số) và dấu cách mới; `changed` = False nếu không phải điện mạng.
    `render`: mẫu -> chữ của bảng mã bản tin (cụm thủ tục đánh liền được viết lại bằng đúng bảng đó)."""
    if render is None:
        from morsedesk.lm.profile import load_profile
        en = load_profile("en")

        def render(p: str) -> str:
            return en.render([p])
    span = body_span(patterns)
    if span is None:
        return Regrouped(list(letters), list(spaces), False)
    start, end = span
    out_l, out_s = list(letters), list(spaces)
    word_to = {i for i in range(start, end - 1) if patterns[i:i + 2] == TO}

    def numeric(k: int) -> bool:
        return k not in word_to and digit_of(patterns[k]) is not None
    runs: list[list[int]] = []
    i = start
    while i < end:
        if not numeric(i):
            i += 1
            continue
        j = i
        while j < end and numeric(j):
            j += 1
        runs.append(list(range(i, j)))
        i = j
    g = group_length(runs, spaces)
    complete = 0
    bt = max((i for i in range(start, end) if patterns[i] == BT), default=None)
    for run in runs:
        a, b = run[0], run[-1] + 1
        local = [spaces[k] if k > a else True for k in run]
        tail = b < len(patterns) and patterns[b] in (QUERY, ERASE)
        starts = set(segment(len(run), local, g, tail))
        for k in run:
            out_s[k] = (k - a) in starts
        whole = len(run) % g == 0
        if whole and b < len(out_s):
            out_s[b] = True             # đủ nhóm: chữ lạ theo sau đứng riêng (`1345 RNQSL`)
        if a != start and patterns[a - 1] not in HARD and not whole:
            out_s[a] = spaces[a]        # dãy lẻ nhóm bị cắt bởi một chữ lạ (`DN5S4`): giữ nguyên chỗ nối đó
        for s in sorted(starts):
            e = min([t for t in starts if t > s], default=len(run))
            if e - s == g:
                if bt is not None and a + s > bt:
                    complete += 1
                for k in range(a + s, a + e):
                    out_l[k] = digit_of(patterns[k]) or out_l[k]
    for k in word_to:                                 # từ `TO` đứng riêng
        out_s[k], out_s[k + 1] = True, False
        if k + 2 < len(out_s):
            out_s[k + 2] = True
    for k in range(start, end):                       # dấu cấu trúc đứng riêng
        if patterns[k] in HARD:
            out_s[k] = True
            if k + 1 < len(out_s):
                out_s[k + 1] = True
    if end < len(out_s):
        out_s[end] = True
    first = _first_rmks(patterns)
    groups = complete if bt is not None else None
    ck = _header(patterns, out_l, out_s, first if first is not None else start - 4,
                 end + 1 if end < len(patterns) else None, groups, render)
    for r in (first, start - 4):                     # RMKS (đầu và cuối) đứng riêng: `RMKS8 O` -> `RMKS 8 O`
        if r is not None and r >= 0:
            if r > 0:
                out_s[r] = True
            if r + 4 < len(out_s):
                out_s[r + 4] = True
    return Regrouped(out_l, out_s, out_l != list(letters) or out_s != list(spaces), ck, groups)


def traffic_words(words: list, profile) -> list | None:
    """Áp `regroup` lên danh sách Word (morsedesk.api.Word): dựng lại từ theo thời điểm từng chữ.
    None nếu không phải điện mạng hoặc không đổi gì."""
    from morsedesk.api import char_confs, geo_conf
    from morsedesk.numbers import letters_of

    flat: list[tuple[str, float, int]] = []          # (chữ, giây, chỉ số từ gốc)
    probs: list[float] = []                          # xác suất từng chữ: mỗi nhóm mới có độ tin cậy CỦA NÓ
    spaces: list[bool] = []
    for wi, w in enumerate(words):
        letters = letters_of(w.text)
        times = [t for _, t in w.chars] if len(w.chars) == len(letters) else [w.start_s] * len(letters)
        cp = char_confs(w)
        cp = cp if len(cp) == len(letters) else [w.confidence] * len(letters)
        for k, (ch, t) in enumerate(zip(letters, times, strict=True)):
            flat.append((ch, t, wi))
            probs.append(cp[k])
            spaces.append(k == 0 and wi > 0)
    pats = [profile.letter_to_pattern.get(ch) or profile.prosign_to_pattern.get(ch) for ch, _, _ in flat]
    rg = regroup([ch for ch, _, _ in flat], pats, spaces, render=lambda p: profile.render([p]))
    if not rg.changed:
        return None
    out = []
    k = 0
    while k < len(flat):
        e = k + 1
        while e < len(flat) and not rg.spaces[e]:
            e += 1
        first_w, last_w = words[flat[k][2]], words[flat[e - 1][2]]
        start = first_w.start_s if (k == 0 or flat[k - 1][2] != flat[k][2]) else flat[k][1]
        end = last_w.end_s if (e == len(flat) or flat[e][2] != flat[e - 1][2]) else flat[e][1]
        # một ô có thể là NHIỀU chữ (chữ đánh liền `7` = `MS`) hoặc rỗng (gộp vào ô trước): bung theo mốc ô gốc
        chars = [(c, flat[q][1]) for q in range(k, e) for c in letters_of(rg.letters[q])]
        cp = [probs[q] for q in range(k, e) for _ in letters_of(rg.letters[q])]
        orig_boundary = k == 0 or flat[k - 1][2] != flat[k][2]
        if chars:
            out.append(replace(first_w, text="".join(c for c, _ in chars), start_s=start, end_s=max(end, start),
                               confidence=geo_conf(cp), chars=chars, char_probs=cp,
                               space_p=first_w.space_p if orig_boundary else 1.0))
        k = e
    return out


@dataclass
class LiveNet:
    """Tầng cấu trúc cho chế độ NGHE (model/stream.py): chữ đã chốt KHÔNG BAO GIỜ đổi (người vận hành chép tay
    theo nó), nên chỉ quyết TIẾN — lúc một phần từ được chốt:
    - sau mốc RMKS (4 chữ chốt gần nhất, theo mẫu) là thân điện, cho tới `<AR>`;
    - trong thân: một từ của mô hình có quá `group` ký tự số liền thì TÁCH (`67A3TD3D6746` -> ba nhóm); nhóm đủ
      rồi gặp chữ lạ cũng tách (`1345 RN`). Gộp qua dấu cách của mô hình CHỈ khi từ trước là nhóm số chưa đủ VÀ
      tổng ký tự số chia hết cho `group` (`T` + `743A5NT` -> `0743 1590`; `671` + `0838` thì không: một chữ số
      bị mất không được làm lệch mọi nhóm sau — chế độ file có quy hoạch động, ở đây không nhìn trước được);
    - `?`, `=`, `<AR>`, 8 chấm xóa, `TO` đứng riêng; số viết tắt đổi ngay lúc chốt khi từ tới đó toàn số;
    - MÀO ĐẦU, khi phiên đã thấy dấu hiệu điện mạng (cụm thủ tục `HR MSG`/`HR WK NR`… hoặc đã có thân điện): cụm
      thủ tục đánh liền trong mẩu vừa chốt được viết lại (`HR7G` -> `HR MSG`); `CK` mở từ mới và dãy số sau nó
      chia 2/2/4/4 (CK / ngày / giờ / giờ — chế độ nghe chưa biết số nhóm nên coi CK hai chữ số), BỎ QUA dấu cách
      của mô hình (`3524 T 828 1827` -> `35 24 0828 1827`); dãy số sau `NR` nối lại (`T 717` -> `0717`)."""
    group: int = DEFAULT_GROUP
    body: bool = False
    recent: list = field(default_factory=list)     # mẫu vài chữ chốt gần nhất (dò RMKS)
    run: int = 0                                   # số ký tự số của từ hiện tại; -1 = từ có chữ lạ
    brk: bool = False                              # chữ kế tiếp phải mở từ mới
    to_o: bool = False                             # chữ kế tiếp là `O` của `TO`
    net: bool = False                              # phiên đã thấy dấu hiệu điện mạng (bật luật mào đầu)
    nr_first: bool = False
    dtg: int | None = None                         # đang trong dãy số sau CK: số chữ số đã nhận
    nr: bool = False                               # đang trong số NR
    elems: str = ""                                # chuỗi chấm-gạch các chữ chốt gần nhất (dò cụm thủ tục)

    def feed(self, chars: list, patterns: list, cont: bool, render=None) -> tuple[list, bool]:
        """`chars` [(chữ, giây)] của một phần từ vừa chốt, `cont` = nối tiếp từ trước. Trả ([(đoạn chữ, nối
        tiếp?)], đã xử lý như thân điện/mào đầu?). `render`: mẫu -> chữ của bảng mã bản tin."""
        segs: list[list] = []
        touched = False
        hits = {} if self.body or render is None else _phrases(patterns, list(range(len(patterns))), render)
        if hits:
            self.net = True
        lead = 0                                     # số ký tự số đầu phần này (để gộp mảnh nhóm)
        while lead < len(patterns) and digit_of(patterns[lead]) is not None and not (
                patterns[lead] == TO[0] and lead + 1 < len(patterns) and patterns[lead + 1] == TO[1]):
            lead += 1
        for k, ((ch, t), p) in enumerate(zip(chars, patterns, strict=True)):
            join = cont if k == 0 else True
            if (k == 0 and not cont and self.body and not self.brk and 0 < self.run < self.group
                    and lead and (self.run + lead) % self.group == 0):
                join = True                          # mảnh nhóm + phần kế ghép khít thành nhóm đủ
            if not join:
                self.run = 0
            if not self.body and self.net:
                touched = True
                if k in hits:
                    ch, start_word = hits[k]
                    join = join and not start_word
                    self.dtg = None
                    if not ch:                       # ký tự gộp vào chữ trước (cụm đánh liền)
                        self.recent = (self.recent + [p])[-4:]
                        self.elems = (self.elems + (p or "?"))[-40:]
                        continue
                elif self.brk or (k - 1) in hits:    # chữ đầu tiên sau một cụm thủ tục mở từ mới
                    join, self.brk = False, False
                if k not in hits and p in HARD:
                    join, self.brk, self.dtg, self.nr = False, True, None, False
                elif k not in hits and p == CK[0] and k + 1 < len(patterns) and patterns[k + 1] == CK[1]:
                    join, self.dtg, self.nr = False, None, False
                elif self.dtg is not None and digit_of(p) is not None:
                    join = self.dtg not in (0, 2, 4, 8)
                    ch = digit_of(p)
                    self.dtg += 1
                    if self.dtg == 12:
                        self.dtg, self.brk = None, True
                elif self.nr and digit_of(p) is not None:
                    join = not self.nr_first          # số NR: chữ số đầu mở từ, các chữ số sau nối lại
                    self.nr_first = False
                    ch = digit_of(p)
                elif k not in hits:
                    self.dtg = None
                    self.nr = False
            if self.body:
                touched = True
                if self.brk:
                    join, self.brk, self.run = False, False, 0
                if self.to_o or p == TO[1]:          # `O` chỉ có trong `TO`: luôn đóng từ
                    join = join if not self.to_o else True
                    self.to_o, self.brk, self.run = False, True, -1
                elif p in HARD:
                    join, self.brk, self.run = False, True, -1
                    if p == AR:
                        self.body = False
                elif p == TO[0] and k + 1 < len(patterns) and patterns[k + 1] == TO[1]:
                    join, self.to_o, self.run = False, True, -1
                elif digit_of(p) is not None:
                    if join and self.run == self.group:
                        join, self.run = False, 0
                    if self.run >= 0:
                        ch = digit_of(p)
                        self.run += 1
                else:
                    if join and self.run == self.group:
                        join = False
                    self.run = -1
            if join and segs:
                segs[-1][0].append((ch, t))
            else:
                segs.append([[(ch, t)], join])
            self.recent = (self.recent + [p])[-4:]
            # mào đầu dính liền được chốt dần từng mẩu 1–3 chữ (`H` `R7` `G`): dò cụm thủ tục XUYÊN các mẩu
            self.elems = (self.elems + (p or "?"))[-40:]
            if not self.net and any(self.elems.endswith(e) for e in PHRASE_ELEMS):
                self.net = True
            if not self.body and self.recent == RMKS:
                self.body, self.brk, self.net, self.dtg, self.nr = True, True, True, None, False
            elif not self.body and self.net and self.recent[-2:] == CK and self.dtg is None:
                self.dtg, self.nr = 0, False                 # vừa xong `CK`: dãy số CK / ngày / giờ / giờ
            elif not self.body and self.net and self.recent[-2:] == ["-.", ".-."]:
                self.nr, self.nr_first, self.brk = True, True, True    # vừa xong `NR`
        return [(c, j) for c, j in segs], touched
