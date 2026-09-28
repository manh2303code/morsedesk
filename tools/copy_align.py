"""Căn BẢN CHÉP của nhân viên vào đáp án giám khảo LLM (T7) — chỉ ở vùng nhóm số (sau RMKS).

Đáp án giám khảo là cái NGHE được trong âm thanh (mẫu chấm-gạch từng ký tự); bản chép là nội dung nhân viên
nhận (đã bỏ nhóm đánh hỏng trước `?`, xóa 8 chấm). Phím nhẹ làm giám khảo đọc nhầm số chấm (`U`/`V`, `D`/`N`,
`5`/`6`) — bản chép gỡ được những chỗ đó. Quy tắc:
- căn theo nghĩa (số viết tắt A1 U2 V3 D8 N9 T0 = chữ số), ưu tiên khớp lần phát SAU (nhóm phát lại sau `?`);
- ký tự khớp: bỏ cờ "không chắc"; lệch: đổi sang chữ số của bản chép, giữ lối đánh (đủ/viết tắt) mà người
  gửi dùng cho chữ số đó nhiều nhất trong bản tin, ghi chú lại. Chỉ bỏ cờ khi bản chép trùng cách đọc của MỘT
  giám khảo hoặc lệch đúng 1 phần tử chấm/gạch (V/U, D/N, 6/5, E/T — lỗi của phím nhẹ); lệch xa hơn (đoạn
  fading sâu: `M` -> `7`) thì sửa nhưng GIỮ cờ không chắc;
- dấu cách vùng nhóm theo ranh giới nhóm của bản chép; ký tự bản chép không có (nhóm hỏng, `?`) giữ nguyên;
- KHÔNG sửa ngoài vùng nhóm (hô hiệu trong bản chép có thể là hô hiệu thật, khác cái được phát: 352 phát
  KK3J, bản chép ghi RY2J — đo nhịp phím 28/09 xác nhận KK3J);
- mỗi ký tự khớp một nhóm của bản chép mang `group` (chỉ số nhóm); `copy_groups` = các nhóm của bản chép.

    uv run python tools/copy_align.py IN.ref.json "BẢN CHÉP" OUT.ref.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.net_eval import CUT, PATTERN_OF, ch_of  # noqa: E402

CUT_OF = {d: c for c, d in CUT.items()}


def copy_groups(copy: str) -> list[str]:
    """Các nhóm số (toàn chữ số, 4 ký tự) sau RMKS trong bản chép."""
    words = re.split(r"[\s/]+", copy.upper())
    try:
        start = words.index("RMKS") + 1
    except ValueError:
        start = 0
    return [w for w in words[start:] if len(w) == 4 and w.isdigit()]


def digit_of(p: str) -> str:
    c = ch_of(p)
    return CUT.get(c, c)


def _pat_dist(a: str, b: str) -> int:
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[-1]


def _plausible(it: dict, new: str) -> bool:
    """Bản chép lệch <= 1 phần tử so với cách đọc của một giám khảo (ghi chú "B p / C q") hoặc của đáp án."""
    m = re.match(r"B (\S+) / C (\S+)", it.get("note", ""))
    reads = [it["pattern"], *(m.groups() if m else ())]
    return min(_pat_dist(r, new) for r in reads) <= 1


def align(items: list[dict], chars: list[str]) -> list[tuple[str, int | None, int | None]]:
    """Levenshtein theo nghĩa. Bỏ qua lần đánh HỎNG (tới 4 ký tự ngay trước `?` / 8 chấm xóa, và chính dấu đó)
    chỉ tốn nửa giá -> khớp lần phát lại; hòa thì truy ngược ưu tiên đường chéo từ CUỐI (lần phát sau)."""
    a = [digit_of(it["pattern"]) for it in items]
    w = [1.0] * len(items)
    for k, it in enumerate(items):
        if it["pattern"] in ("..--..", "........"):
            for q in range(max(0, k - 4), k + 1):
                w[q] = 0.5
    n, m = len(a), len(chars)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = d[i - 1][0] + w[i - 1]
    for j in range(1, m + 1):
        d[0][j] = float(j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + w[i - 1], d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != chars[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (a[i - 1] != chars[j - 1]):
            ops.append(("=" if a[i - 1] == chars[j - 1] else "S", i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + w[i - 1]:
            ops.append(("D", i - 1, None))
            i -= 1
        else:
            ops.append(("I", None, j - 1))
            j -= 1
    return ops[::-1]


def apply_copy(ref: dict, copy: str) -> tuple[dict, dict]:
    items = [dict(it) for it in ref["items"]]
    groups = copy_groups(copy)
    chars = [c for g in groups for c in g]
    starts = {4 * k for k in range(len(groups))}
    # vùng nhóm trong đáp án: sau RMKS (mẫu R M K S liền nhau) nếu có, không thì cả bản tin
    pats = [it["pattern"] for it in items]
    rmks = [".-.", "--", "-.-", "..."]
    lo = next((i + 4 for i in range(len(pats) - 3) if pats[i:i + 4] == rmks), 0)
    ops = align(items[lo:], chars)
    ops = [(op, None if i is None else i + lo, j) for op, i, j in ops]
    # lối đánh người gửi dùng cho từng chữ số (đủ hay viết tắt), đếm trên chỗ khớp
    style: dict[str, Counter] = {}
    for op, i, j in ops:
        if op == "=":
            style.setdefault(chars[j], Counter())[ch_of(items[i]["pattern"]) in CUT] += 1
    st = Counter()
    prev_aligned = True
    for op, i, j in ops:
        if op in "=S":
            it = items[i]
            if op == "S":
                dg = chars[j]
                cut = dg in CUT_OF and style.get(dg, Counter())[True] > style.get(dg, Counter())[False]
                new = PATTERN_OF[CUT_OF[dg] if cut else dg]
                sure = _plausible(it, new)
                it["note"] = (it.get("note", "") + f"; bản chép: {ch_of(it['pattern'])} -> {ch_of(new)}"
                              + ("" if sure else " (lệch xa, giữ không chắc)")).lstrip("; ")
                it["pattern"] = new
            else:
                sure = True
            st[op] += 1
            st["unsure_cleared"] += bool(it.get("unsure")) and sure
            it["unsure"] = bool(it.get("unsure")) and not sure
            it["space_before"] = j in starts
            it["group"] = j // 4
            prev_aligned = True
        elif op == "D":
            if i >= lo and prev_aligned:
                items[i]["space_before"] = True           # nhóm hỏng / `?` / xóa: đứng riêng
            prev_aligned = False
            st["D"] += 1
        else:
            st["I"] += 1
    out = dict(ref, items=items, operator_copy=copy, copy_groups=groups)
    return out, dict(st)


def main() -> None:
    src, copy, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    ref = json.loads(Path(src).read_text(encoding="utf-8"))
    out, st = apply_copy(ref, copy)
    Path(dst).write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{dst}: {len(out['copy_groups'])} nhóm bản chép; khớp {st.get('=', 0)}, sửa {st.get('S', 0)}, "
          f"bỏ cờ không chắc {st.get('unsure_cleared', 0)}, đáp án thừa {st.get('D', 0)}, "
          f"bản chép thừa (không nghe được) {st.get('I', 0)}")
    for it in out["items"]:
        if "bản chép" in it.get("note", ""):
            print(f"   {it['t']:>7}  {it['note']}")


if __name__ == "__main__":
    main()
