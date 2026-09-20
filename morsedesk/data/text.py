"""Lấy mẫu văn bản để sinh dữ liệu: corpus (mỗi dòng một câu) hoặc từ điển tích hợp,
cộng bản tin ham radio giả lập và nhóm ký tự ngẫu nhiên."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from morsedesk.encode.text import _PROSIGN_RE, normalize, text_to_tokens
from morsedesk.lm.profile import Profile

BUILTIN_WORDS: dict[str, list[str]] = {
    "en": [
        "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "WAS", "ONE", "OUR",
        "OUT", "DAY", "GET", "HAS", "HOW", "NEW", "NOW", "OLD", "SEE", "TWO", "WAY", "WHO",
        "RADIO", "SIGNAL", "REPORT", "WEATHER", "STATION", "MESSAGE", "NUMBER", "ANTENNA",
        "POWER", "WATTS", "MORNING", "EVENING", "TONIGHT", "THANKS", "AGAIN", "COPY", "SOLID",
        "FINE", "HELLO", "WORLD", "QUICK", "BROWN", "FOX", "JUMPS", "OVER", "LAZY", "DOG",
    ],
    "ru": [
        "ПРИВЕТ", "ВСЕМ", "СПАСИБО", "ПОГОДА", "СИГНАЛ", "СТАНЦИЯ", "ПЕРЕДАЧА", "СООБЩЕНИЕ",
        "НОМЕР", "АНТЕННА", "МОЩНОСТЬ", "ХОРОШО", "ПЛОХО", "СЕГОДНЯ", "ЗАВТРА", "УТРО", "ВЕЧЕР",
        "НОЧЬ", "ДЕНЬ", "ГОРОД", "МОСКВА", "СВЯЗЬ", "РАДИО", "ОПЕРАТОР", "ПОЖАЛУЙСТА",
        "ПОВТОРИТЕ", "ПРИНЯЛ", "ПОНЯЛ", "ЖДУ", "ОТВЕТ", "ВОПРОС", "ЩУКА", "ЦЕЛЬ", "ЭХО", "ЮГ",
        "ЯКОРЬ", "ШИРОТА", "ЧАСТОТА", "ОБЪЕМ", "ЁЖ",
    ],
    "kk-cyrl-ru": [
        "СӘЛЕМ", "ӘЛЕМ", "РАХМЕТ", "ҚАЗАҚСТАН", "АСТАНА", "АЛМАТЫ", "ХАБАР", "ЖАҚСЫ", "ЖАМАН",
        "БҮГІН", "ЕРТЕҢ", "ТАҢ", "КЕШ", "ТҮН", "КҮН", "ҚАЛА", "БАЙЛАНЫС", "РАДИО", "ОПЕРАТОР",
        "ӨТІНЕМІН", "ҚАЙТАЛАҢЫЗ", "ҚАБЫЛДАДЫМ", "ТҮСІНДІМ", "КҮТЕМІН", "ЖАУАП", "СҰРАҚ", "ҰЛТ",
        "ІНІ", "ҒАЛЫМ", "ӨЗЕН", "ҮЛКЕН", "КІШІ", "НӨМІР", "АНТЕННА", "ҚУАТ", "АУА", "РАЙЫ", "ЖЕЛ",
        "ЖАҢБЫР", "ҺӘМ",
    ],
}

HAM_TEMPLATES = [
    "CQ CQ CQ DE {a} {a} K",
    "{b} DE {a} UR RST 599 599 BK",
    "TNX FER CALL UR 579 579 QTH {city} {city} = NAME {name} {name} HW?",
    "73 ES GL DE {a} <SK>",
    "R R TU 73 CQ DE {a} K",
    "QRZ? DE {a} K",
    "{b} DE {a} GM OM TNX RPRT UR 559 559 = WX {wx} = 73 <AR> {b} DE {a} K",
]
CITIES = ["MOSCOW", "ASTANA", "ALMATY", "LONDON", "BERLIN", "OMSK", "KAZAN", "PARIS"]
NAMES = ["IVAN", "ALEX", "OLEG", "NUR", "ARMAN", "JOHN", "MIKE", "PETE"]
WX = ["SUNNY", "RAIN", "SNOW", "CLOUDY", "COLD", "HOT"]
PREFIXES = ["R", "UA", "UN", "UP", "W", "K", "N", "G", "DL", "F", "EW", "UR"]


def translit_via_patterns(text: str, src: Profile, dst: Profile) -> str:
    """Chuyển chữ giữa hai profile qua mẫu chấm gạch (UN7ABC -> УН7АБЦ)."""
    return dst.render(text_to_tokens(text, src, strict=False))


def random_callsign(rng: np.random.Generator) -> str:
    pre = PREFIXES[rng.integers(len(PREFIXES))]
    digit = str(rng.integers(0, 10))
    suffix = "".join(chr(65 + rng.integers(26)) for _ in range(int(rng.integers(2, 4))))
    return pre + digit + suffix


def keep_supported(raw: str, profile: Profile) -> str:
    """Chuẩn hóa rồi bỏ ký tự không mã hóa được; giữ chữ gốc (Ә, Ғ...) và prosign của profile."""
    norm = normalize(raw, profile)
    out: list[str] = []
    i = 0
    while i < len(norm):
        ch = norm[i]
        if ch == "<":
            m = _PROSIGN_RE.match(norm, i)
            if m:                                   # prosign lạ (<XYZ>) bị bỏ trọn, không rò chữ
                if m.group(0) in profile.prosign_to_pattern:
                    out.append(m.group(0))
                i = m.end()
                continue
        if ch == " " or ch in profile.letter_to_pattern:
            out.append(ch)
        i += 1
    return " ".join("".join(out).split())


class TextSampler:
    def __init__(
        self,
        profiles: dict[str, Profile],
        corpus: dict[str, Path] | None = None,
        ham_ratio: float = 0.3,
        random_ratio: float = 0.1,
    ) -> None:
        self.profiles = profiles
        self.ham_ratio = ham_ratio
        self.random_ratio = random_ratio
        self.corpus: dict[str, list[str]] = {}
        for pid, path in (corpus or {}).items():
            lines = [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines()]
            self.corpus[pid] = [ln for ln in lines if ln]

    def _random_groups(self, profile: Profile, rng: np.random.Generator, n: int) -> str:
        letters = sorted(c for c in profile.letter_to_pattern if len(c) == 1)
        groups = []
        for _ in range(n):
            groups.append("".join(letters[rng.integers(len(letters))] for _ in range(5)))
        return " ".join(groups)

    def _ham(self, profile: Profile, rng: np.random.Generator) -> str:
        t = HAM_TEMPLATES[rng.integers(len(HAM_TEMPLATES))]
        s = t.format(
            a=random_callsign(rng), b=random_callsign(rng),
            city=CITIES[rng.integers(len(CITIES))], name=NAMES[rng.integers(len(NAMES))],
            wx=WX[rng.integers(len(WX))],
        )
        en = self.profiles.get("en")
        if profile.id != "en" and en is not None:
            s = translit_via_patterns(s, en, profile)
        return s

    def _words(self, pid: str, profile: Profile, rng: np.random.Generator, n: int) -> str:
        if pid in self.corpus and self.corpus[pid]:
            line = self.corpus[pid][rng.integers(len(self.corpus[pid]))]
            words = line.split()
            if len(words) > n:
                start = int(rng.integers(0, len(words) - n + 1))
                words = words[start:start + n]
            return " ".join(words)
        vocab = BUILTIN_WORDS[pid]
        return " ".join(vocab[rng.integers(len(vocab))] for _ in range(n))

    def sample(self, profile_id: str, rng: np.random.Generator, n_words: tuple[int, int] = (3, 12)) -> str:
        profile = self.profiles[profile_id]
        n = int(rng.integers(n_words[0], n_words[1] + 1))
        u = rng.random()
        if u < self.random_ratio:
            raw = self._random_groups(profile, rng, n)
        elif u < self.random_ratio + self.ham_ratio:
            raw = self._ham(profile, rng)
        else:
            raw = self._words(profile_id, profile, rng, n)
        cleaned = keep_supported(raw, profile)
        return cleaned or BUILTIN_WORDS[profile_id][0]
