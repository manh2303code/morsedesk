"""Ảnh để GIÁM KHẢO (LLM hoặc người) đọc Morse bằng mắt — dựng đáp án cho bản ghi không có bản chép.

Hai loại ảnh:
- `overview`: phổ 0–2 kHz cả file + đường bao tại tone — thấy ngay đoạn nào là Morse, đoạn nào là
  giọng nói, nhạc, im lặng.
- `strips`: đường bao tone theo hàng (mặc định 8 s/hàng); mỗi xung bật được tô thành khối, ghi độ dài
  theo đơn vị dit ước lượng (1 = chấm, 3 = gạch), khoảng lặng >= 2,5 dit ghi số dit (3 = giữa chữ,
  7 = giữa từ). Tùy chọn chồng chữ mà các bộ giải mã đã đọc (từ tools/multi_decode.py) theo mốc thời gian.

    uv run python tools/envelope_strips.py overview FILE OUT.png
    uv run python tools/envelope_strips.py strips FILE OUTDIR [--t0 0 --t1 60 --row 8 --decodes runs/x.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from morsedesk.audio.io import load_audio, resample  # noqa: E402
from morsedesk.constants import FRAME_RATE, SAMPLE_RATE  # noqa: E402
from morsedesk.dsp.frontend import mix_envelope  # noqa: E402
from morsedesk.dsp.tone import estimate_tone  # noqa: E402

BG, GRID, INK, KEY, TXT = "#101826", "#2a3550", "#8fb3ff", "#f5a623", "#e6e9ef"
DEC_COLORS = {"app_ru": "#7ee787", "app_en": "#79c0ff", "greedy": "#d2a8ff", "dsp": "#ffa198", "e17_ru": "#e3b341",
              "app_auto": "#56d4dd"}


def _app():
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication(sys.argv[:1])


def load8k(path: str) -> np.ndarray:
    x, sr = load_audio(path)
    x = np.asarray(x, dtype=np.float32)
    return resample(x, sr, SAMPLE_RATE) if sr != SAMPLE_RATE else x


def envelope(x: np.ndarray, tone: float | None = None) -> tuple[np.ndarray, float]:
    """Đường bao tại tone (khung 5 ms), chuẩn hóa theo phân vị 99."""
    f0 = tone or (estimate_tone(x).f0_hz or 700.0)
    env = mix_envelope(x, f0)
    top = float(np.percentile(env, 99.5)) or 1.0
    return np.clip(env / top, 0, 1.2), f0


def keying(env: np.ndarray) -> tuple[np.ndarray, float]:
    """Bật/tắt bằng ngưỡng giữa hai cụm (nền, tone) + trễ Schmitt; trả (mảng bool, dit ước lượng giây)."""
    lo, hi = np.percentile(env, 20), np.percentile(env, 97)
    on_t, off_t = lo + 0.5 * (hi - lo), lo + 0.35 * (hi - lo)
    state, out = False, np.zeros(len(env), dtype=bool)
    for i, v in enumerate(env):
        state = v > on_t if not state else v > off_t
        out[i] = state
    runs = _runs(out)
    ons = np.array([n for v, _, n in runs if v]) / FRAME_RATE
    offs = np.array([n for v, _, n in runs[1:-1] if not v]) / FRAME_RATE
    ons, offs = ons[ons > 0.02], offs[offs > 0.02]
    if len(ons) < 4:
        return out, 0.1
    # Đơn vị = khoảng lặng giữa hai phần tử của MỘT chữ (luôn 1 dit), tức cụm ngắn nhất của khoảng
    # lặng; cụm ngắn nhất của xung chỉ là dit khi bản tin CÓ chấm (bài học số 0 toàn gạch thì không).
    def shortest_cluster(v: np.ndarray) -> float:
        s = np.sort(v)
        lo = s[len(s) // 20]
        return float(np.median(s[s <= 1.8 * lo]))

    unit = shortest_cluster(offs) if len(offs) >= 4 else shortest_cluster(ons)
    return out, unit


def _runs(b: np.ndarray) -> list[tuple[bool, int, int]]:
    out, i = [], 0
    while i < len(b):
        j = i
        while j < len(b) and b[j] == b[i]:
            j += 1
        out.append((bool(b[i]), i, j - i))
        i = j
    return out


def overview(path: str, out_png: str, width: int = 1800) -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    _app()
    x = load8k(path)
    dur = len(x) / SAMPLE_RATE
    n_fft, hop = 512, max(64, len(x) // width)
    frames = max(1, (len(x) - n_fft) // hop)
    win = np.hanning(n_fft).astype(np.float32)
    spec = np.empty((frames, n_fft // 2 + 1), dtype=np.float32)
    for k in range(frames):
        seg = x[k * hop:k * hop + n_fft]
        spec[k] = np.abs(np.fft.rfft(seg * win))
    freqs = np.fft.rfftfreq(n_fft, 1 / SAMPLE_RATE)
    band = freqs <= 2000
    db = 20 * np.log10(spec[:, band] + 1e-6)
    db = np.clip((db - np.percentile(db, 5)) / (np.percentile(db, 99.7) - np.percentile(db, 5) + 1e-9), 0, 1)
    env, f0 = envelope(x)
    H_SPEC, H_ENV, PAD = 300, 90, 40
    img = QImage(width + 2 * PAD, H_SPEC + H_ENV + 3 * PAD, QImage.Format.Format_RGB32)
    img.fill(QColor(BG))
    p = QPainter(img)
    p.setFont(QFont("Segoe UI", 10))
    cols = db.shape[0]
    for c in range(width):
        k = min(cols - 1, int(c * cols / width))
        col = db[k]
        rows = len(col)
        for r in range(H_SPEC):
            v = col[min(rows - 1, int((H_SPEC - 1 - r) * rows / H_SPEC))]
            g = int(255 * v)
            img.setPixelColor(PAD + c, PAD + r, QColor(g, int(g * 0.8), int(80 + 150 * v)))
    y0 = PAD + H_SPEC + PAD // 2
    p.setPen(QColor(INK))
    step = max(1, len(env) // width)
    for c in range(width):
        v = float(env[c * step:(c + 1) * step].max()) if c * step < len(env) else 0.0
        p.drawLine(PAD + c, int(y0 + H_ENV), PAD + c, int(y0 + H_ENV - min(1.0, v) * H_ENV))
    p.setPen(QColor(TXT))
    tick = 10 if dur <= 180 else 30 if dur <= 600 else 60
    for t in range(0, int(dur) + 1, tick):
        xx = PAD + int(t / dur * width)
        p.setPen(QColor(GRID))
        p.drawLine(xx, PAD, xx, int(y0 + H_ENV))
        p.setPen(QColor(TXT))
        p.drawText(QRectF(xx - 30, y0 + H_ENV + 4, 60, 18), 0x84, f"{t // 60}:{t % 60:02d}")
    for f in (500, 1000, 1500, 2000):
        yy = PAD + H_SPEC - int(f / 2000 * H_SPEC)
        p.drawText(QRectF(2, yy - 8, PAD - 4, 16), 0x82, f"{f // 100}")
    p.drawText(QRectF(PAD, 6, width, 24), 0x81,
               f"{Path(path).name}  {dur:.0f} s  — phổ 0–2 kHz (trên), đường bao tại tone {f0:.0f} Hz (dưới)")
    p.end()
    img.save(out_png)


def strips(path: str, outdir: str, t0: float = 0.0, t1: float | None = None, row_s: float = 8.0,
           rows_per_image: int = 6, decodes: str | None = None, tone: float | None = None) -> list[str]:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    _app()
    x = load8k(path)
    dur = len(x) / SAMPLE_RATE
    t1 = min(dur, t1 if t1 is not None else dur)
    env, f0 = envelope(x, tone)
    on, dit = keying(env)
    dec = json.loads(Path(decodes).read_text(encoding="utf-8")) if decodes else {}
    W, ROW_H, PAD, LABEL_H = 1800, 150, 50, 16
    px = W / row_s
    n_rows = int(np.ceil((t1 - t0) / row_s))
    out_files = []
    Path(outdir).mkdir(parents=True, exist_ok=True)
    runs = _runs(on)
    for img_i in range(0, n_rows, rows_per_image):
        rows = range(img_i, min(n_rows, img_i + rows_per_image))
        n_dec = len(dec)
        row_total = ROW_H + LABEL_H * n_dec + 28
        img = QImage(W + 2 * PAD, PAD + row_total * len(rows) + 10, QImage.Format.Format_RGB32)
        img.fill(QColor(BG))
        p = QPainter(img)
        f_small = QFont("Consolas", 9)
        f_txt = QFont("Segoe UI", 10)
        p.setFont(f_txt)
        p.setPen(QColor(TXT))
        p.drawText(QRectF(PAD, 8, W, 24), 0x81,
                   f"{Path(path).name}  tone {f0:.0f} Hz  dit ≈ {dit * 1000:.0f} ms (≈ {1.2 / dit:.1f} WPM)  "
                   f"— số trên xung = độ dài theo dit, số dưới khoảng lặng = dit (3 giữa chữ, 7 giữa từ)")
        for k, r in enumerate(rows):
            rs = t0 + r * row_s
            y = PAD + k * row_total
            base = y + ROW_H - 30
            p.setPen(QColor(GRID))
            for s in range(int(np.ceil(rs)), int(rs + row_s) + 1):
                xx = PAD + (s - rs) * px
                p.drawLine(int(xx), y + 10, int(xx), base + 4)
                p.setFont(f_small)
                p.setPen(QColor(TXT))
                p.drawText(QRectF(xx - 30, base + 6, 60, 14), 0x84, f"{s // 60}:{s % 60:02d}")
                p.setPen(QColor(GRID))
            a, b = int(rs * FRAME_RATE), int(min(t1, rs + row_s) * FRAME_RATE)
            p.setPen(QColor(INK))
            prev = None
            for i in range(a, min(b, len(env))):
                xx = PAD + (i / FRAME_RATE - rs) * px
                yy = base - min(1.0, float(env[i])) * (ROW_H - 50)
                if prev:
                    p.drawLine(int(prev[0]), int(prev[1]), int(xx), int(yy))
                prev = (xx, yy)
            p.setFont(f_small)
            for val, s0, n in runs:
                if s0 + n < a or s0 > b:
                    continue
                xa = PAD + (s0 / FRAME_RATE - rs) * px
                xb = PAD + ((s0 + n) / FRAME_RATE - rs) * px
                units = n / FRAME_RATE / dit
                if val:
                    p.fillRect(QRectF(xa, base - 14, max(1.0, xb - xa), 10), QColor(KEY))
                    p.setPen(QColor(KEY))
                    p.drawText(QRectF(xa - 10, base - 32, xb - xa + 20, 14), 0x84, f"{units:.1f}")
                elif units >= 2.5:
                    p.setPen(QColor("#9aa4b8"))
                    p.drawText(QRectF(xa, base - 2, xb - xa, 12), 0x84, f"{units:.0f}")
            yy = base + 22
            for name, d in dec.items():
                color = QColor(DEC_COLORS.get(name, TXT))
                p.setPen(color)
                p.drawText(QRectF(2, yy, PAD - 4, LABEL_H), 0x82, name[:6])
                for w in d.get("words", []):
                    if rs <= w["start"] < rs + row_s:
                        xx = PAD + (w["start"] - rs) * px
                        p.drawText(QRectF(xx, yy, 400, LABEL_H), 0x81, w["text"])
                yy += LABEL_H
        p.end()
        out = str(Path(outdir) / f"{Path(path).stem}_{t0 + img_i * row_s:07.1f}.png")
        img.save(out)
        out_files.append(out)
    return out_files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["overview", "strips"])
    ap.add_argument("file")
    ap.add_argument("out")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--row", type=float, default=8.0)
    ap.add_argument("--rows", type=int, default=6)
    ap.add_argument("--decodes", default=None)
    ap.add_argument("--tone", type=float, default=None)
    a = ap.parse_args()
    if a.mode == "overview":
        overview(a.file, a.out)
        print(a.out)
    else:
        for f in strips(a.file, a.out, a.t0, a.t1, a.row, a.rows, a.decodes, a.tone):
            print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
