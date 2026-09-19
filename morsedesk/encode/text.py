"""Chuẩn hóa văn bản và chuyển thành token mẫu theo profile."""

from __future__ import annotations

import re

from morsedesk.lm.profile import Profile
from morsedesk.model.vocab import SPACE

_PROSIGN_RE = re.compile(r"<([A-Z]{2,3})>")


class UnsupportedCharacter(ValueError):
    def __init__(self, char: str, position: int) -> None:
        super().__init__(f"ký tự không hỗ trợ {char!r} tại vị trí {position}")
        self.char = char
        self.position = position


def normalize(text: str, profile: Profile) -> str:
    """Viết hoa, thay alias (Ё->Е), gộp khoảng trắng."""
    upper = text.upper()
    aliased = "".join(profile.canonical_letter(c) for c in upper)
    return " ".join(aliased.split())


def text_to_tokens(text: str, profile: Profile, strict: bool = True) -> list[str]:
    """Văn bản -> danh sách mẫu chấm gạch và SPACE.

    Vị trí trong UnsupportedCharacter tính trên chuỗi đã chuẩn hóa.
    """
    norm = normalize(text, profile)
    tokens: list[str] = []
    i = 0
    while i < len(norm):
        ch = norm[i]
        if ch == " ":
            if tokens and tokens[-1] != SPACE:
                tokens.append(SPACE)
            i += 1
            continue
        if ch == "<":
            m = _PROSIGN_RE.match(norm, i)
            if m and m.group(0) in profile.prosign_to_pattern:
                tokens.append(profile.prosign_to_pattern[m.group(0)])
                i = m.end()
                continue
        pattern = profile.letter_to_pattern.get(ch)
        if pattern is None:
            if strict:
                raise UnsupportedCharacter(ch, i)
            i += 1
            continue
        tokens.append(pattern)
        i += 1
    while tokens and tokens[-1] == SPACE:
        tokens.pop()
    return tokens
