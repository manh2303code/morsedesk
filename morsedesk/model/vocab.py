"""Từ vựng đầu ra của mô hình: 65 lớp là các mẫu chấm gạch, không phải chữ.

Thứ tự cố định: <blank>, <space>, <unk>, 26 mẫu Latin ITU, 5 mẫu chỉ có trong
bảng Nga, 10 số, 18 dấu câu ITU, 3 prosign có mẫu riêng.
"""

from __future__ import annotations

BLANK = "<blank>"
SPACE = "<space>"
UNK = "<unk>"

LATIN: dict[str, str] = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
}

# Ш, Ч, Ю, Я, Э: mẫu không có trong 26 chữ Latin ITU
RUSSIAN_ONLY: list[str] = ["----", "---.", "..--", ".-.-", "..-.."]

DIGITS: dict[str, str] = {
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}

PUNCT: dict[str, str] = {
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    ";": "-.-.-.", "=": "-...-", "+": ".-.-.", "-": "-....-", "_": "..--.-",
    '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
}

PROSIGNS: dict[str, str] = {
    "SK": "...-.-",
    "SOS": "...---...",
    "ERR": "........",
}


def build_patterns() -> list[str]:
    """Danh sách 62 mẫu theo thứ tự cố định, báo lỗi nếu trùng."""
    ordered = (
        list(LATIN.values())
        + RUSSIAN_ONLY
        + list(DIGITS.values())
        + list(PUNCT.values())
        + list(PROSIGNS.values())
    )
    seen: set[str] = set()
    for p in ordered:
        if p in seen:
            raise ValueError(f"mẫu trùng trong từ vựng: {p}")
        if set(p) - {".", "-"}:
            raise ValueError(f"mẫu chứa ký tự lạ: {p!r}")
        seen.add(p)
    return ordered


class Vocab:
    blank_id = 0
    space_id = 1
    unk_id = 2

    def __init__(self) -> None:
        self.tokens: list[str] = [BLANK, SPACE, UNK] + build_patterns()
        self._index: dict[str, int] = {t: i for i, t in enumerate(self.tokens)}

    def __len__(self) -> int:
        return len(self.tokens)

    def id(self, token: str) -> int:
        return self._index[token]

    def token(self, i: int) -> str:
        return self.tokens[i]

    def is_pattern(self, token: str) -> bool:
        return token in self._index and self._index[token] >= 3

    @property
    def patterns(self) -> list[str]:
        return self.tokens[3:]


VOCAB = Vocab()
