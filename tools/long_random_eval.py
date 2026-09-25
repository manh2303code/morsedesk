"""Bản tin DÀI và NGẪU NHIÊN: model âm học + LM có đọc được không, và LM giúp hay hại?

T1/dev phần lớn là clip ngắn (một từ tới một câu), còn T2 chỉ có bản tin ARRL tiếng Anh. Phép thử
này dựng bản tin ~2 phút cho cả ba ngôn ngữ, ba loại nội dung:
- `natural`: câu THẬT lấy từ corpus/<lang>.holdout.txt — phần LM chưa từng thấy lúc dựng;
- `groups`:  nhóm 5 ký tự ngẫu nhiên (chữ + số của bảng mã) — kiểu điện mật mã, không có "nghĩa";
- `traffic`: điện vô tuyến trộn từ thật, hô hiệu ngẫu nhiên và số 3–4 chữ số.
Gõ máy (nhịp hoàn hảo) và gõ tay (đúng bộ gõ `jitter` của T1: lệch nhịp 15 %, sai khoảng cách
5 %), SNR 8 dB. Gõ máy thì app gần như luôn lấy bộ giải mã CỔ ĐIỂN (nhịp khớp lưới), nên để thấy
hai model làm được gì phải tắt nó đi. Bốn cách giải mã, ngôn ngữ biết trước trừ cột cuối:
- `app`:     đúng như sản phẩm (bộ cổ điển song song + model + LM);
- `model+LM`: chỉ model âm học + LM (tắt bộ cổ điển);
- `model`:   chỉ model âm học, không LM — so với cột trước là đúng phần đóng góp của LM;
- `auto`:    sản phẩm ở chế độ tự nhận ngôn ngữ.
Thêm `--configs live,live-auto`: chế độ NGHE TRỰC TIẾP đúng như LiveWorker (StreamDecoder, không bộ
cổ điển, bỏ cửa sổ không tone), đẩy âm thanh vào từng khối 0,1 s rồi flush — biết trước ngôn ngữ
và tự nhận. Chậm: mỗi nửa giây giải mã lại cả bộ đệm ~9,5 s.
Ghi đủ ref/hyp ra runs/long_random/rows.json.

Hai cột CER: theo CHỮ, và theo MẪU Morse (quy chữ Kazakh riêng, Ъ, Ё về chữ Nga cùng mã). Với
chuỗi ngẫu nhiên, nghe hoàn hảo cũng không phân biệt được Ә với А — cột thứ hai tách lỗi NGHE
khỏi giới hạn của chính bảng mã.

    uv run python tools/long_random_eval.py [--per-cell 3] [--wpm 20] [--workers N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from morsedesk.api import Decoder, Encoder  # noqa: E402
from morsedesk.data.channel import apply_channel, clean  # noqa: E402
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine  # noqa: E402
from morsedesk.data.synth import rescale_elements  # noqa: E402
from morsedesk.data.text import keep_supported  # noqa: E402
from morsedesk.encode.synth import elements_to_audio, tone_power  # noqa: E402
from morsedesk.encode.timing import tokens_to_elements, total_seconds  # noqa: E402
from morsedesk.lm.profile import load_profile  # noqa: E402
from morsedesk.metrics import cer  # noqa: E402
from morsedesk.model.stream import StreamDecoder  # noqa: E402
from morsedesk.parallel import default_workers, map_parallel  # noqa: E402

LANGS = {"en": "en", "ru": "ru", "kk": "kk-cyrl-ru"}
KINDS = ("natural", "groups", "traffic")
TARGET_CHARS = 200
SNR_DB = 8.0
KEYINGS = ("machine", "hand")
CONFIGS = ("app", "model+LM", "model", "auto")
LIVE_CONFIGS = ("live", "live-auto")
LIVE_BLOCK = 800            # 0,1 s ở 8 kHz — cỡ khối card âm thanh đẩy vào LiveWorker
_FLAT = str.maketrans("ӘҒҚҢӨҰҮҺІЪЁ", "АГКНОУУХИЬЕ")


def cer_pattern(ref: str, hyp: str) -> float:
    return cer(ref.translate(_FLAT), hyp.translate(_FLAT))


def alphabet(profile) -> list[str]:
    return sorted({ch for opts in profile.map.values() for ch in opts if len(ch) == 1 and ch.isalnum()})


def natural(lang: str, profile, rng) -> str:
    lines = Path(f"corpus/{lang}.holdout.txt").read_text(encoding="utf-8").splitlines()
    lines = [s for s in (keep_supported(ln.strip(), profile) for ln in lines) if len(s) > 20]
    out: list[str] = []
    while sum(len(s) + 1 for s in out) < TARGET_CHARS:
        out.append(lines[int(rng.integers(len(lines)))])
    return " ".join(out)


def groups(profile, rng) -> str:
    abc = alphabet(profile)
    return " ".join("".join(abc[int(rng.integers(len(abc)))] for _ in range(5))
                    for _ in range(TARGET_CHARS // 6))


def traffic(lang: str, profile, rng) -> str:
    words = natural(lang, profile, rng).split()
    letters = [c for c in alphabet(profile) if not c.isdigit()]

    def pick(n: int) -> str:
        return "".join(letters[int(rng.integers(len(letters)))] for _ in range(n))

    out: list[str] = []
    while sum(len(s) + 1 for s in out) < TARGET_CHARS:
        u = rng.random()
        if u < 0.25:
            out.append(f"{pick(2)}{int(rng.integers(10))}{pick(3)}")      # hô hiệu
        elif u < 0.45:
            out.append(str(int(rng.integers(100, 10000))))                 # số
        else:
            out.append(words[int(rng.integers(len(words)))])
    return keep_supported(" ".join(out), profile)


def make_text(kind: str, lang: str, profile, rng) -> str:
    if kind == "natural":
        return natural(lang, profile, rng)
    if kind == "groups":
        return groups(profile, rng)
    return traffic(lang, profile, rng)


def render(enc: Encoder, text: str, keying: str, wpm: float, seed: int) -> np.ndarray:
    """Âm thanh của `text` với kiểu gõ cho trước, kênh nhiễu trắng SNR_DB (giống bộ sinh T1)."""
    rng = np.random.default_rng(seed)
    keyer = machine(wpm) if keying == "machine" else KeyerParams(wpm, None, 3.0, 0.15, False, 0.0, 0.05, "jitter")
    nominal = tokens_to_elements(enc.to_tokens(text, strict=False), keyer.timing())
    elements = rescale_elements(apply_keyer(nominal, keyer, rng), total_seconds(nominal))
    signal = elements_to_audio(elements, 700.0, 8000, 0.8)
    pad = np.zeros(4000, dtype=np.float32)
    x = np.concatenate([pad, signal, pad])
    return apply_channel(x, clean(SNR_DB, 700.0), rng, 8000, tone_power(0.8)).astype(np.float32)


def summary(rows: list[dict], configs=CONFIGS) -> list[str]:
    lines = ["CER % — theo chữ [theo mẫu Morse]:   " + "   ".join(f"{n:^17s}" for n in configs)]
    for lang, pid in LANGS.items():
        for kind in KINDS:
            for keying in (*KEYINGS, None):
                sel = [r for r in rows if r["lang"] == lang and r["kind"] == kind
                       and (keying is None or r["keying"] == keying)]
                if not sel:
                    continue
                cells = []
                for n in configs:
                    c = 100 * np.mean([r[n]["cer"] for r in sel])
                    f = 100 * np.mean([r[n]["cer_pattern"] for r in sel])
                    cells.append(f"{c:6.2f} [{f:6.2f}]")
                auto = next((n for n in ("auto", "live-auto") if n in configs), None)
                wrong = (f"   tự nhận sai ngôn ngữ {sum(1 for r in sel if r[auto]['language'] != pid)}"
                         f"/{len(sel)}" if auto else "")
                tag = "chung" if keying is None else keying
                lines.append(f"  {lang} {kind:8s} {tag:6s}  " + "   ".join(cells) + wrong)
    return lines


_DECODERS: dict[str, dict[str, Decoder]] = {}


def _decoders(pid: str) -> dict[str, Decoder]:
    """Bốn cách giải mã của một ngôn ngữ; mỗi tiến trình dựng một lần."""
    if pid not in _DECODERS:
        _DECODERS[pid] = {
            "app": Decoder(pid, engine="onnx", lm=True),
            "model+LM": Decoder(pid, engine="onnx", lm=True, fallback=False),
            "model": Decoder(pid, engine="onnx", lm=False, fallback=False),
            "auto": Decoder("auto", engine="onnx", lm=True),
            # đúng cấu hình LiveWorker._ensure_decoder
            "live": Decoder(pid, engine="onnx", lm=True, fallback=False, skip_silent_windows=True),
            "live-auto": Decoder("auto", engine="onnx", lm=True, fallback=False, skip_silent_windows=True),
        }
    return _DECODERS[pid]


def live_decode(dec: Decoder, x: np.ndarray) -> tuple[str, str]:
    """Như một phiên nghe: đẩy từng khối, flush cuối phiên. Trả (văn bản, ngôn ngữ)."""
    stream = StreamDecoder(decoder=dec)
    try:
        for i in range(0, len(x), LIVE_BLOCK):
            stream.push(x[i:i + LIVE_BLOCK])
        up = stream.flush()
        return up.text, up.language
    finally:
        stream.reset()                      # gỡ khóa ngôn ngữ trước bản tin sau


def run_job(job: tuple) -> dict:
    lang, kind, keying, k, wpm, configs = job
    pid = LANGS[lang]
    profile = load_profile(pid)
    seed = zlib.crc32(f"{lang}|{kind}|{keying}|{k}".encode())
    text = make_text(kind, lang, profile, np.random.default_rng(seed))
    x = render(Encoder(pid), text, keying, wpm, seed)
    row = {"lang": lang, "kind": kind, "keying": keying, "k": k, "seconds": len(x) / 8000, "ref": text}
    for name in configs:
        dec = _decoders(pid)[name]
        if name in LIVE_CONFIGS:
            hyp, language, by = *live_decode(dec, x), "live"
        else:
            r = dec.decode_array(x, 8000)
            hyp, language, by = r.text, r.language, r.decoded_by
        row[name] = {"hyp": hyp, "cer": cer(text, hyp), "cer_pattern": cer_pattern(text, hyp),
                     "language": language, "decoded_by": by}
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=3, help="số bản tin cho mỗi (ngôn ngữ, loại, kiểu gõ)")
    ap.add_argument("--wpm", type=float, default=20.0)
    ap.add_argument("--workers", type=int, default=None, help="mặc định số lõi - 2")
    ap.add_argument("--out", default="runs/long_random")
    ap.add_argument("--configs", default=",".join(CONFIGS),
                    help=f"trong {', '.join(CONFIGS + LIVE_CONFIGS)}")
    a = ap.parse_args()
    configs = tuple(c for c in a.configs.split(",") if c)
    unknown = set(configs) - set(CONFIGS + LIVE_CONFIGS)
    if unknown:
        ap.error(f"cách giải mã không có: {', '.join(sorted(unknown))}")
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(lang, kind, keying, k, a.wpm, configs) for lang in LANGS for kind in KINDS for keying in KEYINGS
            for k in range(a.per_cell)]
    t0 = time.time()
    rows = map_parallel(run_job, jobs, a.workers if a.workers is not None else default_workers())
    audio_min = sum(r["seconds"] for r in rows) / 60
    (out_dir / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    text = chr(10).join(summary(rows, configs))
    (out_dir / "summary.txt").write_text(text + chr(10), encoding="utf-8")
    print(f"{len(rows)} bản tin, {audio_min:.0f} phút âm thanh x {len(configs)} cách giải mã"
          f" trong {time.time() - t0:.0f} s")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
