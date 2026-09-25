"""Hiệu chuẩn độ tin cậy của TỪ: ở mỗi mức tin cậy, thực tế bao nhiêu phần trăm từ là đúng?

Tooltip ở trang Giải mã và trang Nghe nói "từ ở mức này đúng khoảng X %". Con số đó phải ĐO, không
đặt tay. Công cụ này giải lại các bộ đo ở chế độ file (đúng như app) và chế độ nghe (đúng như
LiveWorker), ghép từng từ ra với đáp án (khớp dãy từ bằng difflib: từ nằm trong đoạn trùng khớp là
đúng), rồi đếm theo khoảng tin cậy. Ghi `morsedesk/app/data/confidence_calibration.json` cho giao diện.

    uv run python tools/calibrate_confidence.py [--workers N]

Nguồn: T4 (bản ghi thật), dev-OOV (clip ngắn, văn bản model chưa thấy, cả dải SNR/fading) và 54 bản
tin 2 phút của long_random_eval (file + nghe). KHÔNG dùng T1/dev: văn bản của chúng trùng danh sách
từ huấn luyện cũ nên lạc quan.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from morsedesk.api import Decoder, Encoder  # noqa: E402
from morsedesk.audio.io import load_audio  # noqa: E402
from morsedesk.lm.profile import load_profile  # noqa: E402
from morsedesk.parallel import default_workers, map_parallel  # noqa: E402

# Cận dưới của từng khoảng; ba mốc giao diện (0,5 và 0,8) nằm trong số này.
EDGES = [0.0, 0.3, 0.5, 0.65, 0.8, 0.9, 0.97]
OUT = Path("morsedesk/app/data/confidence_calibration.json")

_DEC: dict[str, Decoder] = {}


def _decoder(profile: str, live: bool) -> Decoder:
    key = f"{profile}|{live}"
    if key not in _DEC:
        _DEC[key] = (Decoder(profile, engine="onnx", lm=True, fallback=False, skip_silent_windows=True)
                     if live else Decoder(profile, engine="onnx", lm=True))
    return _DEC[key]


def mark(ref: str, words: list) -> list[tuple[float, bool]]:
    """(độ tin cậy, đúng?) cho từng từ giải ra."""
    ref_w = ref.split()
    hyp_w = [w.text for w in words]
    ok = [False] * len(hyp_w)
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, ref_w, hyp_w, autojunk=False).get_opcodes():
        if tag == "equal":
            for j in range(j1, j2):
                ok[j] = True
    return [(float(w.confidence), o) for w, o in zip(words, ok, strict=True)]


def run_job(job: tuple) -> dict:
    kind, source, profile, payload = job
    if kind == "file":
        x, sr = load_audio(payload["path"])
        r = _decoder(profile, False).decode_array(x, sr)
        return {"mode": "file", "source": source, "pairs": mark(payload["ref"], r.words)}
    # bản tin dài tổng hợp: dựng lại đúng như tools/long_random_eval.py
    sys.path.insert(0, "tools")
    import long_random_eval as L
    lang, text_kind, keying, k = payload
    pid = L.LANGS[lang]
    seed = zlib.crc32(f"{lang}|{text_kind}|{keying}|{k}".encode())
    text = L.make_text(text_kind, lang, load_profile(pid), np.random.default_rng(seed))
    x = L.render(Encoder(pid), text, keying, 20.0, seed)
    if kind == "long_file":
        r = _decoder(pid, False).decode_array(x, 8000)
        return {"mode": "file", "source": source, "pairs": mark(text, r.words)}
    from morsedesk.model.stream import StreamDecoder
    stream = StreamDecoder(decoder=_decoder(pid, True))
    try:
        for i in range(0, len(x), 800):
            stream.push(x[i:i + 800])
        up = stream.flush()
        return {"mode": "live", "source": source, "pairs": mark(text, up.committed_words)}
    finally:
        stream.reset()


MIN_BIN = 30        # khoảng ít từ hơn thì gộp với khoảng kế trên (con số quá nhiễu để nói ra)


def merge_small(bins: list[dict], min_n: int = MIN_BIN) -> list[dict]:
    """Gộp các khoảng có ít hơn `min_n` từ vào khoảng kế bên (trung bình có trọng số)."""
    out: list[dict] = []
    for b in bins:
        if out and (out[-1]["n"] < min_n or (b is bins[-1] and b["n"] < min_n)):
            a = out.pop()
            n = a["n"] + b["n"]
            acc = ((a["accuracy"] or 0) * a["n"] + (b["accuracy"] or 0) * b["n"]) / n if n else None
            b = {"min": a["min"], "max": b["max"], "n": n, "accuracy": round(acc, 4) if n else None}
        out.append(dict(b))
    return [b for b in out if b["n"] > 0]


def table(pairs: list[tuple[float, bool]]) -> list[dict]:
    out = []
    for lo, hi in zip(EDGES, EDGES[1:] + [1.01], strict=True):
        sel = [ok for c, ok in pairs if lo <= c < hi]
        out.append({"min": lo, "max": min(hi, 1.0), "n": len(sel),
                    "accuracy": round(float(np.mean(sel)), 4) if sel else None})
    return merge_small(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    jobs = []
    for manifest, source in (("testdata/private/t4/manifest.jsonl", "t4"),
                             ("testdata/generated/t1oov/manifest.jsonl", "dev-oov")):
        if Path(manifest).exists():
            for line in Path(manifest).read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                jobs.append(("file", source, r["profile"], {"path": r["path"], "ref": r["text_original"]}))
    sys.path.insert(0, "tools")
    import long_random_eval as L
    for lang in L.LANGS:
        for kind in L.KINDS:
            for keying in L.KEYINGS:
                for k in range(3):
                    jobs.append(("long_file", "long", None, (lang, kind, keying, k)))
                    jobs.append(("long_live", "long-live", None, (lang, kind, keying, k)))
    t0 = time.time()
    rows = map_parallel(run_job, jobs, a.workers if a.workers is not None else default_workers())
    by_mode: dict[str, list] = {"file": [], "live": []}
    for r in rows:
        by_mode[r["mode"]] += [tuple(p) for p in r["pairs"]]
    result = {"edges": EDGES, "measured": time.strftime("%Y-%m-%d"),
              "sources": sorted({r["source"] for r in rows}),
              "file": table(by_mode["file"]), "live": table(by_mode["live"])}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(jobs)} lượt giải trong {time.time() - t0:.0f} s -> {OUT}")
    for mode in ("file", "live"):
        print(mode, " | ".join(f"[{b['min']:.2f},{b['max']:.2f}) n={b['n']} đúng={b['accuracy']}"
                               for b in result[mode]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
