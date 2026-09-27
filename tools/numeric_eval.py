"""Bộ đo SỐ: chuỗi số dài, ngẫu nhiên, xen chữ và dấu câu — người dùng 26/09: "khả năng giải mã số học
cực kỳ kém ... sẽ thường xuyên là các chuỗi số học dài và ngẫu nhiên, có thể kèm nhiều ký tự và dấu xen
giữa, gồm cả dấu cách".

Năm loại nội dung, mỗi bản tin ~TARGET_CHARS ký tự:
- `groups5`:   nhóm 5 chữ số (kiểu điện số / trạm số): 48213 90577 ...
- `runs`:      dãy số liền 8–16 chữ số, cách nhau bằng dấu cách: 4821390577 ...
- `alnum`:     nhóm 5 ký tự trộn chữ và số (điện mật mã): A3F9Q 7K2LM ...
- `formatted`: số có định dạng thật: điện thoại, tọa độ, ngày giờ, tần số, mã số, số tiền, biểu
               thức, hô hiệu kèm RST/số thứ tự, locator...
- `punct`:     nhóm số xen dấu câu, không có chữ: 4/7.2 31-08 12:45 (3) 7,5 ...

Chỉ số (ngoài CER): DER = lỗi trên CHỮ SỐ / số chữ số của đáp án (thay, mất, hoặc chèn thêm chữ số —
tính theo căn chỉnh Levenshtein); tỉ lệ NHÓM đúng trọn (nhóm = đoạn giữa hai dấu cách, căn theo nhóm);
bảng nhầm lẫn chữ số (đáp án -> đọc ra). Các cách giải mã như long_random_eval, thêm `dsp` (chỉ bộ
cổ điển) và `deepcw` (model ngoài, chỉ tiếng Anh):

    uv run python tools/numeric_eval.py [--per-cell 1] [--wpm 15,25] [--snr 20,8] [--configs ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from morsedesk.api import Decoder, Encoder  # noqa: E402
from morsedesk.data.channel import apply_channel, clean  # noqa: E402
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine  # noqa: E402
from morsedesk.data.synth import rescale_elements  # noqa: E402
from morsedesk.data.text import keep_supported, translit_via_patterns  # noqa: E402
from morsedesk.encode.synth import elements_to_audio, tone_power  # noqa: E402
from morsedesk.encode.timing import tokens_to_elements, total_seconds  # noqa: E402
from morsedesk.lm.profile import load_profile  # noqa: E402
from morsedesk.metrics import normalize_text  # noqa: E402
from morsedesk.parallel import default_workers, map_parallel  # noqa: E402

LANGS = {"en": "en", "ru": "ru", "kk": "kk-cyrl-ru"}
KINDS = ("groups5", "runs", "alnum", "formatted", "punct")
TARGET_CHARS = 100
KEYINGS = ("machine", "hand")
CONFIGS = ("app", "model+LM", "model", "auto", "dsp", "deepcw", "live", "live-auto")
LIVE_BLOCK = 800            # 0,1 s — khối AudioCapture đẩy vào LiveWorker
DIGITS = "0123456789"
PUNCT_SEPS = "./-:,=+?"


# ---------- văn bản ----------
def _d(rng, n: int) -> str:
    return "".join(DIGITS[int(rng.integers(10))] for _ in range(n))


def _letters(profile) -> list[str]:
    return sorted({ch for opts in profile.map.values() for ch in opts
                   if len(ch) == 1 and ch.isalpha()})


def groups5(profile, rng) -> str:
    return " ".join(_d(rng, 5) for _ in range(TARGET_CHARS // 6))


def runs(profile, rng) -> str:
    out: list[str] = []
    while sum(len(s) + 1 for s in out) < TARGET_CHARS:
        out.append(_d(rng, int(rng.integers(8, 17))))
    return " ".join(out)


def alnum(profile, rng) -> str:
    abc = _letters(profile) + list(DIGITS)
    return " ".join("".join(abc[int(rng.integers(len(abc)))] for _ in range(5))
                    for _ in range(TARGET_CHARS // 6))


def _formatted_one(rng) -> str:
    """Một mẩu số có định dạng thật (viết bằng chữ Latin; bản Nga/Kazakh chuyển theo mẫu Morse)."""
    k = int(rng.integers(12))
    if k == 0:
        return f"+7 {_d(rng, 3)} {_d(rng, 3)}-{_d(rng, 2)}-{_d(rng, 2)}"
    if k == 1:
        return f"{_d(rng, 2)}.{_d(rng, 4)}N/{_d(rng, 3)}.{_d(rng, 4)}E"
    if k == 2:
        return f"20{_d(rng, 2)}-{_d(rng, 2)}-{_d(rng, 2)} {_d(rng, 2)}:{_d(rng, 2)}Z"
    if k == 3:
        return f"{int(rng.integers(1, 30))}.{_d(rng, 3)} MHZ"
    if k == 4:
        return f"ID:{_d(rng, 4)}-{_d(rng, 3)}/{_d(rng, 2)}"
    if k == 5:
        return f"{_d(rng, 1)},{_d(rng, 3)}.{_d(rng, 2)}"
    if k == 6:
        a, b = int(rng.integers(1, 100)), int(rng.integers(1, 100))
        return f"{a}+{b}={a + b}"
    if k == 7:
        pre = ["UN", "UA", "R", "DL", "K", "W", "UP"][int(rng.integers(7))]
        suf = "".join(chr(65 + int(rng.integers(26))) for _ in range(int(rng.integers(2, 4))))
        return f"{pre}{_d(rng, 1)}{suf} 5NN {_d(rng, 3)}"
    if k == 8:
        return f"NR {_d(rng, 5)} QTC {int(rng.integers(1, 50))}/{_d(rng, 3)}"
    if k == 9:
        return f"({_d(rng, 3)}) {_d(rng, 2)}.{_d(rng, 2)}.{_d(rng, 4)}"
    if k == 10:
        return f"{_d(rng, 4)}-{_d(rng, 4)} T={_d(rng, 2)}"
    grid = "".join(chr(65 + int(rng.integers(18))) for _ in range(2))
    return f"{grid}{_d(rng, 2)} {_d(rng, 4)}Z"


def formatted(profile, rng) -> str:
    out: list[str] = []
    while sum(len(s) + 1 for s in out) < TARGET_CHARS:
        out.append(_formatted_one(rng))
    text = " ".join(out)
    if profile.id != "en":
        text = translit_via_patterns(text, load_profile("en"), profile)
    return text


def punct(profile, rng) -> str:
    seps = [c for c in PUNCT_SEPS if c in profile.letter_to_pattern]
    out: list[str] = []
    while sum(len(s) + 1 for s in out) < TARGET_CHARS:
        k = int(rng.integers(4))
        if k == 0:
            out.append(f"{_d(rng, int(rng.integers(1, 4)))}{seps[int(rng.integers(len(seps)))]}"
                       f"{_d(rng, int(rng.integers(1, 4)))}")
        elif k == 1:
            s = seps[int(rng.integers(len(seps)))]
            out.append(s.join(_d(rng, int(rng.integers(1, 3))) for _ in range(3)))
        elif k == 2 and "(" in profile.letter_to_pattern:
            out.append(f"({_d(rng, int(rng.integers(1, 4)))})")
        else:
            out.append(f"{_d(rng, 2)}{seps[int(rng.integers(len(seps)))]}")
    return " ".join(out)


MAKERS = {"groups5": groups5, "runs": runs, "alnum": alnum, "formatted": formatted, "punct": punct}


def make_text(kind: str, profile, rng) -> str:
    return keep_supported(MAKERS[kind](profile, rng), profile)


def render(enc: Encoder, text: str, keying: str, wpm: float, snr_db: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    keyer = machine(wpm) if keying == "machine" else KeyerParams(wpm, None, 3.0, 0.15, False, 0.0, 0.05, "jitter")
    nominal = tokens_to_elements(enc.to_tokens(text, strict=False), keyer.timing())
    elements = rescale_elements(apply_keyer(nominal, keyer, rng), total_seconds(nominal))
    tone = 500.0 + (seed % 7) * 70.0
    signal = elements_to_audio(elements, tone, 8000, 0.8)
    pad = np.zeros(4000, dtype=np.float32)
    x = np.concatenate([pad, signal, pad])
    return apply_channel(x, clean(snr_db, tone), rng, 8000, tone_power(0.8)).astype(np.float32)


# ---------- chỉ số ----------
def align(ref: str, hyp: str) -> list[tuple[str, str | None, str | None]]:
    """Căn chỉnh Levenshtein: danh sách (phép, ký tự đáp án, ký tự đọc ra); phép ∈ ok/sub/del/ins."""
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), dtype=np.int32)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        ri = ref[i - 1]
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ri != hyp[j - 1]))
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            ops.append(("ok" if ref[i - 1] == hyp[j - 1] else "sub", ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and d[i, j] == d[i - 1, j] + 1:
            ops.append(("del", ref[i - 1], None))
            i -= 1
        else:
            ops.append(("ins", None, hyp[j - 1]))
            j -= 1
    return ops[::-1]


def by_pattern(text: str, profile) -> str:
    """Mỗi chữ -> chữ đại diện cho MẪU của nó: Ъ/Ь, Ұ/У, Ң/Н cùng một mẫu, không bộ giải mã nào
    phân biệt được chúng bằng tai (Kazakh còn tùy quy ước bảng mã)."""
    first: dict[str, str] = {}
    for ch, pat in profile.letter_to_pattern.items():
        first.setdefault(pat, ch)
    return "".join(first.get(profile.letter_to_pattern.get(c, ""), c) for c in text)


def score(ref: str, hyp: str, profile=None) -> dict:
    ref, hyp = normalize_text(ref), normalize_text(hyp)
    groups_pat = None
    if profile is not None:
        groups_pat = align_tokens(by_pattern(ref, profile).split(), by_pattern(hyp, profile).split())
    ops = align(ref, hyp)
    errors = sum(op != "ok" for op, _, _ in ops)
    n_digits = sum(c in DIGITS for c in ref)
    digit_err = sum(1 for op, r, h in ops
                    if (op in ("sub", "del") and r in DIGITS) or (op == "ins" and h in DIGITS))
    confusions = Counter(f"{r}>{h if h is not None else '∅'}" for op, r, h in ops
                         if op in ("sub", "del") and r in DIGITS)
    ref_groups, hyp_groups = ref.split(), hyp.split()
    gops = align_tokens(ref_groups, hyp_groups)
    return {"cer": errors / max(1, len(ref)), "der": digit_err / max(1, n_digits), "digits": n_digits,
            "digit_errors": digit_err, "groups": len(ref_groups), "groups_ok": gops,
            "groups_ok_pattern": gops if groups_pat is None else groups_pat, "confusions": dict(confusions)}


def align_tokens(ref: list[str], hyp: list[str]) -> int:
    """Số nhóm của đáp án được đọc ĐÚNG TRỌN (căn Levenshtein theo nhóm)."""
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), dtype=np.int32)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    ok = 0
    i, j = n, m
    while i > 0 and j > 0:
        if d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            ok += ref[i - 1] == hyp[j - 1]
            i, j = i - 1, j - 1
        elif d[i, j] == d[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    return ok


# ---------- chạy ----------
_DECODERS: dict = {}
_MODEL = None


def _decoder(pid: str, name: str) -> Decoder | None:
    key = (pid, name)
    if key not in _DECODERS:
        if name == "app":
            dec = Decoder(pid, engine="onnx", model_path=_MODEL, lm=True)
        elif name == "model+LM":
            dec = Decoder(pid, engine="onnx", model_path=_MODEL, lm=True, fallback=False)
        elif name == "model":
            dec = Decoder(pid, engine="onnx", model_path=_MODEL, lm=False, fallback=False)
        elif name == "auto":
            dec = Decoder("auto", engine="onnx", model_path=_MODEL, lm=True)
        elif name == "dsp":
            dec = Decoder(pid, engine="baseline", lm=False)
        elif name == "deepcw":
            dec = Decoder(pid, engine="deepcw", lm=False) if pid == "en" else None
        elif name == "live":             # đúng cấu hình LiveWorker._ensure_decoder
            dec = Decoder(pid, engine="onnx", model_path=_MODEL, lm=True, fallback=False,
                          skip_silent_windows=True, numbers=False, keyed=False)
        elif name == "live-auto":
            dec = Decoder("auto", engine="onnx", model_path=_MODEL, lm=True, fallback=False,
                          skip_silent_windows=True, numbers=False, keyed=False)
        else:
            raise ValueError(name)
        _DECODERS[key] = dec
    return _DECODERS[key]


def live_decode(dec: Decoder, x: np.ndarray) -> tuple[str, str]:
    """Như một phiên nghe: đẩy từng khối 0,1 s, flush cuối phiên. Trả (văn bản, ngôn ngữ)."""
    from morsedesk.model.stream import StreamDecoder

    stream = StreamDecoder(decoder=dec)
    try:
        for i in range(0, len(x), LIVE_BLOCK):
            stream.push(x[i:i + LIVE_BLOCK])
        up = stream.flush()
        return up.text, up.language
    finally:
        stream.reset()


def run_job(job: tuple) -> dict:
    global _MODEL
    lang, kind, keying, wpm, snr, k, configs, _MODEL = job
    pid = LANGS[lang]
    profile = load_profile(pid)
    seed = zlib.crc32(f"num|{lang}|{kind}|{keying}|{wpm}|{snr}|{k}".encode())
    text = make_text(kind, profile, np.random.default_rng(seed))
    x = render(Encoder(pid), text, keying, wpm, snr, seed)
    row = {"lang": lang, "kind": kind, "keying": keying, "wpm": wpm, "snr": snr, "k": k,
           "seconds": len(x) / 8000, "ref": text}
    for name in configs:
        dec = _decoder(pid, name)
        if dec is None:
            continue
        if name.startswith("live"):
            hyp, language, by = *live_decode(dec, x), "live"
        else:
            r = dec.decode_array(x, 8000)
            hyp, language, by = r.text, r.language, r.decoded_by
        row[name] = {"hyp": hyp, "language": language, "decoded_by": by, **score(text, hyp, profile)}
    return row


def summarize(rows: list[dict], configs: tuple[str, ...]) -> list[str]:
    lines = []
    head = f"{'':28s}" + "".join(f"{c:>26s}" for c in configs)
    lines.append("DER (lỗi chữ số) / nhóm đúng trọn [theo mẫu Morse] — theo loại nội dung")
    lines.append(head)

    def agg(sel, name):
        rs = [r[name] for r in sel if name in r]
        if not rs:
            return "—"
        der = sum(r["digit_errors"] for r in rs) / max(1, sum(r["digits"] for r in rs))
        n = max(1, sum(r["groups"] for r in rs))
        gok = sum(r["groups_ok"] for r in rs) / n
        gpat = sum(r.get("groups_ok_pattern", r["groups_ok"]) for r in rs) / n
        return f"{100 * der:6.1f}% / {100 * gok:5.1f}% [{100 * gpat:5.1f}%]"

    for key, label in ([("kind", k) for k in KINDS] + [("keying", k) for k in KEYINGS]
                       + [("wpm", w) for w in sorted({r['wpm'] for r in rows})]
                       + [("snr", s) for s in sorted({r['snr'] for r in rows})]
                       + [("lang", lg) for lg in LANGS]):
        sel = [r for r in rows if r[key] == label]
        if sel:
            lines.append(f"{key}={label!s:<22s}" + "".join(f"{agg(sel, c):>26s}" for c in configs))
    lines.append(f"{'TỔNG':28s}" + "".join(f"{agg(rows, c):>26s}" for c in configs))
    lines.append("")
    lines.append("CER toàn văn bản (mọi ký tự):")
    for c in configs:
        rs = [r[c] for r in rows if c in r]
        if rs:
            lines.append(f"  {c:10s} {100 * float(np.mean([x['cer'] for x in rs])):6.2f} %")
    for c in configs:
        conf = Counter()
        for r in rows:
            if c in r:
                conf.update(r[c]["confusions"])
        if conf:
            lines.append(f"nhầm chữ số nhiều nhất ({c}): " + ", ".join(f"{k}×{v}" for k, v in conf.most_common(14)))
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=1)
    ap.add_argument("--wpm", default="15,25")
    ap.add_argument("--snr", default="20,8")
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--keyings", default=",".join(KEYINGS))
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", default="runs/numeric")
    ap.add_argument("--model", default=None)
    ap.add_argument("--configs", default="app,model+LM,model,auto,dsp,deepcw")
    a = ap.parse_args()
    configs = tuple(c for c in a.configs.split(",") if c)
    wpms = [float(w) for w in a.wpm.split(",")]
    snrs = [float(s) for s in a.snr.split(",")]
    jobs = [(lang, kind, keying, w, s, k, configs, a.model)
            for lang in a.langs.split(",") for kind in a.kinds.split(",") for keying in a.keyings.split(",")
            for w in wpms for s in snrs for k in range(a.per_cell)]
    t0 = time.time()
    rows = map_parallel(run_job, jobs, a.workers if a.workers is not None else default_workers())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    text = "\n".join(summarize(rows, configs))
    (out / "summary.txt").write_text(text + "\n", encoding="utf-8")
    minutes = sum(r["seconds"] for r in rows) / 60
    print(f"{len(rows)} bản tin, {minutes:.0f} phút âm thanh, {time.time() - t0:.0f} s")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
