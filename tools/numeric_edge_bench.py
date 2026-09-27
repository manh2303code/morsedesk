"""Bộ test CHUẨN cho số: mọi tình huống biên, đáp án tuyệt đối (27/09).

Người dùng 27/09: "thiết kế thuật toán tối ưu tuyệt đối, không sai số cho việc dịch số, tạo bộ test chuẩn
để đánh giá mọi edgecase". Mỗi ca sinh xác định (seed theo mã ca), có đáp án chính xác, và thuộc một
trong ba mức:

- `must`      — âm thanh KHÔNG nhập nhằng (SNR >= 12 dB, gõ máy hoặc tay nhẹ, mọi định dạng): phải đúng
                100 %, từng chữ số VÀ từng dấu cách. Đây là cổng chất lượng.
- `hard`      — nhiễu nặng, fading, gõ tay lệch nhiều: làm tốt nhất có thể, báo số.
- `ambiguous` — chính âm thanh đã nhập nhằng (khoảng lặng giữa chữ bị kéo dài bằng khoảng giữa từ):
                không bộ giải mã nào có đáp án đúng duy nhất; chỉ báo cáo.

Ca có `expect_empty` (chỉ nhiễu / nhạc / giọng nói) đạt khi KHÔNG có chữ số nào được đọc ra.

    uv run python tools/numeric_edge_bench.py [--configs app,auto,live] [--only B3,O] [--out runs/edge]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import zlib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from numeric_eval import score  # noqa: E402

from morsedesk.api import Decoder, Encoder  # noqa: E402
from morsedesk.constants import SAMPLE_RATE  # noqa: E402
from morsedesk.data.channel import apply_channel, clean  # noqa: E402
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine  # noqa: E402
from morsedesk.data.synth import rescale_elements  # noqa: E402
from morsedesk.encode.synth import elements_to_audio, tone_power  # noqa: E402
from morsedesk.encode.timing import (  # noqa: E402
    Element,
    TimingParams,
    gap_seconds,
    tokens_to_elements,
    total_seconds,
)
from morsedesk.lm.profile import load_profile  # noqa: E402
from morsedesk.parallel import default_workers, map_parallel  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "testdata" / "private" / "t6"
DIGITS = "0123456789"


@dataclass(frozen=True)
class Case:
    id: str
    cat: str
    tier: str                       # must | hard | ambiguous
    ref: str                        # đáp án mong đợi
    sent: str | None = None         # văn bản ĐƯỢC ĐÁNH nếu khác đáp án (số viết tắt: 153T4 -> 15304)
    profile: str = "en"
    wpm: float = 20.0
    farnsworth: float | None = None
    word_gap_units: float | None = None     # ghi đè khoảng giữa từ (dit), vd. bài học 30 dit
    word_gaps: tuple = ()           # các khoảng giữa từ (dit) lần lượt xoay vòng — bài học thật lệch nhau
    keyer: str = "machine"          # machine | jitter | bug | drift_up | drift_down | handpause
    tone: float = 700.0
    snr: float = 25.0
    channel: dict = field(default_factory=dict)     # qsb_depth_db, qrm_kind, qrn_rate_per_s, mp3_kbps...
    container: str = "array"        # array | wav44_stereo | wav11k | mp3_vbr_noxing | ogg | flac
    surround: str | None = None     # silence | noise | speech | music | real_speech | real_music
    overlay: str | None = None      # nhạc nền dưới Morse: music
    expect_empty: bool = False
    note: str = ""


# ---------------- văn bản ----------------
def _rng(key: str) -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(key.encode()))


def _groups(key: str, n: int, size: int) -> str:
    r = _rng(key)
    return " ".join("".join(DIGITS[int(r.integers(10))] for _ in range(size)) for _ in range(n))


def cases() -> list[Case]:
    C: list[Case] = []
    add = C.append
    # A. nhận dạng từng chữ số
    for d in DIGITS:
        add(Case(f"A1-{d}", "A1 một chữ số đứng một mình", "must", d))
        add(Case(f"A2-{d}", "A2 năm chữ số giống nhau", "must", d * 5 + " " + d * 5))
    add(Case("A3-asc", "A3 dãy 0-9", "must", "0123456789 9876543210"))
    r = _rng("A3-bigram")
    pairs = [a + b for a in DIGITS for b in DIGITS]
    r.shuffle(pairs)
    flat = "".join(pairs)
    for k in range(4):
        chunk = flat[k * 50:(k + 1) * 50]
        add(Case(f"A3-bi{k}", "A3 mọi cặp chữ số", "must", " ".join(chunk[i:i + 5] for i in range(0, 50, 5))))
    # B. cấu trúc nhóm
    for size in range(1, 11):
        # nhóm 1 chữ số cách đều 7 dit = CÙNG âm thanh với một từ 6 chữ số đánh Farnsworth: nhập nhằng
        add(Case(f"B1-len{size}", "B1 nhóm độ dài 1-10", "ambiguous" if size == 1 else "must",
                 _groups(f"B1-{size}", 6, size)))
    for n in (20, 30, 50):
        add(Case(f"B2-run{n}", "B2 dãy số liền dài", "must", _groups(f"B2-{n}", 1, n)))
        add(Case(f"B2-run{n}-hand", "B2 dãy số liền dài, gõ tay nhẹ", "must", _groups(f"B2h-{n}", 1, n),
                 keyer="jitter"))
    # lặng ĐỀU tăm tắp giữa các chữ rời = cùng âm thanh với một từ Farnsworth: nhập nhằng
    for gap in (15, 30, 50):
        add(Case(f"B3-iso{gap}", "B3 chữ số rời, lặng dài ĐỀU", "ambiguous",
                 " ".join(_groups(f"B3-{gap}", 12, 1).split()), wpm=15, word_gap_units=gap))
    # lặng LỆCH nhau như bài học thật (30/49, 40/59, dải 23–59 dit): phải đúng
    for name, gaps in (("3049", [30, 49]), ("4059", [40, 59]), ("rand", list(range(23, 60, 4)))):
        add(Case(f"B3-lesson{name}", "B3 bài học: chữ số rời, lặng dài lệch nhau", "must",
                 " ".join(_groups(f"B3l-{name}", 14, 1).split()), wpm=15, word_gaps=tuple(gaps)))
    add(Case("B3-lesson-same7", "B3 bài học: chữ số rời, lặng dài lệch nhau", "must", " ".join(["7"] * 14),
             wpm=15, word_gaps=(30, 49)))
    add(Case("B3-lesson-zero", "B3 bài học: chữ số rời, lặng dài lệch nhau", "must", " ".join(["0"] * 14),
             wpm=15, word_gaps=(40, 59)))
    g = _groups("B4", 6, 5).split()
    add(Case("B4-station", "B4 trạm số: mào đầu + nhóm đánh hai lần", "must",
             "379 379 30 30 = = " + " ".join(x for x in g for _ in range(2)) + " = = 379 379 000"))
    add(Case("B4-vvv", "B4 trạm số: mào đầu VVV", "must", "VVV = " + _groups("B4v", 10, 5) + " <SK>"))
    add(Case("B5-tight5", "B5 khoảng giữa nhóm 5 dit", "hard", _groups("B5", 10, 5), word_gap_units=5))
    add(Case("B5-wide10", "B5 khoảng giữa nhóm 10 dit", "must", _groups("B5w", 10, 5), word_gap_units=10))
    # C. số viết tắt
    for k in range(3):
        refs = _groups(f"C1-{k}", 10, 5).split()
        add(Case(f"C1-cut0-{k}", "C1 trạm số 0 = T", "must", " ".join(refs),
                 sent=" ".join(x.replace("0", "T") for x in refs)))
    cut = {"0": "T", "9": "N", "1": "A", "2": "U", "3": "V", "5": "E", "7": "B", "8": "D"}
    refs = _groups("C2", 10, 5).split()
    add(Case("C2-contest", "C2 bộ viết tắt đầy đủ trong nhóm 5", "must", " ".join(refs),
             sent=" ".join("".join(cut.get(c, c) for c in x) for x in refs)))
    # D. chữ + số
    add(Case("D-calls", "D hô hiệu có số", "must", "UA9ABC DE R2DX UN7XY 3Z9X DL1ABC 4X4ZZ K1ABC"))
    add(Case("D-locator", "D lưới locator", "must", "KO85 LO88AA MN83 JO01EX KN29"))
    add(Case("D-codegrp", "D nhóm mã chữ-số", "must", "A3F9Q 7K2LM Q0Z4R 91XZ8 T5T5T"))
    add(Case("D-suffix", "D số có chữ đuôi", "must", "1234Z 0930Z 14MHZ 599 5NN 73 88"))
    # E. dấu câu giữa số
    add(Case("E-punct1", "E dấu câu giữa số", "must", "12.5 12,5 12/3 12-3 12:45"))
    add(Case("E-punct2", "E dấu câu giữa số", "must", "(123) 1+2=3 12?3 45' 7/8/9"))
    add(Case("E-punct3", "E dấu câu giữa số", "must", "3.14159 2.71828 1.41421 0.57721"))
    add(Case("E-punct4", "E dấu câu giữa số", "must", "1-2-3-4-5 6/7/8/9/0 11:22:33"))
    # F. định dạng
    add(Case("F-phone", "F số điện thoại", "must", "+7 727 123-45-67 +84 912 345 678"))
    add(Case("F-coord", "F tọa độ", "must", "43.2567N/076.9286E 21.0285N/105.8542E"))
    add(Case("F-date", "F ngày giờ", "must", "27.09.2026 14:35Z 2026-09-27 0735Z"))
    add(Case("F-freq", "F tần số / số tiền", "must", "14.025 7.030 3.550 1,250.50 99.9"))
    # G. prosign / ngăn cách
    add(Case("G-bt", "G nhóm ngăn bằng BT/AR", "must", "= " + _groups("G", 6, 5) + " = <AR>"))
    add(Case("G-nr", "G điện văn có số", "must", "NR 123 R 5 KAZAKHSTAN 1430 SEP 27 = 45671 = <AR>"))
    # H. tốc độ
    for w in (5, 8, 12, 18, 25, 35, 45, 60):
        add(Case(f"H-wpm{w}", "H tốc độ 5-60 WPM", "must" if w <= 45 else "hard", _groups(f"H-{w}", 6, 5),
                 wpm=w))
    # I. Farnsworth
    for fw in (5, 8, 12):
        add(Case(f"I-farns{fw}", "I Farnsworth (chữ 18 WPM)", "must", _groups(f"I-{fw}", 6, 5), wpm=18,
                 farnsworth=fw))
    # J. tone
    for t in (300, 500, 900, 1300, 1500):
        add(Case(f"J-tone{t}", "J tần số tone", "must", _groups(f"J-{t}", 6, 5), tone=t))
    # K. SNR
    for s in (30, 20, 12, 8, 6, 3, 0):
        add(Case(f"K-snr{s}", "K SNR", "must" if s >= 12 else "hard", _groups(f"K-{s}", 8, 5), snr=s))
    # L. kênh
    add(Case("L-qrm", "L QRM sóng mang lệch 150 Hz", "must", _groups("L-qrm", 8, 5),
             channel={"qrm_kind": "carrier", "qrm_offset_hz": 150.0, "qrm_level_db": 6.0}))
    add(Case("L-qrn", "L QRN xung sét", "hard", _groups("L-qrn", 8, 5), channel={"qrn_rate_per_s": 3.0}))
    add(Case("L-qsb20", "L QSB fading 20 dB", "hard", _groups("L-qsb", 8, 5),
             channel={"qsb_depth_db": 20.0, "qsb_period_s": 4.0}))
    add(Case("L-mp3", "L nén MP3 24 kbps", "must", _groups("L-mp3", 8, 5), channel={"mp3_kbps": 24}))
    add(Case("L-clip", "L tín hiệu bị cắt đỉnh", "must", _groups("L-clip", 8, 5), channel={"clip": True, "gain": 3.0}))
    # M. gõ tay
    add(Case("M-jitter", "M gõ tay lệch nhịp", "hard", _groups("M-j", 8, 5), keyer="jitter"))
    add(Case("M-bug", "M phím bug", "hard", _groups("M-b", 8, 5), keyer="bug"))
    add(Case("M-drift-up", "M nhanh dần", "must", _groups("M-u", 8, 5), keyer="drift_up"))
    add(Case("M-drift-down", "M chậm dần", "must", _groups("M-d", 8, 5), keyer="drift_down"))
    add(Case("M-handpause", "M ngừng giữa dãy bằng khoảng giữa từ", "ambiguous", _groups("M-p", 3, 12),
             keyer="handpause"))
    # N. định dạng file
    for cont in ("wav44_stereo", "wav11k", "mp3_vbr_noxing", "ogg", "flac"):
        add(Case(f"N-{cont}", "N định dạng file", "must", _groups(f"N-{cont}", 20, 5), container=cont))
    # O. xung quanh không phải Morse
    for sur in ("silence", "noise", "speech", "music", "real_speech", "real_music"):
        add(Case(f"O-{sur}", "O Morse giữa đoạn không phải Morse", "must", _groups(f"O-{sur}", 6, 5),
                 surround=sur))
    for sur in ("noise", "speech", "music", "real_speech", "real_music"):
        add(Case(f"O-only-{sur}", "O chỉ có âm thanh không phải Morse", "must", "", surround=sur,
                 expect_empty=True))
    add(Case("O-overlay-music", "O Morse trên nhạc nền", "hard", _groups("O-ov", 8, 5), overlay="music"))
    # P. độ dài
    add(Case("P-long", "P bản tin dài 5 phút", "must", _groups("P", 60, 5), wpm=18))
    # Q. ngôn ngữ
    add(Case("Q-ru", "Q số trong văn bản Nga", "must", "ДОМ 15 КВ 7 ТЕЛ 2345678 В 19 30", profile="ru"))
    add(Case("Q-kk", "Q số trong văn bản Kazakh", "must", "ҮЙ 15 ПӘТЕР 7 САҒАТ 19 30", profile="kk-cyrl-ru"))
    add(Case("Q-en", "Q số trong văn bản Anh", "must", "MEET AT 1930 ROOM 12 GATE 7 FLIGHT KC 853",
             profile="en"))
    return C


# ---------------- dựng âm thanh ----------------
def _keyer(c: Case) -> KeyerParams:
    if c.keyer == "machine":
        return machine(c.wpm)
    if c.keyer == "jitter":
        return KeyerParams(c.wpm, c.farnsworth, 3.0, 0.08, False, 0.0, 0.0, "jitter")
    if c.keyer == "bug":
        return KeyerParams(c.wpm, c.farnsworth, 3.0, 0.10, True, 0.0, 0.0, "bug")
    if c.keyer == "drift_up":
        return KeyerParams(c.wpm, c.farnsworth, 3.0, 0.0, False, -0.25, 0.0, "drift")
    if c.keyer == "drift_down":
        return KeyerParams(c.wpm, c.farnsworth, 3.0, 0.0, False, 0.25, 0.0, "drift")
    if c.keyer == "handpause":
        return KeyerParams(c.wpm, c.farnsworth, 3.0, 0.05, False, 0.0, 0.0, "handpause")
    raise ValueError(c.keyer)


def _elements(c: Case, rng) -> list[Element]:
    enc = Encoder(c.profile)
    timing = TimingParams(c.wpm, c.farnsworth, 3.0)
    nominal = tokens_to_elements(enc.to_tokens(c.sent if c.sent is not None else c.ref, strict=False), timing)
    _, word_gap = gap_seconds(timing)
    u = 1.2 / c.wpm
    if c.word_gap_units is not None:
        nominal = [Element(False, c.word_gap_units * u) if (not e.on and abs(e.duration - word_gap) < 1e-9) else e
                   for e in nominal]
    if c.word_gaps:
        out, k = [], 0
        for e in nominal:
            if not e.on and abs(e.duration - word_gap) < 1e-9:
                e = Element(False, c.word_gaps[k % len(c.word_gaps)] * u)
                k += 1
            out.append(e)
        nominal = out
    if c.keyer == "handpause":                  # 1 khoảng giữa chữ trong mỗi dãy kéo tới 7 dit
        inter, _ = gap_seconds(timing)
        idx = [i for i, e in enumerate(nominal) if not e.on and abs(e.duration - inter) < 1e-9]
        for i in idx[5::11]:
            nominal[i] = Element(False, 7.0 * u)
    return rescale_elements(apply_keyer(nominal, _keyer(c), rng), total_seconds(nominal))


def _babble(rng, seconds: float) -> np.ndarray:
    """Giọng nói giả: 3 giọng, hài âm f0 100–230 Hz trôi, formant di chuyển, nhịp âm tiết 4–6 Hz."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    out = np.zeros(n)
    for _ in range(3):
        f0 = rng.uniform(100, 230) * (1 + 0.15 * np.sin(2 * np.pi * rng.uniform(0.2, 0.6) * t + rng.uniform(0, 6)))
        phase = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE
        f1 = 500 + 300 * np.sin(2 * np.pi * rng.uniform(1, 3) * t + rng.uniform(0, 6))
        f2 = 1400 + 500 * np.sin(2 * np.pi * rng.uniform(1, 3) * t + rng.uniform(0, 6))
        v = np.zeros(n)
        for h in range(1, 25):
            fh = h * f0
            gain = np.exp(-((fh - f1) / 180) ** 2) + 0.6 * np.exp(-((fh - f2) / 250) ** 2) + 0.05
            v += gain * np.sin(h * phase) / h ** 0.3
        syll = np.clip(np.sin(2 * np.pi * rng.uniform(4, 6) * t + rng.uniform(0, 6)), 0, None) ** 0.7
        out += v * syll
    out += 0.05 * rng.standard_normal(n) * (rng.random(n) < 0.3)
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def _music(rng, seconds: float, near_hz: float) -> np.ndarray:
    """Nhạc giả: hợp âm răng cưa đổi mỗi 0,25–0,5 s, giai điệu đi qua cả tần số tone, trống."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    out = np.zeros(n)
    pos = 0
    while pos < n:
        dur = int(rng.uniform(0.25, 0.5) * SAMPLE_RATE)
        seg = slice(pos, min(n, pos + dur))
        root = rng.uniform(110, 330)
        notes = [root, root * 1.26, root * 1.5, near_hz * rng.choice([0.94, 1.0, 1.06])]
        env = np.exp(-np.arange(seg.stop - seg.start) / SAMPLE_RATE * rng.uniform(2, 6))
        for f in notes:
            for h in range(1, 6):
                out[seg] += env * np.sin(2 * np.pi * f * h * t[seg]) / h
        if rng.random() < 0.5:
            k = min(n - pos, 800)
            out[pos:pos + k] += 2 * rng.standard_normal(k) * np.exp(-np.arange(k) / 150)
        pos += dur
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def _real(kind: str, rng, seconds: float) -> np.ndarray | None:
    """Đoạn thật từ testdata/private/t6 (đã có giám khảo xác nhận KHÔNG có Morse)."""
    from morsedesk.audio.io import load_audio

    src = {"real_speech": ("ua3afo_razdel1.mp3", 2.0, 34.0), "real_music": ("piknik_remix.mp3", 60.0, 120.0)}[kind]
    path = PRIVATE / src[0]
    if not path.exists():
        return None
    x, _ = load_audio(path)
    a = int(rng.uniform(src[1], src[2] - seconds) * SAMPLE_RATE)
    return x[a:a + int(seconds * SAMPLE_RATE)].astype(np.float32)


def _distractor(kind: str, rng, seconds: float, tone: float) -> np.ndarray | None:
    n = int(seconds * SAMPLE_RATE)
    if kind == "silence":
        return np.zeros(n, dtype=np.float32)
    if kind == "noise":
        return (0.3 * rng.standard_normal(n)).astype(np.float32)
    if kind == "speech":
        return 0.6 * _babble(rng, seconds)
    if kind == "music":
        return 0.6 * _music(rng, seconds, tone)
    return _real(kind, rng, seconds)


def render(c: Case) -> np.ndarray | None:
    rng = _rng("audio|" + c.id)
    if c.expect_empty:
        body = np.zeros(0, dtype=np.float32)
    else:
        el = _elements(c, rng)
        body = elements_to_audio(el, c.tone, SAMPLE_RATE, 0.8)
        pad = np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)
        body = np.concatenate([pad, body, pad])
    ch = clean(c.snr, c.tone)
    extra = dict(c.channel)
    if extra:
        ch = replace(ch, **extra)
    if len(body):
        body = apply_channel(body, ch, rng, SAMPLE_RATE, tone_power(0.8))
    if c.overlay == "music":
        m = _music(rng, len(body) / SAMPLE_RATE + 0.1, c.tone)[:len(body)]
        body = body + 0.35 * m
    if c.surround:
        before = _distractor(c.surround, rng, 12.0, c.tone)
        after = _distractor(c.surround, rng, 10.0, c.tone)
        if before is None or after is None:
            return None
        gap = np.zeros(int(1.0 * SAMPLE_RATE), dtype=np.float32)
        noise = lambda k: (0.002 * rng.standard_normal(k)).astype(np.float32)  # noqa: E731
        parts = [before, gap + noise(len(gap))]
        if len(body):
            parts += [body, gap + noise(len(gap))]
        parts += [after]
        body = np.concatenate(parts)
    return body.astype(np.float32)


def _container_file(c: Case, x: np.ndarray, tmp: Path) -> Path | None:
    from scipy.signal import resample_poly

    if c.container == "array":
        return None
    if c.container == "wav44_stereo":
        y = resample_poly(x, 441, 80).astype(np.float32)
        p = tmp / "x.wav"
        sf.write(p, np.stack([y, 0.8 * y], axis=1), 44100)
        return p
    if c.container == "wav11k":
        p = tmp / "x.wav"
        sf.write(p, resample_poly(x, 11025, 8000).astype(np.float32), 11025)
        return p
    if c.container in ("ogg", "flac"):
        from morsedesk.audio.io import save_audio  # đúng đường xuất của app (ghi theo khối)

        p = tmp / f"x.{c.container}"
        save_audio(p, x / (np.abs(x).max() + 1e-9) * 0.9, SAMPLE_RATE)
        return p
    if c.container == "mp3_vbr_noxing":
        import subprocess

        wav, mp3 = tmp / "in.wav", tmp / "x.mp3"
        # 1,5 s nhiễu ở đầu để khung đầu có bitrate cao (đúng kiểu file làm libsndfile đoán sai)
        head = (0.8 * _rng("n").standard_normal(int(1.5 * SAMPLE_RATE))).astype(np.float32)
        y = np.concatenate([head, np.zeros(SAMPLE_RATE, np.float32), x / (np.abs(x).max() + 1e-9) * 0.9])
        sf.write(wav, resample_poly(y, 441, 80).astype(np.float32), 44100)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-q:a", "2",
                        "-write_xing", "0", str(mp3)], check=True)
        return mp3
    raise ValueError(c.container)


# ---------------- giải mã + chấm ----------------
_DEC: dict = {}
LIVE_BLOCK = 800


def _decoder(cfg: str, profile: str) -> Decoder:
    key = (cfg, profile)
    if key not in _DEC:
        if cfg == "app":
            _DEC[key] = Decoder(profile, engine="onnx")
        elif cfg == "auto":
            _DEC[key] = Decoder("auto", engine="onnx")
        elif cfg in ("live", "live-auto"):   # đúng như LiveWorker
            _DEC[key] = Decoder("auto" if cfg == "live-auto" else profile, engine="onnx", lm=True,
                                fallback=False, skip_silent_windows=True, numbers=False, keyed=False)
        else:
            raise ValueError(cfg)
    return _DEC[key]


def _decode(cfg: str, c: Case, x: np.ndarray) -> str:
    dec = _decoder(cfg, c.profile)
    if cfg.startswith("live"):
        from morsedesk.model.stream import StreamDecoder

        st = StreamDecoder(decoder=dec)
        try:
            for i in range(0, len(x), LIVE_BLOCK):
                st.push(x[i:i + LIVE_BLOCK])
            return st.flush().text
        finally:
            st.reset()
    with tempfile.TemporaryDirectory(dir=ROOT / "runs") as d:
        p = _container_file(c, x, Path(d))
        return (dec.decode_file(p) if p is not None else dec.decode_array(x, SAMPLE_RATE)).text


def _norm(text: str, profile) -> str:
    """So theo MẪU: chữ cùng mẫu (Ъ/Ь) và prosign cùng mẫu với dấu (<AR> = +, <BT> = =) là một."""
    from morsedesk.numbers import letters_of

    pat_of = dict(profile.letter_to_pattern)
    pat_of.update({name: pat for pat, name in profile.prosigns.items()})
    first: dict[str, str] = {}
    for ch, pat in pat_of.items():
        first.setdefault(pat, ch)
    words = []
    for w in text.upper().split():
        words.append("".join(first.get(pat_of.get(ch, ""), ch) for ch in letters_of(w)))
    return " ".join(words)


def judge(c: Case, hyp: str) -> dict:
    profile = load_profile(c.profile)
    if c.expect_empty:
        digits = sum(ch.isdigit() for ch in hyp)
        return {"ok": digits == 0, "hallucinated_digits": digits, "hyp": hyp}
    s = score(c.ref, hyp, profile)
    ok = _norm(c.ref, profile) == _norm(hyp, profile)
    return {"ok": ok, "hyp": hyp, **{k: s[k] for k in ("cer", "der", "digits", "digit_errors", "groups",
                                                        "groups_ok_pattern")}}


def run_job(job: tuple) -> dict:
    cid, configs = job
    c = next(x for x in cases() if x.id == cid)
    x = render(c)
    row = {"id": c.id, "cat": c.cat, "tier": c.tier, "ref": c.ref}
    if x is None:
        row["skipped"] = "thiếu âm thanh thật (testdata/private/t6)"
        return row
    row["seconds"] = round(len(x) / SAMPLE_RATE, 1)
    for cfg in configs:
        if cfg == "auto" and c.profile != "en" and False:
            continue
        row[cfg] = judge(c, _decode(cfg, c, x))
    return row


def summarize(rows: list[dict], configs: tuple[str, ...]) -> list[str]:
    out = []
    for cfg in configs:
        rs = [r for r in rows if cfg in r]
        out.append(f"== {cfg}")
        for tier in ("must", "hard", "ambiguous"):
            t = [r for r in rs if r["tier"] == tier]
            if not t:
                continue
            ok = sum(r[cfg]["ok"] for r in t)
            dig = sum(r[cfg].get("digits", 0) for r in t)
            derr = sum(r[cfg].get("digit_errors", r[cfg].get("hallucinated_digits", 0)) for r in t)
            out.append(f"  {tier:9s} đúng trọn {ok}/{len(t)}   lỗi chữ số {derr}/{dig}")
        cats: dict[str, list] = {}
        for r in rs:
            cats.setdefault(r["cat"], []).append(r)
        for cat, t in sorted(cats.items()):
            ok = sum(r[cfg]["ok"] for r in t)
            out.append(f"    {cat:48s} {ok}/{len(t)}")
        fails = [r for r in rs if not r[cfg]["ok"] and r["tier"] == "must"]
        if fails:
            out.append("  -- ca MUST sai:")
            for r in fails:
                out.append(f"    {r['id']:18s} ref: {r['ref'][:70]}")
                out.append(f"    {'':18s} hyp: {r[cfg]['hyp'][:70]}")
    skipped = [r["id"] for r in rows if "skipped" in r]
    if skipped:
        out.append("bỏ qua (thiếu âm thanh thật): " + ", ".join(skipped))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="app")
    ap.add_argument("--only", default="", help="tiền tố mã ca, phẩy: B3,O")
    ap.add_argument("--out", default="runs/edge")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--write-wavs", default=None, help="ghi âm thanh + manifest.jsonl ra thư mục này")
    a = ap.parse_args()
    allc = cases()
    sel = [c for c in allc if not a.only or any(c.id.startswith(p) for p in a.only.split(","))]
    if a.list:
        for c in sel:
            print(f"{c.id:18s} {c.tier:9s} {c.cat:40s} {c.ref[:60]}")
        print(len(sel), "ca")
        return 0
    if a.write_wavs:
        d = Path(a.write_wavs)
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "manifest.jsonl", "w", encoding="utf-8") as f:
            for c in sel:
                x = render(c)
                if x is None:
                    continue
                sf.write(d / f"{c.id}.wav", x, SAMPLE_RATE, subtype="PCM_16")
                f.write(json.dumps({"path": str(d / f"{c.id}.wav"), "text": c.ref, "profile": c.profile,
                                    **{k: v for k, v in asdict(c).items() if k not in ("ref",)}},
                                   ensure_ascii=False) + "\n")
        print(f"đã ghi {len(sel)} ca vào {d}")
        return 0
    configs = tuple(x for x in a.configs.split(",") if x)
    t0 = time.time()
    rows = map_parallel(run_job, [(c.id, configs) for c in sel],
                        a.workers if a.workers is not None else default_workers())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    text = "\n".join(summarize(rows, configs))
    (out / "summary.txt").write_text(text + "\n", encoding="utf-8")
    print(f"{len(rows)} ca, {sum(r.get('seconds', 0) for r in rows) / 60:.0f} phút âm thanh, {time.time() - t0:.0f} s")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
