"""Bảng chữ của mô hình ngôn ngữ ký tự cho một profile."""

from __future__ import annotations

import json
from pathlib import Path

from morsedesk.lm.profile import Profile

BOS = "<s>"
EOS = "</s>"
UNK = "<unk>"
SPACE_CHAR = " "
SPACE_TOKEN = "▁"  # U+2581, thay khoảng trắng trong file token hóa cho lmplz


class LMAlphabet:
    def __init__(self, symbols: list[str]) -> None:
        if symbols[:4] != [BOS, EOS, UNK, SPACE_CHAR]:
            raise ValueError("bốn ký hiệu đầu phải là <s>, </s>, <unk>, ' '")
        if len(set(symbols)) != len(symbols):
            raise ValueError("bảng chữ có ký hiệu trùng")
        self.symbols = list(symbols)
        self.index = {s: i for i, s in enumerate(self.symbols)}
        self.bos_id, self.eos_id, self.unk_id, self.space_id = 0, 1, 2, 3

    @classmethod
    def for_profile(cls, profile: Profile) -> LMAlphabet:
        letters: list[str] = []
        for options in profile.map.values():
            for ch in options:
                if ch not in letters:
                    letters.append(ch)
        return cls([BOS, EOS, UNK, SPACE_CHAR] + letters)

    def __len__(self) -> int:
        return len(self.symbols)

    def encode(self, text: str) -> list[int]:
        return [self.index.get(ch, self.unk_id) for ch in text]

    def decode(self, ids) -> str:
        return "".join(self.symbols[int(i)] for i in ids)

    def to_tokens_line(self, text: str) -> str:
        return " ".join(SPACE_TOKEN if ch == SPACE_CHAR else ch for ch in text)

    def from_tokens_line(self, line: str) -> str:
        return "".join(SPACE_CHAR if tok == SPACE_TOKEN else tok for tok in line.split())

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps({"symbols": self.symbols}, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> LMAlphabet:
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["symbols"])
