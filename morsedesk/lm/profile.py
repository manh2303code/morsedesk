"""Nạp và kiểm tra profile ngôn ngữ: ánh xạ mẫu chấm gạch -> chữ."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from morsedesk.model.vocab import SPACE, UNK, VOCAB

PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"
UNK_DISPLAY = "#"


@dataclass
class Profile:
    id: str
    script: str
    display_name: str
    lm: str
    map: dict[str, list[str]]
    prosigns: dict[str, str]
    encode_aliases: dict[str, str]
    lexicon_bonus: list[str]
    letter_to_pattern: dict[str, str] = field(init=False, repr=False)
    prosign_to_pattern: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        inverse: dict[str, str] = {}
        for pattern, letters in self.map.items():
            if not VOCAB.is_pattern(pattern):
                raise ValueError(f"profile {self.id}: mẫu {pattern!r} không có trong từ vựng")
            if not letters:
                raise ValueError(f"profile {self.id}: mẫu {pattern!r} không có chữ")
            for letter in letters:
                if letter in inverse and inverse[letter] != pattern:
                    raise ValueError(
                        f"profile {self.id}: chữ {letter!r} gán cho hai mẫu "
                        f"{inverse[letter]!r} và {pattern!r}"
                    )
                inverse[letter] = pattern
        for pattern in self.prosigns:
            if not VOCAB.is_pattern(pattern):
                raise ValueError(f"profile {self.id}: prosign {pattern!r} không có trong từ vựng")
        self.letter_to_pattern = inverse
        self.prosign_to_pattern = {name: pat for pat, name in self.prosigns.items()}

    def canonical_letter(self, ch: str) -> str:
        return self.encode_aliases.get(ch, ch)

    def decode_options(self, pattern: str) -> list[str]:
        """Các chữ có thể ứng với mẫu, theo thứ tự ưu tiên. Mẫu lạ -> [UNK]."""
        if pattern in self.map:
            return list(self.map[pattern])
        if pattern in self.prosigns:
            return [self.prosigns[pattern]]
        return [UNK]

    def render(self, tokens: list[str]) -> str:
        """Chuỗi token (mẫu hoặc SPACE) -> văn bản, chọn chữ đầu tiên của mỗi mẫu."""
        out: list[str] = []
        for tok in tokens:
            if tok == SPACE:
                out.append(" ")
                continue
            first = self.decode_options(tok)[0]
            out.append(UNK_DISPLAY if first == UNK else first)
        return "".join(out)


def _as_str_list_map(raw: dict) -> dict[str, list[str]]:
    return {str(k): [str(v) for v in vals] for k, vals in (raw or {}).items()}


def load_profile(profile_id_or_path: str | Path) -> Profile:
    p = Path(profile_id_or_path)
    path = p if p.suffix == ".yaml" else PROFILES_DIR / f"{profile_id_or_path}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"không tìm thấy profile: {path}")
    common = yaml.safe_load((PROFILES_DIR / "_common.yaml").read_text(encoding="utf-8"))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    merged_map = _as_str_list_map(common.get("map"))
    merged_map.update(_as_str_list_map(data.get("map")))
    prosigns = {str(k): str(v) for k, v in (common.get("prosigns") or {}).items()}
    prosigns.update({str(k): str(v) for k, v in (data.get("prosigns") or {}).items()})

    return Profile(
        id=str(data["id"]),
        script=str(data.get("script", "")),
        display_name=str(data.get("display_name", data["id"])),
        lm=str(data.get("lm", "")),
        map=merged_map,
        prosigns=prosigns,
        encode_aliases={str(k): str(v) for k, v in (data.get("encode_aliases") or {}).items()},
        lexicon_bonus=[str(x) for x in (data.get("lexicon_bonus") or [])],
    )


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml") if not p.stem.startswith("_"))
