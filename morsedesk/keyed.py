"""Đối chiếu kết quả mô hình với NHỊP PHÍM đo được — từng ký tự, khi tín hiệu sạch.

Vì sao (đo 27/09 trên file thật tải từ internet, đáp án do các cặp giám khảo LLM độc lập chép từ ảnh
đường bao, khớp 100 %; và trên tools/numeric_edge_bench.py):
- Bài học đánh TỪNG chữ số, lặng 23–59 dit: mô hình ghép thành `531 2279 5 30 57` (đáp án
  `5 3 1 2 2 7 9 5 3 0 5 7`), bỏ sót vài số, và đọc 5 trên 61 số 0 (5 gạch) thành Ч/Ш/9/О. Bộ DSP cổ
  điển cũng hỏng: nó phân cụm độ dài xung/khoảng lặng TƯƠNG ĐỐI, nên bản tin toàn gạch hoặc toàn
  khoảng lặng dài không còn hai cụm để phân.
- Chữ số đơn cách nhau đúng 7 dit (gõ máy): mô hình ghép `0 5 0 2 6 7` thành `050267`.
- Giọng đọc xen Morse (khóa học UA3AFO): mô hình gộp chữ Morse thật với rác của giọng nói trong cùng
  một "từ" (`ТТ888ЕТ88848`), và đọc giọng nói/nhạc thành chữ số bịa.

Cách làm:
1. Đọc nhịp phím (`read_keying`): ký tự = nhóm xung cách nhau < 2 dit; dit đo từ khoảng lặng GIỮA các
   phần tử của một ký tự (luôn 1 dit) — đúng cả với bản tin toàn gạch. Mỗi ký tự nhịp phím là
   MORSE RÕ (mọi phần tử rõ chấm/gạch, mẫu có trong bảng, thuần tone), MORSE MỜ (thuần tone nhưng phần
   tử không rõ — gõ tay lệch) hoặc KHÔNG PHẢI MORSE (không thuần tone: giọng nói, nhạc).
2. Căn chuỗi ký tự mô hình với chuỗi ký tự nhịp phím (quy hoạch động theo mẫu và thứ tự, băng theo
   thời gian) — KHÔNG theo mốc thời gian đơn thuần: khi các ký tự cách nhau bằng khoảng lặng dài, mô
   hình phát mốc của ký tự k+1 ngay đầu khoảng lặng trước nó, và ký tự đầu ở khung 0.
3. Dựng lại: khớp mẫu -> giữ chữ mô hình chọn (LM chọn Ә hay А); lệch với MORSE RÕ -> theo nhịp phím;
   MORSE RÕ mà mô hình bỏ sót -> chèn; chữ mô hình nằm trên KHÔNG PHẢI MORSE -> bỏ (trừ khi từ của nó
   rất chắc); dấu cách theo nhịp phím (khoảng lặng dài, nhịp gõ máy), còn lại theo mô hình.
Chỉ chạy khi SNR >= MIN_SNR_DB và mô hình khớp nhịp phím ở >= MIN_AGREEMENT số ký tự Morse rõ.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from morsedesk.constants import FRAME_RATE

MIN_SNR_DB = 15.0          # đối chiếu với nhịp phím chỉ khi tín hiệu sạch (T1 10 dB có nhiễu xung: tệ đi)
LONG_GAP_UNITS = 10.0      # khoảng lặng >= ngần này dit ...
LONG_GAP_S = 0.5           # ... và >= ngần này giây, lặng thật, là dấu cách (trừ cụm dưới của Farnsworth)
QUIET = 0.25               # lặng thật: đường bao < nền + QUIET * (mức tone - nền)
TWO_CLUSTER_RATIO = 1.9    # hai cụm khoảng lặng (giữa chữ / giữa từ) cách nhau ít nhất ngần này lần
MACHINE_SEPARATION = 1.5   # ... và tách bạch thế này (gõ máy): nhịp phím quyết MỌI dấu cách
SINGLE_SPREAD = 1.35       # một cụm lặng dài lệch nhau hơn ngần này lần = chữ rời (bài học); đều hơn = nhập nhằng
SINGLE_WORD_UNITS = 5.5    # (dựng lại từ) khoảng >= ngần này dit mà không có quyết định chắc thì là giữa từ
DIT_UNITS = (0.5, 1.8)     # xung rõ là chấm
DAH_UNITS = (2.2, 4.6)     # xung rõ là gạch
CRISP_DIT = (0.7, 1.4)     # phần tử SẮC NÉT: chỉ những ký tự như thế mới được sửa khi lệch >= 2 phần tử
CRISP_DAH = (2.5, 3.7)
SKIPPED_BREAK_S = 1.0      # đoạn bị bỏ giữa hai chữ dài ngần này giây mới là ranh giới từ
HAND_LONG_GAP_UNITS = 20.0 # gõ tay: chỉ khoảng lặng dài ngần này mới chắc là dấu cách (SAQ ngừng giữa từ)
DROPOUT_UNITS = 0.5        # khoảng lặng ngắn hơn ngần này dit giữa hai xung = rớt tín hiệu, không phải khoảng
STABLE_RATIO = 2.0         # biên độ ký tự thuần tone p90/p10 <= ngần này (6 dB): không fading
STABLE_TONAL = 0.4         # ... tính trên mọi ký tự thuần tone từ ngần này (giọng nói <= 0,37 không tính)
NON_MORSE_TONAL = 0.3      # ký tự nhịp phím dưới ngần này là KHÔNG phải Morse (bỏ chữ mô hình đọc ở đó)
LEVEL_RANGE = (0.5, 2.0)   # biên độ ký tự ngoài khoảng này lần mức Morse (xung sét) -> mẫu không rõ
PRECISE_SPREAD = 0.12      # (tứ phân vị 3 - 1) / trung vị của độ dài chấm VÀ của gạch <= ngần này: nhịp máy
                           # (27/09: máy <= 0,05; bài học/khóa học thật <= 0,06; gõ tay, bug ~0,2)
JOIN_MAX_UNITS = 5.0       # chỉ ghép khoảng lặng ngắn hơn ngần này dit
LESSON_MIN_GAPS = 8        # bài học: ít nhất ngần này khoảng lặng ...
LESSON_MAX_OVER_MEDIAN = 2.0   # ... và khoảng dài nhất < ngần này lần trung vị (Farnsworth: ~2,33)
TONAL_MIN = 0.5            # ký tự thuần tone (Morse sạch đo 0,85–0,92; giọng nói 0,02–0,37)
MIN_AGREEMENT = 0.8        # mô hình khớp nhịp phím ở ngần này ký tự Morse rõ thì mới tin phép căn (27/09:
                           # file sạch 0,87–1,0; trạm số M14 thu sóng ngắn 0,735 — nhịp phím đọc nhầm nhiễu)
MIN_COVERAGE = 0.85        # ... và nhịp phím có đối ứng cho ngần này ký tự mô hình (trong khoảng Morse)
SPAN_MARGIN_S = 1.0        # khoảng Morse = từ ký tự nhịp phím Morse đầu tới cuối, nới ngần này giây
KEEP_CONF = 0.9            # chữ thuộc từ mô hình chắc chắn thì không bỏ
BAND = 30                  # nửa bề rộng băng quy hoạch động (ký tự)
SPEECHLIKE_CONF = 0.6      # (mọi SNR) từ kém chắc VÀ không thuần tone = giọng nói/nhạc
SPEECHLIKE_TONAL = 0.4


# ---------------- nhịp phím ----------------
def keying(env: np.ndarray) -> tuple[list[tuple[bool, int, int]], float, float, float]:
    """Bật/tắt từ đường bao (khung FRAME_RATE), ngưỡng Schmitt giữa nền và mức tone.
    Trả (các đoạn (bật?, khung đầu, số khung), dit giây, mức nền, mức tone)."""
    lo, hi = float(np.percentile(env, 20)), float(np.percentile(env, 97))
    on_t, off_t = lo + 0.5 * (hi - lo), lo + 0.35 * (hi - lo)
    state, out = False, np.zeros(len(env), dtype=bool)
    for i, v in enumerate(env):
        state = v > on_t if not state else v > off_t
        out[i] = state
    runs: list[tuple[bool, int, int]] = []
    i = 0
    while i < len(out):
        j = i
        while j < len(out) and out[j] == out[i]:
            j += 1
        runs.append((bool(out[i]), i, j - i))
        i = j
    ons = np.array([n for v, _, n in runs if v], dtype=float) / FRAME_RATE
    offs = np.array([n for v, _, n in runs[1:-1] if not v], dtype=float) / FRAME_RATE
    ons, offs = ons[ons > 0.02], offs[offs > 0.02]

    def shortest(v: np.ndarray) -> float:
        s = np.sort(v)
        base = s[len(s) // 20]
        return float(np.median(s[s <= 1.8 * base]))

    unit = shortest(offs) if len(offs) >= 4 else shortest(ons) if len(ons) >= 2 else 0.0
    return runs, unit, lo, hi


def two_clusters(log_gaps: np.ndarray) -> float | None:
    """Ngưỡng (log) tách khoảng lặng thành "giữa chữ" / "giữa từ" nếu có hai cụm thật. Timing chuẩn và
    Farnsworth có hai cụm tỉ lệ ~7:3 (Farnsworth 5 WPM: 23 và 55 dit); bài học đánh từng chữ số với
    khoảng lặng ngẫu nhiên thì không (30/49, 40/59 dit, dải 23–59: tỉ lệ < 1,7)."""
    x = np.sort(log_gaps)
    n = len(x)
    if n < 4:
        return None
    best, k_best = np.inf, 0
    for k in range(1, n):
        cost = x[:k].var() * k + x[k:].var() * (n - k)
        if cost < best:
            best, k_best = cost, k
    lo, hi = x[:k_best], x[k_best:]
    # cụm trên được phép chỉ có MỘT khoảng: bản tin hai từ Farnsworth (`TNX FER`) có đúng một khoảng giữa từ
    if len(lo) < 2 or not len(hi) or np.exp(hi.mean() - lo.mean()) < TWO_CLUSTER_RATIO:
        return None
    return float((lo[-1] + hi[0]) / 2)


def tonality_track(x8: np.ndarray, f0: float, sr: int = 8000, n: int = 512) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(mốc giây, năng lượng dải hẹp f0 ± 16 Hz, tỉ số hẹp / (hẹp + f0 ± 250 Hz)), khung 64 ms bước 32 ms.
    Tone Morse là sin thuần: năng lượng dồn ở dải hẹp; giọng nói/nhạc trải rộng và trôi tần số."""
    hop = n // 2
    if len(x8) < n:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    frames = np.lib.stride_tricks.sliding_window_view(np.asarray(x8, dtype=np.float32), n)[::hop]
    P = np.abs(np.fft.rfft(frames * np.hanning(n).astype(np.float32), axis=1)) ** 2
    freqs = np.fft.rfftfreq(n, 1 / sr)
    narrow = np.abs(freqs - f0) <= 16
    wide = (np.abs(freqs - f0) <= 250) & ~narrow
    pn, pw = P[:, narrow].sum(axis=1), P[:, wide].sum(axis=1)
    t = (np.arange(len(frames)) * hop + n / 2) / sr
    return t, pn, pn / (pn + pw + 1e-12)


@dataclass(frozen=True)
class KeyedChar:
    pattern: str | None          # None: có phần tử không rõ chấm/gạch
    start_s: float
    end_s: float
    tonal: float                 # độ thuần tone trung vị trong ký tự
    gap_after: float             # khoảng lặng sau ký tự (dit); inf với ký tự cuối
    clean_gap: bool              # khoảng lặng sau là lặng thật (không phải đáy fading)
    level: float = 0.0           # đỉnh đường bao trong ký tự
    crisp: bool = False          # mọi phần tử SẮC NÉT (chấm 0,7–1,4 dit, gạch 2,5–3,7 dit)


@dataclass
class Keyed:
    chars: list[KeyedChar]
    breaks: set[int]             # chắc chắn có dấu cách sau ký tự i
    joins: set[int]              # chắc chắn KHÔNG có dấu cách sau ký tự i
    unit: float
    stable: bool = False         # biên độ các ký tự Morse ổn định (không fading): tin được nhịp phím
    precise: bool = False        # nhịp như máy (chấm, gạch tụ chặt): nhịp phím được SỬA/CHÈN ký tự
    track: tuple = ()            # (mốc, năng lượng dải hẹp, độ thuần tone) — xem tonality_track

    def toned_at(self, t: float) -> bool:
        """Ngay sau mốc `t` có tone thuần (kể cả đáy fading ~0 dB), không phải giọng nói/nhạc/im lặng."""
        if not self.track:
            return True
        tt, pn, ratio = self.track
        sel = (tt >= t - 0.1) & (tt <= t + 0.4)
        if not sel.any():
            return False
        sel &= pn >= 0.25 * pn[sel].max()
        return bool(np.median(ratio[sel]) >= NON_MORSE_TONAL)


def read_keying(x8: np.ndarray, env: np.ndarray, f0: float) -> Keyed:
    """Đọc bản tin từ nhịp phím. Dấu cách chắc chắn:
    - khoảng lặng dài, lặng thật (>= LONG_GAP_UNITS dit và >= LONG_GAP_S s), trừ cụm dưới của Farnsworth;
    - nhịp gõ máy (hai cụm tách bạch): cụm trên là dấu cách, cụm dưới thì không;
    - một cụm lặng dài LỆCH nhau (bài học): khoảng lặng dài là dấu cách; một cụm đều là nhập nhằng.
    Gõ tay (khoảng 4–6 dit nhập nhằng) không có dấu cách "chắc chắn" nào ngoài khoảng lặng dài."""
    runs, unit, lo, hi = keying(env)
    if unit <= 0 or hi <= lo:
        return Keyed([], set(), set(), 0.0)
    quiet = lo + QUIET * (hi - lo)
    raw = [(s, s + n) for on, s, n in runs if on and n / FRAME_RATE >= 0.4 * unit]
    if not raw:
        return Keyed([], set(), set(), unit)
    # Rớt tín hiệu giữa một phần tử (khoảng lặng < DROPOUT_UNITS dit — khoảng lặng hợp lệ ngắn nhất là 1
    # dit) là MỘT phần tử: gạch vỡ thành gạch + chấm (`...--.`), số 0 vỡ thành `--..--` (dấu phẩy).
    marks = [raw[0]]
    for s1, e1 in raw[1:]:
        if (s1 - marks[-1][1]) / FRAME_RATE / unit < DROPOUT_UNITS:
            marks[-1] = (marks[-1][0], e1)
        else:
            marks.append((s1, e1))
    groups: list[list[tuple[int, int]]] = [[marks[0]]]
    gaps: list[tuple[float, bool]] = []
    for (_, e0), (s1, e1) in zip(marks, marks[1:], strict=False):
        units = (s1 - e0) / FRAME_RATE / unit
        if units < 2.0:
            groups[-1].append((s1, e1))
            continue
        core = env[e0 + (s1 - e0) // 5:s1 - (s1 - e0) // 5]      # bỏ đuôi tone đang tắt ở hai đầu
        gaps.append((units, not len(core) or float(np.percentile(core, 90)) < quiet, e0, s1))
        groups.append([(s1, e1)])
    t, pn, ratio = tonality_track(x8, f0)
    # lặng THẬT còn phải không thuần tone: đáy fading (T1 qsb 20 dB) thấp dưới ngưỡng nhưng vẫn là tone
    fixed_gaps = []
    for units, quiet_ok, e0, s1 in gaps:
        a, b = e0 / FRAME_RATE + 0.05, s1 / FRAME_RATE - 0.05
        sel = (t >= a) & (t <= b)
        tone_in_gap = bool(sel.any()) and float(np.median(ratio[sel])) >= NON_MORSE_TONAL
        fixed_gaps.append((units, quiet_ok and not tone_in_gap))
    gaps = fixed_gaps
    chars = []
    for k, els in enumerate(groups):
        pat = "".join("." if DIT_UNITS[0] <= (b - a) / FRAME_RATE / unit <= DIT_UNITS[1]
                      else "-" if DAH_UNITS[0] <= (b - a) / FRAME_RATE / unit <= DAH_UNITS[1] else "?"
                      for a, b in els)
        s0, s1 = els[0][0] / FRAME_RATE, els[-1][1] / FRAME_RATE
        sel = (t >= s0 - 0.02) & (t <= s1 + 0.02)
        if sel.any():                           # chỉ khung phím NHẤN (ký tự 35 WPM ngắn hơn khung 64 ms)
            sel &= pn >= 0.25 * pn[sel].max()
        tonal = float(np.median(ratio[sel])) if sel.any() else 0.0
        gap, clean = gaps[k] if k < len(gaps) else (np.inf, False)
        level = float(env[els[0][0]:els[-1][1]].max())
        crisp = all(CRISP_DIT[0] <= (b - a) / FRAME_RATE / unit <= CRISP_DIT[1]
                    or CRISP_DAH[0] <= (b - a) / FRAME_RATE / unit <= CRISP_DAH[1] for a, b in els)
        chars.append(KeyedChar(None if "?" in pat else pat, s0, s1, tonal, gap, clean, level, crisp))
    levels = [c.level for c in chars if c.tonal >= TONAL_MIN and c.pattern is not None]
    if levels:                                  # xung sét trong ký tự: biên độ vọt khỏi mức Morse -> không rõ
        ref = float(np.median(levels))
        chars = [c if LEVEL_RANGE[0] * ref <= c.level <= LEVEL_RANGE[1] * ref else replace(c, pattern=None)
                 for c in chars]
    morse = [c for c in chars if c.tonal >= TONAL_MIN and c.pattern is not None]
    toned = [c for c in chars if c.tonal >= STABLE_TONAL]     # gồm cả ký tự trong đáy fading (0 dB: 0,47)
    stable = precise = False
    if len(morse) >= 3 and len(toned) >= 3:
        lv = np.array([c.level for c in toned])
        stable = float(np.percentile(lv, 90) / max(np.percentile(lv, 10), 1e-9)) <= STABLE_RATIO
        d = np.array([(b - a) / FRAME_RATE / unit for c, els in zip(chars, groups, strict=True)
                      if c in morse for a, b in els])
        dits, dahs = d[d < 2.0], d[d >= 2.0]

        def spread(v: np.ndarray) -> float:     # IQR / trung vị: vài phần tử rớt tín hiệu không kéo lệch
            q1, q2, q3 = np.percentile(v, [25, 50, 75])
            return float((q3 - q1) / q2)

        parts = [v for v in (dits, dahs) if len(v) >= 3]
        precise = bool(parts) and all(spread(v) <= PRECISE_SPREAD for v in parts)
    ok = [(k, c.gap_after) for k, c in enumerate(chars) if c.clean_gap and np.isfinite(c.gap_after)]
    breaks: set[int] = set()
    joins: set[int] = set()
    if ok:
        logs = np.log([g for _, g in ok])
        gs = np.array([g for _, g in ok])
        split = two_clusters(logs)
        if split is not None:                   # hai cụm: cụm trên là giữa từ nếu dài; gõ máy thì quyết hết
            breaks = {k for k, g in ok if g >= LONG_GAP_UNITS and g * unit >= LONG_GAP_S and np.log(g) > split}
            lo_c, hi_c = logs[logs <= split], logs[logs > split]
            if np.exp(hi_c.min() - lo_c.max()) >= MACHINE_SEPARATION:
                breaks |= {k for k, g in ok if np.log(g) > split}
                # chỉ GHÉP khoảng ngắn kiểu timing chuẩn; khoảng giữa chữ Farnsworth (>= 5 dit) để mô hình
                joins = {k for k, g in ok if np.log(g) <= split and g < JOIN_MAX_UNITS}
        elif (len(ok) >= LESSON_MIN_GAPS and gs.min() >= LONG_GAP_UNITS
              and gs.max() / gs.min() > SINGLE_SPREAD and gs.max() / np.median(gs) < LESSON_MAX_OVER_MEDIAN):
            # Bài học đánh từng chữ: nhiều khoảng, MỌI khoảng dài, lệch nhau rõ nhưng không có dạng 7:3 (bài
            # thật: 30/49, 40/59, 23–59 dit) -> mọi khoảng là dấu cách. Một cụm ĐỀU TĂM TẮP thì nhập nhằng
            # thật — cùng âm thanh với một từ Farnsworth (T1: `СПАСИБО` từng bị tách thành `С П А С И Б О`,
            # `TNX FER` thành `T N X F E R`, 27/09) — để mô hình quyết.
            breaks = {k for k, g in ok if g * unit >= LONG_GAP_S}
    return Keyed(chars, breaks, joins, unit, stable, precise, (t, pn, ratio))


# ---------------- đối chiếu ----------------
def _pattern_map(profile) -> dict[str, str]:
    pat_of = dict(profile.letter_to_pattern)
    pat_of.update({name: pat for pat, name in profile.prosigns.items()})
    return pat_of


def _edit_distance(a: str, b: str) -> int:
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[len(b)]


def _isolated(K: list, j: int) -> bool:
    """Ký tự nhịp phím j đứng riêng: lặng dài VÀ sạch ở cả hai bên (đầu/cuối bản tin coi như lặng)."""
    before = K[j - 1] if j > 0 else None
    after = K[j]
    ok_before = before is None or (before.clean_gap and before.gap_after >= LONG_GAP_UNITS)
    ok_after = not np.isfinite(after.gap_after) or (after.clean_gap and after.gap_after >= LONG_GAP_UNITS)
    return ok_before and ok_after


def _opens(K: list, j: int) -> bool:
    """Ký tự nhịp phím j MỞ ĐẦU một đoạn (sau khoảng lặng dài, sạch, hoặc đầu bản tin): chỗ mô hình yếu
    nhất — nó phát ký tự đầu sớm, có khi rơi hẳn vào giọng nói trước đó (`6` đọc thành `E`, 27/09)."""
    return j == 0 or (K[j - 1].clean_gap and K[j - 1].gap_after >= LONG_GAP_UNITS)


def _render(profile, pattern: str) -> str | None:
    if pattern in profile.prosigns:
        return profile.prosigns[pattern]
    if pattern in profile.map:
        return profile.render([pattern])
    return None


def reconcile(words: list, keyed: Keyed, profile) -> list | None:
    """Dựng lại các từ theo đối chiếu từng ký tự (xem đầu module). None nếu không đổi gì hoặc không tin
    được phép căn."""
    K = keyed.chars
    if not words or not K or not keyed.stable:    # fading: nhịp phím trong đáy fading không đáng tin
        return None
    pat_of = _pattern_map(profile)
    kind = []                                   # 2 = Morse rõ, 1 = Morse mờ, 0 = không phải Morse
    for c in K:
        if c.tonal < NON_MORSE_TONAL:
            kind.append(0)
        elif c.tonal < TONAL_MIN:
            kind.append(1)
        elif c.pattern is not None and _render(profile, c.pattern) is not None:
            kind.append(2)
        else:
            kind.append(1)
    D = []                                      # (chữ, mốc, chỉ số từ, độ tin cậy từ)
    for wi, w in enumerate(words):
        chars = list(getattr(w, "chars", None) or [])
        if not chars or "".join(c for c, _ in chars) != w.text:
            return None
        D += [(c, t, wi, w.confidence) for c, t in chars]
    n, m = len(D), len(K)
    starts = np.array([c.start_s for c in K])
    center = np.searchsorted(starts, np.array([t for _, t, _, _ in D]) + 0.05)   # mốc phát sớm -> chữ kế tiếp
    # quy hoạch động có băng: cost[i][j] với j trong [center_i - BAND, center_i + BAND]
    INF = 1e18
    lo_j = np.clip(np.concatenate([[0], center - BAND]), 0, m)
    hi_j = np.clip(np.concatenate([[BAND], center + BAND]), 0, m)
    hi_j[0] = max(hi_j[0], hi_j[1] if n else m)             # ký tự nhịp phím trước chữ đầu: xóa được
    hi_j[n] = m                                             # ... và sau chữ cuối
    lo_j = np.minimum.accumulate(lo_j[::-1])[::-1]          # băng đơn điệu
    hi_j = np.maximum.accumulate(hi_j)
    cost = [dict() for _ in range(n + 1)]
    back = [dict() for _ in range(n + 1)]

    def sub_cost(i: int, j: int) -> float:
        same = pat_of.get(D[i][0]) == K[j].pattern
        return 0.0 if same else (1.0 if kind[j] == 2 else 0.3 if kind[j] == 1 else 0.6)

    def del_cost(j: int) -> float:              # ký tự nhịp phím không có trong mô hình
        return 1.0 if kind[j] == 2 else 0.5 if kind[j] == 1 else 0.2

    def ins_cost(i: int) -> float:              # ký tự mô hình không có nhịp phím
        return 1.0 if D[i][3] >= KEEP_CONF else 0.7

    for j in range(0, int(hi_j[0]) + 1):
        cost[0][j] = sum(del_cost(q) for q in range(j))
        back[0][j] = "K" if j else None
    for i in range(1, n + 1):
        for j in range(int(lo_j[i]), int(hi_j[i]) + 1):
            best, how = INF, None
            if j - 1 in cost[i - 1]:
                v = cost[i - 1][j - 1] + sub_cost(i - 1, j - 1)
                if v < best:
                    best, how = v, "M"
            if j in cost[i - 1]:
                v = cost[i - 1][j] + ins_cost(i - 1)
                if v < best:
                    best, how = v, "D"
            if j - 1 in cost[i]:
                v = cost[i][j - 1] + del_cost(j - 1)
                if v < best:
                    best, how = v, "K"
            if how is not None:
                cost[i][j], back[i][j] = best, how
    if m not in cost[n]:
        return None
    path = []
    i, j = n, m
    while i > 0 or j > 0:
        how = back[i].get(j)
        if how == "M":
            path.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif how == "D":
            path.append((i - 1, None))
            i -= 1
        elif how == "K":
            path.append((None, j - 1))
            j -= 1
        else:
            return None
    path.reverse()
    clear = [j for j in range(m) if kind[j] == 2]
    if len(clear) < 3:
        return None
    # Mức đồng ý chỉ tính trên ký tự TRONG NHÓM: ký tự đứng riêng giữa hai khoảng lặng dài và sạch là chỗ
    # nhịp phím đáng tin nhất (bài học số 0: mô hình đọc 3/14 số 0 thành M/G), không để chúng kéo mức
    # đồng ý xuống; trong nhóm, mức đồng ý thấp = nhịp phím đọc nhầm nhiễu (M14 thu sóng ngắn: 0,735).
    grouped = [j for j in clear if not _isolated(K, j)]
    agree = sum(1 for a, b in path if a is not None and b is not None and b in set(grouped)
                and pat_of.get(D[a][0]) == K[b].pattern)
    if len(grouped) >= 3 and agree < MIN_AGREEMENT * len(grouped):
        return None
    # Độ phủ BÊN TRONG bản tin Morse: fading giấu ký tự dưới ngưỡng phím (T1 qsb 20 dB: 7/15 ký tự) —
    # chữ mô hình "không có xung" ở đó là do nhịp phím thiếu, không phải bịa. Chữ NGOÀI khoảng Morse (giọng
    # nói/nhạc trước và sau bản tin) không tính vào độ phủ và bị bỏ nếu kém chắc.
    morse_k = [c for c, kd in zip(K, kind, strict=True) if kd >= 1]
    if not morse_k:
        return None
    span = (morse_k[0].start_s - SPAN_MARGIN_S, morse_k[-1].end_s + SPAN_MARGIN_S)
    backed = {a for a, b in path if a is not None and b is not None}
    starts_k = np.array([c.start_s for c in morse_k])
    ends_k = np.array([c.end_s for c in morse_k])

    def on_keyed(t: float) -> bool:             # mốc nằm trên (hoặc ngay trước) một ký tự nhịp phím
        return bool(((starts_k - 0.3 <= t) & (t <= ends_k + 0.1)).any())

    # Chữ mô hình không có đối ứng nhịp phím:
    # - chồng lên một ký tự nhịp phím ở mức tone đầy đủ = MẢNH VỠ (rớt tín hiệu đọc thành chữ thừa:
    #   khóa UA3AFO `333Т3АТ33С` chỉ có 7 số 3) -> rác;
    # - có tone nhưng KHÔNG có ký tự nhịp phím nào = chữ bị fading che dưới ngưỡng phím -> nhịp phím
    #   thiếu (T1 qsb 20 dB: 7/15 ký tự); quá nhiều thì không đối chiếu;
    # - không có tone (giọng nói, nhạc, im lặng) -> rác.
    hidden = {a for a in range(n) if a not in backed and not on_keyed(D[a][1]) and keyed.toned_at(D[a][1])}
    inside = [a for a in range(n) if span[0] <= D[a][1] <= span[1] and (a in backed or a in hidden)]
    if inside and sum(1 for a in inside if a in backed) < MIN_COVERAGE * len(inside):
        return None
    out = []                                    # (chữ, mốc, chỉ số nhịp phím|None, chỉ số từ|None, tin cậy)
    for a, b in path:
        if a is not None and b is not None:
            ch, t, wi, conf = D[a]
            if kind[b] == 2:
                same = pat_of.get(ch) == K[b].pattern
                # Chỉ sửa khi lệch ĐÚNG MỘT phần tử (Ч `---.` / 0 `-----`, 9 / 0): nhầm một chấm-gạch là lỗi
                # nhịp phím sửa được; lệch nhiều là nhịp phím đọc nhầm nhiễu (trạm số M14 thu sóng ngắn:
                # `:` bị "sửa" thành `T`). Gõ tay: đọc chấm/gạch theo nhịp kém mô hình, giữ chữ.
                known = pat_of.get(ch)
                near = known is not None and _edit_distance(known, K[b].pattern) <= 1
                # lệch 1 phần tử: nhịp phím rõ là đủ; lệch nhiều (chỉ ở ký tự đứng riêng / mở đầu đoạn, hoặc
                # mô hình ra ký hiệu không có mẫu) thì phải SẮC NÉT — bài học Nga (T4): dấu chấm cuối bài
                # `.-.-.-` bị "sửa" thành `<SK>` `...-.-` vì một gạch cuối bản tin đọc thành chấm.
                far_ok = K[b].crisp and (_isolated(K, b) or _opens(K, b) or known is None)
                fix = not same and keyed.precise and (near or far_ok)
                out.append((_render(profile, K[b].pattern) if fix else ch, K[b].start_s, b, wi, conf))
            elif kind[b] == 1 or conf >= KEEP_CONF:
                out.append((ch, K[b].start_s, b, wi, conf))
        elif a is not None:
            ch, t, wi, conf = D[a]
            outside = not span[0] <= t <= span[1]
            fragment = on_keyed(t)                  # chồng lên ký tự nhịp phím: mảnh vỡ (chỉ tin khi nhịp máy;
            silent = not fragment and a not in hidden   # gõ tay thì nhịp phím hay gộp hai ký tự làm một)
            garbage = outside or silent or (fragment and keyed.precise)
            if conf >= KEEP_CONF or not garbage:
                out.append((ch, t, None, wi, conf))
        elif kind[b] == 2 and keyed.precise and _isolated(K, b):
            # chèn ký tự mô hình bỏ sót CHỈ khi nó đứng riêng giữa hai khoảng lặng dài và sạch (bài học);
            # trong nhóm bình thường, ký tự nhịp phím mà mô hình không đọc thường là nhiễu/đài khác (M14)
            out.append((_render(profile, K[b].pattern), K[b].start_s, b, None, 0.9))
    if not out:
        return []
    groups: list[list[tuple]] = [[out[0]]]
    for p, q in zip(out, out[1:], strict=False):
        ka, kb, wa, wb = p[2], q[2], p[3], q[3]
        if ka is not None and kb is not None:
            if kb > ka + 1 and K[kb].start_s - K[ka].end_s >= SKIPPED_BREAK_S:
                new = True                      # giữa hai chữ có đoạn dài bị bỏ (giọng nói...); nhiễu lụp bụp
                                                # ngắn giữa một từ (SAQ gõ tay) thì không
            elif ka in keyed.breaks and (keyed.precise or K[ka].gap_after >= HAND_LONG_GAP_UNITS):
                new = True                      # gõ tay: người gõ hay ngừng giữa từ (SAQ `N OVEMBER`)
            elif ka in keyed.joins:
                new = False
            elif wa is not None and wb is not None:
                new = wa != wb
            else:
                new = K[ka].gap_after >= SINGLE_WORD_UNITS
        else:
            new = wa is None or wb is None or wa != wb
        if new:
            groups.append([q])
        else:
            groups[-1].append(q)
    template = words[0]
    new_words = []
    for g in groups:
        text = "".join(c for c, *_ in g)
        src = [words[wi] for *_, wi, _ in g if wi is not None]
        base = src[0] if src else template
        end_s = K[g[-1][2]].end_s if g[-1][2] is not None else (src[-1].end_s if src else g[-1][1])
        conf = float(min(c for *_, c in g))
        new_words.append(replace(base, text=text, start_s=g[0][1], end_s=end_s, confidence=conf,
                                 chars=[(c, t) for c, t, *_ in g]))
    if [w.text for w in new_words] == [w.text for w in words]:
        return None
    return new_words


# ---------------- mọi SNR: giọng nói rõ ràng ----------------
def speechlike(words: list, x8: np.ndarray, f0: float) -> list[bool]:
    """Từ kém chắc (< SPEECHLIKE_CONF) VÀ không thuần tone (< SPEECHLIKE_TONAL) = giọng nói/nhạc mô hình
    đọc thành chữ. An toàn ở mọi SNR: Morse thật đo 0,47 thuần tone ngay cả ở 0 dB (27/09)."""
    weak = [i for i, w in enumerate(words) if w.confidence < SPEECHLIKE_CONF]
    flags = [False] * len(words)
    if not weak:
        return flags
    t, pn, ratio = tonality_track(x8, f0)
    if not len(t):
        return flags
    ref = float(np.percentile(pn, 95))
    for i in weak:
        w = words[i]
        on = (t >= w.start_s - 0.1) & (t <= w.end_s + 0.1) & (pn >= 0.1 * ref)
        tonal = float(np.median(ratio[on])) if on.any() else 0.0
        flags[i] = tonal < SPEECHLIKE_TONAL
    return flags


# ---------------- cả clip: không phải Morse ----------------
NOT_MORSE_MIN_S = 60.0     # chỉ phán cả clip khi đủ dài: bản ghi Morse thật dài vài phút luôn có từ chắc chắn
NOT_MORSE_MAX_CONF = 0.8   # ... không từ nào đạt độ tin cậy này ...
NOT_MORSE_CLEAR = 0.2      # ... và dưới ngần này ký tự nhịp phím là Morse rõ
NOT_MORSE_MIN_S_WEAK = 20.0    # clip >= 20 s mà không từ nào đạt NOT_MORSE_WEAK_CONF (chỉ giọng nói)
NOT_MORSE_WEAK_CONF = 0.6


def clear_fraction(keyed: Keyed, profile) -> float:
    """Tỉ lệ ký tự nhịp phím là Morse rõ (mẫu hợp lệ, thuần tone)."""
    if not keyed.chars:
        return 0.0
    ok = sum(1 for c in keyed.chars if c.tonal >= TONAL_MIN and c.pattern is not None
             and _render(profile, c.pattern) is not None)
    return ok / len(keyed.chars)


def not_morse_clip(words: list, keyed: Keyed, profile, seconds: float) -> bool:
    """Cả clip là nhạc/giọng nói. Đo 27/09: hai bài hát "Азбука Морзе" (Piknik) — độ tin cậy lớn nhất
    0,72–0,75, 3–9 % ký tự nhịp phím là Morse rõ; mọi bản ghi Morse thật (kể cả SAQ gõ tay, T1 0–6 dB)
    có từ >= 0,92, trừ vài clip fading sâu NGẮN (<= 12 s) — nên chỉ phán với clip >= 60 s."""
    if not words:
        return False
    top = max(w.confidence for w in words)
    if not ((seconds >= NOT_MORSE_MIN_S and top < NOT_MORSE_MAX_CONF)
            or (seconds >= NOT_MORSE_MIN_S_WEAK and top < NOT_MORSE_WEAK_CONF)):
        return False
    return clear_fraction(keyed, profile) < NOT_MORSE_CLEAR
