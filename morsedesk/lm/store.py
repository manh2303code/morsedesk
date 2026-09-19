"""Nạp và cache LM n-gram theo profile từ thư mục models/lm."""

from __future__ import annotations

from pathlib import Path

from morsedesk.lm.ngram import CharNGramLM, load_bin
from morsedesk.lm.profile import Profile, load_profile


def default_lm_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "lm"


def lm_file_for(profile: Profile, lm_dir: Path) -> Path:
    return Path(lm_dir) / Path(profile.lm).name


class LMStore:
    def __init__(self, lm_dir: Path | None = None) -> None:
        self.lm_dir = Path(lm_dir) if lm_dir else default_lm_dir()
        self._lms: dict[str, CharNGramLM] = {}
        self._profiles: dict[str, Profile] = {}

    def get_profile(self, profile_id: str) -> Profile:
        if profile_id not in self._profiles:
            self._profiles[profile_id] = load_profile(profile_id)
        return self._profiles[profile_id]

    def register(self, profile: Profile) -> None:
        self._profiles[profile.id] = profile

    def available(self, profile_id: str) -> bool:
        return lm_file_for(self.get_profile(profile_id), self.lm_dir).exists()

    def get(self, profile_id: str) -> CharNGramLM:
        if profile_id not in self._lms:
            path = lm_file_for(self.get_profile(profile_id), self.lm_dir)
            if not path.exists():
                raise FileNotFoundError(
                    f"thiếu mô hình ngôn ngữ {path}; chạy tools/build_lm.sh và tools/arpa_to_bin.py"
                )
            self._lms[profile_id] = load_bin(path)
        return self._lms[profile_id]
