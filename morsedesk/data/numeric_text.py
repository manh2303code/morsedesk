"""Văn bản "điện số" cho dữ liệu huấn luyện (E18, 27/09): số dài, ngẫu nhiên, xen chữ và dấu câu.

Vì sao: E17 học 50 % câu thật + 20 % nhóm mã 1–8 ký tự trộn đều 54 ký tự, nên một nhóm TOÀN số 5 chữ
số gần như không bao giờ xuất hiện ((10/54)^5), dãy số liền dài hơn 8 thì không bao giờ. Trên số tổng
hợp gõ máy nó vẫn đọc đúng, nhưng gõ tay thì chèn dấu cách vào giữa dãy số dài (nhóm đúng 79 % ở dãy
8–16 chữ số) — "LM ngầm" của BiGRU cho rằng "từ" không dài như vậy. Trạm số thật còn đánh 0 bằng một
gạch dài (mẫu của T) và đánh các nhóm sát nhau; mô hình cần thấy cả hai.

Nhãn vẫn là MẪU Morse: `T` trong nhóm số là mẫu `-`; việc đọc nó thành 0 là của morsedesk/numbers.py.
"""

from __future__ import annotations

import numpy as np

DIGITS = "0123456789"
SEPARATORS = "./-:,=+?"
# Số viết tắt (mẫu của chữ Latin): 0 = T phổ biến nhất (trạm số), cả bộ trong điện thi đấu.
CUT_ZERO = {"0": "T"}
CUT_ALL = {"0": "T", "9": "N", "1": "A", "2": "U", "3": "V", "5": "E", "7": "B", "8": "D"}


def _d(rng: np.random.Generator, n: int) -> str:
    return "".join(DIGITS[int(rng.integers(10))] for _ in range(n))


def _cut(text: str, table: dict[str, str]) -> str:
    return "".join(table.get(c, c) for c in text)


def digit_groups(rng: np.random.Generator, n: int) -> str:
    size = int(rng.choice([5, 5, 5, 4, 3, 6, 7]))           # đa số nhóm 5 như điện số
    groups = [_d(rng, size) for _ in range(n)]
    u = rng.random()
    if u < 0.25:
        groups = [_cut(g, CUT_ZERO) for g in groups]
    elif u < 0.35:
        groups = [_cut(g, CUT_ALL) for g in groups]
    if rng.random() < 0.3:                                    # trạm số đánh mỗi nhóm hai lần
        groups = [g for g in groups for _ in range(2)]
    return " ".join(groups)


def digit_runs(rng: np.random.Generator, n: int) -> str:
    return " ".join(_d(rng, int(rng.integers(6, 15))) for _ in range(max(1, n // 3)))


def alnum_groups(letters: list[str], rng: np.random.Generator, n: int) -> str:
    abc = letters + list(DIGITS) * 2                          # số nặng gấp đôi chữ
    return " ".join("".join(abc[int(rng.integers(len(abc)))] for _ in range(int(rng.integers(3, 8))))
                    for _ in range(n))


def formatted(rng: np.random.Generator, n: int) -> str:
    out = []
    for _ in range(max(1, n // 2)):
        k = int(rng.integers(10))
        if k == 0:
            out.append(f"+{_d(rng, 1)} {_d(rng, 3)} {_d(rng, 3)}-{_d(rng, 2)}-{_d(rng, 2)}")
        elif k == 1:
            out.append(f"{_d(rng, 2)}.{_d(rng, 4)}N/{_d(rng, 3)}.{_d(rng, 4)}E")
        elif k == 2:
            out.append(f"{_d(rng, 2)}.{_d(rng, 2)}.{_d(rng, 4)} {_d(rng, 2)}:{_d(rng, 2)}")
        elif k == 3:
            out.append(f"{int(rng.integers(1, 30))}.{_d(rng, 3)}")
        elif k == 4:
            out.append(f"NR {_d(rng, int(rng.integers(3, 6)))} {_d(rng, 2)}/{_d(rng, 3)}")
        elif k == 5:
            out.append(f"{_d(rng, 1)},{_d(rng, 3)}.{_d(rng, 2)}")
        elif k == 6:
            a, b = int(rng.integers(1, 1000)), int(rng.integers(1, 1000))
            out.append(f"{a}+{b}={a + b}")
        elif k == 7:
            out.append(f"({_d(rng, 3)}) {_d(rng, 4)}-{_d(rng, 4)}")
        elif k == 8:
            out.append(f"{_d(rng, 3)} {_d(rng, 2)} = {_d(rng, 5)} {_d(rng, 5)}")
        else:
            out.append(f"5NN {_d(rng, 3)} {_d(rng, 4)}Z")
    return " ".join(out)


def punct_groups(rng: np.random.Generator, n: int) -> str:
    out = []
    for _ in range(n):
        s = SEPARATORS[int(rng.integers(len(SEPARATORS)))]
        out.append(s.join(_d(rng, int(rng.integers(1, 4))) for _ in range(int(rng.integers(2, 4)))))
    return " ".join(out)


def numeric_text(letters: list[str], rng: np.random.Generator, n: int, net_share: float = 0.0) -> str:
    """Một mẩu văn bản số; `letters`: chữ đơn của bảng mã (cho nhóm chữ-số). `net_share`: phần điện văn
    mạng CW (E20)."""
    u = rng.random()
    if u < net_share:                       # E20: điện văn mạng CW; 0 = phân bố y hệt E18
        return net_traffic(letters, rng, n)
    u = rng.random()
    if u < 0.35:
        return digit_groups(rng, n)
    if u < 0.55:
        return digit_runs(rng, n)
    if u < 0.70:
        return alnum_groups(letters, rng, n)
    if u < 0.88:
        return formatted(rng, n)
    return punct_groups(rng, n)


# ---- Điện văn mạng CW (28/09): định dạng M89/M95 của các file thật testdata/private/t7 ----
# Số viết tắt kiểu mạng này: 0 1 2 8 9 (và đôi khi 3) viết tắt, 4–7 đủ; bảng chung của app đọc lại được.
NET_CUT = {"0": "T", "1": "A", "2": "U", "3": "V", "8": "D", "9": "N"}
NET_PHRASES = ["HR MSG GA", "QSL?", "MSG AGN", "PSE CY", "GA", "K", "R", "QRU?", "QSL", "HR", "NIL"]


def _net_call(letters: list[str], rng: np.random.Generator) -> str:
    """Hô hiệu 4 ký tự: đa số toàn chữ Latin (CYHM, NJWY), đôi khi có số (MW3D, 2SLC)."""
    latin = [c for c in letters if "A" <= c <= "Z"] or list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    if rng.random() < 0.75:
        return "".join(latin[int(rng.integers(len(latin)))] for _ in range(4))
    abc = latin + list(DIGITS)
    return "".join(abc[int(rng.integers(len(abc)))] for _ in range(4))


def net_group(rng: np.random.Generator, cut_p: float) -> str:
    """Nhóm 4 ký tự của thân điện: chữ số, mỗi chữ số 0/1/2/3/8/9 viết tắt với xác suất `cut_p`."""
    return "".join(NET_CUT[c] if c in NET_CUT and rng.random() < cut_p else c for c in _d(rng, 4))


def net_traffic(letters: list[str], rng: np.random.Generator, n: int) -> str:
    """Một mẩu điện văn mạng CW (clip huấn luyện 4–12 s chỉ chứa một đoạn): gọi đài, mào đầu, thân điện
    nhóm 4 ký tự số viết tắt, kết; có tín hiệu xóa 8 chấm và `?` báo đánh lại như bản ghi thật."""
    cut_p = float(rng.choice([0.0, 0.35, 0.6, 0.9]))
    c1, c2 = _net_call(letters, rng), _net_call(letters, rng)
    k = int(rng.integers(6))
    if k == 0:
        parts = ["VV" if rng.random() < 0.6 else "VVV", c1, c1, "DE", c2, c2]
    elif k == 1:
        parts = [c1, "DE", c2, str(rng.choice(NET_PHRASES))]
    elif k == 2:
        dtg = f"{int(rng.integers(1, 40)):02d} {int(rng.integers(1, 13)):02d}{int(rng.integers(1, 32)):02d} " \
              f"{int(rng.integers(0, 24)):02d}{int(rng.integers(0, 60)):02d}"
        parts = ["NR", f"{int(rng.integers(1, 1000)):03d}/CK", str(int(rng.integers(5, 120))), dtg]
        if rng.random() < 0.5:
            parts = ["HR MSG GA"] + parts
    elif k == 3:
        parts = ["RMKS"] + [net_group(rng, cut_p) for _ in range(int(rng.integers(1, 5)))] + ["="]
    else:
        parts = [net_group(rng, cut_p) for _ in range(max(2, n))]
    if rng.random() < 0.15:                     # xóa: 8 chấm rồi đánh lại nhóm cuối
        i = int(rng.integers(len(parts)))
        parts = parts[:i + 1] + ["<ERR>"] + parts[i:]
    elif rng.random() < 0.1:                    # nhóm hỏng + `?` + đánh lại
        i = int(rng.integers(len(parts)))
        parts = parts[:i] + [parts[i][: max(1, len(parts[i]) // 2)] + " ?"] + parts[i:]
    if rng.random() < 0.15:
        parts.append(str(rng.choice(["<AR>", "<AR> HR", "K", "=", "<BT>"])))
    return " ".join(parts)


def is_numeric_heavy(text: str) -> bool:
    chars = [c for c in text if not c.isspace()]
    return bool(chars) and sum(c.isdigit() for c in chars) >= 0.5 * len(chars)
