"""T7: điện văn mạng CW THẬT (định dạng M89/M95), đáp án từng ký tự do giám khảo LLM + bản chép nhân viên.

Chấm ba cách (docs/research/06-net-traffic-light-keying.md):
- `pat`: CER theo MẪU chấm-gạch, bỏ dấu cách; số viết tắt của điện mạng coi như chữ số của nó (A = 1: app đổi
  số viết tắt trong thân điện thành chữ số, morsedesk/traffic.py); Kirin cùng mẫu = đúng;
- cụm thủ tục đánh liền (`HR 7G GA` = HR MSG GA, cùng chuỗi chấm-gạch, chỉ khác chỗ ngắt ký tự) được chuẩn hóa
  ở CẢ HAI phía trước khi so (morsedesk.traffic.PHRASES): đáp án ghi cái được đánh, app hiện ý định;
- `sem`: CER theo NGHĨA — số viết tắt trong nhóm số quy về chữ số (A1 U2 V3 D8 N9 T0), bỏ dấu cách; ký tự đáp
  án thuộc một nhóm của bản chép (`group`) luôn là chữ số; ở MÀO ĐẦU cột này thiên lệch: nó quy số viết tắt theo cách
  ngắt từ của giám khảo (ngắt theo cảm nhận), `TT` đứng riêng trong đáp án không thành `00` — dùng `pat`;
- `body`: số nhóm 4 ký tự của thân điện (giữa `=` và `<AR>`) đúng trọn, bỏ phần đánh hỏng trước `?`;
  đáp án đã căn bản chép (tools/copy_align.py) thì nhóm lấy theo trường `group` (RMKS + thân);
- `copy`: số nhóm của BẢN CHÉP nhân viên (`copy_groups`) mà app ra đúng trọn theo nghĩa — căn chuỗi nhóm
  của app (từ 4 ký tự toàn số/số viết tắt) với chuỗi nhóm bản chép. Thước đo gần người dùng nhất.

    uv run python tools/net_eval.py [--configs app,en,greedy] [--manifest testdata/private/t7/manifest.jsonl]

Manifest: mỗi dòng {"path": WAV, "ref": FILE.ref.json}; FILE.ref.json = {"items": [{"t", "pattern",
"space_before", "unsure"}, ...]}.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from morsedesk.lm.profile import load_profile  # noqa: E402

EN, RU, KK = load_profile("en"), load_profile("ru"), load_profile("kk-cyrl-ru")
CUT = {"A": "1", "U": "2", "V": "3", "D": "8", "N": "9", "T": "0"}
NUMERIC = set("0123456789") | set(CUT)
PATTERN_OF = {}
for prof in (EN, RU, KK):
    for ch, p in prof.letter_to_pattern.items():
        PATTERN_OF.setdefault(ch, p)
    for ch, p in prof.prosign_to_pattern.items():
        PATTERN_OF.setdefault(ch, p)
PATTERN_OF["+"] = ".-.-."
CH_OF = {}
for ch, p in EN.letter_to_pattern.items():
    CH_OF.setdefault(p, ch)
for ch, p in EN.prosign_to_pattern.items():
    CH_OF.setdefault(p, ch)


def ch_of(p: str) -> str:
    return CH_OF.get(p, "<" + p + ">")


def text_tokens(text: str) -> list[tuple[str, bool]]:
    """Chữ (mọi bảng) -> [(mẫu, dấu cách trước)]; prosign <..> là một ký tự."""
    out, i, space = [], 0, False
    while i < len(text):
        c = text[i]
        if c.isspace():
            space = True
            i += 1
            continue
        if c == "<" and ">" in text[i:]:
            j = text.index(">", i)
            tok, i = text[i:j + 1], j + 1
        else:
            tok, i = c, i + 1
        out.append((PATTERN_OF.get(tok, "?" + tok), space and bool(out)))
        space = False
    return out


def ref_tokens(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["items"]


def ref_copy(path: Path) -> list[str]:
    return json.loads(Path(path).read_text(encoding="utf-8")).get("copy_groups", [])


def lev_ops(a: list, b: list) -> tuple[int, list]:
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        ai = a[i - 1]
        row, prev = d[i], d[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (ai != b[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ops.append(("=" if a[i - 1] == b[j - 1] else "S", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("D", i - 1, None))
            i -= 1
        else:
            ops.append(("I", None, j - 1))
            j -= 1
    return d[n][m], ops[::-1]


def semantic(tokens: list[tuple[str, bool]]) -> list[str]:
    """Chuỗi ký tự theo nghĩa: trong "từ" toàn số/số viết tắt có ít nhất một chữ số, số viết tắt -> số."""
    words, cur = [], []
    for p, sp in tokens:
        if sp and cur:
            words.append(cur)
            cur = []
        cur.append(ch_of(p))
    if cur:
        words.append(cur)
    out = []
    for w in words:
        if any(c.isdigit() for c in w) and all(c in NUMERIC for c in w):
            w = [CUT.get(c, c) for c in w]
        out += w
    return out


def body_groups(ref: list[dict]) -> list[list[int]]:
    """Chỉ số ký tự của từng nhóm 4 ký tự thân điện (giữa `-...-` cuối cùng trước thân và `.-.-.`)."""
    if any("group" in it for it in ref):
        by: dict[int, list[int]] = {}
        for i, it in enumerate(ref):
            if "group" in it:
                by.setdefault(it["group"], []).append(i)
        return [g for _, g in sorted(by.items()) if len(g) == 4]
    pats = [it["pattern"] for it in ref]
    try:
        start = max(i for i, p in enumerate(pats) if p == "-...-") + 1
    except ValueError:
        return []
    end = next((i for i in range(start, len(pats)) if pats[i] == ".-.-."), len(pats))
    idx = list(range(start, end))
    for q in [i for i in idx if pats[i] == "..--.."]:          # nhóm đánh hỏng trước `?`: bỏ
        idx = [i for i in idx if i not in (q, q - 1, q - 2)]
    idx = [i for i in idx if pats[i] != "........"]
    return [idx[k:k + 4] for k in range(0, len(idx) - len(idx) % 4, 4)]


def copy_hits(copy_groups: list[str], hyp_text: str) -> int:
    """Số nhóm bản chép có trong kết quả ĐÚNG NHƯ HIỆN RA (từ 4 ký tự, mọi bảng chữ quy về mẫu -> Latin,
    số viết tắt -> số), đúng thứ tự (căn chuỗi nhóm, như LCS). Nhóm dính liền nhau = sai."""
    words, cur = [], []
    for p, sp in text_tokens(hyp_text):
        if sp and cur:
            words.append(cur)
            cur = []
        cur.append(ch_of(p))
    if cur:
        words.append(cur)
    hyp = ["".join(CUT.get(c, c) for c in w) for w in words if len(w) == 4 and all(c in NUMERIC for c in w)]
    n, m = len(copy_groups), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = max(d[i - 1][j], d[i][j - 1], d[i - 1][j - 1] + (copy_groups[i - 1] == hyp[j - 1]))
    return d[n][m]


def canon(p: str) -> str:
    """Số viết tắt của điện mạng -> mẫu chữ số đủ (A1 U2 V3 D8 N9 T0)."""
    c = CH_OF.get(p)
    return PATTERN_OF[CUT[c]] if c in CUT else p


def phrase_norm(tokens: list[tuple[str, bool]]) -> tuple[list[tuple[str, bool]], list[int]]:
    """Cụm thủ tục theo chuỗi chấm-gạch -> chữ của cụm (như app làm ở mào đầu). Trả (token mới, chỉ số token gốc
    của từng token mới). Áp CẢ đáp án lẫn kết quả nên so công bằng."""
    from morsedesk.traffic import _phrases
    pats = [p for p, _ in tokens]
    hits = _phrases(pats, list(range(len(pats))), lambda q: "\x00" + q)
    out, owner = [], []
    for i, (p, sp) in enumerate(tokens):
        if i in hits:
            text, start = hits[i]
            parts = [q for q in text.split("\x00") if q]
            for j, q in enumerate(parts):
                out.append((q, (start or sp) if j == 0 else False))
                owner.append(i)
        else:
            out.append((p, sp))
            owner.append(i)
    return out, owner


def score(ref: list[dict], hyp_text: str, copy_groups: list[str] | None = None) -> dict:
    rt, owner = phrase_norm([(it["pattern"], it.get("space_before", False)) for it in ref])
    a = [canon(p) for p, _ in rt]
    hyp, _ = phrase_norm(text_tokens(hyp_text))
    b = [canon(p) for p, _ in hyp]
    dist, ops = lev_ops(a, b)
    bad_pos = {i for op, i, _ in ops if op in "SD"}
    ok = {owner[i] for op, i, _ in ops if op == "="} - {owner[i] for i in bad_pos}
    ins_after, prev = set(), None
    for op, i, _ in ops:
        if op == "I" and prev is not None:
            ins_after.add(owner[prev])
        if i is not None:
            prev = i
    sure_bad = sum(1 for op, i, _ in ops if op in "SD" and not ref[owner[i]].get("unsure"))
    n_sure = sum(1 for it in ref if not it.get("unsure"))
    ins = sum(1 for op, *_ in ops if op == "I")
    rs = semantic(rt)
    rs = [CUT.get(c, c) if "group" in ref[owner[k]] else c for k, c in enumerate(rs)]
    hs = semantic(hyp)
    sdist, _ = lev_ops(rs, hs)
    groups = body_groups(ref)
    g_ok = sum(1 for g in groups if all(k in ok for k in g) and not any(k in ins_after for k in g[:-1]))
    cg = copy_groups or []
    return {"n": len(a), "pat": dist, "sure_bad": sure_bad + ins, "n_sure": n_sure, "sem": sdist,
            "n_sem": len(rs), "groups": len(groups), "groups_ok": g_ok,
            "copy": len(cg), "copy_ok": copy_hits(cg, hyp_text) if cg else 0}


CONFIGS = {
    "app": dict(profile="auto", lm=True),        # đúng như trang Giải mã mặc định
    "en": dict(profile="en", lm=True),
    "greedy": dict(profile="en", lm=False),
    # chế độ NGHE đúng như LiveWorker: StreamDecoder bọc Decoder không nhịp phím, không xử lý số (tự làm)
    "live": dict(profile="auto", lm=True, live=True),
}
_DEC: dict = {}


def run_one(args):
    path, cfg_name, model = args
    from morsedesk.api import Decoder
    from morsedesk.audio.io import load_audio
    key = (cfg_name, model)
    c = CONFIGS[cfg_name]
    if key not in _DEC:
        kw = dict(engine="onnx", lm=c["lm"])
        if c.get("live"):
            kw.update(fallback=False, skip_silent_windows=True, numbers=False, keyed=False)
        if model:
            kw["model_path"] = model
        _DEC[key] = Decoder(c["profile"], **kw)
    x, sr = load_audio(path)
    if c.get("live"):
        from morsedesk.audio.io import resample
        from morsedesk.model.stream import StreamDecoder
        from tools.long_random_eval import LIVE_BLOCK
        x = resample(x, sr, 8000) if sr != 8000 else x
        stream = StreamDecoder(decoder=_DEC[key])
        try:
            for i in range(0, len(x), LIVE_BLOCK):
                stream.push(x[i:i + LIVE_BLOCK])
            return path, cfg_name, stream.flush().text
        finally:
            stream.reset()
    return path, cfg_name, _DEC[key].decode_array(x, sr).text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "testdata/private/t7/manifest.jsonl"))
    ap.add_argument("--configs", default="app,en,greedy")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default=None, help="thư mục ghi kết quả JSON")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    rows = [json.loads(line) for line in Path(a.manifest).read_text(encoding="utf-8").splitlines() if line.strip()]
    cfgs = a.configs.split(",")
    jobs = [(r["path"], c, a.model) for r in rows for c in cfgs]
    with ProcessPoolExecutor(min(a.workers, len(jobs))) as ex:
        outs = list(ex.map(run_one, jobs))
    texts = {(p, c): t for p, c, t in outs}
    tot = {c: dict(n=0, pat=0, sure_bad=0, n_sure=0, sem=0, n_sem=0, groups=0, groups_ok=0, copy=0, copy_ok=0)
           for c in cfgs}
    W = 34
    print(f"{'file':16s} " + " ".join(f"{c:>{W}s}" for c in cfgs))
    print(f"{'':16s} " + " ".join(f"{'pat%   sem%  nhóm  bản chép':>{W}s}" for _ in cfgs))

    def cell(t: dict) -> str:
        return (f"{100 * t['pat'] / t['n']:6.2f} {100 * t['sem'] / t['n_sem']:6.2f} {t['groups_ok']:3d}/{t['groups']:<3d}"
                f" {t['copy_ok']:3d}/{t['copy']:<3d}").rjust(W)
    results = []
    for r in rows:
        rp = ROOT / r["ref"] if not Path(r["ref"]).is_absolute() else Path(r["ref"])
        ref, cg = ref_tokens(rp), ref_copy(rp)
        cells = []
        for c in cfgs:
            s = score(ref, texts[(r["path"], c)], cg)
            for k in tot[c]:
                tot[c][k] += s[k]
            cells.append(cell(s))
            results.append({"path": r["path"], "config": c, "text": texts[(r["path"], c)], **s})
        print(f"{Path(r['path']).name[:16]:16s} " + " ".join(cells))
    print(f"{'TỔNG':16s} " + " ".join(cell(t) for t in tot.values()))
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
