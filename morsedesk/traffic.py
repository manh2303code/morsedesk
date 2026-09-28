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
    letters: list[str]
    spaces: list[bool]
    changed: bool


def regroup(letters: list[str], patterns: list[str | None], spaces: list[bool]) -> Regrouped:
    """Chia lại nhóm thân điện. `spaces[k]`: có dấu cách trước ký tự k. Trả ký tự (số viết tắt trong nhóm đủ
    độ dài đã đổi thành chữ số) và dấu cách mới; `changed` = False nếu không phải điện mạng."""
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
    return Regrouped(out_l, out_s, out_l != list(letters) or out_s != list(spaces))


def traffic_words(words: list, profile) -> list | None:
    """Áp `regroup` lên danh sách Word (morsedesk.api.Word): dựng lại từ theo thời điểm từng chữ.
    None nếu không phải điện mạng hoặc không đổi gì."""
    from morsedesk.numbers import letters_of

    flat: list[tuple[str, float, int]] = []          # (chữ, giây, chỉ số từ gốc)
    spaces: list[bool] = []
    for wi, w in enumerate(words):
        letters = letters_of(w.text)
        times = [t for _, t in w.chars] if len(w.chars) == len(letters) else [w.start_s] * len(letters)
        for k, (ch, t) in enumerate(zip(letters, times, strict=True)):
            flat.append((ch, t, wi))
            spaces.append(k == 0 and wi > 0)
    pats = [profile.letter_to_pattern.get(ch) or profile.prosign_to_pattern.get(ch) for ch, _, _ in flat]
    rg = regroup([ch for ch, _, _ in flat], pats, spaces)
    if not rg.changed:
        return None
    out = []
    k = 0
    while k < len(flat):
        e = k + 1
        while e < len(flat) and not rg.spaces[e]:
            e += 1
        src = sorted({flat[q][2] for q in range(k, e)})
        first_w, last_w = words[flat[k][2]], words[flat[e - 1][2]]
        start = first_w.start_s if (k == 0 or flat[k - 1][2] != flat[k][2]) else flat[k][1]
        end = last_w.end_s if (e == len(flat) or flat[e][2] != flat[e - 1][2]) else flat[e][1]
        chars = [(rg.letters[q], flat[q][1]) for q in range(k, e)]
        orig_boundary = k == 0 or flat[k - 1][2] != flat[k][2]
        out.append(replace(first_w, text="".join(rg.letters[k:e]), start_s=start, end_s=max(end, start),
                           confidence=min(words[s].confidence for s in src), chars=chars,
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
    - `?`, `=`, `<AR>`, 8 chấm xóa, `TO` đứng riêng; số viết tắt đổi ngay lúc chốt khi từ tới đó toàn số."""
    group: int = DEFAULT_GROUP
    body: bool = False
    recent: list = field(default_factory=list)     # mẫu vài chữ chốt gần nhất (dò RMKS)
    run: int = 0                                   # số ký tự số của từ hiện tại; -1 = từ có chữ lạ
    brk: bool = False                              # chữ kế tiếp phải mở từ mới
    to_o: bool = False                             # chữ kế tiếp là `O` của `TO`

    def feed(self, chars: list, patterns: list, cont: bool) -> tuple[list, bool]:
        """`chars` [(chữ, giây)] của một phần từ vừa chốt, `cont` = nối tiếp từ trước. Trả ([(đoạn chữ, nối
        tiếp?)], đã xử lý như thân điện?)."""
        segs: list[list] = []
        touched = False
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
            if not self.body and self.recent == RMKS:
                self.body, self.brk = True, True
        return [(c, j) for c, j in segs], touched
