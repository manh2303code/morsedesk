"""Bộ giải mã DSP thích nghi: thử nhiều cặp (ngưỡng, độ dài dit), chọn cặp khớp timing nhất.

Dùng làm baseline đo lường và fallback khi mô hình nơ-ron kém tin cậy. Khi timing mơ hồ
(bản tin ngắn không tương phản dot/dash), một prior tốc độ nhẹ quanh SPEED_PRIOR_WPM
phá thế hòa giữa các giả thuyết (ngưỡng, độ dài dit) có timing_cost gần bằng nhau.

Tách mark/space dùng **trễ Schmitt** rồi **xóa run ngắn hơn MIN_RUN_RATIO lần dit**. Với một
ngưỡng cứng, mỗi lần envelope rung qua ngưỡng lại sinh thêm một run, và bộ giải mã sinh một ký
tự cho MỌI run nên chèn thừa tràn lan: đo trên 152 clip `en` của T1 là 306,84 % CER với ngưỡng
cứng, 72,20 % khi thêm trễ Schmitt, **26,44 %** khi thêm cả xóa run ngắn. Cơ chế trễ lấy từ
HamFist (`cw_decoder/cw_dsp.cpp`, MIT); xem `docs/research/06-hamfist.md`.

Đã thử và bỏ: quét song song cả mask ngưỡng cứng lẫn mask Schmitt rồi để chi phí timing tự
chọn. Nghe hợp lý nhưng làm xấu đi (33,62 % so với 26,44 %), vì trên clip nhiễu mask cứng sinh
những giả thuyết có chi phí thấp giả tạo.

Giới hạn đã biết: bản tin ngắn không có tương phản chấm/gạch (HI, SI, TTT) có thể bị đọc thành
alias 3× khi timing của hai cách đọc trùng nhau. "TTT" ở 36 WPM khớp hệt "S" ở 12 WPM, và "TTT"
ở 60 WPM khớp hệt "S" ở 20 WPM: chi phí timing bằng nhau tới bốn chữ số, chỉ còn prior tốc độ
phá thế hòa và prior lại ưu ái giả thuyết chậm. Đây là mơ hồ thật của tín hiệu, không phải lỗi
cài đặt; muốn giải đúng thì cần manh mối ngoài timing (mô hình ngôn ngữ), tức engine ONNX.
Ngược lại, các ca 40 WPM (SI), 48 WPM (HI) và 60 WPM (HI, SI) từng hỏng vì nhiễu lượng tử nay
đã đúng nhờ trễ Schmitt — test tương ứng để `xfail(strict=False)` nên chúng hiện báo XPASS.

Engine ONNX là bộ giải mã chính; baseline vừa là đối chứng, vừa là thứ GUI hiện ra khi độ tin
cậy của model thấp, vừa là đường chính khi tín hiệu sạch hơn dải huấn luyện của model (xem
`morsedesk/dsp/selection.py`).

Đã thử và bỏ: nội suy ranh giới dưới khung. Lập luận nghe rất chắc — ở 40 WPM một dit chỉ dài
6 khung nên sai số nửa khung là 8 % — nhưng đo thì T1 xấu đi 5,6 điểm (40,73 % so với 35,12 %)
và **cả mười bản ghi thật của T2 không đổi một chữ số nào**. Lý do: bộ giải mã so TỈ LỆ giữa
dấu và khoảng lặng, mà lượng tử hóa dời cả hai cùng chiều nên phần lớn sai số tự triệt tiêu;
đổi lại, trên tín hiệu nhiễu thì điểm cắt ngưỡng dao động theo nhiễu và biên nội suy kém ổn
định hơn biên làm tròn. Chi tiết: docs/research/02-baseline-numbers.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.constants import FRAME_RATE, SAMPLE_RATE
from morsedesk.dsp.frontend import mix_envelope
from morsedesk.dsp.tone import ToneEstimate, estimate_tone
from morsedesk.model.vocab import SPACE

THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55, 0.65)
# Trễ Schmitt: bật khi vượt ngưỡng, chỉ tắt khi rơi dưới HYSTERESIS_RATIO lần ngưỡng. Lấy từ
# HamFist (`cw_decoder/cw_dsp.cpp`, MIT), nơi tỉ lệ là 0,7; đo trên 152 clip `en` của T1 thì 0,67
# cho kết quả tốt nhất trong dải 0,55-0,80.
HYSTERESIS_RATIO = 0.67
# Run ngắn hơn ngần này lần dit bị gộp vào hàng xóm. Bộ giải mã sinh một ký tự cho MỌI run nên
# vài chục gai nhiễu một khung đủ đẩy CER vượt 100 % vì chèn thừa. Quét trên 152 clip `en` của T1:
# 0,0 -> 72,20 %; 0,4 -> 29,72; 0,6 -> 26,44; 0,8 -> 34,64; 0,9 -> 34,93. Phải nhỏ hơn 1 để không
# bao giờ nuốt khoảng lặng 1 dit giữa hai dấu trong cùng một chữ.
MIN_RUN_RATIO = 0.6
IDEAL_ON = np.array([1.0, 3.0])
IDEAL_OFF = np.array([1.0, 3.0, 7.0])

SPEED_PRIOR_WPM = 20.0       # tốc độ tiên nghiệm khi timing mơ hồ
# Đo thực nghiệm: cửa sổ khả thi để "HI"/"SI" đúng ở 5-8 WPM (wpm giả thuyết đúng cách xa 20)
# và "SI" đúng ở 50 WPM (giả thuyết sai có cost thô thấp hơn chút) là khoảng [0.0015, 0.0025];
# 0.01 (giá trị cũ) đủ lớn để prior lấn át chênh lệch timing_cost thật ở tốc độ thấp.
SPEED_PRIOR_WEIGHT = 0.002   # nhỏ so với chi phí timing, chỉ phá thế hòa

OFF_LONG_CAP_UNITS = 12.0   # khoảng tắt dài hơn 12 dit coi như "12": chỉ phạt nhẹ, không loại giả thuyết


@dataclass
class Symbol:
    token: str
    start_frame: int
    end_frame: int


@dataclass
class BaselineResult:
    symbols: list[Symbol]
    unit_frames: float
    threshold: float
    cost: float

    @property
    def tokens(self) -> list[str]:
        return [s.token for s in self.symbols]

    @property
    def wpm(self) -> float:
        return 1.2 * FRAME_RATE / self.unit_frames if self.unit_frames > 0 else 0.0


def run_lengths(mask: np.ndarray) -> list[tuple[bool, int, int]]:
    """Các đoạn liên tiếp (is_on, start, end)."""
    if len(mask) == 0:
        return []
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(mask)]])
    return [(bool(mask[s]), int(s), int(e)) for s, e in zip(starts, ends, strict=True)]


def schmitt_mask(env: np.ndarray, threshold: float, ratio: float = HYSTERESIS_RATIO) -> np.ndarray:
    """Mask bật/tắt với trễ Schmitt: bật khi vượt `threshold`, tắt khi rơi xuống `ratio*threshold`.

    Một ngưỡng cứng cắt mỗi lần envelope rung qua ngưỡng thành một run mới, và mỗi run thừa là
    một ký tự thừa.

    Viết không vòng lặp: trạng thái tại khung i chỉ phụ thuộc sự kiện gần nhất trước đó — nếu
    lần vượt ngưỡng cao gần nhất mới hơn lần rơi xuống ngưỡng thấp gần nhất thì đang bật. Hai
    "lần gần nhất" đó chính là `np.maximum.accumulate` trên chỉ số. Đáng làm vì bộ DSP quét sáu
    ngưỡng trên clip dài tới 20 phút, tức 240 000 khung mỗi lượt.
    """
    n = len(env)
    if n == 0:
        return np.zeros(0, dtype=bool)
    v = np.asarray(env, dtype=np.float64)
    hi = float(threshold)
    lo = hi * float(ratio)
    idx = np.arange(n)
    last_hi = np.maximum.accumulate(np.where(v > hi, idx, -1))
    last_lo = np.maximum.accumulate(np.where(v <= lo, idx, -1))
    return last_hi > last_lo        # chưa có sự kiện nào: cả hai bằng -1 -> tắt, đúng trạng thái đầu


def despeckle(mask: np.ndarray, min_len: int) -> np.ndarray:
    """Xóa gai bật ngắn hơn `min_len`, rồi lấp khe tắt ngắn hơn `min_len`.

    Hai bước tuần tự chứ không lật mọi run ngắn cùng lúc: lật đồng thời làm hai run ngắn kề nhau
    đổi chỗ cho nhau mỗi vòng và không bao giờ ổn định. Thứ tự này cũng đúng về mặt vật lý — bỏ
    gai nhiễu trước, rồi mới nối lại dấu bị nhiễu cắt vỡ.

    Khe tắt hợp lệ ngắn nhất là 1 dit, còn `min_len` đặt theo `MIN_RUN_RATIO` (0,4 dit), nên bước
    lấp khe không nuốt mất khoảng lặng thật. Run duy nhất phủ toàn mask không bao giờ bị xóa.
    """
    if min_len <= 1 or len(mask) == 0:
        return mask
    m = np.asarray(mask, dtype=bool).copy()
    for polarity in (True, False):
        for on, s, e in run_lengths(m):
            if on is polarity and e - s < min_len and not (s == 0 and e == len(m)):
                m[s:e] = not polarity
    return m


def _two_means_log(values: np.ndarray) -> tuple[float, float]:
    """2-means trên log; trả (tâm thấp, tâm cao) theo thang tuyến tính."""
    logs = np.log(values.astype(float))
    c_lo, c_hi = float(logs.min()), float(logs.max())
    for _ in range(20):
        assign = np.abs(logs - c_lo) <= np.abs(logs - c_hi)
        if assign.all() or (~assign).all():
            break
        c_lo, c_hi = float(logs[assign].mean()), float(logs[~assign].mean())
    return float(np.exp(c_lo)), float(np.exp(c_hi))


def candidate_units(on_lengths: np.ndarray) -> list[float]:
    """Ứng viên độ dài dit (khung) từ các đoạn bật."""
    cands: set[float] = set()
    if len(on_lengths) >= 2:
        lo, hi = _two_means_log(on_lengths)
        cands.update([lo, hi / 3.0])
    med = float(np.median(on_lengths))
    cands.update([med, med / 3.0])
    return sorted(c for c in cands if c >= 1.0)


def timing_cost(runs: list[tuple[bool, int, int]], unit: float) -> float:
    """Trung bình bình phương log-tỉ lệ so với mốc lý tưởng gần nhất (bật: 1/3; tắt <=7u: 1/3/7);
    đoạn tắt dài hơn 7u dùng kẹp mềm (so với OFF_LONG_CAP_UNITS) thay vì kẹp cứng về 7, để vẫn phạt
    khoảng tắt quá dài mà không loại hẳn giả thuyết; bỏ đoạn tắt đầu/cuối."""
    inner = list(runs)
    if inner and not inner[0][0]:
        inner = inner[1:]
    if inner and not inner[-1][0]:
        inner = inner[:-1]
    costs = []
    for on, s, e in inner:
        r = (e - s) / unit
        if on:
            costs.append(float(np.min(np.abs(np.log(r) - np.log(IDEAL_ON))) ** 2))
        elif r <= 7.0:
            costs.append(float(np.min(np.abs(np.log(r) - np.log(IDEAL_OFF))) ** 2))
        else:
            costs.append(float(np.log(min(r, OFF_LONG_CAP_UNITS) / 7.0) ** 2))
    return float(np.mean(costs)) if costs else float("inf")


def split_gap_threshold(gap_units: np.ndarray) -> float:
    """Ngưỡng (đơn vị dit) tách khoảng giữa chữ và giữa từ; thích nghi Farnsworth."""
    if len(gap_units) == 0:
        return 5.0
    if len(gap_units) < 2 or gap_units.max() / gap_units.min() < 1.8:
        return float(gap_units.max()) * 1.5
    lo, hi = _two_means_log(gap_units)
    return float(np.sqrt(lo * hi))


def runs_to_symbols(runs: list[tuple[bool, float, float]], unit: float) -> list[Symbol]:
    """Ranh giới có thể là số thực sau khi nội suy dưới khung; `Symbol` vẫn đếm theo khung nên
    làm tròn ở đây, còn mọi phép so tỉ lệ bên trong dùng giá trị thực."""
    gaps = np.array([(e - s) / unit for on, s, e in runs[1:-1] if not on and (e - s) / unit >= 2.0])
    word_thr = split_gap_threshold(gaps)
    symbols: list[Symbol] = []
    cur = ""
    cur_start = 0.0

    def flush(end: float) -> None:
        nonlocal cur
        if cur:
            symbols.append(Symbol(cur, int(round(cur_start)), int(round(end))))
            cur = ""

    for on, s, e in runs:
        r = (e - s) / unit
        if on:
            if not cur:
                cur_start = s
            cur += "." if r < 2.0 else "-"
            continue
        if r < 2.0:
            continue
        flush(s)
        if r >= word_thr and symbols and symbols[-1].token != SPACE:
            symbols.append(Symbol(SPACE, int(round(s)), int(round(e))))
    flush(runs[-1][2] if runs else 0)
    while symbols and symbols[-1].token == SPACE:
        symbols.pop()
    return symbols


class BaselineDecoder:
    def __init__(self, thresholds: tuple[float, ...] = THRESHOLDS) -> None:
        self.thresholds = thresholds

    def decode_envelope(self, env: np.ndarray) -> BaselineResult:
        if len(env) < 3:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        env = env / (np.percentile(env, 98) + 1e-9)
        env = np.convolve(env, np.ones(3) / 3.0, mode="same")
        best: tuple[float, float, float, float, list[tuple[bool, int, int]]] | None = None
        for thr in self.thresholds:
            mask = schmitt_mask(env, thr)
            raw_runs = run_lengths(mask)
            raw_on = np.array([e - s for on, s, e in raw_runs if on])
            if len(raw_on) < 2:
                continue
            # Ngưỡng xóa run ngắn suy từ CHÍNH ứng viên dit đang xét, không từ thống kê chung:
            # một giả thuyết dit sai sẽ xóa nhầm (hoặc bỏ sót) và tự lộ ra ở timing_cost, nên
            # vòng quét tự loại nó. Dùng trung vị các dấu thì bản tin nhiều gạch có trung vị bằng
            # 3 dit và ngưỡng nuốt luôn khoảng lặng 1 dit trong chữ ("CQ CQ DE R1ABC K" đọc thành
            # "FFE EDII"); dùng tâm cụm thấp thì bản tin toàn gạch vẫn hỏng ("TTT" thành "S").
            for unit in candidate_units(raw_on):
                cleaned = despeckle(mask, max(2, int(MIN_RUN_RATIO * unit)))
                runs = run_lengths(cleaned)
                on_lengths = np.array([e - s for on, s, e in runs if on])
                if len(on_lengths) < 2:
                    continue
                # Xóa run ngắn đổi thống kê độ dài, nên xét lại cả ứng viên dit của mask đã sạch.
                for u in (unit, *candidate_units(on_lengths)):
                    cost = timing_cost(runs, u)
                    wpm = 1.2 * FRAME_RATE / u
                    total = cost + SPEED_PRIOR_WEIGHT * float(np.log(wpm / SPEED_PRIOR_WPM)) ** 2
                    if best is None or total < best[0]:
                        best = (total, cost, thr, u, runs)
        if best is None:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        _total, cost, thr, unit, runs = best
        return BaselineResult(runs_to_symbols(runs, unit), unit, thr, cost)

    def decode_audio(
        self, x: np.ndarray, sample_rate: int = SAMPLE_RATE
    ) -> tuple[BaselineResult, ToneEstimate]:
        est = estimate_tone(x, sample_rate)
        if not est.has_signal or est.f0_hz is None:
            return BaselineResult([], 0.0, 0.0, float("inf")), est
        env = mix_envelope(x, est.f0_hz, sample_rate)
        return self.decode_envelope(env), est
