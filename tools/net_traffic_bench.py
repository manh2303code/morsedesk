"""Bộ tổng hợp điện văn mạng CW (M89/M95) x lối phím x SNR — chấm theo NGHĨA (Kirin->Latin, số viết tắt->số).

Vì sao (docs/research/06): cùng nội dung, phím CHUẨN thì app đúng tuyệt đối tới 8 dB, phím NHẸ thì không.
Lối phím ĐO trên 3 file thật T7 (28/09, docs/research/06 §5) và dùng CHUNG mô hình với dữ liệu huấn luyện
(morsedesk/data/keyer.apply_fist): t7light ~ file 351, t7mid ~ file 352.

    uv run python tools/net_traffic_bench.py [--n 6] [--snrs 30,20,12,8,4] [--model models/eval_E20.onnx]
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.net_eval import lev_ops, semantic, text_tokens  # noqa: E402

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CUT = {"1": "A", "2": "U", "3": "V", "8": "D", "9": "N", "0": "T"}
# Đo 28/09 (đơn vị nhịp): 351 chấm 0,6 gạch 2,65, lặng sau gạch 0,87 / sau chấm 1,27, giữa chữ 4,3, giữa từ nén
# vào ~5–6; 352 chấm 0,75 gạch 2,8, lặng sau gạch 0,8–1,0, giữa chữ 3,5–4,5, giữa từ 7–14; 347 gần chuẩn.
FISTS: dict[str, dict | None] = {
    "std": None,
    "t7mid": dict(mark_offset=-0.25, dah_gap_cut=0.3, char_stretch=1.15, word_stretch=1.2),
    "t7light": dict(mark_offset=-0.4, dah_gap_cut=0.5, char_stretch=1.3, word_stretch=0.8),
}


def message_pair(rng: np.random.Generator) -> tuple[str, str]:
    """(văn bản phát — số viết tắt, NGHĨA — nhóm là chữ số). Chấm theo nghĩa: nhóm toàn chữ viết tắt (`TVVV`)
    vẫn là số 0333."""
    def call() -> str:
        return "".join(rng.choice(list(LETTERS), 4))

    sent, meant = [], []

    def group() -> None:
        g = "".join(str(d) for d in rng.integers(0, 10, 4))
        sent.append("".join(CUT[c] if c in CUT and rng.random() < 0.4 else c for c in g))
        meant.append(g)

    def word(w: str) -> None:
        sent.append(w)
        meant.append(w)
    c1, c2 = call(), call()
    k = int(rng.integers(12, 25))
    for w in (f"VV {c1} {c1} DE {c2} {c2} HR MSG GA NR {rng.integers(1, 999):03d}/CK {k} "
              f"{rng.integers(1, 31):02d} {rng.integers(1, 13):02d}{rng.integers(1, 29):02d} "
              f"{rng.integers(0, 24):02d}{rng.integers(0, 60):02d} RMKS").split():
        word(w)
    group()
    word("=")
    for _ in range(k):
        group()
    word("<AR>")
    return " ".join(sent), " ".join(meant)


def message(rng: np.random.Generator) -> str:
    return message_pair(rng)[0]


def render(text: str, fist: str, snr: float, seed: int) -> np.ndarray:
    from morsedesk.api import Encoder
    from morsedesk.data.keyer import KeyerParams, apply_fist
    from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
    from morsedesk.encode.timing import Element, TimingParams, tokens_to_elements, unit_seconds
    from morsedesk.lm.profile import load_profile
    rng = np.random.default_rng(seed)
    wpm = float(rng.uniform(15, 20))
    u = unit_seconds(wpm)
    el = tokens_to_elements(Encoder(load_profile("en")).to_tokens(text), TimingParams(wpm))
    el = [Element(e.on, e.duration * float(np.exp(rng.normal(0, 0.06)))) for e in el]
    if FISTS[fist]:
        el = apply_fist(el, KeyerParams(wpm=wpm, farnsworth_wpm=None, weight=3.0, jitter=0.0, bug=False, drift=0.0,
                                        spacing_error_rate=0.0, **FISTS[fist]), u)
    x = elements_to_audio(el, float(rng.uniform(700, 1100)), 8000, 0.5)
    x = np.concatenate([np.zeros(4000, np.float32), x, np.zeros(4000, np.float32)])
    return add_noise(x, snr, tone_power(0.5), rng=rng)


_DEC: dict = {}


def job(args):
    idx, fist, snr, model = args
    from morsedesk.api import Decoder
    text, meant = message_pair(np.random.default_rng(1000 + idx))
    x = render(text, fist, snr, seed=idx * 100 + int(snr) * 7 + len(fist))
    if model not in _DEC:
        kw = dict(engine="onnx", lm=True)
        if model:
            kw["model_path"] = model
        _DEC[model] = Decoder("auto", **kw)
    return idx, fist, snr, meant, _DEC[model].decode_array(x, 8000).text


def sem_cer(ref: str, hyp: str) -> tuple[int, int]:
    """`ref` = NGHĨA (nhóm là chữ số)."""
    r = semantic(text_tokens(ref))
    h = semantic(text_tokens(hyp))
    d, _ = lev_ops(r, h)
    return d, len(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--snrs", default="30,20,12,8,4")
    ap.add_argument("--fists", default="std,t7mid,t7light")
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    snrs = [float(s) for s in a.snrs.split(",")]
    tasks = [(i, f, s, a.model) for i in range(a.n) for f in a.fists.split(",") for s in snrs]
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(job, tasks))
    agg: dict = {}
    for _, fist, snr, text, hyp in res:
        d, n = sem_cer(text, hyp)
        s = agg.setdefault((fist, snr), [0, 0])
        s[0] += d
        s[1] += n
    fists = a.fists.split(",")
    print(f"{'SNR':>5s} " + " ".join(f"{f:>9s}" for f in fists) + "   (CER theo nghĩa, %)")
    for snr in snrs:
        print(f"{snr:5.0f} " + " ".join(f"{100 * agg[(f, snr)][0] / agg[(f, snr)][1]:9.2f}" for f in fists))
    tot = [sum(agg[(f, s)][0] for s in snrs) / sum(agg[(f, s)][1] for s in snrs) for f in fists]
    print("  TB  " + " ".join(f"{100 * t:9.2f}" for t in tot))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
