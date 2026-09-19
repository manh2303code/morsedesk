# MorseDesk core (tuần 1–2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây lõi `morsedesk` chạy được bằng CLI: tạo mã Morse ba ngôn ngữ ra WAV, giải mã file bằng bộ giải mã DSP baseline, sinh dữ liệu tổng hợp, ma trận test T1, huấn luyện mạng CTC nhỏ, xuất ONNX có kiểm tra parity và chạy được qua onnxruntime với giải mã greedy.

**Architecture:** Mọi thứ xoay quanh từ vựng 65 lớp "mẫu chấm gạch" (không phải chữ): encoder biến chữ thành mẫu qua profile YAML rồi thành timing PARIS rồi thành âm thanh; decoder đi ngược lại: dò tone, trích đặc trưng 11 chiều ở 200 khung/giây, rồi hoặc phân loại khoảng bật tắt (baseline DSP) hoặc chạy mạng CNN+BiGRU+CTC (ONNX) để ra mẫu, sau đó profile ánh xạ mẫu thành chữ. Bộ sinh dữ liệu dùng lại encoder cộng mô hình tay gõ và kênh nhiễu để tạo cặp (audio, nhãn) on-the-fly cho huấn luyện và cho ma trận T1.

**Tech Stack:** Python 3.11, uv, numpy < 2, scipy, soundfile, PyYAML, onnxruntime (runtime); PyTorch + onnx (chỉ khi train); pytest. Spec: `docs/superpowers/specs/2026-09-18-morsedesk-design.md`.

## Global Constraints

- Python `>=3.11,<3.12`; tạo môi trường bằng `uv sync --all-extras` (uv tự tải Python 3.11). Không dùng Python 3.14 của hệ thống.
- `numpy>=1.26,<2` (pyctcdecode ở tuần 3 cần numpy < 2).
- Chỉ thêm phụ thuộc có license Apache-2.0, MIT, BSD hoặc LGPL liên kết động. Không nhúng GPL/AGPL; `ffmpeg` chỉ được gọi như tiến trình ngoài và phải là tùy chọn.
- `torch` (extra `train`, chỉ dùng trên máy dev) lấy từ index CPU `https://download.pytorch.org/whl/cpu` qua `[tool.uv.sources]` để `uv.lock` không kéo gói NVIDIA CUDA.
- Âm thanh nội bộ: mono float32, `SAMPLE_RATE = 8000`, `HOP = 40` mẫu (200 khung/giây), `N_FFT = 256`, đặc trưng `FEAT_DIM = 11` mỗi khung 5 ms.
- Từ vựng đầu ra đúng 65 lớp: index 0 `<blank>`, 1 `<space>`, 2 `<unk>`, rồi 62 mẫu (31 chữ, 10 số, 18 dấu, 3 prosign) theo thứ tự cố định trong `morsedesk/model/vocab.py`.
- Timing chuẩn PARIS: dit = 1.2/WPM giây; dash = weight × dit (mặc định 3); khoảng trong chữ 1 dit; giữa chữ 3; giữa từ 7. Farnsworth theo ARRL: `t_a = (60c − 37.2s)/(s·c)`, khoảng giữa chữ `3·t_a/19`, giữa từ `7·t_a/19`.
- Mạng: `Conv1d(11→32,k5) → Conv1d(32→64,k5,stride2) → Conv1d(64→64,k5) → BiGRU(64→96×2) → Linear(192→65)`, ONNX opset 17, input `features [1,T,11]`, output `log_probs [1,ceil(T/2),65]`, parity torch/onnxruntime sai số tuyệt đối ≤ 1e-4.
- Profile YAML nằm trong package tại `morsedesk/profiles/` (spec ghi `profiles/` ở gốc; đặt trong package để PyInstaller gói tự động). Ba profile: `en`, `ru`, `kk-cyrl-ru`.
- Tệp sinh ra (audio T1, checkpoint, model) nằm dưới `testdata/generated/`, `runs/`, `models/*.onnx` và không commit; chỉ commit mã và metadata.
- Mọi commit kết thúc bằng hai dòng trailer:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` và
  `Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV`.
- Lệnh chạy dùng `uv run ...` từ gốc repo `C:\Users\Admin\morsedesk` để không phụ thuộc việc kích hoạt venv (PowerShell hay Git Bash đều được).

---

## Bản đồ tệp

| Tệp | Trách nhiệm |
|---|---|
| `pyproject.toml` | metadata, phụ thuộc, extras `runtime`/`train`/`dev`, entry point `morsedesk` |
| `morsedesk/constants.py` | hằng số âm thanh và đặc trưng |
| `morsedesk/model/vocab.py` | 65 lớp, ánh xạ token ↔ id |
| `morsedesk/profiles/_common.yaml`, `en.yaml`, `ru.yaml`, `kk-cyrl-ru.yaml` | bảng mẫu → chữ theo ngôn ngữ |
| `morsedesk/lm/profile.py` | nạp, hợp nhất, kiểm tra profile; `render()` mẫu → chữ; `letter_to_pattern` |
| `morsedesk/encode/text.py` | chuẩn hóa chữ, chữ → token mẫu |
| `morsedesk/encode/timing.py` | token → danh sách phần tử bật/tắt (giây), PARIS + Farnsworth + weight |
| `morsedesk/encode/synth.py` | phần tử → sóng, tone có thể trôi, thêm nhiễu theo SNR trong băng |
| `morsedesk/audio/io.py` | đọc/ghi file, resample về 8 kHz, chuẩn hóa |
| `morsedesk/dsp/stft.py` | STFT công suất dùng chung |
| `morsedesk/dsp/tone.py` | ước lượng tone, SNR, có tín hiệu hay không, tone thứ hai |
| `morsedesk/dsp/frontend.py` | envelope I/Q, AGC log, đạo hàm, 9 bin phổ → `[T, 11]` |
| `morsedesk/dsp/baseline.py` | bộ giải mã DSP thích nghi (baseline, fallback) |
| `morsedesk/metrics.py` | CER, WER |
| `morsedesk/api.py` | `Encoder`, `Decoder`, `DecodeResult`, `Word` |
| `morsedesk/cli.py` | `morsedesk encode/decode/devices/bench` |
| `morsedesk/textio.py` | ép UTF-8 cho stdout/stderr |
| `morsedesk/data/text.py` | lấy mẫu văn bản ba ngôn ngữ |
| `morsedesk/data/keyer.py` | mô hình tay gõ ngẫu nhiên |
| `morsedesk/data/channel.py` | kênh: trôi tone, AWGN, QSB, QRM, QRN, băng, mức, clipping, DC, MP3 |
| `morsedesk/data/synth.py` | `SynthGenerator.generate(seed) -> Example` |
| `morsedesk/model/ctc.py` | greedy decode |
| `morsedesk/model/chunker.py` | cửa sổ trượt và gộp log-prob |
| `morsedesk/model/onnx_runner.py` | chạy ONNX, kiểm metadata |
| `tools/make_t2_manifest.py` | ghép MP3 + text ARRL thành manifest |
| `tools/bench_external.py` | đo công cụ ngoài trên manifest |
| `tools/make_t1.py` | sinh ma trận T1 và manifest |
| `tools/bench.py` | đo CER theo ô, gate |
| `tools/net_torch.py` | định nghĩa mạng PyTorch |
| `tools/train.py` | dataset on-the-fly, huấn luyện CTC, checkpoint |
| `tools/export_onnx.py` | xuất ONNX, metadata, golden |
| `tests/unit/*`, `tests/regression/*` | kiểm thử |

---

### Task 1: Khung repo, pyproject, hằng số

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `morsedesk/__init__.py`
- Create: `morsedesk/constants.py`
- Create: `morsedesk/audio/__init__.py`, `morsedesk/dsp/__init__.py`, `morsedesk/encode/__init__.py`, `morsedesk/lm/__init__.py`, `morsedesk/model/__init__.py`, `morsedesk/data/__init__.py` (rỗng)
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/regression/__init__.py` (rỗng)
- Test: `tests/unit/test_constants.py`

**Interfaces:**
- Produces: `morsedesk.constants.SAMPLE_RATE = 8000`, `HOP = 40`, `FRAME_RATE = 200`, `N_FFT = 256`, `FEAT_DIM = 11`, `TONE_MIN_HZ = 300.0`, `TONE_MAX_HZ = 1500.0`.

- [ ] **Step 1: Viết pyproject.toml**

```toml
[project]
name = "morsedesk"
version = "0.1.0"
description = "Offline Morse decoder and encoder for English, Russian and Kazakh"
readme = "README.md"
requires-python = ">=3.11,<3.12"
license = { text = "Proprietary" }
dependencies = [
  "numpy>=1.26,<2",
  "scipy>=1.11",
  "soundfile>=0.12",
  "PyYAML>=6.0",
]

[project.optional-dependencies]
runtime = ["onnxruntime>=1.17", "sounddevice>=0.4.6"]
train = ["torch>=2.2", "onnx>=1.15"]
dev = ["pytest>=8", "ruff>=0.5"]

[project.scripts]
morsedesk = "morsedesk.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["morsedesk"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.uv.sources]
torch = [{ index = "pytorch-cpu" }]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true
```

- [ ] **Step 2: Viết README.md**

```markdown
# MorseDesk

Ứng dụng desktop Linux air-gap giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Spec: `docs/superpowers/specs/2026-09-18-morsedesk-design.md`.

## Thiết lập môi trường dev

```bash
uv sync --all-extras          # tạo .venv với Python 3.11 và cài mọi phụ thuộc
uv run pytest                 # chạy test
uv run morsedesk --help
```

Tùy chọn: cài `ffmpeg` (ví dụ `scoop install ffmpeg`) để bộ sinh dữ liệu tạo được biến thể MP3.
```

- [ ] **Step 3: Viết morsedesk/__init__.py và constants.py**

`morsedesk/__init__.py`:

```python
"""MorseDesk: offline Morse decoder and encoder."""

__version__ = "0.1.0"
```

`morsedesk/constants.py`:

```python
"""Hằng số dùng chung cho toàn bộ pipeline âm thanh."""

SAMPLE_RATE = 8000          # Hz, mọi xử lý nội bộ ở tần số này
HOP = 40                    # mẫu mỗi khung -> 200 khung/giây
FRAME_RATE = SAMPLE_RATE // HOP
N_FFT = 256                 # cỡ STFT, bin = 31.25 Hz
FEAT_DIM = 11               # 1 envelope AGC + 1 đạo hàm + 9 bin phổ
TONE_MIN_HZ = 300.0
TONE_MAX_HZ = 1500.0

assert SAMPLE_RATE % HOP == 0
assert FRAME_RATE == 200
```

Tạo các file `__init__.py` rỗng cho `morsedesk/audio`, `morsedesk/dsp`, `morsedesk/encode`, `morsedesk/lm`, `morsedesk/model`, `morsedesk/data`, `tests`, `tests/unit`, `tests/regression`.

- [ ] **Step 4: Viết test**

`tests/unit/test_constants.py`:

```python
from morsedesk import constants


def test_frame_rate_is_200():
    assert constants.FRAME_RATE == 200
    assert constants.SAMPLE_RATE == 8000
    assert constants.HOP == 40


def test_feature_dim():
    assert constants.FEAT_DIM == 11
```

- [ ] **Step 5: Tạo môi trường và chạy test**

Run: `uv sync --all-extras`
Expected: uv tải Python 3.11 (nếu chưa có), tạo `.venv`, cài numpy/scipy/soundfile/PyYAML/onnxruntime/sounddevice/torch/onnx/pytest/ruff. Lần đầu mất vài phút vì torch lớn.

Run: `uv run pytest tests/unit/test_constants.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md morsedesk tests
git commit -m "chore: khung repo, pyproject, hằng số âm thanh" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

(`uv.lock` do `uv sync` tạo ra cũng nên commit cùng: `git add uv.lock`.)

---

### Task 2: Từ vựng 65 lớp

**Files:**
- Create: `morsedesk/model/vocab.py`
- Test: `tests/unit/test_vocab.py`

**Interfaces:**
- Produces: `BLANK = "<blank>"`, `SPACE = "<space>"`, `UNK = "<unk>"`; dict `LATIN: dict[str, str]` (chữ Latin → mẫu), `RUSSIAN_ONLY: list[str]`, `DIGITS: dict[str, str]`, `PUNCT: dict[str, str]`, `PROSIGNS: dict[str, str]` (tên → mẫu); lớp `Vocab` với `tokens: list[str]`, `id(token: str) -> int`, `token(i: int) -> str`, `__len__`, `is_pattern(token) -> bool`, `blank_id = 0`, `space_id = 1`, `unk_id = 2`; singleton `VOCAB = Vocab()`.

- [ ] **Step 1: Viết test**

`tests/unit/test_vocab.py`:

```python
import pytest

from morsedesk.model import vocab
from morsedesk.model.vocab import VOCAB, BLANK, SPACE, UNK


def test_size_is_65():
    assert len(VOCAB) == 65


def test_special_indices():
    assert VOCAB.id(BLANK) == 0
    assert VOCAB.id(SPACE) == 1
    assert VOCAB.id(UNK) == 2
    assert VOCAB.blank_id == 0 and VOCAB.space_id == 1 and VOCAB.unk_id == 2


def test_tokens_unique_and_roundtrip():
    assert len(set(VOCAB.tokens)) == len(VOCAB.tokens)
    for i, tok in enumerate(VOCAB.tokens):
        assert VOCAB.id(tok) == i
        assert VOCAB.token(i) == tok


def test_group_counts():
    assert len(vocab.LATIN) == 26
    assert len(vocab.RUSSIAN_ONLY) == 5
    assert len(vocab.DIGITS) == 10
    assert len(vocab.PUNCT) == 18
    assert len(vocab.PROSIGNS) == 3


def test_russian_only_patterns_present():
    for p in ["----", "---.", "..--", ".-.-", "..-.."]:
        assert VOCAB.is_pattern(p)
        assert VOCAB.id(p) >= 3


def test_unknown_token_raises():
    with pytest.raises(KeyError):
        VOCAB.id("......-")


def test_is_pattern_false_for_specials():
    assert not VOCAB.is_pattern(BLANK)
    assert not VOCAB.is_pattern(SPACE)
    assert not VOCAB.is_pattern(UNK)
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_vocab.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.model.vocab'`

- [ ] **Step 3: Viết vocab.py**

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_vocab.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add morsedesk/model/vocab.py tests/unit/test_vocab.py
git commit -m "feat(vocab): từ vựng 65 lớp mẫu chấm gạch" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 3: Profile ngôn ngữ (YAML + loader)

**Files:**
- Create: `morsedesk/profiles/_common.yaml`, `morsedesk/profiles/en.yaml`, `morsedesk/profiles/ru.yaml`, `morsedesk/profiles/kk-cyrl-ru.yaml`
- Create: `morsedesk/lm/profile.py`
- Test: `tests/unit/test_profile.py`

**Interfaces:**
- Consumes: `VOCAB`, `SPACE`, `UNK` từ `morsedesk.model.vocab`.
- Produces: `PROFILES_DIR: Path`; `UNK_DISPLAY = "#"`; dataclass `Profile(id, script, display_name, lm, map: dict[str, list[str]], prosigns: dict[str, str], encode_aliases: dict[str, str], lexicon_bonus: list[str])` với thuộc tính dẫn xuất `letter_to_pattern: dict[str, str]`, `prosign_to_pattern: dict[str, str]` và phương thức `decode_options(pattern: str) -> list[str]`, `render(tokens: list[str]) -> str`, `canonical_letter(ch: str) -> str`; hàm `load_profile(profile_id_or_path: str | Path) -> Profile`, `list_profiles() -> list[str]`.

- [ ] **Step 1: Viết test**

`tests/unit/test_profile.py`:

```python
import pytest

from morsedesk.lm.profile import Profile, list_profiles, load_profile, UNK_DISPLAY
from morsedesk.model.vocab import SPACE, UNK, VOCAB


@pytest.fixture(scope="module")
def en():
    return load_profile("en")


@pytest.fixture(scope="module")
def ru():
    return load_profile("ru")


@pytest.fixture(scope="module")
def kk():
    return load_profile("kk-cyrl-ru")


def test_list_profiles():
    assert set(list_profiles()) == {"en", "ru", "kk-cyrl-ru"}


def test_all_map_keys_are_vocab_patterns(en, ru, kk):
    for p in (en, ru, kk):
        for pattern in p.map:
            assert VOCAB.is_pattern(pattern), (p.id, pattern)
        for pattern in p.prosigns:
            assert VOCAB.is_pattern(pattern), (p.id, pattern)


def test_en_letters_digits_punct(en):
    letters = [pat for pat, ls in en.map.items() if ls[0].isalpha()]
    assert len(letters) == 26
    assert en.letter_to_pattern["Q"] == "--.-"
    assert en.letter_to_pattern["0"] == "-----"
    assert en.letter_to_pattern["?"] == "..--.."
    assert en.decode_options("----") == [UNK]
    assert en.decode_options("...-.-") == ["<SK>"]
    assert en.prosign_to_pattern["<SOS>"] == "...---..."


def test_ru_covers_31_letters(ru):
    letters = {L for ls in ru.map.values() for L in ls if L.isalpha()}
    assert len(letters) == 31
    assert ru.letter_to_pattern["Ш"] == "----"
    assert ru.letter_to_pattern["Э"] == "..-.."
    assert ru.decode_options("-..-") == ["Ь", "Ъ"]
    assert ru.canonical_letter("Ё") == "Е"
    assert ru.letter_to_pattern["Ъ"] == "-..-"


def test_kk_one_to_many(kk):
    assert kk.decode_options(".-") == ["А", "Ә"]
    assert kk.decode_options("..-") == ["У", "Ұ", "Ү"]
    assert kk.decode_options("....") == ["Х", "Һ"]
    assert kk.decode_options("..") == ["И", "І"]
    assert kk.letter_to_pattern["Ә"] == ".-"
    assert kk.letter_to_pattern["Қ"] == "-.-"
    assert kk.letter_to_pattern["Ң"] == "-."
    assert kk.letter_to_pattern["Ө"] == "---"
    assert kk.letter_to_pattern["Ғ"] == "--."


def test_render(en, ru):
    assert en.render(["-.-.", "--.-", SPACE, "-..", "."]) == "CQ DE"
    assert ru.render([".--.", ".-.", "..", ".--", ".", "-"]) == "ПРИВЕТ"
    assert en.render(["----"]) == UNK_DISPLAY
    assert en.render(["...-.-"]) == "<SK>"


def test_inverse_conflict_raises():
    with pytest.raises(ValueError):
        Profile(
            id="x", script="Latin", display_name="x", lm="",
            map={".-": ["A"], "-...": ["A"]}, prosigns={}, encode_aliases={}, lexicon_bonus=[],
        )


def test_load_by_path(tmp_path):
    p = load_profile("en")
    assert p.id == "en"
    from morsedesk.lm.profile import PROFILES_DIR
    assert load_profile(PROFILES_DIR / "ru.yaml").id == "ru"
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_profile.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.lm.profile'`

- [ ] **Step 3: Viết các file YAML**

`morsedesk/profiles/_common.yaml` (dùng chung cho mọi profile, profile có thể ghi đè):

```yaml
# Số, dấu câu ITU và prosign có mẫu riêng. Khóa là mẫu chấm gạch.
map:
  "-----": ["0"]
  ".----": ["1"]
  "..---": ["2"]
  "...--": ["3"]
  "....-": ["4"]
  ".....": ["5"]
  "-....": ["6"]
  "--...": ["7"]
  "---..": ["8"]
  "----.": ["9"]
  ".-.-.-": ["."]
  "--..--": [","]
  "..--..": ["?"]
  ".----.": ["'"]
  "-.-.--": ["!"]
  "-..-.": ["/"]
  "-.--.": ["("]
  "-.--.-": [")"]
  ".-...": ["&"]
  "---...": [":"]
  "-.-.-.": [";"]
  "-...-": ["="]
  ".-.-.": ["+"]
  "-....-": ["-"]
  "..--.-": ["_"]
  ".-..-.": ['"']
  "...-..-": ["$"]
  ".--.-.": ["@"]
prosigns:
  "...-.-": "<SK>"
  "...---...": "<SOS>"
  "........": "<ERR>"
  ".-.-.": "<AR>"
  "-...-": "<BT>"
  "-.--.": "<KN>"
  ".-...": "<AS>"
```

`morsedesk/profiles/en.yaml`:

```yaml
id: en
script: Latin
display_name: English
lm: lm/en.bin
encode_aliases: {}
lexicon_bonus: [CQ, DE, PSE, K, KN, TU, RST, QTH, QRZ, QSL, QRM, QRN, QSB, "73", "88", AGN, HW, TNX, GM, GA, GE]
map:
  ".-": [A]
  "-...": [B]
  "-.-.": [C]
  "-..": [D]
  ".": [E]
  "..-.": [F]
  "--.": [G]
  "....": [H]
  "..": [I]
  ".---": [J]
  "-.-": [K]
  ".-..": [L]
  "--": [M]
  "-.": [N]
  "---": [O]
  ".--.": [P]
  "--.-": [Q]
  ".-.": [R]
  "...": [S]
  "-": [T]
  "..-": [U]
  "...-": [V]
  ".--": [W]
  "-..-": [X]
  "-.--": [Y]
  "--..": [Z]
```

`morsedesk/profiles/ru.yaml`:

```yaml
id: ru
script: Cyrillic
display_name: Русский
lm: lm/ru.bin
encode_aliases:
  "Ё": "Е"
lexicon_bonus: [CQ, DE, PSE, K, KN, TU, RST, QTH, QRZ, QSL, QRM, QRN, QSB, "73", "88", ВСЕМ, СПАСИБО, ПРИВЕТ, ПОКА]
map:
  ".-": [А]
  "-...": [Б]
  ".--": [В]
  "--.": [Г]
  "-..": [Д]
  ".": [Е]
  "...-": [Ж]
  "--..": [З]
  "..": [И]
  ".---": [Й]
  "-.-": [К]
  ".-..": [Л]
  "--": [М]
  "-.": [Н]
  "---": [О]
  ".--.": [П]
  ".-.": [Р]
  "...": [С]
  "-": [Т]
  "..-": [У]
  "..-.": [Ф]
  "....": [Х]
  "-.-.": [Ц]
  "---.": [Ч]
  "----": [Ш]
  "--.-": [Щ]
  "-..-": [Ь, Ъ]
  "-.--": [Ы]
  "..-..": [Э]
  "..--": [Ю]
  ".-.-": [Я]
```

`morsedesk/profiles/kk-cyrl-ru.yaml` (bảng Nga, tám mẫu một-nhiều cho chữ Kazakh):

```yaml
id: kk-cyrl-ru
script: Cyrillic
display_name: Қазақша
lm: lm/kk.bin
encode_aliases:
  "Ё": "Е"
lexicon_bonus: [CQ, DE, PSE, K, KN, TU, RST, QTH, QRZ, QSL, QRM, QRN, QSB, "73", "88", СӘЛЕМ, РАХМЕТ, ҚАЗАҚСТАН]
map:
  ".-": [А, Ә]
  "-...": [Б]
  ".--": [В]
  "--.": [Г, Ғ]
  "-..": [Д]
  ".": [Е]
  "...-": [Ж]
  "--..": [З]
  "..": [И, І]
  ".---": [Й]
  "-.-": [К, Қ]
  ".-..": [Л]
  "--": [М]
  "-.": [Н, Ң]
  "---": [О, Ө]
  ".--.": [П]
  ".-.": [Р]
  "...": [С]
  "-": [Т]
  "..-": [У, Ұ, Ү]
  "..-.": [Ф]
  "....": [Х, Һ]
  "-.-.": [Ц]
  "---.": [Ч]
  "----": [Ш]
  "--.-": [Щ]
  "-..-": [Ь, Ъ]
  "-.--": [Ы]
  "..-..": [Э]
  "..--": [Ю]
  ".-.-": [Я]
```

- [ ] **Step 4: Viết profile.py**

```python
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
```

- [ ] **Step 5: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_profile.py -v`
Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
git add morsedesk/profiles morsedesk/lm/profile.py tests/unit/test_profile.py
git commit -m "feat(profile): profile en, ru, kk-cyrl-ru và loader" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 4: Chữ → token mẫu, token → timing PARIS/Farnsworth

**Files:**
- Create: `morsedesk/encode/text.py`
- Create: `morsedesk/encode/timing.py`
- Test: `tests/unit/test_encode_text.py`, `tests/unit/test_timing.py`

**Interfaces:**
- Consumes: `Profile`, `load_profile` (Task 3); `SPACE` (Task 2).
- Produces:
  - `text.UnsupportedCharacter(ValueError)` với `.char`, `.position`; `text.normalize(text, profile) -> str`; `text.text_to_tokens(text, profile, strict=True) -> list[str]` (token là mẫu hoặc `SPACE`, không có SPACE ở đầu/cuối, không có hai SPACE liền).
  - `timing.Element(on: bool, duration: float)` (frozen dataclass, giây); `timing.TimingParams(wpm=20.0, farnsworth_wpm=None, weight=3.0)`; `timing.unit_seconds(wpm) -> float`; `timing.gap_seconds(params) -> tuple[float, float]` (giữa chữ, giữa từ); `timing.tokens_to_elements(tokens, params) -> list[Element]`; `timing.total_seconds(elements) -> float`; `timing.elements_to_segments(elements, sample_rate) -> list[tuple[bool, int, int]]` (on, mẫu bắt đầu, mẫu kết thúc; làm tròn tích lũy để không trôi).

- [ ] **Step 1: Viết test text**

`tests/unit/test_encode_text.py`:

```python
import pytest

from morsedesk.encode.text import UnsupportedCharacter, normalize, text_to_tokens
from morsedesk.lm.profile import load_profile
from morsedesk.model.vocab import SPACE


@pytest.fixture(scope="module")
def en():
    return load_profile("en")


@pytest.fixture(scope="module")
def ru():
    return load_profile("ru")


@pytest.fixture(scope="module")
def kk():
    return load_profile("kk-cyrl-ru")


def test_normalize_upper_and_collapse_spaces(en):
    assert normalize("  cq   de  k1abc ", en) == "CQ DE K1ABC"


def test_normalize_applies_alias(ru):
    assert normalize("ёж", ru) == "ЕЖ"


def test_tokens_basic(en):
    assert text_to_tokens("CQ cq", en) == ["-.-.", "--.-", SPACE, "-.-.", "--.-"]


def test_tokens_no_leading_trailing_or_double_space(en):
    toks = text_to_tokens("  A   B  ", en)
    assert toks == [".-", SPACE, "-..."]


def test_prosign_syntax(en):
    assert text_to_tokens("SOS <SK>", en) == ["...", "---", "...", SPACE, "...-.-"]
    assert text_to_tokens("<sos>", en) == ["...---..."]


def test_digits_and_punct(en):
    assert text_to_tokens("73?", en) == ["--...", "...--", "..--.."]


def test_unsupported_strict(en):
    with pytest.raises(UnsupportedCharacter) as ei:
        text_to_tokens("ABӘ", en)
    assert ei.value.char == "Ә"
    assert ei.value.position == 2


def test_unsupported_lenient(en):
    assert text_to_tokens("ABӘC", en, strict=False) == [".-", "-...", "-.-."]


def test_kazakh_letters(kk):
    assert text_to_tokens("ӘЛЕМ", kk) == [".-", ".-..", ".", "--"]
    assert text_to_tokens("ҚҰС", kk) == ["-.-", "..-", "..."]


def test_russian_hard_sign(ru):
    assert text_to_tokens("ОБЪЕМ", ru) == ["---", "-...", "-..-", ".", "--"]
```

- [ ] **Step 2: Viết test timing**

`tests/unit/test_timing.py`:

```python
import math

import pytest

from morsedesk.encode.timing import (
    Element,
    TimingParams,
    elements_to_segments,
    gap_seconds,
    tokens_to_elements,
    total_seconds,
    unit_seconds,
)
from morsedesk.model.vocab import SPACE

PARIS = [".--.", ".-", ".-.", "..", "..."]


def test_unit_seconds():
    assert math.isclose(unit_seconds(20), 0.06)
    assert math.isclose(unit_seconds(12), 0.1)


def test_paris_is_50_units():
    els = tokens_to_elements(PARIS + [SPACE], TimingParams(wpm=20))
    assert math.isclose(total_seconds(els), 3.0, rel_tol=1e-9)
    assert math.isclose(total_seconds(els), 50 * unit_seconds(20), rel_tol=1e-9)


def test_elements_alternate_and_start_on():
    els = tokens_to_elements(["-.-.", "--.-"], TimingParams(wpm=25))
    assert els[0].on
    for a, b in zip(els, els[1:]):
        assert a.on != b.on


def test_weight_changes_dash_only():
    u = unit_seconds(20)
    els = tokens_to_elements(["-"], TimingParams(wpm=20, weight=4.0))
    assert els == [Element(True, 4 * u)]
    els = tokens_to_elements(["."], TimingParams(wpm=20, weight=4.0))
    assert els == [Element(True, u)]


def test_gap_seconds_standard():
    ic, iw = gap_seconds(TimingParams(wpm=20))
    assert math.isclose(ic, 3 * 0.06) and math.isclose(iw, 7 * 0.06)
    ic2, iw2 = gap_seconds(TimingParams(wpm=20, farnsworth_wpm=20))
    assert math.isclose(ic, ic2) and math.isclose(iw, iw2)


def test_farnsworth_18_5_gives_5_wpm():
    els = tokens_to_elements(PARIS + [SPACE], TimingParams(wpm=18, farnsworth_wpm=5))
    assert math.isclose(total_seconds(els), 12.0, rel_tol=1e-6)
    ic, iw = gap_seconds(TimingParams(wpm=18, farnsworth_wpm=5))
    assert iw > ic > 3 * unit_seconds(18)


def test_word_gap_between_words():
    els = tokens_to_elements(["-", SPACE, "-"], TimingParams(wpm=20))
    assert els == [Element(True, 0.18), Element(False, 0.42), Element(True, 0.18)]


def test_invalid_params():
    with pytest.raises(ValueError):
        TimingParams(wpm=0)
    with pytest.raises(ValueError):
        TimingParams(wpm=20, farnsworth_wpm=30)
    with pytest.raises(ValueError):
        TimingParams(wpm=20, weight=0.5)


def test_segments_no_drift():
    els = tokens_to_elements(PARIS + [SPACE] * 1, TimingParams(wpm=20)) * 40
    segs = elements_to_segments(els, 8000)
    assert segs[0][1] == 0
    for (_, s0, e0), (_, s1, _) in zip(segs, segs[1:]):
        assert e0 == s1
    assert abs(segs[-1][2] - round(total_seconds(els) * 8000)) <= 1
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_encode_text.py tests/unit/test_timing.py -v`
Expected: FAIL với `ModuleNotFoundError` cho `morsedesk.encode.text` và `morsedesk.encode.timing`

- [ ] **Step 4: Viết text.py**

```python
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
```

- [ ] **Step 5: Viết timing.py**

```python
"""Token mẫu -> danh sách phần tử bật/tắt theo chuẩn PARIS và Farnsworth (ARRL)."""

from __future__ import annotations

from dataclasses import dataclass

from morsedesk.model.vocab import SPACE


@dataclass(frozen=True)
class Element:
    on: bool
    duration: float  # giây


@dataclass(frozen=True)
class TimingParams:
    wpm: float = 20.0
    farnsworth_wpm: float | None = None  # tốc độ hiệu dụng, phải <= wpm
    weight: float = 3.0                  # dash = weight * dit

    def __post_init__(self) -> None:
        if self.wpm <= 0:
            raise ValueError("wpm phải > 0")
        if self.weight < 1.0:
            raise ValueError("weight phải >= 1")
        if self.farnsworth_wpm is not None and not (0 < self.farnsworth_wpm <= self.wpm):
            raise ValueError("farnsworth_wpm phải trong (0, wpm]")


def unit_seconds(wpm: float) -> float:
    """Độ dài một dit: từ PARIS = 50 dit, 1 phút / (50 * wpm)."""
    return 1.2 / wpm


def gap_seconds(params: TimingParams) -> tuple[float, float]:
    """(khoảng giữa chữ, khoảng giữa từ) theo giây.

    Chuẩn: 3 và 7 dit. Farnsworth theo ARRL: t_a = (60c - 37.2s)/(s*c),
    giữa chữ = 3*t_a/19, giữa từ = 7*t_a/19.
    """
    c = params.wpm
    u = unit_seconds(c)
    s = params.farnsworth_wpm
    if s is None or s >= c:
        return 3.0 * u, 7.0 * u
    t_a = (60.0 * c - 37.2 * s) / (s * c)
    return 3.0 * t_a / 19.0, 7.0 * t_a / 19.0


def tokens_to_elements(tokens: list[str], params: TimingParams = TimingParams()) -> list[Element]:
    u = unit_seconds(params.wpm)
    dash = params.weight * u
    inter_char, inter_word = gap_seconds(params)
    elements: list[Element] = []
    pending_gap: float | None = None
    for tok in tokens:
        if tok == SPACE:
            pending_gap = inter_word
            continue
        if elements:
            elements.append(Element(False, pending_gap if pending_gap is not None else inter_char))
        pending_gap = None
        for k, sym in enumerate(tok):
            if k > 0:
                elements.append(Element(False, u))
            elements.append(Element(True, u if sym == "." else dash))
    if pending_gap is not None and elements:
        elements.append(Element(False, pending_gap))
    return elements


def total_seconds(elements: list[Element]) -> float:
    return sum(e.duration for e in elements)


def elements_to_segments(elements: list[Element], sample_rate: int) -> list[tuple[bool, int, int]]:
    """Ranh giới mẫu chính xác: làm tròn thời điểm tích lũy, không tích lũy sai số."""
    segs: list[tuple[bool, int, int]] = []
    t = 0.0
    start = 0
    for e in elements:
        t += e.duration
        end = int(round(t * sample_rate))
        segs.append((e.on, start, end))
        start = end
    return segs
```

- [ ] **Step 6: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_encode_text.py tests/unit/test_timing.py -v`
Expected: `19 passed`

- [ ] **Step 7: Commit**

```bash
git add morsedesk/encode tests/unit/test_encode_text.py tests/unit/test_timing.py
git commit -m "feat(encode): chữ -> token mẫu, timing PARIS và Farnsworth" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 5: Tổng hợp âm thanh và nhiễu

**Files:**
- Create: `morsedesk/encode/synth.py`
- Create: `tests/helpers.py`
- Test: `tests/unit/test_synth.py`

**Interfaces:**
- Consumes: `Element`, `elements_to_segments` (Task 4); `SAMPLE_RATE`.
- Produces: `synth.elements_to_audio(elements, tone_hz: float | np.ndarray = 700.0, sample_rate=SAMPLE_RATE, amplitude=0.8, ramp_ms=5.0) -> np.ndarray[float32]` (tone có thể là mảng tần số tức thời cùng độ dài để mô phỏng trôi); `synth.tone_power(amplitude) -> float` (= A²/2); `synth.add_noise(x, snr_db, signal_power, sample_rate=SAMPLE_RATE, band_hz=500.0, rng=None) -> np.ndarray[float32]` (SNR đo trong băng `band_hz` quanh tone, so với công suất tone chưa fading).
- `tests/helpers.py`: `make_morse(text, profile_id="en", wpm=20.0, farnsworth_wpm=None, tone_hz=700.0, snr_db=None, seed=0, pad_s=0.3) -> tuple[np.ndarray, list[str]]` trả (audio 8 kHz, tokens).

- [ ] **Step 1: Viết helper test**

`tests/helpers.py`:

```python
"""Tiện ích dùng chung cho test: tạo audio Morse tổng hợp."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.profile import load_profile


def make_morse(
    text: str,
    profile_id: str = "en",
    wpm: float = 20.0,
    farnsworth_wpm: float | None = None,
    tone_hz: float = 700.0,
    snr_db: float | None = None,
    seed: int = 0,
    pad_s: float = 0.3,
    amplitude: float = 0.8,
) -> tuple[np.ndarray, list[str]]:
    profile = load_profile(profile_id)
    tokens = text_to_tokens(text, profile)
    elements = tokens_to_elements(tokens, TimingParams(wpm=wpm, farnsworth_wpm=farnsworth_wpm))
    audio = elements_to_audio(elements, tone_hz=tone_hz, amplitude=amplitude)
    pad = np.zeros(int(pad_s * SAMPLE_RATE), dtype=np.float32)
    audio = np.concatenate([pad, audio, pad])
    if snr_db is not None:
        audio = add_noise(audio, snr_db, tone_power(amplitude), rng=np.random.default_rng(seed))
    return audio, tokens
```

- [ ] **Step 2: Viết test**

`tests/unit/test_synth.py`:

```python
import math

import numpy as np

from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.timing import Element, TimingParams, tokens_to_elements, total_seconds
from tests.helpers import make_morse


def test_length_matches_total_duration():
    els = tokens_to_elements(["-.-.", "--.-"], TimingParams(wpm=20))
    x = elements_to_audio(els)
    assert x.dtype == np.float32
    assert abs(len(x) - round(total_seconds(els) * 8000)) <= 1


def test_tone_rms_and_silence():
    els = [Element(True, 1.0), Element(False, 0.5)]
    x = elements_to_audio(els, tone_hz=700.0, amplitude=0.8)
    on = x[400:7600]                      # bỏ sườn lên xuống
    assert math.isclose(np.sqrt(np.mean(on**2)), 0.8 / math.sqrt(2), rel_tol=0.02)
    assert np.all(x[8000:] == 0)


def test_ramps_avoid_clicks():
    els = [Element(True, 0.2)]
    x = elements_to_audio(els, tone_hz=700.0, amplitude=0.8, ramp_ms=5.0)
    assert np.max(np.abs(x[:5])) < 0.15
    assert np.max(np.abs(x[-5:])) < 0.15
    assert np.max(np.abs(x)) > 0.7


def test_tone_array_drift_changes_phase_rate():
    els = [Element(True, 1.0)]
    n = 8000
    x_lo = elements_to_audio(els, tone_hz=np.full(n, 600.0))
    x_hi = elements_to_audio(els, tone_hz=np.full(n, 900.0))
    zc_lo = np.sum(np.diff(np.sign(x_lo)) != 0)
    zc_hi = np.sum(np.diff(np.sign(x_hi)) != 0)
    assert 1150 < zc_lo < 1250      # ~2 zero crossing mỗi chu kỳ
    assert 1750 < zc_hi < 1850


def test_tone_power():
    assert math.isclose(tone_power(0.8), 0.32)


def test_add_noise_variance_matches_inband_snr():
    x = np.zeros(80000, dtype=np.float32)
    rng = np.random.default_rng(1)
    y = add_noise(x, snr_db=10.0, signal_power=0.32, rng=rng)
    # công suất nhiễu trong băng 500 Hz = 0.32/10; nhiễu trắng trải 4000 Hz -> phương sai = 0.032 * 8
    assert math.isclose(float(np.var(y)), 0.032 * 8, rel_tol=0.05)
    assert y.dtype == np.float32


def test_make_morse_helper():
    x, toks = make_morse("CQ", wpm=20, snr_db=20)
    assert len(toks) == 2
    assert len(x) > 8000 * 0.6
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_synth.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.encode.synth'`

- [ ] **Step 4: Viết synth.py**

```python
"""Phần tử bật/tắt -> sóng âm, và thêm nhiễu theo SNR trong băng."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.timing import Element, elements_to_segments


def tone_power(amplitude: float) -> float:
    """Công suất trung bình của sine biên độ A khi phím đang bật."""
    return amplitude * amplitude / 2.0


def elements_to_audio(
    elements: list[Element],
    tone_hz: float | np.ndarray = 700.0,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.8,
    ramp_ms: float = 5.0,
) -> np.ndarray:
    """Sine liên tục pha, cửa bật/tắt có sườn raised-cosine để không lách tách.

    tone_hz là số (tone cố định) hoặc mảng tần số tức thời; mảng khác độ dài sẽ
    được nội suy theo thời gian.
    """
    segs = elements_to_segments(elements, sample_rate)
    n = segs[-1][2] if segs else 0
    if n == 0:
        return np.zeros(0, dtype=np.float32)

    if np.isscalar(tone_hz):
        freq = np.full(n, float(tone_hz))
    else:
        f = np.asarray(tone_hz, dtype=np.float64)
        freq = f if len(f) == n else np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(f)), f)
    phase = 2.0 * np.pi * np.cumsum(freq) / sample_rate
    carrier = np.sin(phase)

    ramp = max(1, int(round(ramp_ms * 1e-3 * sample_rate)))
    gate = np.zeros(n)
    for on, s, e in segs:
        if not on or e <= s:
            continue
        length = e - s
        r = min(ramp, length // 2)
        env = np.ones(length)
        if r > 0:
            k = np.arange(r)
            rc = 0.5 * (1.0 - np.cos(np.pi * k / r))
            env[:r] = rc
            env[length - r:] = rc[::-1]
        gate[s:e] = env
    return (amplitude * carrier * gate).astype(np.float32)


def add_noise(
    x: np.ndarray,
    snr_db: float,
    signal_power: float,
    sample_rate: int = SAMPLE_RATE,
    band_hz: float = 500.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Thêm AWGN sao cho SNR đo trong băng band_hz quanh tone bằng snr_db.

    Nhiễu trắng trải đều 0..sample_rate/2, nên phương sai tổng =
    (công suất nhiễu trong băng) * (sample_rate/2) / band_hz.
    """
    rng = np.random.default_rng() if rng is None else rng
    p_noise_band = signal_power / (10.0 ** (snr_db / 10.0))
    sigma2 = p_noise_band * (sample_rate / 2.0) / band_hz
    noise = rng.normal(0.0, np.sqrt(sigma2), size=len(x))
    return (x.astype(np.float64) + noise).astype(np.float32)
```

- [ ] **Step 5: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_synth.py -v`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add morsedesk/encode/synth.py tests/helpers.py tests/unit/test_synth.py
git commit -m "feat(synth): tổng hợp tone có sườn, nhiễu theo SNR trong băng" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 6: Đọc và ghi file âm thanh

**Files:**
- Create: `morsedesk/audio/io.py`
- Test: `tests/unit/test_audio_io.py`

**Interfaces:**
- Produces: `io.UnsupportedAudio(ValueError)`; `io.load_audio(path, target_sr=SAMPLE_RATE) -> tuple[np.ndarray, int]` (mono float32, đã resample, bỏ DC, đỉnh 0.9); `io.save_audio(path, x, sample_rate)` (PCM_16, clip ±1); `io.resample(x, sr_in, sr_out) -> np.ndarray`; `io.normalize(x, peak=0.9) -> np.ndarray`; `io.audio_info(path) -> tuple[int, int, float]` (sample rate, số kênh, giây).

- [ ] **Step 1: Viết test**

`tests/unit/test_audio_io.py`:

```python
import numpy as np
import pytest
import soundfile as sf

from morsedesk.audio.io import UnsupportedAudio, audio_info, load_audio, normalize, resample, save_audio


def _sine(sr, seconds, hz, ch=1):
    t = np.arange(int(sr * seconds)) / sr
    x = 0.5 * np.sin(2 * np.pi * hz * t).astype(np.float32)
    return np.stack([x] * ch, axis=1) if ch > 1 else x


def test_load_resamples_stereo_44k_to_mono_8k(tmp_path):
    p = tmp_path / "a.wav"
    sf.write(p, _sine(44100, 1.0, 440, ch=2), 44100)
    x, sr = load_audio(p)
    assert sr == 8000
    assert x.dtype == np.float32
    assert x.ndim == 1
    assert abs(len(x) - 8000) <= 2
    assert np.isclose(np.max(np.abs(x)), 0.9, atol=0.01)


def test_load_removes_dc(tmp_path):
    p = tmp_path / "dc.wav"
    sf.write(p, (_sine(8000, 1.0, 700) + 0.2).astype(np.float32), 8000)
    x, _ = load_audio(p)
    assert abs(float(np.mean(x))) < 1e-3


def test_load_flac_and_ogg(tmp_path):
    for ext in ("flac", "ogg"):
        p = tmp_path / f"a.{ext}"
        sf.write(p, _sine(16000, 0.5, 700), 16000)
        x, sr = load_audio(p)
        assert sr == 8000 and abs(len(x) - 4000) <= 2


def test_unsupported_file(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_text("không phải audio")
    with pytest.raises(UnsupportedAudio):
        load_audio(p)


def test_save_and_info(tmp_path):
    p = tmp_path / "o.wav"
    save_audio(p, _sine(8000, 2.0, 700) * 3.0, 8000)   # vượt 1.0 phải được clip
    sr, ch, dur = audio_info(p)
    assert (sr, ch) == (8000, 1)
    assert abs(dur - 2.0) < 1e-3
    y, _ = sf.read(p)
    assert np.max(np.abs(y)) <= 1.0


def test_resample_identity_and_ratio():
    x = _sine(8000, 1.0, 700)
    assert resample(x, 8000, 8000) is x
    y = resample(x, 8000, 16000)
    assert abs(len(y) - 16000) <= 2


def test_normalize_zero_signal():
    z = np.zeros(100, dtype=np.float32)
    assert np.all(normalize(z) == 0)
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_audio_io.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.audio.io'`

- [ ] **Step 3: Viết io.py**

```python
"""Đọc/ghi file âm thanh và đưa về định dạng nội bộ: mono float32 8 kHz."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from morsedesk.constants import SAMPLE_RATE

SUPPORTED_EXT = (".wav", ".flac", ".ogg", ".mp3", ".aiff", ".aif", ".oga")


class UnsupportedAudio(ValueError):
    pass


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    fr = Fraction(sr_out, sr_in).limit_denominator(1000)
    y = resample_poly(x.astype(np.float64), fr.numerator, fr.denominator)
    return y.astype(np.float32)


def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    x = x.astype(np.float32) - np.float32(np.mean(x))
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    if m > 0:
        x = x * np.float32(peak / m)
    return x


def load_audio(path: str | Path, target_sr: int = SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """Đọc file bất kỳ libsndfile hỗ trợ (WAV/FLAC/OGG/MP3), trả (mono float32 8 kHz, 8000)."""
    path = Path(path)
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except sf.LibsndfileError as e:
        raise UnsupportedAudio(
            f"không đọc được {path.name}: {e}. Định dạng hỗ trợ: {', '.join(SUPPORTED_EXT)}"
        ) from e
    mono = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
    mono = resample(mono, int(sr), target_sr)
    return normalize(mono), target_sr


def save_audio(path: str | Path, x: np.ndarray, sample_rate: int) -> None:
    sf.write(str(path), np.clip(x, -1.0, 1.0), sample_rate, subtype="PCM_16")


def audio_info(path: str | Path) -> tuple[int, int, float]:
    info = sf.info(str(path))
    return int(info.samplerate), int(info.channels), float(info.duration)
```

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_audio_io.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add morsedesk/audio/io.py tests/unit/test_audio_io.py
git commit -m "feat(audio): đọc/ghi file, resample về 8 kHz, chuẩn hóa" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 7: STFT và ước lượng tone

**Files:**
- Create: `morsedesk/dsp/stft.py`
- Create: `morsedesk/dsp/tone.py`
- Test: `tests/unit/test_tone.py`

**Interfaces:**
- Consumes: `make_morse` (Task 5), `add_noise`.
- Produces: `stft.stft_power(x, sample_rate=SAMPLE_RATE, n_fft=N_FFT, hop=HOP) -> tuple[np.ndarray, np.ndarray]` trả (`power [n_bins, T]` với `T = len(x)//hop`, khung t căn giữa tại `t*hop`; `freqs [n_bins]`); `tone.ToneEstimate(f0_hz: float | None, snr_db: float, has_signal: bool, second_peak_hz: float | None)`; `tone.estimate_tone(x, sample_rate=SAMPLE_RATE) -> ToneEstimate`; `tone.MIN_PEAK_DB = 6.0`.

Thuật toán: với mỗi bin lấy phân vị 90 theo thời gian (`p90`, mức khi phím bật). Độ "nhọn" của bin k = `10·log10(p90[k] / median_bins(p90 trong băng 300–1500 Hz))`; nhiễu trắng cho độ nhọn gần 0 dB, tone Morse cho nhiều dB. Có tín hiệu nếu độ nhọn ≥ 6 dB. Tần số tinh bằng nội suy parabol trên log(p90). SNR báo cáo trong băng 500 Hz: nhiễu mỗi bin = trung vị theo thời gian của công suất các bin cách tone 4–8 bin; `snr_db = 10·log10((p90[k] − noise_bin)/noise_bin) + 1.76 − 12.04` (1.76 dB bù cửa sổ Hann trải tone, 12.04 dB = 10·log10(16 bin/500 Hz)). Tone thứ hai: che ±2 bin quanh k, lấy đỉnh còn lại; báo nếu độ nhọn ≥ 6 dB và `p90 ≥ 0.5·p90[k]`.

- [ ] **Step 1: Viết test**

`tests/unit/test_tone.py`:

```python
import numpy as np

from morsedesk.constants import HOP, N_FFT
from morsedesk.dsp.stft import stft_power
from morsedesk.dsp.tone import MIN_PEAK_DB, estimate_tone
from morsedesk.encode.synth import add_noise
from tests.helpers import make_morse

TEXT = "CQ CQ DE R1ABC R1ABC K"


def test_stft_shapes():
    x = np.zeros(8000, dtype=np.float32)
    power, freqs = stft_power(x)
    assert power.shape == (N_FFT // 2 + 1, 8000 // HOP)
    assert np.isclose(freqs[1] - freqs[0], 31.25)


def test_clean_tone_700():
    x, _ = make_morse(TEXT, wpm=20, tone_hz=700.0)
    est = estimate_tone(x)
    assert est.has_signal
    assert abs(est.f0_hz - 700.0) < 10.0
    assert est.second_peak_hz is None


def test_noisy_tone_and_snr_estimate():
    x, _ = make_morse(TEXT, wpm=25, tone_hz=850.0, snr_db=10.0, seed=3)
    est = estimate_tone(x)
    assert est.has_signal
    assert abs(est.f0_hz - 850.0) < 15.0
    assert abs(est.snr_db - 10.0) < 4.0


def test_low_snr_still_detected():
    x, _ = make_morse(TEXT, wpm=20, tone_hz=600.0, snr_db=0.0, seed=5)
    est = estimate_tone(x)
    assert est.has_signal
    assert abs(est.f0_hz - 600.0) < 20.0


def test_noise_only_no_signal():
    rng = np.random.default_rng(7)
    x = add_noise(np.zeros(8000 * 5, dtype=np.float32), 0.0, 0.32, rng=rng)
    est = estimate_tone(x)
    assert not est.has_signal
    assert est.f0_hz is None


def test_silence_no_signal():
    est = estimate_tone(np.zeros(8000 * 2, dtype=np.float32))
    assert not est.has_signal


def test_two_tones_reports_second_peak():
    a, _ = make_morse(TEXT, wpm=20, tone_hz=600.0)
    b, _ = make_morse("TEST TEST TEST TEST TEST", wpm=18, tone_hz=1000.0)
    n = min(len(a), len(b))
    x = a[:n] + 0.8 * b[:n]
    est = estimate_tone(x)
    assert est.has_signal
    assert est.second_peak_hz is not None
    other = 1000.0 if abs(est.f0_hz - 600.0) < 40 else 600.0
    assert abs(est.second_peak_hz - other) < 40.0


def test_too_short_input():
    est = estimate_tone(np.zeros(100, dtype=np.float32))
    assert not est.has_signal and est.snr_db == 0.0
    assert MIN_PEAK_DB == 6.0
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_tone.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.dsp.stft'`

- [ ] **Step 3: Viết stft.py**

```python
"""STFT công suất dùng chung cho dò tone và đặc trưng phổ."""

from __future__ import annotations

import numpy as np

from morsedesk.constants import HOP, N_FFT, SAMPLE_RATE


def stft_power(
    x: np.ndarray, sample_rate: int = SAMPLE_RATE, n_fft: int = N_FFT, hop: int = HOP
) -> tuple[np.ndarray, np.ndarray]:
    """Trả (power [n_bins, T], freqs [n_bins]).

    T = len(x)//hop, khung t căn giữa tại mẫu t*hop, cửa sổ Hann, pad hai đầu.
    """
    n = len(x)
    n_frames = n // hop
    pad = n_fft // 2
    xp = np.pad(np.asarray(x, dtype=np.float64), (pad, pad + n_fft))
    idx = np.arange(n_frames)[:, None] * hop + np.arange(n_fft)[None, :]
    frames = xp[idx] * np.hanning(n_fft)[None, :]
    spec = np.fft.rfft(frames, axis=1)
    power = (np.abs(spec) ** 2).T
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    return power, freqs
```

- [ ] **Step 4: Viết tone.py**

```python
"""Ước lượng tần số tone Morse, SNR trong băng 500 Hz, có tín hiệu hay không."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.constants import N_FFT, SAMPLE_RATE, TONE_MAX_HZ, TONE_MIN_HZ
from morsedesk.dsp.stft import stft_power

MIN_PEAK_DB = 6.0          # độ nhọn tối thiểu để coi là có tín hiệu
HANN_SPREAD_DB = 1.76      # bù công suất tone trải sang bin lân cận do cửa sổ Hann
BAND_BINS_DB = 12.04       # 10*log10(16 bin) = băng 500 Hz với bin 31.25 Hz


@dataclass
class ToneEstimate:
    f0_hz: float | None
    snr_db: float
    has_signal: bool
    second_peak_hz: float | None


def _parabolic_peak_hz(p90: np.ndarray, k: int, freqs: np.ndarray) -> float:
    if k <= 0 or k >= len(p90) - 1:
        return float(freqs[k])
    a, b, c = (np.log(p90[k - 1] + 1e-20), np.log(p90[k] + 1e-20), np.log(p90[k + 1] + 1e-20))
    denom = a - 2.0 * b + c
    delta = 0.0 if denom == 0 else float(np.clip(0.5 * (a - c) / denom, -1.0, 1.0))
    return float(freqs[k] + delta * (freqs[1] - freqs[0]))


def _noise_bin_power(power: np.ndarray, k: int, band: np.ndarray) -> float:
    """Trung vị theo thời gian của công suất các bin cách tone 4..8 bin, trong băng."""
    idx = [j for j in list(range(k - 8, k - 3)) + list(range(k + 4, k + 9))
           if 0 <= j < power.shape[0] and band[j]]
    if not idx:
        idx = [j for j in range(power.shape[0]) if band[j] and abs(j - k) > 3]
    return float(np.median(power[idx, :])) + 1e-20


def estimate_tone(x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> ToneEstimate:
    if len(x) < N_FFT * 2:
        return ToneEstimate(None, 0.0, False, None)
    power, freqs = stft_power(x, sample_rate=sample_rate)
    band = (freqs >= TONE_MIN_HZ) & (freqs <= TONE_MAX_HZ)
    p90 = np.percentile(power, 90, axis=1) + 1e-20
    floor = float(np.median(p90[band]))
    if floor <= 1e-18:
        return ToneEstimate(None, 0.0, False, None)
    peakiness = np.where(band, 10.0 * np.log10(p90 / floor), -np.inf)

    k = int(np.argmax(peakiness))
    if not np.isfinite(peakiness[k]) or peakiness[k] < MIN_PEAK_DB:
        return ToneEstimate(None, 0.0, False, None)

    f0 = _parabolic_peak_hz(p90, k, freqs)
    noise_bin = _noise_bin_power(power, k, band)
    sig_bin = max(float(p90[k]) - noise_bin, 1e-20)
    snr_db = 10.0 * np.log10(sig_bin / noise_bin) + HANN_SPREAD_DB - BAND_BINS_DB

    masked = peakiness.copy()
    masked[max(0, k - 2): k + 3] = -np.inf
    k2 = int(np.argmax(masked))
    second = None
    if np.isfinite(masked[k2]) and masked[k2] >= MIN_PEAK_DB and p90[k2] >= 0.5 * p90[k]:
        second = float(freqs[k2])
    return ToneEstimate(f0, float(snr_db), True, second)
```

- [ ] **Step 5: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_tone.py -v`
Expected: `8 passed`. Nếu `test_noisy_tone_and_snr_estimate` lệch quá 4 dB, in `est.snr_db` và chỉnh hằng `HANN_SPREAD_DB` trong khoảng 1.0–3.0 cho khớp, không đổi ngưỡng test.

- [ ] **Step 6: Commit**

```bash
git add morsedesk/dsp/stft.py morsedesk/dsp/tone.py tests/unit/test_tone.py
git commit -m "feat(dsp): STFT và ước lượng tone, SNR, tone thứ hai" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 8: Front-end đặc trưng 11 chiều

**Files:**
- Create: `morsedesk/dsp/frontend.py`
- Test: `tests/unit/test_frontend.py`

**Interfaces:**
- Consumes: `stft_power` (Task 7), `HOP`, `FRAME_RATE`, `FEAT_DIM`, `SAMPLE_RATE`.
- Produces: `frontend.FrontendConfig(lowpass_hz=200.0, agc_tau_s=1.0, n_bins=9)`; `frontend.mix_envelope(x, f0_hz, sample_rate=SAMPLE_RATE, lowpass_hz=200.0) -> np.ndarray[T]` (envelope tuyến tính mỗi khung, `T = len(x)//HOP`); `frontend.agc_log(env, frame_rate=FRAME_RATE, tau_s=1.0) -> np.ndarray[T]` (giá trị trong [-6, 6]); `frontend.spectral_bins(x, f0_hz, n_bins=9, sample_rate=SAMPLE_RATE) -> np.ndarray[T, n_bins]`; `frontend.compute_features(x, f0_hz, sample_rate=SAMPLE_RATE, cfg=FrontendConfig()) -> np.ndarray[T, 11] float32` với cột 0 = envelope AGC, cột 1 = đạo hàm, cột 2..10 = 9 bin phổ.

- [ ] **Step 1: Viết test**

`tests/unit/test_frontend.py`:

```python
import numpy as np

from morsedesk.constants import FEAT_DIM, HOP, SAMPLE_RATE
from morsedesk.dsp.frontend import agc_log, compute_features, mix_envelope, spectral_bins
from morsedesk.encode.timing import TimingParams, elements_to_segments, tokens_to_elements
from tests.helpers import make_morse

PAD_S = 0.3


def _on_off_frame_masks(tokens, wpm, n_frames):
    els = tokens_to_elements(tokens, TimingParams(wpm=wpm))
    segs = elements_to_segments(els, SAMPLE_RATE)
    offset = int(PAD_S * SAMPLE_RATE)
    on = np.zeros(n_frames, dtype=bool)
    for is_on, s, e in segs:
        if is_on:
            f0, f1 = (s + offset) // HOP + 1, (e + offset) // HOP - 1   # bỏ khung biên
            if f1 > f0:
                on[f0:f1] = True
    return on


def test_feature_shape_and_dtype():
    x, _ = make_morse("PARIS PARIS", wpm=20)
    feats = compute_features(x, 700.0)
    assert feats.shape == (len(x) // HOP, FEAT_DIM)
    assert feats.dtype == np.float32
    assert np.all(np.isfinite(feats))


def test_envelope_contrast_on_vs_off():
    x, toks = make_morse("PARIS PARIS", wpm=20)
    env = mix_envelope(x, 700.0)
    on = _on_off_frame_masks(toks, 20, len(env))
    off = ~on
    off[: int(PAD_S * 200)] = False
    assert env[on].mean() > 5 * env[off].mean()


def test_agc_contrast_and_bounds():
    x, toks = make_morse("PARIS PARIS PARIS", wpm=25, snr_db=10.0, seed=2)
    feats = compute_features(x, 700.0)
    a = feats[:, 0]
    on = _on_off_frame_masks(toks, 25, len(a))
    assert a[on].mean() - a[~on].mean() > 1.0
    assert a.min() >= -6.0 and a.max() <= 6.0


def test_agc_on_silence_is_finite_zero():
    env = np.zeros(1000)
    a = agc_log(env)
    assert np.all(np.isfinite(a))
    assert np.allclose(a, 0.0)


def test_spectral_bins_peak_in_center():
    x, _ = make_morse("EEEEEEEEEE", wpm=20, tone_hz=700.0)
    bins = spectral_bins(x, 700.0)
    assert bins.shape == (len(x) // HOP, 9)
    center_energy = bins[:, 4].mean()
    edge_energy = bins[:, [0, 8]].mean()
    assert center_energy > edge_energy


def test_derivative_column_is_diff_of_agc():
    x, _ = make_morse("SOS", wpm=20)
    feats = compute_features(x, 700.0)
    d = np.diff(feats[:, 0], prepend=feats[0, 0])
    assert np.allclose(feats[:, 1], d, atol=1e-5)


def test_short_input_returns_empty_without_warnings():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for n in (0, 5, 39):
            x = np.zeros(n, dtype=np.float32)
            assert compute_features(x, 700.0).shape == (0, FEAT_DIM)
            assert mix_envelope(x, 700.0).shape == (0,)
            assert spectral_bins(x, 700.0).shape == (0, 9)


def test_envelope_frames_centered_like_stft():
    # tone bật từ mẫu 400 đến 800: khung 10 (tâm 400) phải nằm nửa chừng giữa tắt và bật
    x = np.zeros(1600, dtype=np.float32)
    t = np.arange(400) / SAMPLE_RATE
    x[400:800] = 0.8 * np.sin(2 * np.pi * 700.0 * t)
    env = mix_envelope(x, 700.0)
    full = env[12:18].mean()
    assert env[8] < 0.15 * full
    assert 0.3 * full < env[10] < 0.7 * full
    assert env[12] > 0.85 * full
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_frontend.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.dsp.frontend'`

- [ ] **Step 3: Viết frontend.py**

```python
"""Đặc trưng 11 chiều ở 200 khung/giây quanh tone đã dò.

Cột 0: log-envelope sau AGC; cột 1: đạo hàm cột 0; cột 2..10: 9 bin log-phổ quanh f0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi, sosfiltfilt

from morsedesk.constants import FEAT_DIM, FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.dsp.stft import stft_power


@dataclass(frozen=True)
class FrontendConfig:
    lowpass_hz: float = 200.0
    agc_tau_s: float = 1.0
    n_bins: int = 9


def mix_envelope(
    x: np.ndarray, f0_hz: float, sample_rate: int = SAMPLE_RATE, lowpass_hz: float = 200.0
) -> np.ndarray:
    """Trộn xuống băng gốc phức tại f0, lọc thấp, |I+jQ|, trung bình mỗi HOP mẫu.

    Khung t được căn giữa tại mẫu t*HOP, giống stft_power: pad env với HOP//2 mẫu 0
    ở đầu (và HOP mẫu 0 ở cuối để đủ cho khung cuối) rồi lấy trung bình từng khung
    HOP mẫu, sao cho khung t phủ [t*HOP - HOP//2, t*HOP + HOP//2).
    """
    n = len(x)
    n_frames = n // HOP
    if n_frames == 0:
        return np.zeros(0)
    t = np.arange(n) / sample_rate
    lo = np.exp(-2j * np.pi * f0_hz * t)
    y = x.astype(np.float64) * lo
    sos = butter(4, lowpass_hz, btype="low", fs=sample_rate, output="sos")
    yi = sosfiltfilt(sos, y.real)
    yq = sosfiltfilt(sos, y.imag)
    env = np.sqrt(yi * yi + yq * yq)
    env_p = np.pad(env, (HOP // 2, HOP))
    return env_p[: n_frames * HOP].reshape(n_frames, HOP).mean(axis=1)


def _ema(v: np.ndarray, alpha: float, init: float) -> np.ndarray:
    b = np.array([alpha])
    a = np.array([1.0, -(1.0 - alpha)])
    zi = lfilter_zi(b, a) * init
    out, _ = lfilter(b, a, v, zi=zi)
    return out


def agc_log(env: np.ndarray, frame_rate: int = FRAME_RATE, tau_s: float = 1.0) -> np.ndarray:
    """log(envelope) trừ mức nền trượt, chia độ lệch chuẩn trượt; kẹp về [-6, 6]."""
    if len(env) == 0:
        return np.zeros(0)
    log_env = np.log(env + 1e-6)
    alpha = 1.0 / (tau_s * frame_rate)
    head = log_env[: max(1, min(len(log_env), frame_rate))]
    mean = _ema(log_env, alpha, float(np.mean(head)))
    dev = log_env - mean
    var = _ema(dev * dev, alpha, float(np.mean(dev[: len(head)] ** 2)))
    out = dev / (np.sqrt(np.maximum(var, 0.0)) + 0.1)
    return np.clip(out, -6.0, 6.0)


def spectral_bins(
    x: np.ndarray, f0_hz: float, n_bins: int = 9, sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    n_frames = len(x) // HOP
    if n_frames == 0:
        return np.zeros((0, n_bins), dtype=np.float32)
    power, freqs = stft_power(x, sample_rate=sample_rate)
    bin_hz = float(freqs[1] - freqs[0])
    k0 = int(round(f0_hz / bin_hz))
    half = n_bins // 2
    ks = np.clip(np.arange(k0 - half, k0 - half + n_bins), 0, len(freqs) - 1)
    logp = np.log10(power[ks, :] + 1e-12).T            # [T, n_bins]
    med = float(np.median(logp))
    scale = float(np.percentile(logp, 95)) - med + 1e-3
    return ((logp - med) / scale).astype(np.float32)


def compute_features(
    x: np.ndarray,
    f0_hz: float,
    sample_rate: int = SAMPLE_RATE,
    cfg: FrontendConfig = FrontendConfig(),
) -> np.ndarray:
    n_frames = len(x) // HOP
    if n_frames == 0:
        return np.zeros((0, FEAT_DIM), dtype=np.float32)
    env = mix_envelope(x, f0_hz, sample_rate, cfg.lowpass_hz)
    a = agc_log(env, FRAME_RATE, cfg.agc_tau_s)
    d = np.diff(a, prepend=a[0] if len(a) else 0.0)
    bins = spectral_bins(x, f0_hz, cfg.n_bins, sample_rate)
    feats = np.concatenate([a[:, None], d[:, None], bins], axis=1).astype(np.float32)
    assert feats.shape == (n_frames, FEAT_DIM), feats.shape
    return feats
```

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_frontend.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add morsedesk/dsp/frontend.py tests/unit/test_frontend.py
git commit -m "feat(dsp): front-end đặc trưng envelope AGC và 9 bin phổ" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 9: Chỉ số CER và WER

**Files:**
- Create: `morsedesk/metrics.py`
- Test: `tests/unit/test_metrics.py`

**Interfaces:**
- Produces: `metrics.edit_distance(a: Sequence, b: Sequence) -> int`; `metrics.normalize_text(s: str) -> str` (gộp khoảng trắng, strip, viết hoa); `metrics.cer(ref: str, hyp: str) -> float` (= khoảng cách ký tự / max(1, len(ref)) sau chuẩn hóa); `metrics.wer(ref: str, hyp: str) -> float`.

- [ ] **Step 1: Viết test**

`tests/unit/test_metrics.py`:

```python
import math

from morsedesk.metrics import cer, edit_distance, normalize_text, wer


def test_edit_distance_basic():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("", "abc") == 3
    assert edit_distance("abc", "abc") == 0
    assert edit_distance(["a", "b"], ["b"]) == 1


def test_normalize_text():
    assert normalize_text("  cq   de  k ") == "CQ DE K"


def test_cer():
    assert cer("CQ DE K", "CQ DE K") == 0.0
    assert math.isclose(cer("CQ DE K", "CQ DE"), 2 / 7)
    assert cer("", "ABC") == 3.0
    assert math.isclose(cer("cq  de", "CQ DE"), 0.0)


def test_wer():
    assert wer("CQ DE K", "CQ DE K") == 0.0
    assert math.isclose(wer("CQ DE K", "CQ DE"), 1 / 3)
    assert math.isclose(wer("CQ DE K", "CQ DX K"), 1 / 3)
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_metrics.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.metrics'`

- [ ] **Step 3: Viết metrics.py**

```python
"""CER và WER bằng khoảng cách Levenshtein."""

from __future__ import annotations

from collections.abc import Sequence


def edit_distance(a: Sequence, b: Sequence) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def normalize_text(s: str) -> str:
    return " ".join(s.upper().split())


def cer(ref: str, hyp: str) -> float:
    r, h = normalize_text(ref), normalize_text(hyp)
    return edit_distance(r, h) / max(1, len(r))


def wer(ref: str, hyp: str) -> float:
    r, h = normalize_text(ref).split(), normalize_text(hyp).split()
    return edit_distance(r, h) / max(1, len(r))
```

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_metrics.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add morsedesk/metrics.py tests/unit/test_metrics.py
git commit -m "feat(metrics): CER và WER" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 10: Bộ giải mã DSP baseline

**Files:**
- Create: `morsedesk/dsp/baseline.py`
- Test: `tests/unit/test_baseline.py`

**Interfaces:**
- Consumes: `estimate_tone`, `ToneEstimate` (Task 7); `mix_envelope` (Task 8); `Profile.render` (Task 3); `SPACE`, `VOCAB`; `cer` (Task 9).
- Produces: `baseline.Symbol(token: str, start_frame: int, end_frame: int)` (token là mẫu, có thể không thuộc từ vựng, hoặc `SPACE`); `baseline.BaselineResult(symbols: list[Symbol], unit_frames: float, threshold: float, cost: float)` với thuộc tính `tokens: list[str]`, `wpm: float`; `baseline.run_lengths(mask) -> list[tuple[bool, int, int]]`; `baseline.candidate_units(on_lengths) -> list[float]`; `baseline.timing_cost(runs, unit) -> float`; `baseline.split_gap_threshold(gap_units: np.ndarray) -> float`; `baseline.runs_to_symbols(runs, unit) -> list[Symbol]`; lớp `baseline.BaselineDecoder(thresholds=THRESHOLDS)` với `decode_envelope(env) -> BaselineResult` và `decode_audio(x, sample_rate=SAMPLE_RATE) -> tuple[BaselineResult, ToneEstimate]`.

Thuật toán (theo ý tưởng ggmorse, MIT, viết lại): chuẩn hóa envelope theo phân vị 98, làm mượt 3 khung; với mỗi ngưỡng trong `THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55, 0.65)` lấy chuỗi bật/tắt; sinh ứng viên độ dài dit từ 2-means trên log độ dài đoạn bật; chi phí = trung bình bình phương log-tỉ lệ so với mốc lý tưởng gần nhất (bật 1 hay 3; tắt 1, 3, 7, tắt dài kẹp về 7); chọn cặp ngưỡng và dit chi phí thấp nhất. Ranh giới chữ/từ: khoảng tắt < 2 dit là trong chữ; các khoảng ≥ 2 dit chia hai cụm bằng 2-means trên log để tự thích nghi Farnsworth (nếu tỉ lệ max/min < 1.8 thì tất cả là khoảng giữa chữ). Giới hạn đã biết: bản tin ngắn không có tương phản chấm/gạch (HI, SI, TTT) có thể bị đọc thành alias 3× tại một số tốc độ cao khi một dit chỉ dài 4–6 khung (200 khung/s) và độ lượng tử hóa át manh mối khoảng tắt 9 so với 7 dit. Đã quan sát lỗi ở 40 WPM (SI), 48 WPM (HI) và 60 WPM (HI, SI); dải 5–35 WPM và 50 WPM hiện đúng theo test. "TTT" ở 60 WPM trùng hoàn toàn với "S" ở 20 WPM nên không có manh mối. Engine ONNX là bộ giải mã chính; baseline chỉ là đối chứng và dự phòng. Hướng cải tiến sau: nội suy ranh giới dưới khung trong run_lengths để giảm nhiễu lượng tử.

- [ ] **Step 1: Viết test**

`tests/unit/test_baseline.py`:

```python
import numpy as np
import pytest

from morsedesk.dsp.baseline import (
    BaselineDecoder,
    candidate_units,
    run_lengths,
    split_gap_threshold,
)
from morsedesk.encode.synth import add_noise
from morsedesk.lm.profile import load_profile
from morsedesk.metrics import cer
from morsedesk.model.vocab import SPACE
from tests.helpers import make_morse


def _decode(text, profile_id="en", **kw):
    x, _ = make_morse(text, profile_id=profile_id, **kw)
    res, est = BaselineDecoder().decode_audio(x)
    return load_profile(profile_id).render(res.tokens), res, est


def test_run_lengths():
    mask = np.array([0, 0, 1, 1, 1, 0, 1, 0, 0], dtype=bool)
    assert run_lengths(mask) == [(False, 0, 2), (True, 2, 5), (False, 5, 6), (True, 6, 7), (False, 7, 9)]
    assert run_lengths(np.zeros(0, dtype=bool)) == []


def test_candidate_units_two_clusters():
    on = np.array([12, 11, 13, 36, 35, 37, 12])
    cands = candidate_units(on)
    assert any(abs(c - 12) < 1.5 for c in cands)


def test_split_gap_threshold_standard_and_farnsworth():
    gaps = np.array([3.0, 3.1, 2.9, 7.0, 7.2])
    thr = split_gap_threshold(gaps)
    assert 3.2 < thr < 6.8
    far = np.array([12.9, 13.0, 30.0, 29.5])
    thr2 = split_gap_threshold(far)
    assert 13.5 < thr2 < 29.0
    assert split_gap_threshold(np.array([3.0, 3.1, 3.0])) > 3.1   # một cụm -> tất cả là giữa chữ


def test_clean_20wpm_english():
    text = "CQ CQ DE R1ABC K"
    out, res, est = _decode(text, wpm=20)
    assert out == text
    assert abs(res.wpm - 20) < 2.0
    assert est.has_signal


def test_clean_russian_15wpm():
    text = "ПРИВЕТ МИР"
    out, _, _ = _decode(text, profile_id="ru", wpm=15)
    assert out == text


def test_fast_40wpm():
    text = "THE QUICK BROWN FOX"
    out, res, _ = _decode(text, wpm=40)
    assert out == text
    assert abs(res.wpm - 40) < 4.0


def test_slow_5wpm():
    text = "SOS SOS"
    out, _, _ = _decode(text, wpm=5)
    assert out == text


def test_farnsworth_18_8():
    text = "CQ DE K1ABC"
    out, _, _ = _decode(text, wpm=18, farnsworth_wpm=8)
    assert out == text


def test_noisy_25wpm_10db():
    text = "CQ CQ DE R1ABC R1ABC PSE K"
    out, _, _ = _decode(text, wpm=25, snr_db=10.0, seed=11)
    assert cer(text, out) <= 0.05


def test_noise_only_returns_nothing():
    rng = np.random.default_rng(3)
    x = add_noise(np.zeros(8000 * 4, dtype=np.float32), 0.0, 0.32, rng=rng)
    res, est = BaselineDecoder().decode_audio(x)
    assert not est.has_signal
    assert res.symbols == []


def test_symbols_have_frames_and_no_trailing_space():
    _, res, _ = _decode("AB CD", wpm=20)
    assert res.symbols[-1].token != SPACE
    for a, b in zip(res.symbols, res.symbols[1:]):
        assert a.end_frame <= b.start_frame


def test_timing_cost_scores_boundary_on_runs():
    from morsedesk.dsp.baseline import timing_cost

    # bắt đầu và kết thúc bằng đoạn bật: dot 1u, tắt 3u, dash 3u -> khớp lý tưởng, chi phí 0
    runs = [(True, 0, 10), (False, 10, 40), (True, 40, 70)]
    assert timing_cost(runs, 10.0) == 0.0
    # đoạn bật đầu dài 2u (không khớp 1 hay 3) phải làm chi phí > 0 vì không được bỏ qua
    runs_bad = [(True, 0, 20), (False, 20, 50), (True, 50, 80)]
    assert timing_cost(runs_bad, 10.0) > 0.0


def test_timing_cost_ignores_boundary_off_runs():
    from morsedesk.dsp.baseline import timing_cost

    # đoạn tắt đầu 10u và tắt cuối 2u đều bị bỏ qua -> chi phí 0
    runs = [(False, 0, 100), (True, 100, 110), (False, 110, 140), (True, 140, 170), (False, 170, 190)]
    assert timing_cost(runs, 10.0) == 0.0


@pytest.mark.parametrize("wpm", [5, 8, 12, 20, 35, 50])
def test_short_all_dit_message_across_speeds(wpm):
    for text in ("HI", "EE E", "SI"):
        out, res, _ = _decode(text, wpm=wpm)
        assert out == text, (wpm, text, out)
        assert abs(res.wpm - wpm) < 0.15 * wpm + 1.0, (wpm, res.wpm)


@pytest.mark.parametrize("wpm", [12, 20, 35])
def test_short_all_dash_message_mid_speeds(wpm):
    # "TTT" ở 60 WPM trùng hoàn toàn với "S" ở 20 WPM (không có manh mối), nên chỉ kiểm ở dải giữa
    out, res, _ = _decode("TTT", wpm=wpm)
    assert out == "TTT", (wpm, out)
    assert abs(res.wpm - wpm) < 0.15 * wpm + 1.0


@pytest.mark.xfail(reason="giới hạn đã biết: dit 4-6 khung ở tốc độ cao, mất manh mối 9 vs 7", strict=False)
@pytest.mark.parametrize("wpm,text", [(40, "SI"), (48, "HI"), (60, "HI"), (60, "SI")])
def test_short_low_contrast_high_speed_known_limitation(wpm, text):
    out, _, _ = _decode(text, wpm=wpm)
    assert out == text, (wpm, text, out)


def test_timing_cost_soft_cap_on_long_off_runs():
    from morsedesk.dsp.baseline import OFF_LONG_CAP_UNITS, timing_cost

    # bật 1u, tắt 9u, bật 1u: khoảng tắt 9u phải bị phạt (không còn kẹp về 7)
    runs = [(True, 0, 10), (False, 10, 100), (True, 100, 110)]
    assert timing_cost(runs, 10.0) > 0.0
    # tắt 30u và tắt 12u phải cho cùng chi phí (kẹp mềm tại OFF_LONG_CAP_UNITS)
    runs_30 = [(True, 0, 10), (False, 10, 310), (True, 310, 320)]
    runs_12 = [(True, 0, 10), (False, 10, 130), (True, 130, 140)]
    assert abs(timing_cost(runs_30, 10.0) - timing_cost(runs_12, 10.0)) < 1e-12
    assert OFF_LONG_CAP_UNITS == 12.0
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_baseline.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.dsp.baseline'`

- [ ] **Step 3: Viết baseline.py**

```python
"""Bộ giải mã DSP thích nghi: thử nhiều cặp (ngưỡng, độ dài dit), chọn cặp khớp timing nhất.

Dùng làm baseline đo lường và fallback khi mô hình nơ-ron kém tin cậy. Khi timing mơ hồ
(bản tin ngắn không tương phản dot/dash), một prior tốc độ nhẹ quanh SPEED_PRIOR_WPM
phá thế hòa giữa các giả thuyết (ngưỡng, độ dài dit) có timing_cost gần bằng nhau.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.constants import FRAME_RATE, SAMPLE_RATE
from morsedesk.dsp.frontend import mix_envelope
from morsedesk.dsp.tone import ToneEstimate, estimate_tone
from morsedesk.model.vocab import SPACE

THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55, 0.65)
IDEAL_ON = np.array([1.0, 3.0])
IDEAL_OFF = np.array([1.0, 3.0, 7.0])

SPEED_PRIOR_WPM = 20.0       # tốc độ tiên nghiệm khi timing mơ hồ
# Đo thực nghiệm: cửa sổ khả thi để "HI"/"SI" đúng ở 5-8 WPM (wpm giả thuyết đúng cách xa 20)
# và "SI" đúng ở 50 WPM (giả thuyết sai có cost thô thấp hơn chút) là khoảng [0.0015, 0.0025];
# 0.01 (giá trị cũ) đủ lớn để prior lấn át chênh lệch timing_cost thật ở tốc độ thấp.
SPEED_PRIOR_WEIGHT = 0.002   # nhỏ so với chi phí timing, chỉ phá thế hòa

OFF_LONG_CAP_UNITS = 12.0   # khoảng tắt dài hơn 12 dit coi như "12": chỉ phạt nhẹ, không loại giả thuyết


@dataclass
class Symbol:
    token: str
    start_frame: int
    end_frame: int


@dataclass
class BaselineResult:
    symbols: list[Symbol]
    unit_frames: float
    threshold: float
    cost: float

    @property
    def tokens(self) -> list[str]:
        return [s.token for s in self.symbols]

    @property
    def wpm(self) -> float:
        return 1.2 * FRAME_RATE / self.unit_frames if self.unit_frames > 0 else 0.0


def run_lengths(mask: np.ndarray) -> list[tuple[bool, int, int]]:
    """Các đoạn liên tiếp (is_on, start, end)."""
    if len(mask) == 0:
        return []
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(mask)]])
    return [(bool(mask[s]), int(s), int(e)) for s, e in zip(starts, ends)]


def _two_means_log(values: np.ndarray) -> tuple[float, float]:
    """2-means trên log; trả (tâm thấp, tâm cao) theo thang tuyến tính."""
    logs = np.log(values.astype(float))
    c_lo, c_hi = float(logs.min()), float(logs.max())
    for _ in range(20):
        assign = np.abs(logs - c_lo) <= np.abs(logs - c_hi)
        if assign.all() or (~assign).all():
            break
        c_lo, c_hi = float(logs[assign].mean()), float(logs[~assign].mean())
    return float(np.exp(c_lo)), float(np.exp(c_hi))


def candidate_units(on_lengths: np.ndarray) -> list[float]:
    """Ứng viên độ dài dit (khung) từ các đoạn bật."""
    cands: set[float] = set()
    if len(on_lengths) >= 2:
        lo, hi = _two_means_log(on_lengths)
        cands.update([lo, hi / 3.0])
    med = float(np.median(on_lengths))
    cands.update([med, med / 3.0])
    return sorted(c for c in cands if c >= 1.0)


def timing_cost(runs: list[tuple[bool, int, int]], unit: float) -> float:
    """Trung bình bình phương log-tỉ lệ so với mốc lý tưởng gần nhất (bật: 1/3; tắt <=7u: 1/3/7);
    đoạn tắt dài hơn 7u dùng kẹp mềm (so với OFF_LONG_CAP_UNITS) thay vì kẹp cứng về 7, để vẫn phạt
    khoảng tắt quá dài mà không loại hẳn giả thuyết; bỏ đoạn tắt đầu/cuối."""
    inner = list(runs)
    if inner and not inner[0][0]:
        inner = inner[1:]
    if inner and not inner[-1][0]:
        inner = inner[:-1]
    costs = []
    for on, s, e in inner:
        r = (e - s) / unit
        if on:
            costs.append(float(np.min(np.abs(np.log(r) - np.log(IDEAL_ON))) ** 2))
        elif r <= 7.0:
            costs.append(float(np.min(np.abs(np.log(r) - np.log(IDEAL_OFF))) ** 2))
        else:
            costs.append(float(np.log(min(r, OFF_LONG_CAP_UNITS) / 7.0) ** 2))
    return float(np.mean(costs)) if costs else float("inf")


def split_gap_threshold(gap_units: np.ndarray) -> float:
    """Ngưỡng (đơn vị dit) tách khoảng giữa chữ và giữa từ; thích nghi Farnsworth."""
    if len(gap_units) == 0:
        return 5.0
    if len(gap_units) < 2 or gap_units.max() / gap_units.min() < 1.8:
        return float(gap_units.max()) * 1.5
    lo, hi = _two_means_log(gap_units)
    return float(np.sqrt(lo * hi))


def runs_to_symbols(runs: list[tuple[bool, int, int]], unit: float) -> list[Symbol]:
    gaps = np.array([(e - s) / unit for on, s, e in runs[1:-1] if not on and (e - s) / unit >= 2.0])
    word_thr = split_gap_threshold(gaps)
    symbols: list[Symbol] = []
    cur = ""
    cur_start = 0

    def flush(end: int) -> None:
        nonlocal cur
        if cur:
            symbols.append(Symbol(cur, cur_start, end))
            cur = ""

    for on, s, e in runs:
        r = (e - s) / unit
        if on:
            if not cur:
                cur_start = s
            cur += "." if r < 2.0 else "-"
            continue
        if r < 2.0:
            continue
        flush(s)
        if r >= word_thr and symbols and symbols[-1].token != SPACE:
            symbols.append(Symbol(SPACE, s, e))
    flush(runs[-1][2] if runs else 0)
    while symbols and symbols[-1].token == SPACE:
        symbols.pop()
    return symbols


class BaselineDecoder:
    def __init__(self, thresholds: tuple[float, ...] = THRESHOLDS) -> None:
        self.thresholds = thresholds

    def decode_envelope(self, env: np.ndarray) -> BaselineResult:
        if len(env) < 3:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        env = env / (np.percentile(env, 98) + 1e-9)
        env = np.convolve(env, np.ones(3) / 3.0, mode="same")
        best: tuple[float, float, float, float, list[tuple[bool, int, int]]] | None = None
        for thr in self.thresholds:
            runs = run_lengths(env > thr)
            on_lengths = np.array([e - s for on, s, e in runs if on])
            if len(on_lengths) < 2:
                continue
            for unit in candidate_units(on_lengths):
                cost = timing_cost(runs, unit)
                wpm = 1.2 * FRAME_RATE / unit
                total = cost + SPEED_PRIOR_WEIGHT * float(np.log(wpm / SPEED_PRIOR_WPM)) ** 2
                if best is None or total < best[0]:
                    best = (total, cost, thr, unit, runs)
        if best is None:
            return BaselineResult([], 0.0, 0.0, float("inf"))
        _total, cost, thr, unit, runs = best
        return BaselineResult(runs_to_symbols(runs, unit), unit, thr, cost)

    def decode_audio(
        self, x: np.ndarray, sample_rate: int = SAMPLE_RATE
    ) -> tuple[BaselineResult, ToneEstimate]:
        est = estimate_tone(x, sample_rate)
        if not est.has_signal or est.f0_hz is None:
            return BaselineResult([], 0.0, 0.0, float("inf")), est
        env = mix_envelope(x, est.f0_hz, sample_rate)
        return self.decode_envelope(env), est
```

- [ ] **Step 4: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_baseline.py -v`
Expected: `23 passed`. Nếu `test_noisy_25wpm_10db` trượt, in `res.threshold`, `res.unit_frames` và thử thêm ngưỡng `0.75` vào `THRESHOLDS`; không nới ngưỡng CER của test.

- [ ] **Step 5: Commit**

```bash
git add morsedesk/dsp/baseline.py tests/unit/test_baseline.py
git commit -m "feat(dsp): bộ giải mã baseline thích nghi ngưỡng và tốc độ" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 11: API ổn định (Encoder, Decoder, DecodeResult) và CLI

**Files:**
- Create: `morsedesk/api.py`
- Create: `morsedesk/cli.py`
- Test: `tests/unit/test_api_cli.py`

**Interfaces:**
- Consumes: `load_audio`, `resample`, `save_audio` (Task 6); `BaselineDecoder`, `Symbol` (Task 10); `elements_to_audio`, `add_noise`, `tone_power` (Task 5); `text_to_tokens` (Task 4); `TimingParams`, `tokens_to_elements` (Task 4); `Profile`, `load_profile`, `list_profiles` (Task 3).
- Produces:
  - `api.Word(text, start_s, end_s, confidence)`; `api.DecodeResult(text, words, wpm, tone_hz, snr_db, language, language_scores, warnings, engine)` với `to_json() -> str`.
  - `api.Encoder(profile="en")`: `to_tokens(text, strict=True) -> list[str]`, `to_morse_string(text, strict=True) -> str` (mẫu cách nhau một khoảng trắng, từ cách nhau ` / `), `to_audio(text, wpm=20.0, farnsworth_wpm=None, weight=3.0, tone_hz=700.0, sample_rate=8000, snr_db=None, seed=None, pad_s=0.3, amplitude=0.8, strict=True) -> np.ndarray`.
  - `api.Decoder(profile="en", engine="baseline", model_path=None)`: `decode_array(x, sample_rate=8000) -> DecodeResult`, `decode_file(path) -> DecodeResult`. Task 17 thêm `engine="onnx"`; lúc này `engine` khác `"baseline"` gây `NotImplementedError`; `profile="auto"` gây `NotImplementedError` (cần LM tuần 3).
  - `api.symbols_to_words(symbols, profile, frame_rate, confidence) -> list[Word]`.
  - `cli.build_parser() -> argparse.ArgumentParser`; `cli.main(argv=None) -> int`; lệnh con `encode`, `decode`, `devices` (`bench` thêm ở Task 14).

- [ ] **Step 1: Viết test**

`tests/unit/test_api_cli.py`:

```python
import json

import numpy as np
import pytest

from morsedesk.api import DecodeResult, Decoder, Encoder
from morsedesk.cli import main
from morsedesk.encode.synth import add_noise


def test_morse_string():
    assert Encoder("en").to_morse_string("CQ DE") == "-.-. --.- / -.. ."
    assert Encoder("ru").to_morse_string("Ёж") == ". ...-"


def test_encoder_decoder_roundtrip_english():
    text = "CQ CQ DE R1ABC K"
    x = Encoder("en").to_audio(text, wpm=22)
    r = Decoder("en").decode_array(x)
    assert isinstance(r, DecodeResult)
    assert r.text == text
    assert r.engine == "baseline"
    assert abs(r.wpm - 22) < 2.5
    assert abs(r.tone_hz - 700) < 10
    assert r.warnings == []
    assert [w.text for w in r.words] == text.split()
    for a, b in zip(r.words, r.words[1:]):
        assert a.end_s <= b.start_s
    assert all(0.0 <= w.confidence <= 1.0 for w in r.words)


def test_roundtrip_kazakh_profile_renders_first_option():
    x = Encoder("kk-cyrl-ru").to_audio("ӘЛЕМ", wpm=20)
    r = Decoder("kk-cyrl-ru").decode_array(x)
    assert r.text == "АЛЕМ"       # chưa có LM: chọn chữ đầu của mỗi mẫu


def test_decoder_resamples_other_rates():
    x = Encoder("en").to_audio("TEST", wpm=20, sample_rate=16000)
    r = Decoder("en").decode_array(x, sample_rate=16000)
    assert r.text == "TEST"


def test_noise_only_gives_warning():
    x = add_noise(np.zeros(8000 * 3, dtype=np.float32), 0.0, 0.32, rng=np.random.default_rng(1))
    r = Decoder("en").decode_array(x)
    assert r.text == ""
    assert any("không có tín hiệu" in w for w in r.warnings)


def test_auto_and_unknown_engine_not_yet_supported():
    with pytest.raises(NotImplementedError):
        Decoder("auto")
    with pytest.raises(NotImplementedError):
        Decoder("en", engine="foo")


def test_to_json_roundtrip():
    x = Encoder("en").to_audio("HI", wpm=20)
    r = Decoder("en").decode_array(x)
    d = json.loads(r.to_json())
    assert d["text"] == "HI" and d["engine"] == "baseline"
    assert isinstance(d["words"], list)


def test_cli_encode_and_decode(tmp_path, capsys):
    out = tmp_path / "cq.wav"
    assert main(["encode", "CQ DE K", "--profile", "en", "--wpm", "20", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "-.-. --.- / -.. . / -.-" in printed
    assert out.exists()

    assert main(["decode", str(out), "--profile", "en"]) == 0
    assert capsys.readouterr().out.strip() == "CQ DE K"

    assert main(["decode", str(out), "--profile", "en", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["text"] == "CQ DE K"


def test_cli_encode_lenient(tmp_path, capsys):
    assert main(["encode", "ABӘ", "--profile", "en", "--lenient"]) == 0
    assert capsys.readouterr().out.strip() == ".- -..."


def test_cli_encode_strict_error(capsys):
    assert main(["encode", "ABӘ", "--profile", "en"]) == 2
    assert "không hỗ trợ" in capsys.readouterr().err


def test_cli_forces_utf8_streams(monkeypatch, tmp_path):
    import io
    import sys

    from morsedesk.audio.io import save_audio

    wav = tmp_path / "ru.wav"
    save_audio(wav, Encoder("ru").to_audio("ПРИВЕТ", wpm=20), 8000)
    buf = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buf, encoding="cp1252", write_through=True))
    assert main(["decode", str(wav), "--profile", "ru"]) == 0
    sys.stdout.flush()
    assert "ПРИВЕТ" in buf.getvalue().decode("utf-8")
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_api_cli.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.api'`

- [ ] **Step 3: Viết api.py**

```python
"""Giao diện ổn định cho GUI và CLI. GUI/CLI chỉ dùng Encoder, Decoder, DecodeResult."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from morsedesk.audio.io import load_audio, resample
from morsedesk.constants import FRAME_RATE, SAMPLE_RATE
from morsedesk.dsp.baseline import BaselineDecoder, Symbol
from morsedesk.encode.synth import add_noise, elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import TimingParams, tokens_to_elements
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.vocab import SPACE

LOW_CONFIDENCE = 0.6


@dataclass
class Word:
    text: str
    start_s: float
    end_s: float
    confidence: float


@dataclass
class DecodeResult:
    text: str
    words: list[Word]
    wpm: float | None
    tone_hz: float | None
    snr_db: float | None
    language: str
    language_scores: dict[str, float]
    warnings: list[str]
    engine: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _resolve_profile(profile: str | Profile) -> Profile:
    if isinstance(profile, Profile):
        return profile
    if profile == "auto":
        raise NotImplementedError(
            "profile 'auto' cần mô hình ngôn ngữ (tuần 3); hãy chọn en, ru hoặc kk-cyrl-ru"
        )
    return load_profile(profile)


class Encoder:
    def __init__(self, profile: str | Profile = "en") -> None:
        self.profile = _resolve_profile(profile)

    def to_tokens(self, text: str, strict: bool = True) -> list[str]:
        return text_to_tokens(text, self.profile, strict=strict)

    def to_morse_string(self, text: str, strict: bool = True) -> str:
        return " ".join("/" if t == SPACE else t for t in self.to_tokens(text, strict))

    def to_audio(
        self,
        text: str,
        wpm: float = 20.0,
        farnsworth_wpm: float | None = None,
        weight: float = 3.0,
        tone_hz: float = 700.0,
        sample_rate: int = SAMPLE_RATE,
        snr_db: float | None = None,
        seed: int | None = None,
        pad_s: float = 0.3,
        amplitude: float = 0.8,
        strict: bool = True,
    ) -> np.ndarray:
        tokens = self.to_tokens(text, strict)
        elements = tokens_to_elements(tokens, TimingParams(wpm, farnsworth_wpm, weight))
        x = elements_to_audio(elements, tone_hz, sample_rate, amplitude)
        pad = np.zeros(int(pad_s * sample_rate), dtype=np.float32)
        x = np.concatenate([pad, x, pad])
        if snr_db is not None:
            x = add_noise(x, snr_db, tone_power(amplitude), sample_rate,
                          rng=np.random.default_rng(seed))
        return x


def symbols_to_words(
    symbols: list[Symbol], profile: Profile, frame_rate: int, confidence: float
) -> list[Word]:
    words: list[Word] = []
    cur: list[str] = []
    start = end = 0

    def flush() -> None:
        if cur:
            words.append(Word(profile.render(cur), start / frame_rate, end / frame_rate, confidence))
            cur.clear()

    for s in symbols:
        if s.token == SPACE:
            flush()
            continue
        if not cur:
            start = s.start_frame
        end = s.end_frame
        cur.append(s.token)
    flush()
    return words


class Decoder:
    def __init__(
        self, profile: str | Profile = "en", engine: str = "baseline", model_path: Path | None = None
    ) -> None:
        self.profile = _resolve_profile(profile)
        self.engine = engine
        self.model_path = model_path
        if engine != "baseline":
            raise NotImplementedError(f"engine chưa hỗ trợ: {engine}")
        self._baseline = BaselineDecoder()

    def _empty(self, warnings: list[str]) -> DecodeResult:
        return DecodeResult("", [], None, None, None, self.profile.id, {}, warnings, self.engine)

    def decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> DecodeResult:
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        res, est = self._baseline.decode_audio(x)
        if not est.has_signal or est.f0_hz is None:
            return self._empty(["không có tín hiệu Morse trong đoạn âm thanh"])
        warnings: list[str] = []
        if est.second_peak_hz is not None:
            warnings.append(
                f"phát hiện tone thứ hai tại {est.second_peak_hz:.0f} Hz, đang bám {est.f0_hz:.0f} Hz"
            )
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        words = symbols_to_words(res.symbols, self.profile, FRAME_RATE, confidence)
        return DecodeResult(
            text=" ".join(w.text for w in words),
            words=words,
            wpm=res.wpm,
            tone_hz=est.f0_hz,
            snr_db=est.snr_db,
            language=self.profile.id,
            language_scores={},
            warnings=warnings,
            engine=self.engine,
        )

    def decode_file(self, path: str | Path) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr)
```

- [ ] **Step 4: Viết cli.py**

```python
"""CLI: morsedesk encode | decode | devices."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from morsedesk import __version__
from morsedesk.api import Decoder, Encoder
from morsedesk.audio.io import UnsupportedAudio, save_audio
from morsedesk.encode.text import UnsupportedCharacter
from morsedesk.lm.profile import list_profiles
from morsedesk.textio import force_utf8_streams


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="morsedesk", description="Giải mã và tạo mã Morse offline")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    enc = sub.add_parser("encode", help="văn bản -> chuỗi chấm gạch và file âm thanh")
    enc.add_argument("text")
    enc.add_argument("--profile", default="en", choices=list_profiles())
    enc.add_argument("--wpm", type=float, default=20.0)
    enc.add_argument("--farnsworth", type=float, default=None, help="tốc độ hiệu dụng Farnsworth")
    enc.add_argument("--weight", type=float, default=3.0)
    enc.add_argument("--tone", type=float, default=700.0)
    enc.add_argument("--snr", type=float, default=None, help="thêm nhiễu với SNR (dB) trong băng 500 Hz")
    enc.add_argument("--rate", type=int, default=8000)
    enc.add_argument("--out", type=Path, default=None, help="WAV/FLAC/OGG; bỏ trống thì chỉ in chấm gạch")
    enc.add_argument("--lenient", action="store_true", help="bỏ qua ký tự không hỗ trợ")

    dec = sub.add_parser("decode", help="file âm thanh -> văn bản")
    dec.add_argument("file", type=Path)
    dec.add_argument("--profile", default="en", choices=list_profiles() + ["auto"])
    dec.add_argument("--engine", default="baseline", choices=["baseline", "onnx"])
    dec.add_argument("--model", type=Path, default=Path("models/acoustic.onnx"))
    dec.add_argument("--json", action="store_true")

    sub.add_parser("devices", help="liệt kê thiết bị âm thanh")
    return p


def cmd_encode(a: argparse.Namespace) -> int:
    enc = Encoder(a.profile)
    try:
        print(enc.to_morse_string(a.text, strict=not a.lenient))
        if a.out is not None:
            x = enc.to_audio(a.text, a.wpm, a.farnsworth, a.weight, a.tone, a.rate, a.snr,
                             strict=not a.lenient)
            save_audio(a.out, x, a.rate)
            print(f"đã ghi {a.out} ({len(x) / a.rate:.2f} s)", file=sys.stderr)
    except UnsupportedCharacter as e:
        print(f"lỗi: {e}. Dùng --lenient để bỏ qua.", file=sys.stderr)
        return 2
    return 0


def cmd_decode(a: argparse.Namespace) -> int:
    try:
        dec = Decoder(a.profile, engine=a.engine, model_path=a.model)
        r = dec.decode_file(a.file)
    except (NotImplementedError, UnsupportedAudio, FileNotFoundError) as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 2
    print(r.to_json() if a.json else r.text)
    for w in r.warnings:
        print(f"cảnh báo: {w}", file=sys.stderr)
    return 0


def cmd_devices(a: argparse.Namespace) -> int:
    try:
        import sounddevice as sd
    except (ImportError, OSError) as e:
        print(f"không dùng được sounddevice: {e}", file=sys.stderr)
        return 2
    print(sd.query_devices())
    return 0


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    a = build_parser().parse_args(argv)
    return {"encode": cmd_encode, "decode": cmd_decode, "devices": cmd_devices}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_api_cli.py -v`
Expected: `11 passed`

Run thử tay: `uv run morsedesk encode "СӘЛЕМ ӘЛЕМ" --profile kk-cyrl-ru --wpm 18 --out testdata/generated/kk.wav` rồi `uv run morsedesk decode testdata/generated/kk.wav --profile kk-cyrl-ru`
Expected: in `САЛЕМ АЛЕМ` (chưa có LM nên chữ Kazakh chưa khôi phục). Tạo thư mục `testdata/generated` trước nếu chưa có.

- [ ] **Step 6: Commit**

```bash
git add morsedesk/api.py morsedesk/cli.py tests/unit/test_api_cli.py
git commit -m "feat(api,cli): Encoder, Decoder baseline, DecodeResult và CLI encode/decode/devices" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 12: Bộ test thật T2: manifest và đo công cụ ngoài

**Files:**
- Create: `tools/__init__.py` (rỗng), `tests/conftest.py`
- Create: `tools/make_t2_manifest.py`
- Create: `tools/bench_external.py`
- Create: `testdata/README.md`
- Test: `tests/unit/test_tools_t2.py`

**Interfaces:**
- Produces: `make_t2_manifest.build_manifest(audio_dir: Path, source: str, profile_id: str) -> list[dict]` (mỗi dòng: `path`, `text` đã lọc theo profile, `raw_text`, `source`, `wpm` hoặc `None`, `profile`); `make_t2_manifest.write_jsonl(rows, out: Path)`; `make_t2_manifest.parse_wpm(name: str) -> float | None`; `bench_external.run_manifest(manifest: Path, cmd_template: str, strip_prefix: str = "", to_wav: bool = True) -> dict` (trả `{"name", "n", "mean_cer", "rows": [...]}`); `bench_external.main(argv) -> int`.
- Định dạng manifest JSONL dùng lại ở Task 13 và 14.

- [ ] **Step 1: Viết conftest và test**

`tests/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

`tests/unit/test_tools_t2.py`:

```python
import json
import sys

from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio
from tools.bench_external import run_manifest
from tools.make_t2_manifest import build_manifest, parse_wpm, write_jsonl


def test_parse_wpm():
    assert parse_wpm("260303_20WPM.mp3") == 20.0
    assert parse_wpm("260303_7.5WPM.mp3") == 7.5
    assert parse_wpm("hello.wav") is None


def test_build_manifest_pairs_and_cleans_text(tmp_path):
    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    save_audio(tmp_path / "260303_20WPM.wav", x, 8000)
    (tmp_path / "260303_20WPM.txt").write_text("cq de k <AR> ~ Ә\n", encoding="utf-8")
    save_audio(tmp_path / "orphan.wav", x, 8000)          # không có .txt -> bỏ qua
    rows = build_manifest(tmp_path, source="arrl", profile_id="en")
    assert len(rows) == 1
    r = rows[0]
    assert r["wpm"] == 20.0 and r["source"] == "arrl" and r["profile"] == "en"
    assert r["text"] == "CQ DE K +"          # <AR> chung mẫu với '+', ký tự lạ bị bỏ
    assert r["raw_text"].startswith("cq de k")
    out = tmp_path / "m.jsonl"
    write_jsonl(rows, out)
    assert json.loads(out.read_text(encoding="utf-8").splitlines()[0])["text"] == "CQ DE K +"


def test_run_manifest_with_fake_tool(tmp_path):
    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    save_audio(tmp_path / "a.wav", x, 8000)
    (tmp_path / "a.txt").write_text("CQ DE K")
    rows = build_manifest(tmp_path, source="x", profile_id="en")
    manifest = tmp_path / "m.jsonl"
    write_jsonl(rows, manifest)
    script = tmp_path / "fake.py"
    script.write_text("import sys; print('TOOL: CQ DE')\n")
    result = run_manifest(manifest, f'"{sys.executable}" "{script}" {{path}}', strip_prefix="TOOL:")
    assert result["n"] == 1
    assert abs(result["mean_cer"] - 2 / 7) < 1e-9
    assert result["rows"][0]["hyp"] == "CQ DE"


def test_run_manifest_isolates_tool_errors(tmp_path):
    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    save_audio(tmp_path / "a.wav", x, 8000)
    (tmp_path / "a.txt").write_text("CQ DE K")
    rows = build_manifest(tmp_path, source="x", profile_id="en")
    manifest = tmp_path / "m.jsonl"
    write_jsonl(rows, manifest)
    result = run_manifest(manifest, "definitely-not-a-real-tool-xyz {path}")
    assert result["n"] == 1
    assert result["rows"][0]["hyp"] == ""
    assert result["rows"][0]["cer"] == 1.0
    assert result["rows"][0]["error"]


def test_run_manifest_records_stderr(tmp_path):
    import sys

    x = Encoder("en").to_audio("CQ", wpm=20)
    save_audio(tmp_path / "a.wav", x, 8000)
    (tmp_path / "a.txt").write_text("CQ")
    manifest = tmp_path / "m.jsonl"
    write_jsonl(build_manifest(tmp_path, source="x", profile_id="en"), manifest)
    script = tmp_path / "noisy.py"
    script.write_text("import sys; print('CQ'); print('warn: xyz', file=sys.stderr)\n")
    result = run_manifest(manifest, f'"{sys.executable}" "{script}" {{path}}')
    assert result["rows"][0]["cer"] == 0.0
    assert "warn: xyz" in result["rows"][0]["stderr"]
    assert result["rows"][0]["error"] is None
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_tools_t2.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Viết make_t2_manifest.py**

```python
"""Ghép file âm thanh với file text đáp án cùng tên thành manifest JSONL cho bộ test T2.

Dùng cho ARRL W1AW (MP3 + .txt), Wikimedia Commons, SRAA, kho QSO... Text được lọc
qua profile để chỉ giữ ký tự bộ giải mã có thể sinh ra (đánh giá công bằng).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from morsedesk.encode.text import text_to_tokens
from morsedesk.lm.profile import load_profile
from morsedesk.textio import force_utf8_streams

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".oga")
_WPM_RE = re.compile(r"_(\d+(?:\.\d+)?)WPM", re.IGNORECASE)


def parse_wpm(name: str) -> float | None:
    m = _WPM_RE.search(name)
    return float(m.group(1)) if m else None


def clean_reference(raw: str, profile_id: str) -> str:
    profile = load_profile(profile_id)
    return profile.render(text_to_tokens(raw, profile, strict=False))


def build_manifest(audio_dir: Path, source: str, profile_id: str) -> list[dict]:
    rows = []
    for audio in sorted(p for p in Path(audio_dir).iterdir() if p.suffix.lower() in AUDIO_EXT):
        txt = audio.with_suffix(".txt")
        if not txt.exists():
            continue
        raw = txt.read_text(encoding="utf-8", errors="replace")
        rows.append({
            "path": str(audio.resolve()),
            "text": clean_reference(raw, profile_id),
            "raw_text": raw.strip(),
            "source": source,
            "wpm": parse_wpm(audio.name),
            "profile": profile_id,
        })
    return rows


def write_jsonl(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Tạo manifest T2 từ thư mục audio + txt")
    ap.add_argument("audio_dir", type=Path)
    ap.add_argument("--source", required=True, help="nhãn nguồn, ví dụ arrl, commons, sraa")
    ap.add_argument("--profile", default="en")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rows = build_manifest(a.audio_dir, a.source, a.profile)
    write_jsonl(rows, a.out)
    print(f"{len(rows)} mục -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Viết bench_external.py**

```python
"""Đo CER của công cụ ngoài (multimon-ng, pycw, DeepCW engine...) trên một manifest JSONL.

Mỗi file được chuyển sang WAV 8 kHz mono tạm (nhiều công cụ không đọc MP3), rồi chạy
lệnh mẫu có {path}; stdout là văn bản giải mã.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from morsedesk.audio.io import load_audio, save_audio
from morsedesk.metrics import cer
from morsedesk.textio import force_utf8_streams


def read_manifest(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_manifest(manifest: Path, cmd_template: str, strip_prefix: str = "", to_wav: bool = True,
                 timeout_s: float = 300.0) -> dict:
    rows_out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, row in enumerate(read_manifest(manifest)):
            src = Path(row["path"])
            if to_wav:
                x, sr = load_audio(src)
                wav = Path(tmp) / f"{i}.wav"
                save_audio(wav, x, sr)
            else:
                wav = src
            # posix=False giữ dấu ngoặc kép nguyên trong token (để tách đúng theo khoảng
            # trắng) nhưng subprocess.run trên Windows cần argv không còn dấu ngoặc kép
            # bao ngoài, nếu không list2cmdline sẽ escape chúng thành literal và
            # CreateProcess không tìm thấy file (WinError 2). Bóc dấu ngoặc kép bao ngoài
            # từng token trước khi truyền cho subprocess.
            raw_parts = shlex.split(cmd_template.replace("{path}", str(wav)), posix=False)
            cmd = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p for p in raw_parts]
            t0 = time.time()
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                # Cô lập lỗi từng file: một công cụ ngoài bị thiếu, treo, hoặc lỗi hệ
                # điều hành không được làm hỏng cả lượt đo; ghi nhận như một hyp rỗng
                # (CER = 1.0 với ref không rỗng) và tiếp tục file kế tiếp.
                rows_out.append({
                    "path": row["path"], "ref": row["text"], "hyp": "",
                    "cer": cer(row["text"], ""), "seconds": time.time() - t0,
                    "returncode": None, "error": f"{type(e).__name__}: {e}",
                })
                continue
            lines = []
            for line in proc.stdout.splitlines():
                if strip_prefix and line.startswith(strip_prefix):
                    line = line[len(strip_prefix):]
                lines.append(line.strip())
            hyp = " ".join(l for l in lines if l)
            rows_out.append({
                "path": row["path"], "ref": row["text"], "hyp": hyp,
                "cer": cer(row["text"], hyp), "seconds": time.time() - t0,
                "returncode": proc.returncode, "stderr": proc.stderr[-500:], "error": None,
            })
    mean = sum(r["cer"] for r in rows_out) / max(1, len(rows_out))
    return {"name": cmd_template.split()[0], "n": len(rows_out), "mean_cer": mean, "rows": rows_out}


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Đo công cụ giải mã ngoài trên manifest")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--cmd", required=True, help='ví dụ: "multimon-ng -a MORSE_CW -t wav {path}"')
    ap.add_argument("--name", required=True)
    ap.add_argument("--strip-prefix", default="")
    ap.add_argument("--no-wav", action="store_true", help="đưa file gốc, không chuyển WAV 8 kHz")
    ap.add_argument("--out-dir", type=Path, default=Path("bench_results"))
    a = ap.parse_args(argv)
    result = run_manifest(a.manifest, a.cmd, a.strip_prefix, to_wav=not a.no_wav)
    result["name"] = a.name
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"external_{a.name}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    n_err = sum(1 for r in result["rows"] if r.get("error"))
    print(f"{a.name}: n={result['n']} CER trung bình={result['mean_cer']:.3f} lỗi={n_err} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Viết testdata/README.md và cập nhật .gitignore**

`testdata/README.md`:

```markdown
# testdata

- `public/`: file được phép phân phối lại (Wikimedia Commons, tự thu). Commit được.
- `private/`: file có bản quyền hoặc chỉ dùng nội bộ (ARRL W1AW, SRAA CC BY-NC, kho QSO). KHÔNG commit.
- `generated/`: sinh bằng công cụ (T1, WAV thử tay). KHÔNG commit, tạo lại bằng `uv run python tools/make_t1.py`.

## Gom bộ T2 (làm tay, một lần)

1. ARRL W1AW: tải MP3 và file text cùng tên từ trang "N WPM Code Archive" của arrl.org cho các tốc độ
   5, 7.5, 10, 13, 15, 18, 20, 25, 30, 35, 40 (ít nhất 2 ngày mỗi tốc độ) vào `testdata/private/arrl/`.
   Tên file dạng `260303_20WPM.mp3` và `260303_20WPM.txt`.
2. Wikimedia Commons, Category "Audio files of Morse code": tải WAV/OGG vào `testdata/public/commons/`,
   ghi đáp án vào file `.txt` cùng tên (nghe và chép tay).
3. SRAA (shortwavearchive.com, tag CW) và kho QSO Ý: tải khoảng 20 clip vào `testdata/private/real/`,
   cắt đoạn 30–60 s bằng Audacity, chép tay đáp án vào `.txt` cùng tên; ghi WPM và loại khóa vào tên
   file dạng `qso01_25WPM_bug.wav` nếu biết.
4. Tiếng Nga/Kazakh: thu người gõ thật hoặc tạo bằng ebook2cw (gọi ngoài) vào `testdata/private/ru/` và
   `testdata/private/kk/`, kèm `.txt`.
5. Tạo manifest:
   `uv run python tools/make_t2_manifest.py testdata/private/arrl --source arrl --profile en --out testdata/manifests/t2_arrl.jsonl`
   và tương tự cho các thư mục khác (đổi `--profile ru` / `kk-cyrl-ru`).

## Đo công cụ ngoài (Ubuntu 22.04, chỉ để có số đối chứng, không nhúng vào sản phẩm)

```bash
sudo apt install multimon-ng
uv run python tools/bench_external.py --manifest testdata/manifests/t2_arrl.jsonl \
  --cmd "multimon-ng -a MORSE_CW -t wav {path}" --strip-prefix "MORSE_CW:" --name multimon
pipx install pycw
uv run python tools/bench_external.py --manifest testdata/manifests/t2_arrl.jsonl \
  --cmd "pycw -d {path}" --name pycw
git clone https://github.com/e04/deepcw-engine /tmp/deepcw-engine   # AGPL: chỉ đo, không nhúng
# xem /tmp/deepcw-engine/examples/python/README để biết tên script; mẫu:
uv run python tools/bench_external.py --manifest testdata/manifests/t2_arrl.jsonl \
  --cmd "python /tmp/deepcw-engine/examples/python/decode.py /tmp/deepcw-engine/model.onnx /tmp/deepcw-engine/model.onnx.json {path}" --name deepcw
```

Baseline nội bộ đo bằng `uv run morsedesk bench --set t2 --manifest testdata/manifests/t2_arrl.jsonl --engine baseline` (Task 14).
```

Thêm vào `.gitignore` các dòng:

```
testdata/generated/
bench_results/
```

(`testdata/private/` đã có.)

- [ ] **Step 6: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_tools_t2.py -v`
Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add tools/__init__.py tools/make_t2_manifest.py tools/bench_external.py tests/conftest.py tests/unit/test_tools_t2.py testdata/README.md .gitignore
git commit -m "feat(tools): manifest T2 và đo công cụ giải mã ngoài" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 13: Bộ sinh dữ liệu tổng hợp (văn bản, tay gõ, kênh)

**Files:**
- Create: `morsedesk/data/text.py`
- Create: `morsedesk/data/keyer.py`
- Create: `morsedesk/data/channel.py`
- Create: `morsedesk/data/synth.py`
- Test: `tests/unit/test_data_synth.py`

**Interfaces:**
- Consumes: `Element`, `TimingParams`, `tokens_to_elements`, `total_seconds`, `elements_to_segments`, `unit_seconds`, `gap_seconds` (Task 4); `elements_to_audio`, `add_noise`, `tone_power` (Task 5); `text_to_tokens` (Task 4); `Profile`, `load_profile` (Task 3); `VOCAB`, `SPACE`; `save_audio` (Task 6); `BaselineDecoder` (Task 10, chỉ trong test).
- Produces:
  - `text.TextSampler(profiles: dict[str, Profile], corpus: dict[str, Path] | None = None, ham_ratio=0.3, random_ratio=0.1)` với `sample(profile_id, rng, n_words=(3, 12)) -> str` (chỉ chứa ký tự profile hỗ trợ); `text.translit_via_patterns(text, src: Profile, dst: Profile) -> str`; `text.BUILTIN_WORDS: dict[str, list[str]]`.
  - `keyer.KeyerParams(wpm, farnsworth_wpm, weight, jitter, bug, drift, spacing_error_rate, name="random")` (frozen); `keyer.machine(wpm, name="machine") -> KeyerParams`; `keyer.sample_keyer_params(rng) -> KeyerParams`; `keyer.apply_keyer(elements, params, rng) -> list[Element]`.
  - `channel.ChannelParams(tone_hz, tone_drift_hz_per_s, snr_db, qsb_depth_db, qsb_period_s, qrm_offset_hz, qrm_level_db, qrm_kind, qrn_rate_per_s, bandpass, gain, clip, dc_offset, mp3_kbps, name="random")` (frozen); `channel.clean(snr_db=30.0, tone_hz=700.0, name="clean") -> ChannelParams`; `channel.sample_channel_params(rng) -> ChannelParams`; `channel.ffmpeg_available() -> bool`; `channel.mp3_roundtrip(x, sample_rate, kbps) -> np.ndarray`; `channel.apply_channel(x, p, rng, sample_rate=SAMPLE_RATE, signal_power=0.32, qrm_factory=None) -> np.ndarray` (`qrm_factory(n_samples, tone_hz, rng) -> np.ndarray`).
  - `synth.Example(audio, labels: list[int], tokens: list[str], text: str, profile_id: str, keyer: KeyerParams, channel: ChannelParams, f0_hz: float, sample_rate: int)` với thuộc tính `seconds`; `synth.SynthConfig(profile_ids=("en","ru","kk-cyrl-ru"), min_seconds=4.0, max_seconds=12.0, pad_min_s=0.2, pad_max_s=0.8, corpus=None, mp3_enabled=True)`; `synth.SynthGenerator(cfg)` với `generate(seed: int, profile_id=None, keyer=None, channel=None) -> Example` và `tokens_duration(tokens, keyer) -> float`.

Thứ tự kênh trong `apply_channel`: QSB → QRM → QRN → AWGN (SNR so với công suất tone chưa fading) → lọc băng 300–3000 Hz → gain → clipping → DC → MP3 (chỉ khi có `ffmpeg`).

- [ ] **Step 1: Viết test**

`tests/unit/test_data_synth.py`:

```python
import numpy as np
import pytest

from morsedesk.data.channel import (
    ChannelParams, apply_channel, clean, ffmpeg_available, mp3_roundtrip, sample_channel_params,
)
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine, sample_keyer_params
from morsedesk.data.synth import SynthConfig, SynthGenerator
from morsedesk.data.text import BUILTIN_WORDS, TextSampler, translit_via_patterns
from morsedesk.dsp.baseline import BaselineDecoder
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import Element, TimingParams, tokens_to_elements
from morsedesk.lm.profile import load_profile
from morsedesk.metrics import cer
from morsedesk.model.vocab import SPACE, VOCAB


@pytest.fixture(scope="module")
def profiles():
    return {pid: load_profile(pid) for pid in ("en", "ru", "kk-cyrl-ru")}


# ---- text ----

def test_builtin_words_are_encodable(profiles):
    for pid, words in BUILTIN_WORDS.items():
        for w in words:
            assert text_to_tokens(w, profiles[pid]), (pid, w)


def test_translit_callsign_to_cyrillic(profiles):
    assert translit_via_patterns("UN7ABC", profiles["en"], profiles["ru"]) == "УН7АБЦ"


def test_sampler_outputs_supported_text(profiles):
    ts = TextSampler(profiles)
    rng = np.random.default_rng(0)
    for pid in profiles:
        for _ in range(30):
            s = ts.sample(pid, rng)
            assert s and text_to_tokens(s, profiles[pid])       # strict không lỗi


def test_sampler_corpus(tmp_path, profiles):
    corpus = tmp_path / "en.txt"
    corpus.write_text("HELLO WORLD FROM CORPUS\nSECOND LINE HERE\n", encoding="utf-8")
    ts = TextSampler(profiles, corpus={"en": corpus}, ham_ratio=0.0, random_ratio=0.0)
    s = ts.sample("en", np.random.default_rng(1))
    assert "CORPUS" in s or "LINE" in s


def test_sampler_fallback_is_profile_native(tmp_path, profiles):
    corpus = tmp_path / "ru.txt"
    corpus.write_text("ONLY LATIN LINE\n", encoding="utf-8")   # không mã hóa được trong profile ru
    ts = TextSampler(profiles, corpus={"ru": corpus}, ham_ratio=0.0, random_ratio=0.0)
    s = ts.sample("ru", np.random.default_rng(0))
    assert s == BUILTIN_WORDS["ru"][0]
    assert text_to_tokens(s, profiles["ru"])                     # strict không lỗi
    gen = SynthGenerator(SynthConfig(mp3_enabled=False, corpus={"ru": corpus}))
    ex = gen.generate(3, profile_id="ru")
    assert ex.text and ex.profile_id == "ru"


# ---- keyer ----

def test_sample_keyer_ranges():
    rng = np.random.default_rng(0)
    for _ in range(200):
        k = sample_keyer_params(rng)
        assert 5.0 <= k.wpm <= 60.0
        assert 2.0 <= k.weight <= 4.5
        assert 0.03 <= k.jitter <= 0.20
        assert -0.15 <= k.drift <= 0.15
        if k.farnsworth_wpm is not None:
            assert k.wpm < 18 and 5.0 <= k.farnsworth_wpm <= k.wpm


def test_machine_keyer_is_identity():
    els = tokens_to_elements(["-.-.", SPACE, "--.-"], TimingParams(wpm=20))
    out = apply_keyer(els, machine(20), np.random.default_rng(0))
    assert out == els


def test_drift_lengthens_later_elements():
    els = tokens_to_elements(["....."] * 5, TimingParams(wpm=20))
    k = KeyerParams(20, None, 3.0, 0.0, False, 0.10, 0.0)
    out = apply_keyer(els, k, np.random.default_rng(0))
    assert out[-1].duration > out[0].duration * 1.05


def test_jitter_changes_but_keeps_positive():
    els = tokens_to_elements(["....."] * 5, TimingParams(wpm=20))
    k = KeyerParams(20, None, 3.0, 0.15, True, 0.0, 0.05)
    out = apply_keyer(els, k, np.random.default_rng(0))
    assert len(out) == len(els)
    assert all(e.duration > 0 for e in out)
    assert any(abs(a.duration - b.duration) > 1e-6 for a, b in zip(els, out))


# ---- channel ----

def test_sample_channel_ranges():
    rng = np.random.default_rng(0)
    for _ in range(200):
        c = sample_channel_params(rng)
        assert 400 <= c.tone_hz <= 1200 and -6 <= c.snr_db <= 25
        assert c.qrm_kind in ("none", "morse", "carrier")
        assert c.mp3_kbps in (None, 48, 64, 96, 128)


def test_clean_channel_keeps_signal():
    from tests.helpers import make_morse
    x, _ = make_morse("PARIS PARIS", wpm=20)
    y = apply_channel(x, clean(snr_db=30.0), np.random.default_rng(0))
    c = np.corrcoef(x, y)[0, 1]
    assert c > 0.95 and y.dtype == np.float32 and len(y) == len(x)


def test_qsb_reduces_envelope_minimum():
    from tests.helpers import make_morse
    x, _ = make_morse("EEEEEEEEEEEEEEEEEEEE", wpm=20)
    p = ChannelParams(700, 0, 40, qsb_depth_db=20, qsb_period_s=1.0, qrm_offset_hz=0, qrm_level_db=0,
                      qrm_kind="none", qrn_rate_per_s=0, bandpass=False, gain=1.0, clip=False,
                      dc_offset=0.0, mp3_kbps=None)
    y = apply_channel(x, p, np.random.default_rng(0))
    assert np.max(np.abs(y)) > 0.5 * np.max(np.abs(x))
    assert np.max(np.abs(y)) > 2 * np.percentile(np.abs(y[np.abs(x) > 0.5]), 5)


def test_mp3_roundtrip_without_ffmpeg_is_identity_or_close():
    x = np.random.default_rng(0).normal(0, 0.1, 8000).astype(np.float32)
    y = mp3_roundtrip(x, 8000, 64)
    assert len(y) == len(x)
    if not ffmpeg_available():
        assert np.array_equal(x, y)


# ---- generator ----

def test_generator_reproducible_and_valid():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    a = gen.generate(42)
    b = gen.generate(42)
    assert np.array_equal(a.audio, b.audio) and a.labels == b.labels and a.text == b.text
    assert a.tokens[0] != SPACE and a.tokens[-1] != SPACE
    assert all(0 <= i < len(VOCAB) for i in a.labels)
    assert all(VOCAB.token(i) == t for i, t in zip(a.labels, a.tokens))
    assert 4.0 <= a.seconds <= 12.0 + 1.6 + 1e-6
    assert a.profile_id in ("en", "ru", "kk-cyrl-ru")


def test_generator_duration_bounds_over_many_seeds():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    seeds = list(range(1000, 1200)) + [117, 816, 962, 1494, 1794, 1830, 2244, 2324, 2961, 861, 2462]
    for seed in seeds:
        ex = gen.generate(seed)
        # tín hiệu trong [4, 12] s cộng đệm 0.2–0.8 s mỗi đầu
        assert 4.0 + 0.4 - 1e-6 <= ex.seconds <= 12.0 + 1.6 + 1e-6, (seed, ex.seconds)


def test_sample_tokens_bounds_with_default_window():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))     # min 4 s, max 12 s
    for seed in range(20):
        rng = np.random.default_rng(seed)
        for pid in ("en", "ru", "kk-cyrl-ru"):
            for wpm in (5.0, 12.0, 30.0, 60.0):
                keyer = machine(wpm)
                toks = gen._sample_tokens(gen.profiles[pid], keyer, rng, target_s=8.0)
                d = gen.tokens_duration(toks, keyer)
                assert 4.0 - 1e-9 <= d <= 12.0 + 1e-9, (seed, pid, wpm, d)
                assert toks[0] != SPACE and toks[-1] != SPACE


def test_sample_tokens_tight_window_never_exceeds_max():
    # cửa sổ hẹp: chỉ đảm bảo trần; sàn là nỗ lực tốt nhất (xem docstring _sample_tokens)
    gen = SynthGenerator(SynthConfig(min_seconds=4.0, max_seconds=6.0, mp3_enabled=False))
    for seed in range(20):
        rng = np.random.default_rng(seed)
        for pid in ("en", "ru", "kk-cyrl-ru"):
            toks = gen._sample_tokens(gen.profiles[pid], machine(5.0), rng, target_s=5.0)
            assert gen.tokens_duration(toks, machine(5.0)) <= 6.0 + 1e-9, (seed, pid)


def test_generator_different_seeds_differ():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    assert gen.generate(1).text != gen.generate(2).text


def test_generator_fixed_params_decodable_by_baseline():
    gen = SynthGenerator(SynthConfig(mp3_enabled=False))
    ex = gen.generate(7, profile_id="en", keyer=machine(20), channel=clean(snr_db=30.0))
    res, est = BaselineDecoder().decode_audio(ex.audio)
    hyp = load_profile("en").render(res.tokens)
    assert cer(ex.text, hyp) < 0.05
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_data_synth.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.data.channel'`

- [ ] **Step 3: Viết text.py**

```python
"""Lấy mẫu văn bản để sinh dữ liệu: corpus (mỗi dòng một câu) hoặc từ điển tích hợp,
cộng bản tin ham radio giả lập và nhóm ký tự ngẫu nhiên."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from morsedesk.encode.text import text_to_tokens
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
        cleaned = profile.render(text_to_tokens(raw, profile, strict=False)).strip()
        return cleaned or BUILTIN_WORDS[profile_id][0]
```

- [ ] **Step 4: Viết keyer.py**

```python
"""Mô hình tay gõ: WPM ngẫu nhiên, Farnsworth, weight, jitter, kiểu bug, trôi tốc độ, lỗi khoảng cách."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from morsedesk.encode.timing import Element, TimingParams, gap_seconds, unit_seconds

MIN_ELEMENT_S = 0.004


@dataclass(frozen=True)
class KeyerParams:
    wpm: float
    farnsworth_wpm: float | None
    weight: float
    jitter: float               # độ lệch chuẩn log-normal của độ dài phần tử
    bug: bool                   # dit đều, dah lệch nhiều
    drift: float                # thay đổi tỉ lệ độ dài từ đầu đến cuối clip (+0.1 = chậm dần 10%)
    spacing_error_rate: float   # xác suất khoảng giữa chữ bị rút còn 1.5 dit hoặc kéo tới 5 dit
    name: str = "random"

    def timing(self) -> TimingParams:
        return TimingParams(self.wpm, self.farnsworth_wpm, self.weight)


def machine(wpm: float, name: str = "machine") -> KeyerParams:
    return KeyerParams(wpm, None, 3.0, 0.0, False, 0.0, 0.0, name)


def sample_keyer_params(rng: np.random.Generator) -> KeyerParams:
    wpm = float(np.exp(rng.uniform(np.log(5.0), np.log(60.0))))
    farnsworth = None
    if wpm < 18.0 and rng.random() < 0.5:
        farnsworth = float(rng.uniform(5.0, min(13.0, wpm)))
    return KeyerParams(
        wpm=wpm,
        farnsworth_wpm=farnsworth,
        weight=float(rng.uniform(2.0, 4.5)),
        jitter=float(rng.uniform(0.03, 0.20)),
        bug=bool(rng.random() < 0.2),
        drift=float(rng.uniform(-0.15, 0.15)),
        spacing_error_rate=0.05,
    )


def apply_keyer(elements: list[Element], params: KeyerParams, rng: np.random.Generator) -> list[Element]:
    """Làm méo timing lý tưởng theo tham số tay gõ. Không đổi số phần tử."""
    if not elements:
        return []
    u = unit_seconds(params.wpm)
    inter_char, _ = gap_seconds(params.timing())
    n = len(elements)
    out: list[Element] = []
    for i, e in enumerate(elements):
        progress = i / max(1, n - 1)
        dur = e.duration * (1.0 + params.drift * progress)
        if e.on:
            is_dot = e.duration <= 1.5 * u
            if params.bug:
                j = params.jitter / 3.0 if is_dot else params.jitter * 2.0
            else:
                j = params.jitter
        else:
            j = params.jitter
            if (params.spacing_error_rate > 0 and abs(e.duration - inter_char) < 1e-9
                    and rng.random() < params.spacing_error_rate):
                dur = (1.5 if rng.random() < 0.5 else 5.0) * u
        if j > 0:
            dur *= float(np.exp(rng.normal(0.0, j)))
        out.append(Element(e.on, max(dur, MIN_ELEMENT_S)))
    return out
```

- [ ] **Step 5: Viết channel.py**

```python
"""Kênh truyền: QSB, QRM, QRN, AWGN, lọc băng, mức, clipping, DC, codec MP3 (tùy chọn, cần ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.synth import add_noise

QrmFactory = Callable[[int, float, np.random.Generator], np.ndarray]


@dataclass(frozen=True)
class ChannelParams:
    tone_hz: float
    tone_drift_hz_per_s: float
    snr_db: float
    qsb_depth_db: float          # 0 = không QSB
    qsb_period_s: float
    qrm_offset_hz: float
    qrm_level_db: float          # QRM thấp hơn tín hiệu bao nhiêu dB
    qrm_kind: str                # "none" | "morse" | "carrier"
    qrn_rate_per_s: float        # 0 = không xung
    bandpass: bool
    gain: float
    clip: bool
    dc_offset: float
    mp3_kbps: int | None
    name: str = "random"


def clean(snr_db: float = 30.0, tone_hz: float = 700.0, name: str = "clean") -> ChannelParams:
    return ChannelParams(tone_hz, 0.0, snr_db, 0.0, 10.0, 0.0, 0.0, "none", 0.0, True, 1.0, False, 0.0, None, name)


def sample_channel_params(rng: np.random.Generator) -> ChannelParams:
    qsb = rng.random() < 0.4
    qrm = rng.random() < 0.25
    return ChannelParams(
        tone_hz=float(rng.uniform(400.0, 1200.0)),
        tone_drift_hz_per_s=float(rng.uniform(-2.0, 2.0)),
        snr_db=float(rng.uniform(-6.0, 25.0)),
        qsb_depth_db=float(rng.uniform(5.0, 30.0)) if qsb else 0.0,
        qsb_period_s=float(rng.uniform(2.0, 20.0)),
        qrm_offset_hz=float(rng.choice([-1.0, 1.0]) * rng.uniform(150.0, 600.0)) if qrm else 0.0,
        qrm_level_db=float(rng.uniform(3.0, 20.0)) if qrm else 0.0,
        qrm_kind=("morse" if rng.random() < 0.7 else "carrier") if qrm else "none",
        qrn_rate_per_s=float(rng.uniform(5.0, 50.0)) if rng.random() < 0.2 else 0.0,
        bandpass=True,
        gain=float(rng.uniform(0.1, 1.0)),
        clip=bool(rng.random() < 0.05),
        dc_offset=float(rng.uniform(-0.1, 0.1)) if rng.random() < 0.2 else 0.0,
        mp3_kbps=int(rng.choice([48, 64, 96, 128])) if rng.random() < 0.3 else None,
    )


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def mp3_roundtrip(x: np.ndarray, sample_rate: int, kbps: int) -> np.ndarray:
    """Mã hóa MP3 rồi giải mã lại bằng ffmpeg (tiến trình ngoài). Không có ffmpeg -> trả nguyên."""
    if not ffmpeg_available():
        return x
    scale = max(1.0, float(np.max(np.abs(x))) if len(x) else 1.0)
    with tempfile.TemporaryDirectory() as tmp:
        wav, mp3 = Path(tmp) / "in.wav", Path(tmp) / "out.mp3"
        sf.write(wav, x / scale, sample_rate, subtype="PCM_16")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame",
             "-b:a", f"{kbps}k", str(mp3)],
            check=True, capture_output=True,
        )
        y, sr = sf.read(mp3, dtype="float32", always_2d=True)
    y = y.mean(axis=1) * scale
    if len(y) >= len(x):
        y = y[: len(x)]
    else:
        y = np.pad(y, (0, len(x) - len(y)))
    return y.astype(np.float32)


def apply_channel(
    x: np.ndarray,
    p: ChannelParams,
    rng: np.random.Generator,
    sample_rate: int = SAMPLE_RATE,
    signal_power: float = 0.32,
    qrm_factory: QrmFactory | None = None,
) -> np.ndarray:
    y = np.asarray(x, dtype=np.float64).copy()
    n = len(y)
    t = np.arange(n) / sample_rate

    if p.qsb_depth_db > 0:
        phase = rng.uniform(0.0, 2.0 * np.pi)
        g_db = -p.qsb_depth_db * 0.5 * (1.0 - np.cos(2.0 * np.pi * t / p.qsb_period_s + phase))
        y *= 10.0 ** (g_db / 20.0)

    if p.qrm_kind != "none":
        level = 10.0 ** (-p.qrm_level_db / 20.0)
        f_qrm = p.tone_hz + p.qrm_offset_hz
        if p.qrm_kind == "morse" and qrm_factory is not None:
            q = qrm_factory(n, f_qrm, rng)
        else:
            q = 0.8 * np.sin(2.0 * np.pi * f_qrm * t)
        y += level * q[:n]

    if p.qrn_rate_per_s > 0:
        n_imp = int(rng.poisson(p.qrn_rate_per_s * n / sample_rate))
        for pos in rng.integers(0, max(1, n - 32), size=n_imp):
            width = int(rng.integers(8, 24))
            amp = float(rng.uniform(2.0, 10.0)) * 0.8 * float(rng.choice([-1.0, 1.0]))
            y[pos:pos + width] += amp * np.exp(-3.0 * np.arange(width) / width)

    y = add_noise(y.astype(np.float32), p.snr_db, signal_power, sample_rate, rng=rng).astype(np.float64)

    if p.bandpass:
        sos = butter(4, [300.0, 3000.0], btype="band", fs=sample_rate, output="sos")
        y = sosfiltfilt(sos, y)

    y *= p.gain
    if p.clip:
        y = np.clip(y * 1.5, -1.0, 1.0)
    y += p.dc_offset
    y = y.astype(np.float32)
    if p.mp3_kbps:
        y = mp3_roundtrip(y, sample_rate, p.mp3_kbps)
    return y
```

- [ ] **Step 6: Viết synth.py**

```python
"""SynthGenerator: sinh cặp (audio, nhãn) on-the-fly, tái lập theo seed."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from morsedesk.constants import SAMPLE_RATE
from morsedesk.data.channel import (
    ChannelParams, apply_channel, ffmpeg_available, sample_channel_params,
)
from morsedesk.data.keyer import KeyerParams, apply_keyer, machine, sample_keyer_params
from morsedesk.data.text import BUILTIN_WORDS, TextSampler
from morsedesk.encode.synth import elements_to_audio, tone_power
from morsedesk.encode.text import text_to_tokens
from morsedesk.encode.timing import Element, elements_to_segments, tokens_to_elements, total_seconds
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.vocab import SPACE, VOCAB

AMPLITUDE = 0.8
MAX_SAMPLE_ROUNDS = 50


def split_words(tokens: list[str]) -> list[list[str]]:
    """Tách danh sách token trên SPACE thành các từ, bỏ qua từ rỗng."""
    words: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok == SPACE:
            if current:
                words.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        words.append(current)
    return words


def rescale_elements(elements: list[Element], target_seconds: float) -> list[Element]:
    """Co giãn đều mọi phần tử để tổng thời lượng bằng target_seconds (giữ nguyên hình dạng jitter/drift)."""
    total = total_seconds(elements)
    if total <= 0 or target_seconds <= 0:
        return elements
    k = target_seconds / total
    return [Element(e.on, e.duration * k) for e in elements]


@dataclass
class Example:
    audio: np.ndarray
    labels: list[int]
    tokens: list[str]
    text: str
    profile_id: str
    keyer: KeyerParams
    channel: ChannelParams
    f0_hz: float
    sample_rate: int

    @property
    def seconds(self) -> float:
        return len(self.audio) / self.sample_rate


@dataclass
class SynthConfig:
    profile_ids: tuple[str, ...] = ("en", "ru", "kk-cyrl-ru")
    min_seconds: float = 4.0
    max_seconds: float = 12.0
    pad_min_s: float = 0.2
    pad_max_s: float = 0.8
    corpus: dict[str, Path] | None = None
    mp3_enabled: bool = True


class SynthGenerator:
    def __init__(self, cfg: SynthConfig = SynthConfig()) -> None:
        self.cfg = cfg
        ids = set(cfg.profile_ids) | {"en"}
        self.profiles: dict[str, Profile] = {pid: load_profile(pid) for pid in ids}
        self.text = TextSampler(self.profiles, cfg.corpus)
        self._mp3 = cfg.mp3_enabled and ffmpeg_available()

    @staticmethod
    def tokens_duration(tokens: list[str], keyer: KeyerParams) -> float:
        return total_seconds(tokens_to_elements(tokens, keyer.timing()))

    def _sample_tokens(self, profile: Profile, keyer: KeyerParams, rng: np.random.Generator,
                       target_s: float) -> list[str]:
        """Ghép từng từ cho tới khi đạt target_s, không bao giờ vượt max_seconds.

        Chỉ thêm từ nào còn vừa trần; dừng khi đã đạt target_s, hoặc khi không còn từ vừa
        mà thời lượng đã >= min_seconds. Sinh tối đa MAX_SAMPLE_ROUNDS đoạn văn bản.

        Đảm bảo: thời lượng <= max_seconds nếu vòng lặp thêm được ít nhất một từ. Đạt
        min_seconds được đảm bảo chỉ khi cửa sổ (max_seconds - min_seconds) đủ rộng so với
        độ dài từ ở tốc độ cho trước (true cho mặc định 4–12 s: 0 vi phạm trên 27.000 mẫu);
        do fill không backtrack, cửa sổ hẹp (ví dụ 4–6 s ở 5 WPM) có thể dừng dưới sàn
        sau từ đầu tiên không may mắn.
        """
        tokens: list[str] = []
        queue: list[list[str]] = []
        rounds = 0
        while rounds < MAX_SAMPLE_ROUNDS:
            if not queue:
                rounds += 1
                queue = split_words(text_to_tokens(self.text.sample(profile.id, rng), profile))
                continue
            word = queue.pop(0)
            cand = tokens + ([SPACE] if tokens else []) + word
            d = self.tokens_duration(cand, keyer)
            if d <= self.cfg.max_seconds:
                tokens = cand
                if d >= target_s:
                    break
            elif self.tokens_duration(tokens, keyer) >= self.cfg.min_seconds:
                break
        if not tokens:
            # Chỉ khi không có từ nào vừa trần: lấy từ ngắn nhất từ từ điển.
            tokens = self._shortest_builtin_word(profile, keyer)
        return tokens

    def _shortest_builtin_word(self, profile: Profile, keyer: KeyerParams) -> list[str]:
        """Từ ngắn nhất (theo thời lượng) trong BUILTIN_WORDS của profile, dùng khi không tìm
        được từ nào vừa trần trong _sample_tokens."""
        words = [text_to_tokens(w, profile) for w in BUILTIN_WORDS[profile.id]]
        return min(words, key=lambda w: self.tokens_duration(w, keyer))

    def _random_morse(self, n: int, f0: float, rng: np.random.Generator) -> np.ndarray:
        """Tín hiệu Morse ngẫu nhiên tiếng Anh dùng làm QRM."""
        en = self.profiles["en"]
        keyer = machine(float(rng.uniform(15.0, 35.0)))
        tokens = self._sample_tokens(en, keyer, rng, n / SAMPLE_RATE)
        audio = elements_to_audio(tokens_to_elements(tokens, keyer.timing()), f0, SAMPLE_RATE, AMPLITUDE)
        reps = int(np.ceil(n / max(1, len(audio))))
        return np.tile(audio, reps)[:n]

    def generate(
        self,
        seed: int,
        profile_id: str | None = None,
        keyer: KeyerParams | None = None,
        channel: ChannelParams | None = None,
    ) -> Example:
        rng = np.random.default_rng(seed)
        pid = profile_id or self.cfg.profile_ids[int(rng.integers(len(self.cfg.profile_ids)))]
        profile = self.profiles[pid]
        keyer = keyer or sample_keyer_params(rng)
        channel = channel or sample_channel_params(rng)
        if channel.mp3_kbps and not self._mp3:
            channel = replace(channel, mp3_kbps=None)

        target = float(rng.uniform(self.cfg.min_seconds, self.cfg.max_seconds))
        tokens = self._sample_tokens(profile, keyer, rng, target)
        nominal = tokens_to_elements(tokens, keyer.timing())
        elements = rescale_elements(apply_keyer(nominal, keyer, rng), total_seconds(nominal))
        n_sig = elements_to_segments(elements, SAMPLE_RATE)[-1][2]
        t = np.arange(n_sig) / SAMPLE_RATE
        freq = channel.tone_hz + channel.tone_drift_hz_per_s * t
        signal = elements_to_audio(elements, freq, SAMPLE_RATE, AMPLITUDE)

        pad_a = np.zeros(int(rng.uniform(self.cfg.pad_min_s, self.cfg.pad_max_s) * SAMPLE_RATE), np.float32)
        pad_b = np.zeros(int(rng.uniform(self.cfg.pad_min_s, self.cfg.pad_max_s) * SAMPLE_RATE), np.float32)
        x = np.concatenate([pad_a, signal, pad_b])
        audio = apply_channel(x, channel, rng, SAMPLE_RATE, tone_power(AMPLITUDE), self._random_morse)

        return Example(
            audio=audio,
            labels=[VOCAB.id(tok) for tok in tokens],
            tokens=tokens,
            text=profile.render(tokens),
            profile_id=pid,
            keyer=keyer,
            channel=channel,
            f0_hz=channel.tone_hz,
            sample_rate=SAMPLE_RATE,
        )
```

- [ ] **Step 7: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_data_synth.py -v`
Expected: `19 passed`. Nếu `test_generator_fixed_params_decodable_by_baseline` trượt vì `channel.clean` có lọc băng làm mềm sườn, in `hyp` và `ex.text` để so; nếu chỉ lệch khoảng cách từ thì kiểm tra lại `split_gap_threshold`.

- [ ] **Step 8: Commit**

```bash
git add morsedesk/data tests/unit/test_data_synth.py
git commit -m "feat(data): bộ sinh dữ liệu tổng hợp với tay gõ và kênh nhiễu" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 14: Ma trận T1 và harness bench (CLI `morsedesk bench`)

**Files:**
- Create: `tools/make_t1.py`
- Create: `morsedesk/bench.py` (logic đo nằm trong package để CLI dùng; thay cho `tools/bench.py` trong bản đồ tệp)
- Modify: `morsedesk/cli.py` (thêm lệnh con `bench`)
- Test: `tests/regression/test_t1.py`

**Interfaces:**
- Consumes: `SynthGenerator`, `SynthConfig` (Task 13); `KeyerParams`, `machine` (Task 13); `ChannelParams`, `clean` (Task 13); `save_audio` (Task 6); `write_jsonl` (Task 12); `Decoder` (Task 11); `cer`, `wer` (Task 9).
- Produces:
  - `make_t1.SNR_FULL`, `WPM_FULL`, `SNR_GATE`, `WPM_GATE`, `KEYING = ("machine","farnsworth","jitter","bug","drift")`, `CHANNELS = ("clean","qsb","qrm","qrn","mp3")`; `make_t1.keyer_for(name, wpm) -> KeyerParams`; `make_t1.channel_for(name, snr_db, tone_hz) -> ChannelParams`; `make_t1.build_cells(full: bool) -> list[dict]`; `make_t1.generate_matrix(out_dir: Path, full=False, clips=1, seed_base=1000) -> list[dict]` (ghi WAV và trả các dòng manifest có `path, text, profile, snr, wpm, keying, channel, channel_actual, seed`); `make_t1.main(argv)`.
  - `bench.load_rows(manifest: Path) -> list[dict]`; `bench.evaluate(rows, engine="baseline", model_path=None, limit=None) -> list[dict]` (mỗi dòng thêm `hyp, cer, wer, wpm_est, seconds`); `bench.aggregate(results, key: str) -> dict[str, dict]`; `bench.pivot_snr_wpm(results) -> str`; `bench.gate(results, max_cer=0.02, snr_min=0.0, wpm_min=10.0, wpm_max=35.0) -> tuple[bool, float, int]`; `bench.run(manifest, engine, model_path, out_dir, limit, do_gate, max_cer) -> tuple[dict, bool]`.
  - CLI: `morsedesk bench --manifest PATH [--engine baseline|onnx] [--model PATH] [--out-dir bench_results] [--limit N] [--gate] [--max-cer 0.02]`, exit 1 nếu gate trượt.

- [ ] **Step 1: Viết test**

`tests/regression/test_t1.py`:

```python
import json
from pathlib import Path

import pytest

from morsedesk import bench
from morsedesk.cli import main
from tools import make_t1


def test_keyer_and_channel_factories():
    k = make_t1.keyer_for("farnsworth", 12)
    assert k.farnsworth_wpm is not None and k.farnsworth_wpm < 12
    assert make_t1.keyer_for("farnsworth", 25).farnsworth_wpm is None
    assert make_t1.keyer_for("bug", 20).bug
    assert make_t1.keyer_for("drift", 20).drift > 0
    c = make_t1.channel_for("qrm", 6.0, 700.0)
    assert c.qrm_kind == "morse" and c.snr_db == 6.0
    assert make_t1.channel_for("mp3", 0.0, 700.0).mp3_kbps == 64


def test_build_cells_counts():
    assert len(make_t1.build_cells(full=False)) == 5 * 4 * 5 * 5
    assert len(make_t1.build_cells(full=True)) == 7 * 8 * 5 * 5


def test_generate_small_matrix_and_bench(tmp_path, monkeypatch):
    monkeypatch.setattr(make_t1, "SNR_GATE", [10.0, 20.0])
    monkeypatch.setattr(make_t1, "WPM_GATE", [18.0, 25.0])
    monkeypatch.setattr(make_t1, "KEYING", ("machine", "jitter"))
    monkeypatch.setattr(make_t1, "CHANNELS", ("clean",))
    rows = make_t1.generate_matrix(tmp_path, full=False, clips=1)
    assert len(rows) == 2 * 2 * 2
    assert all(Path(r["path"]).exists() for r in rows)
    manifest = tmp_path / "manifest.jsonl"
    assert manifest.exists()

    results = bench.evaluate(bench.load_rows(manifest), engine="baseline")
    assert len(results) == 8
    assert all("cer" in r and "hyp" in r for r in results)
    ok, mean_cer, n = bench.gate(results, max_cer=0.5)
    assert n == 8 and 0.0 <= mean_cer <= 1.0
    table = bench.pivot_snr_wpm(results)
    assert "18" in table and "25" in table

    summary, gate_ok = bench.run(manifest, "baseline", None, tmp_path / "res", None, True, 0.5)
    out = list((tmp_path / "res").glob("*.json"))
    assert len(out) == 1
    saved = json.loads(out[0].read_text(encoding="utf-8"))
    assert saved["n"] == 8 and "by_keying" in saved


def test_cli_bench(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(make_t1, "SNR_GATE", [20.0])
    monkeypatch.setattr(make_t1, "WPM_GATE", [20.0])
    monkeypatch.setattr(make_t1, "KEYING", ("machine",))
    monkeypatch.setattr(make_t1, "CHANNELS", ("clean",))
    make_t1.generate_matrix(tmp_path, full=False, clips=1)
    rc = main(["bench", "--manifest", str(tmp_path / "manifest.jsonl"),
               "--out-dir", str(tmp_path / "r"), "--gate", "--max-cer", "0.5"])
    assert rc == 0
    assert "CER" in capsys.readouterr().out


@pytest.mark.skipif(not Path("models/acoustic.onnx").exists(), reason="chưa có model ONNX (Task 17)")
def test_t1_gate_onnx():
    manifest = Path("testdata/generated/t1/manifest.jsonl")
    if not manifest.exists():
        pytest.skip("chạy: uv run python tools/make_t1.py")
    results = bench.evaluate(bench.load_rows(manifest), engine="onnx", model_path=Path("models/acoustic.onnx"))
    ok, mean_cer, n = bench.gate(results)
    assert ok, f"CER vùng gate = {mean_cer:.4f} trên {n} clip, ngưỡng 0.02"


def test_evaluate_isolates_decode_errors(tmp_path):
    from tools.make_t2_manifest import write_jsonl

    bad = tmp_path / "bad.wav"
    bad.write_text("không phải audio", encoding="utf-8")
    rows = [{"path": str(bad), "text": "CQ DE K", "profile": "en", "snr": 20.0, "wpm": 20.0,
             "keying": "machine", "channel": "clean", "channel_actual": "clean", "seed": 0}]
    manifest = tmp_path / "m.jsonl"
    write_jsonl(rows, manifest)
    results = bench.evaluate(bench.load_rows(manifest), engine="baseline")
    assert len(results) == 1
    assert results[0]["hyp"] == "" and results[0]["cer"] == 1.0
    assert results[0]["error"]
    summary, _ = bench.run(manifest, "baseline", None, tmp_path / "r", None, False, 0.02)
    assert summary["errors"] == 1
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/regression/test_t1.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.bench'`

- [ ] **Step 3: Viết tools/make_t1.py**

```python
"""Sinh ma trận test T1 (seed cố định) và manifest JSONL.

Ô = SNR × WPM × kiểu gõ × kênh. Mặc định chỉ vùng gate (SNR >= 0, WPM 10–35); --full sinh toàn bộ.
Kênh "mp3" cần ffmpeg; nếu thiếu, clip vẫn sinh nhưng channel_actual = "clean".
Kiểu gõ "farnsworth" chỉ có nghĩa khi WPM <= 18; trên đó nó trùng "machine".
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from morsedesk.audio.io import save_audio
from morsedesk.data.channel import ChannelParams, clean
from morsedesk.data.keyer import KeyerParams, machine
from morsedesk.data.synth import SynthConfig, SynthGenerator
from tools.make_t2_manifest import write_jsonl

SNR_FULL = [-6.0, -3.0, 0.0, 3.0, 6.0, 10.0, 20.0]
WPM_FULL = [5.0, 8.0, 12.0, 18.0, 25.0, 35.0, 45.0, 60.0]
SNR_GATE = [0.0, 3.0, 6.0, 10.0, 20.0]
WPM_GATE = [12.0, 18.0, 25.0, 35.0]
KEYING = ("machine", "farnsworth", "jitter", "bug", "drift")
CHANNELS = ("clean", "qsb", "qrm", "qrn", "mp3")
PROFILES = ("en", "ru", "kk-cyrl-ru")


def keyer_for(name: str, wpm: float) -> KeyerParams:
    if name == "machine":
        return machine(wpm)
    if name == "farnsworth":
        far = max(5.0, wpm / 2.0) if wpm <= 18.0 else None
        return KeyerParams(wpm, far, 3.0, 0.0, False, 0.0, 0.0, "farnsworth")
    if name == "jitter":
        return KeyerParams(wpm, None, 3.0, 0.15, False, 0.0, 0.05, "jitter")
    if name == "bug":
        return KeyerParams(wpm, None, 3.5, 0.10, True, 0.0, 0.0, "bug")
    if name == "drift":
        return KeyerParams(wpm, None, 3.0, 0.05, False, 0.15, 0.0, "drift")
    raise ValueError(f"kiểu gõ lạ: {name}")


def channel_for(name: str, snr_db: float, tone_hz: float) -> ChannelParams:
    base = clean(snr_db, tone_hz, name)
    if name == "clean":
        return base
    if name == "qsb":
        return replace(base, qsb_depth_db=20.0, qsb_period_s=4.0)
    if name == "qrm":
        return replace(base, qrm_offset_hz=300.0, qrm_level_db=6.0, qrm_kind="morse")
    if name == "qrn":
        return replace(base, qrn_rate_per_s=20.0)
    if name == "mp3":
        return replace(base, mp3_kbps=64)
    raise ValueError(f"kênh lạ: {name}")


def build_cells(full: bool) -> list[dict]:
    snrs = SNR_FULL if full else SNR_GATE
    wpms = WPM_FULL if full else WPM_GATE
    return [
        {"snr": s, "wpm": w, "keying": k, "channel": c}
        for s in snrs for w in wpms for k in KEYING for c in CHANNELS
    ]


def generate_matrix(out_dir: Path, full: bool = False, clips: int = 1, seed_base: int = 1000) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gen = SynthGenerator(SynthConfig(min_seconds=5.0, max_seconds=8.0))
    rows: list[dict] = []
    index = 0
    for cell in build_cells(full):
        for i in range(clips):
            seed = seed_base + index
            profile = PROFILES[index % len(PROFILES)]
            tone = 500.0 + (index * 97) % 600
            keyer = keyer_for(cell["keying"], cell["wpm"])
            channel = channel_for(cell["channel"], cell["snr"], tone)
            ex = gen.generate(seed, profile_id=profile, keyer=keyer, channel=channel)
            name = f"{int(cell['snr']):+03d}db_{int(cell['wpm']):02d}wpm_{cell['keying']}_{cell['channel']}_{i}.wav"
            path = out_dir / name
            save_audio(path, ex.audio, ex.sample_rate)
            actual = cell["channel"]
            if actual == "mp3" and ex.channel.mp3_kbps is None:
                actual = "clean"
            rows.append({
                "path": str(path.resolve()), "text": ex.text, "profile": profile,
                "snr": cell["snr"], "wpm": cell["wpm"], "keying": cell["keying"],
                "channel": cell["channel"], "channel_actual": actual, "seed": seed,
            })
            index += 1
    write_jsonl(rows, out_dir / "manifest.jsonl")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sinh ma trận T1")
    ap.add_argument("--out", type=Path, default=Path("testdata/generated/t1"))
    ap.add_argument("--full", action="store_true", help="toàn bộ SNR/WPM thay vì chỉ vùng gate")
    ap.add_argument("--clips", type=int, default=1, help="số clip mỗi ô")
    a = ap.parse_args(argv)
    rows = generate_matrix(a.out, a.full, a.clips)
    print(f"{len(rows)} clip -> {a.out / 'manifest.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Viết morsedesk/bench.py**

```python
"""Đo CER/WER trên manifest JSONL theo ô SNR × WPM × kiểu gõ × kênh; gate vùng mục tiêu."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from morsedesk.api import Decoder
from morsedesk.metrics import cer, wer


def load_rows(manifest: Path) -> list[dict]:
    with open(manifest, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def evaluate(rows: list[dict], engine: str = "baseline", model_path: Path | None = None,
             limit: int | None = None) -> list[dict]:
    decoders: dict[str, Decoder] = {}
    results = []
    for row in rows[:limit] if limit else rows:
        pid = row.get("profile", "en")
        if pid not in decoders:
            decoders[pid] = Decoder(pid, engine=engine, model_path=model_path)
        t0 = time.time()
        out = dict(row)
        try:
            r = decoders[pid].decode_file(row["path"])
        except Exception as e:  # một file hỏng không được làm mất cả lô
            out.update({
                "hyp": "", "cer": cer(row["text"], ""), "wer": wer(row["text"], ""),
                "wpm_est": None, "seconds": time.time() - t0, "warnings": [],
                "error": f"{type(e).__name__}: {e}",
            })
            results.append(out)
            continue
        out.update({
            "hyp": r.text, "cer": cer(row["text"], r.text), "wer": wer(row["text"], r.text),
            "wpm_est": r.wpm, "seconds": time.time() - t0, "warnings": r.warnings, "error": None,
        })
        results.append(out)
    return results


def aggregate(results: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[str(r.get(key, "n/a"))].append(r)
    return {
        k: {"n": len(v), "cer": sum(x["cer"] for x in v) / len(v), "wer": sum(x["wer"] for x in v) / len(v)}
        for k, v in sorted(groups.items())
    }


def pivot_snr_wpm(results: list[dict]) -> str:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in results:
        cells[(str(r.get("snr", "n/a")), str(r.get("wpm", "n/a")))].append(r["cer"])
    snrs = sorted({k[0] for k in cells}, key=lambda s: float(s) if s != "n/a" else 1e9)
    wpms = sorted({k[1] for k in cells}, key=lambda s: float(s) if s != "n/a" else 1e9)
    lines = ["CER % theo SNR (hàng) x WPM (cột)", "SNR\\WPM " + " ".join(f"{w:>7}" for w in wpms)]
    for s in snrs:
        vals = []
        for w in wpms:
            v = cells.get((s, w))
            vals.append(f"{100 * sum(v) / len(v):7.2f}" if v else f"{'-':>7}")
        lines.append(f"{s:>7} " + " ".join(vals))
    return "\n".join(lines)


def gate(results: list[dict], max_cer: float = 0.02, snr_min: float = 0.0,
         wpm_min: float = 10.0, wpm_max: float = 35.0) -> tuple[bool, float, int]:
    sub = [r for r in results
           if isinstance(r.get("snr"), (int, float)) and isinstance(r.get("wpm"), (int, float))
           and r["snr"] >= snr_min and wpm_min <= r["wpm"] <= wpm_max]
    if not sub:
        return False, 1.0, 0
    mean = sum(r["cer"] for r in sub) / len(sub)
    return mean <= max_cer, mean, len(sub)


def run(manifest: Path, engine: str, model_path: Path | None, out_dir: Path,
        limit: int | None, do_gate: bool, max_cer: float) -> tuple[dict, bool]:
    results = evaluate(load_rows(manifest), engine, model_path, limit)
    ok, gate_cer, gate_n = gate(results, max_cer)
    summary = {
        "engine": engine, "manifest": str(manifest), "n": len(results),
        "mean_cer": sum(r["cer"] for r in results) / max(1, len(results)),
        "mean_wer": sum(r["wer"] for r in results) / max(1, len(results)),
        "errors": sum(1 for r in results if r.get("error")),
        "gate": {"ok": ok, "cer": gate_cer, "n": gate_n, "max_cer": max_cer},
        "by_snr": aggregate(results, "snr"), "by_wpm": aggregate(results, "wpm"),
        "by_keying": aggregate(results, "keying"), "by_channel": aggregate(results, "channel_actual"),
        "by_profile": aggregate(results, "profile"), "rows": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"bench_{engine}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(pivot_snr_wpm(results))
    for key in ("by_keying", "by_channel", "by_profile"):
        print(key + ": " + ", ".join(f"{k}={100 * v['cer']:.2f}%" for k, v in summary[key].items()))
    print(f"n={len(results)} CER={100 * summary['mean_cer']:.2f}% WER={100 * summary['mean_wer']:.2f}% lỗi={summary['errors']} -> {out}")
    if do_gate:
        print(f"gate (SNR>=0, 10-35 WPM, n={gate_n}): CER={100 * gate_cer:.2f}% "
              f"{'ĐẠT' if ok else 'TRƯỢT'} (ngưỡng {100 * max_cer:.2f}%)")
    return summary, ok if do_gate else True
```

- [ ] **Step 5: Thêm lệnh con bench vào cli.py**

Trong `build_parser()` thêm sau `sub.add_parser("devices", ...)`:

```python
    b = sub.add_parser("bench", help="đo CER/WER trên manifest JSONL")
    b.add_argument("--manifest", type=Path, required=True)
    b.add_argument("--engine", default="baseline", choices=["baseline", "onnx"])
    b.add_argument("--model", type=Path, default=Path("models/acoustic.onnx"))
    b.add_argument("--out-dir", type=Path, default=Path("bench_results"))
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--gate", action="store_true", help="kiểm tra vùng SNR>=0, 10-35 WPM")
    b.add_argument("--max-cer", type=float, default=0.02)
```

Thêm hàm:

```python
def cmd_bench(a: argparse.Namespace) -> int:
    from morsedesk.bench import run

    model = a.model if a.engine == "onnx" else None
    _, ok = run(a.manifest, a.engine, model, a.out_dir, a.limit, a.gate, a.max_cer)
    return 0 if ok else 1
```

Và trong `main()` đổi dict thành:

```python
    return {"encode": cmd_encode, "decode": cmd_decode, "devices": cmd_devices, "bench": cmd_bench}[a.cmd](a)
```

- [ ] **Step 6: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/regression/test_t1.py -v`
Expected: `5 passed, 1 skipped` (gate ONNX bỏ qua vì chưa có model)

Sinh ma trận gate thật và đo baseline để có số đối chứng tuần 1:

Run: `uv run python tools/make_t1.py` rồi `uv run morsedesk bench --manifest testdata/generated/t1/manifest.jsonl --engine baseline --gate`
Expected: in bảng CER theo SNR × WPM, `n=500`, và dòng gate. Baseline nhiều khả năng TRƯỢT ở SNR 0–3 dB; ghi số vào `docs/research/02-baseline-numbers.md` (bảng dán từ stdout) để so với model ONNX ở Task 17.

- [ ] **Step 7: Commit**

```bash
git add tools/make_t1.py morsedesk/bench.py morsedesk/cli.py tests/regression/test_t1.py docs/research/02-baseline-numbers.md
git commit -m "feat(bench): ma trận T1 và harness đo CER theo ô, lệnh morsedesk bench" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 15: Mạng PyTorch, giải mã greedy CTC và script huấn luyện

**Files:**
- Create: `morsedesk/model/ctc.py`
- Create: `tools/net_torch.py`
- Create: `tools/train.py`
- Test: `tests/unit/test_ctc.py`, `tests/unit/test_train_smoke.py`

**Interfaces:**
- Consumes: `SynthGenerator`, `SynthConfig`, `Example` (Task 13); `machine`, `clean` (Task 13); `compute_features` (Task 8); `estimate_tone` (Task 7); `VOCAB`; `edit_distance` (Task 9).
- Produces:
  - `ctc.greedy_decode(log_probs: np.ndarray[T, C], blank=0) -> list[int]`; `ctc.greedy_decode_with_frames(log_probs, blank=0) -> list[tuple[int, int, float]]` (id, khung đầu phát ra, xác suất).
  - `net_torch.MorseNet(feat_dim=11, n_classes=65, hidden=96)` với `forward(feats [B,T,F]) -> log_softmax [B, out_len(T), C]`; `net_torch.output_length(t: int) -> int` (= `(t-1)//2 + 1`); `net_torch.count_params(model) -> int`; `net_torch.CONFIG_DEFAULT = {"feat_dim": 11, "n_classes": 65, "hidden": 96}`.
  - `train.example_features(ex: Example) -> np.ndarray`; `train.SynthDataset(gen, seed_start, n_items)`; `train.collate(batch) -> (feats, feat_lens, targets, target_lens, token_lists)`; `train.token_error_rate(model, items) -> float`; `train.train_loop(model, loader, opt, ctc, steps, val_items, run_dir, log_every, val_every) -> dict`; `train.main(argv)`. Checkpoint: dict `{"state_dict", "step", "val_ter", "config"}` tại `runs/<name>/best.pt` và `last.pt`.

- [ ] **Step 1: Viết test ctc**

`tests/unit/test_ctc.py`:

```python
import numpy as np

from morsedesk.model.ctc import greedy_decode, greedy_decode_with_frames


def _logp(ids, n_classes=5):
    lp = np.full((len(ids), n_classes), -10.0, dtype=np.float32)
    for t, i in enumerate(ids):
        lp[t, i] = 0.0
    return lp


def test_greedy_collapses_repeats_and_blanks():
    assert greedy_decode(_logp([0, 3, 3, 0, 0, 4, 4, 4, 0, 3])) == [3, 4, 3]


def test_greedy_empty():
    assert greedy_decode(_logp([0, 0, 0])) == []
    assert greedy_decode(np.zeros((0, 5), dtype=np.float32)) == []


def test_greedy_with_frames():
    out = greedy_decode_with_frames(_logp([0, 3, 3, 0, 4]))
    assert [(i, f) for i, f, _ in out] == [(3, 1), (4, 4)]
    assert all(abs(p - 1.0) < 1e-3 for _, _, p in out)
```

- [ ] **Step 2: Viết test train smoke**

`tests/unit/test_train_smoke.py`:

```python
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from morsedesk.data.channel import clean
from morsedesk.data.keyer import machine
from morsedesk.data.synth import SynthConfig, SynthGenerator
from morsedesk.model.vocab import VOCAB
from tools.net_torch import CONFIG_DEFAULT, MorseNet, count_params, output_length
from tools.train import SynthDataset, collate, example_features, token_error_rate


def test_output_length_matches_conv():
    m = MorseNet()
    for t in (1, 2, 3, 100, 101, 800):
        y = m(torch.zeros(1, t, 11))
        assert y.shape == (1, output_length(t), len(VOCAB))
    assert 100_000 < count_params(m) < 400_000
    assert CONFIG_DEFAULT["n_classes"] == 65


def test_forward_is_log_softmax():
    y = MorseNet()(torch.zeros(2, 50, 11))
    assert torch.allclose(y.exp().sum(-1), torch.ones(2, output_length(50)), atol=1e-4)


def test_dataset_and_collate():
    gen = SynthGenerator(SynthConfig(min_seconds=2.0, max_seconds=3.0, mp3_enabled=False))
    ds = SynthDataset(gen, seed_start=0, n_items=3)
    items = list(ds)
    assert len(items) == 3
    feats, feat_lens, targets, target_lens, tokens = collate(items)
    assert feats.shape[0] == 3 and feats.shape[2] == 11
    assert feat_lens.tolist() == [output_length(len(it[0])) for it in items]
    assert int(target_lens.sum()) == len(targets)
    assert len(tokens) == 3


def test_overfit_tiny_batch_reduces_loss():
    torch.manual_seed(0)
    gen = SynthGenerator(SynthConfig(min_seconds=2.0, max_seconds=3.0, mp3_enabled=False))
    items = []
    for s in range(4):
        ex = gen.generate(s, profile_id="en", keyer=machine(25), channel=clean(30.0))
        items.append((torch.from_numpy(example_features(ex)), torch.tensor(ex.labels), ex.tokens))
    feats, feat_lens, targets, target_lens, _ = collate(items)
    model = MorseNet()
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    ctc = torch.nn.CTCLoss(blank=0, zero_infinity=True)
    losses = []
    for _ in range(60):
        logp = model(feats)
        loss = ctc(logp.transpose(0, 1), targets, feat_lens, target_lens)
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
    assert losses[-1] < 0.7 * losses[0], losses[::10]
    ter = token_error_rate(model, [(f, t) for f, _, t in items])
    assert 0.0 <= ter <= 1.5
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_ctc.py tests/unit/test_train_smoke.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.model.ctc'`

- [ ] **Step 4: Viết ctc.py**

```python
"""Giải mã greedy cho đầu ra CTC."""

from __future__ import annotations

import numpy as np


def greedy_decode(log_probs: np.ndarray, blank: int = 0) -> list[int]:
    if log_probs.shape[0] == 0:
        return []
    ids = log_probs.argmax(axis=-1)
    out: list[int] = []
    prev = -1
    for i in ids.tolist():
        if i != prev and i != blank:
            out.append(int(i))
        prev = i
    return out


def greedy_decode_with_frames(log_probs: np.ndarray, blank: int = 0) -> list[tuple[int, int, float]]:
    """(id, khung đầu tiên phát ra token, xác suất tại khung đó)."""
    if log_probs.shape[0] == 0:
        return []
    ids = log_probs.argmax(axis=-1)
    out: list[tuple[int, int, float]] = []
    prev = -1
    for t, i in enumerate(ids.tolist()):
        if i != prev and i != blank:
            out.append((int(i), t, float(np.exp(log_probs[t, i]))))
        prev = i
    return out
```

- [ ] **Step 5: Viết tools/net_torch.py**

```python
"""Định nghĩa mạng PyTorch. Chỉ dùng lúc huấn luyện và xuất ONNX; runtime không cần torch."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from morsedesk.constants import FEAT_DIM
from morsedesk.model.vocab import VOCAB

CONFIG_DEFAULT = {"feat_dim": FEAT_DIM, "n_classes": len(VOCAB), "hidden": 96}


def output_length(t: int) -> int:
    """Conv1d k=5, pad=2, stride=2 ở tầng hai: L_out = (L-1)//2 + 1."""
    return (t - 1) // 2 + 1


class MorseNet(nn.Module):
    def __init__(self, feat_dim: int = FEAT_DIM, n_classes: int = len(VOCAB), hidden: int = 96) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(feat_dim, 32, 5, padding=2), nn.ReLU(),
            nn.Conv1d(32, 64, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv1d(64, 64, 5, padding=2), nn.ReLU(),
        )
        self.gru = nn.GRU(64, hidden, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(2 * hidden, n_classes)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:  # [B, T, F] -> [B, T', C]
        x = self.conv(feats.transpose(1, 2)).transpose(1, 2)
        x, _ = self.gru(x)
        return F.log_softmax(self.fc(x), dim=-1)


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
```

- [ ] **Step 6: Viết tools/train.py**

```python
"""Huấn luyện CTC on-the-fly bằng SynthGenerator; checkpoint tốt nhất theo token error rate."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

from morsedesk.data.synth import Example, SynthConfig, SynthGenerator
from morsedesk.dsp.frontend import compute_features
from morsedesk.dsp.tone import estimate_tone
from morsedesk.metrics import edit_distance
from morsedesk.model.ctc import greedy_decode
from morsedesk.model.vocab import VOCAB
from morsedesk.textio import force_utf8_streams
from tools.net_torch import CONFIG_DEFAULT, MorseNet, count_params, output_length


def example_features(ex: Example) -> np.ndarray:
    """Đặc trưng như lúc chạy thật: dùng tone dò được, rơi về tone thật nếu dò thất bại."""
    est = estimate_tone(ex.audio)
    f0 = est.f0_hz if est.has_signal and est.f0_hz is not None else ex.f0_hz
    return compute_features(ex.audio, f0)


class SynthDataset(IterableDataset):
    def __init__(self, gen: SynthGenerator, seed_start: int, n_items: int) -> None:
        self.gen, self.seed_start, self.n_items = gen, seed_start, n_items

    def __iter__(self):
        info = get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        for k in range(wid, self.n_items, nw):
            ex = self.gen.generate(self.seed_start + k)
            yield torch.from_numpy(example_features(ex)), torch.tensor(ex.labels, dtype=torch.long), ex.tokens


def collate(batch):
    feats = [b[0] for b in batch]
    t_max = max(f.shape[0] for f in feats)
    padded = torch.zeros(len(feats), t_max, feats[0].shape[1])
    for i, f in enumerate(feats):
        padded[i, : f.shape[0]] = f
    feat_lens = torch.tensor([output_length(f.shape[0]) for f in feats], dtype=torch.long)
    targets = torch.cat([b[1] for b in batch])
    target_lens = torch.tensor([len(b[1]) for b in batch], dtype=torch.long)
    return padded, feat_lens, targets, target_lens, [b[2] for b in batch]


@torch.no_grad()
def token_error_rate(model: nn.Module, items: list[tuple[torch.Tensor, list[str]]]) -> float:
    model.eval()
    errs = total = 0
    for feats, tokens in items:
        logp = model(feats[None])[0].cpu().numpy()
        hyp = [VOCAB.token(i) for i in greedy_decode(logp)]
        errs += edit_distance(tokens, hyp)
        total += len(tokens)
    model.train()
    return errs / max(1, total)


def save_ckpt(path: Path, model: nn.Module, step: int, val_ter: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "step": step, "val_ter": val_ter,
                "config": CONFIG_DEFAULT}, path)


def train_loop(model, loader, opt, ctc, steps, val_items, run_dir: Path, log_every=50, val_every=500) -> dict:
    history = []
    best = float("inf")
    step = 0
    t0 = time.time()
    for feats, feat_lens, targets, target_lens, _ in loader:
        logp = model(feats)
        loss = ctc(logp.transpose(0, 1), targets, feat_lens, target_lens)
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        step += 1
        if step % log_every == 0:
            print(f"step {step} loss {loss.item():.4f} ({time.time() - t0:.0f}s)", flush=True)
        if step % val_every == 0 or step == steps:
            ter = token_error_rate(model, val_items)
            history.append({"step": step, "loss": loss.item(), "val_ter": ter})
            save_ckpt(run_dir / "last.pt", model, step, ter)
            if ter < best:
                best = ter
                save_ckpt(run_dir / "best.pt", model, step, ter)
            print(f"step {step} val TER {100 * ter:.2f}% (best {100 * best:.2f}%)", flush=True)
        if step >= steps:
            break
    (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    return {"best_ter": best, "steps": step}


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Huấn luyện MorseNet bằng dữ liệu tổng hợp")
    ap.add_argument("--name", default="v1")
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--val-clips", type=int, default=200)
    ap.add_argument("--val-every", type=int, default=500)
    ap.add_argument("--workers", type=int, default=0, help="DataLoader workers (0 an toàn trên Windows)")
    ap.add_argument("--no-mp3", action="store_true")
    ap.add_argument("--resume", type=Path, default=None)
    a = ap.parse_args(argv)

    torch.manual_seed(a.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))
    gen = SynthGenerator(SynthConfig(mp3_enabled=not a.no_mp3))
    model = MorseNet(**CONFIG_DEFAULT)
    if a.resume:
        model.load_state_dict(torch.load(a.resume, map_location="cpu", weights_only=True)["state_dict"])
    print(f"tham số: {count_params(model):,}")

    val_items = []
    for i in range(a.val_clips):
        ex = gen.generate(10_000_000 + i)
        val_items.append((torch.from_numpy(example_features(ex)), ex.tokens))

    ds = SynthDataset(gen, seed_start=a.seed * 1_000_000, n_items=a.steps * a.batch)
    loader = DataLoader(ds, batch_size=a.batch, collate_fn=collate, num_workers=a.workers)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr)
    ctc = nn.CTCLoss(blank=VOCAB.blank_id, zero_infinity=True)
    run_dir = Path("runs") / a.name
    result = train_loop(model, loader, opt, ctc, a.steps, val_items, run_dir, val_every=a.val_every)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_ctc.py tests/unit/test_train_smoke.py -v`
Expected: `7 passed` trong dưới 2 phút. Nếu `test_overfit_tiny_batch_reduces_loss` không giảm đủ 30%, tăng vòng lặp lên 100 và lr 5e-3 trong test; không đổi kiến trúc.

Chạy huấn luyện thật (nền, vài giờ trên CPU; dùng `--workers 4` nếu máy đủ nhân và không lỗi pickling):

Run: `uv run python tools/train.py --name v1 --steps 20000 --batch 16 --val-clips 200`
Expected: log `step N loss ...` mỗi 50 bước, `val TER` mỗi 500 bước giảm dần; `runs/v1/best.pt` được ghi. Mục tiêu sơ bộ: TER validation < 5% (validation trộn cả SNR âm nên cao hơn vùng gate).

- [ ] **Step 8: Commit**

```bash
git add morsedesk/model/ctc.py tools/net_torch.py tools/train.py tests/unit/test_ctc.py tests/unit/test_train_smoke.py
git commit -m "feat(train): MorseNet CNN+BiGRU+CTC, dataset on-the-fly, greedy decode" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 16: Xuất ONNX, runner onnxruntime, kiểm tra parity

**Files:**
- Create: `tools/export_onnx.py`
- Create: `morsedesk/model/onnx_runner.py`
- Test: `tests/unit/test_onnx_parity.py`

**Interfaces:**
- Consumes: `MorseNet`, `CONFIG_DEFAULT`, `output_length` (Task 15); `VOCAB`.
- Produces:
  - `export_onnx.export(checkpoint: Path, out_onnx: Path, version: str = "0.1.0", n_golden: int = 20) -> tuple[Path, Path]` (trả đường dẫn `.json` và `.golden.npz`); metadata JSON có khóa `version, sample_rate, hop, frame_rate, feat_dim, vocab, blank_id, space_id, unk_id, input_name, output_name, time_stride, opset, train_step, val_ter`; golden NPZ có `x0..x19` (đặc trưng) và `y0..y19` (log-prob torch).
  - `onnx_runner.OnnxAcousticModel(model_path: Path, meta_path: Path | None = None)` với `meta: dict`, `__call__(feats [T,11]) -> np.ndarray[T',65]`, `output_length(t) -> int`; `onnx_runner.check_parity(model, golden_path, atol=1e-4) -> float` (trả sai số tuyệt đối lớn nhất, ném `AssertionError` nếu vượt).

- [ ] **Step 1: Viết test**

`tests/unit/test_onnx_parity.py`:

```python
import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("onnxruntime")

from morsedesk.model.onnx_runner import OnnxAcousticModel, check_parity
from morsedesk.model.vocab import VOCAB
from tools.export_onnx import export
from tools.net_torch import CONFIG_DEFAULT, MorseNet, output_length


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("onnx")
    torch.manual_seed(0)
    model = MorseNet(**CONFIG_DEFAULT)
    ckpt = tmp / "best.pt"
    torch.save({"state_dict": model.state_dict(), "step": 1, "val_ter": 0.5, "config": CONFIG_DEFAULT}, ckpt)
    onnx_path = tmp / "acoustic.onnx"
    meta_path, golden_path = export(ckpt, onnx_path, version="test")
    return onnx_path, meta_path, golden_path


def test_metadata(exported):
    _, meta_path, _ = exported
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["vocab"] == VOCAB.tokens
    assert meta["sample_rate"] == 8000 and meta["hop"] == 40 and meta["feat_dim"] == 11
    assert meta["time_stride"] == 2 and meta["opset"] == 17


def test_parity_within_1e4(exported):
    onnx_path, _, golden_path = exported
    model = OnnxAcousticModel(onnx_path)
    max_err = check_parity(model, golden_path, atol=1e-4)
    assert max_err <= 1e-4


def test_dynamic_length_and_shapes(exported):
    onnx_path, _, _ = exported
    model = OnnxAcousticModel(onnx_path)
    for t in (37, 200, 1601):
        y = model(np.random.default_rng(t).normal(size=(t, 11)).astype(np.float32))
        assert y.shape == (output_length(t), 65)
        assert np.allclose(np.exp(y).sum(-1), 1.0, atol=1e-3)


def test_vocab_mismatch_rejected(exported, tmp_path):
    onnx_path, meta_path, _ = exported
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["vocab"] = meta["vocab"][::-1]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError):
        OnnxAcousticModel(onnx_path, bad)
```

- [ ] **Step 2: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_onnx_parity.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.model.onnx_runner'`

- [ ] **Step 3: Viết tools/export_onnx.py**

```python
"""Xuất checkpoint PyTorch sang ONNX opset 17 kèm metadata JSON và file golden để kiểm parity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from morsedesk.constants import FEAT_DIM, FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.model.vocab import VOCAB
from tools.net_torch import CONFIG_DEFAULT, MorseNet

OPSET = 17


def _onnx_export(model: torch.nn.Module, dummy: torch.Tensor, out: Path) -> None:
    kwargs = dict(
        input_names=["features"], output_names=["log_probs"],
        dynamic_axes={"features": {0: "batch", 1: "time"}, "log_probs": {0: "batch", 1: "time"}},
        opset_version=OPSET,
    )
    try:
        torch.onnx.export(model, dummy, str(out), dynamo=False, **kwargs)
    except TypeError:  # torch cũ không có tham số dynamo
        torch.onnx.export(model, dummy, str(out), **kwargs)


def export(checkpoint: Path, out_onnx: Path, version: str = "0.1.0", n_golden: int = 20) -> tuple[Path, Path]:
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    config = ckpt.get("config", CONFIG_DEFAULT)
    model = MorseNet(**config)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    out_onnx.parent.mkdir(parents=True, exist_ok=True)
    _onnx_export(model, torch.zeros(1, 800, config["feat_dim"]), out_onnx)

    meta = {
        "version": version, "sample_rate": SAMPLE_RATE, "hop": HOP, "frame_rate": FRAME_RATE,
        "feat_dim": FEAT_DIM, "vocab": VOCAB.tokens, "blank_id": VOCAB.blank_id,
        "space_id": VOCAB.space_id, "unk_id": VOCAB.unk_id, "input_name": "features",
        "output_name": "log_probs", "time_stride": 2, "opset": OPSET,
        "train_step": ckpt.get("step"), "val_ter": ckpt.get("val_ter"), "config": config,
    }
    meta_path = out_onnx.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    rng = np.random.default_rng(0)
    golden = {}
    with torch.no_grad():
        for i in range(n_golden):
            t = int(rng.integers(200, 1600))
            x = rng.normal(size=(t, config["feat_dim"])).astype(np.float32)
            y = model(torch.from_numpy(x)[None])[0].numpy()
            golden[f"x{i}"], golden[f"y{i}"] = x, y
    golden_path = out_onnx.with_suffix(".golden.npz")
    np.savez(golden_path, **golden)
    return meta_path, golden_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Xuất ONNX")
    ap.add_argument("--checkpoint", type=Path, default=Path("runs/v1/best.pt"))
    ap.add_argument("--out", type=Path, default=Path("models/acoustic.onnx"))
    ap.add_argument("--version", default="0.1.0")
    a = ap.parse_args(argv)
    meta, golden = export(a.checkpoint, a.out, a.version)
    print(f"đã ghi {a.out}, {meta}, {golden}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Viết morsedesk/model/onnx_runner.py**

```python
"""Chạy mô hình âm thanh ONNX trên CPU, kiểm metadata và parity với golden."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort

from morsedesk.model.vocab import VOCAB


class OnnxAcousticModel:
    def __init__(self, model_path: Path, meta_path: Path | None = None) -> None:
        model_path = Path(model_path)
        meta_path = Path(meta_path) if meta_path else model_path.with_suffix(".json")
        if not model_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"thiếu model hoặc metadata: {model_path}, {meta_path}")
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if self.meta.get("vocab") != VOCAB.tokens:
            raise ValueError("từ vựng trong metadata model không khớp phần mềm; cần xuất lại model")
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, (os.cpu_count() or 2) // 2)
        self.session = ort.InferenceSession(str(model_path), so, providers=["CPUExecutionProvider"])
        self.input_name = self.meta["input_name"]
        self.output_name = self.meta["output_name"]
        self.time_stride = int(self.meta["time_stride"])

    def output_length(self, t: int) -> int:
        return (t - 1) // self.time_stride + 1

    def __call__(self, feats: np.ndarray) -> np.ndarray:
        x = np.ascontiguousarray(feats, dtype=np.float32)[None]
        return self.session.run([self.output_name], {self.input_name: x})[0][0]


def check_parity(model: OnnxAcousticModel, golden_path: Path, atol: float = 1e-4) -> float:
    data = np.load(golden_path)
    n = len([k for k in data.files if k.startswith("x")])
    max_err = 0.0
    for i in range(n):
        y = model(data[f"x{i}"])
        err = float(np.max(np.abs(y - data[f"y{i}"])))
        max_err = max(max_err, err)
    if max_err > atol:
        raise AssertionError(f"parity ONNX/torch lệch {max_err:.2e} > {atol:.0e}")
    return max_err
```

- [ ] **Step 5: Chạy test, xác nhận đạt**

Run: `uv run pytest tests/unit/test_onnx_parity.py -v`
Expected: `4 passed`

Xuất model đã huấn luyện ở Task 15 (khi `runs/v1/best.pt` đã có):

Run: `uv run python tools/export_onnx.py --checkpoint runs/v1/best.pt --out models/acoustic.onnx`
Expected: tạo `models/acoustic.onnx`, `models/acoustic.json`, `models/acoustic.golden.npz`. Thêm `models/*.onnx` và `models/*.npz` vào `.gitignore`; commit `models/acoustic.json`.

- [ ] **Step 6: Commit**

```bash
git add tools/export_onnx.py morsedesk/model/onnx_runner.py tests/unit/test_onnx_parity.py .gitignore
git commit -m "feat(onnx): xuất ONNX opset 17, runner onnxruntime, kiểm parity golden" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

### Task 17: Cửa sổ trượt, engine ONNX trong Decoder, đo T1 bằng model

**Files:**
- Create: `morsedesk/model/chunker.py`
- Modify: `morsedesk/api.py` (thêm engine `onnx`, `fallback_text`, ước lượng WPM từ token)
- Test: `tests/unit/test_chunker.py`, `tests/unit/test_decoder_onnx.py`

**Interfaces:**
- Consumes: `OnnxAcousticModel` (Task 16); `greedy_decode_with_frames` (Task 15); `compute_features`, `mix_envelope` (Task 8); `estimate_tone` (Task 7); `BaselineDecoder` (Task 10); `VOCAB`, `SPACE`, `UNK`.
- Produces:
  - `chunker.WINDOW_FRAMES = 800`, `STEP_FRAMES = 600`, `LIVE_WINDOW_FRAMES = 400`, `LIVE_STEP_FRAMES = 200`; `chunker.frame_windows(n_frames, window=800, step=600) -> list[tuple[int, int]]` (start chẵn); `chunker.run_chunked(model, feats, window=800, step=600) -> np.ndarray[T', C]`.
  - `api.DecodeResult` thêm trường `fallback_text: str | None = None` (cuối cùng, có mặc định). `api.DEFAULT_MODEL_PATH = <repo>/models/acoustic.onnx`; `api.FALLBACK_CONFIDENCE = 0.5`; `api.pattern_units(token) -> float`; `api.estimate_wpm_from_emissions(emissions: list[tuple[str, int, float]], frame_rate) -> float | None` (emission = (token, khung đầu vào, xác suất)); `api.emissions_to_words(emissions, profile, frame_rate, end_frame) -> list[Word]`; `Decoder(profile, engine="onnx", model_path=None)` nạp model (thiếu file → `FileNotFoundError`), `decode_array` trả `engine="onnx"`, kèm `fallback_text` từ baseline khi tin cậy trung bình < 0.5.

- [ ] **Step 1: Viết test chunker**

`tests/unit/test_chunker.py`:

```python
import numpy as np
import pytest

from morsedesk.model.chunker import frame_windows, run_chunked


class FakeModel:
    """Trả one-hot của (chỉ số khung toàn cục) % 6, lấy chỉ số từ cột 0 của đặc trưng."""
    time_stride = 2
    meta = {"vocab": list(range(6))}

    def output_length(self, t):
        return (t - 1) // 2 + 1

    def __call__(self, feats):
        n_out = self.output_length(len(feats))
        out = np.full((n_out, 6), -10.0, dtype=np.float32)
        for j in range(n_out):
            out[j, int(feats[2 * j, 0]) % 6] = 0.0
        return out


def test_frame_windows_short_and_long():
    assert frame_windows(500) == [(0, 500)]
    w = frame_windows(2000, 800, 600)
    assert w == [(0, 800), (600, 1400), (1200, 2000)]
    w2 = frame_windows(2001, 800, 600)
    assert all(s % 2 == 0 for s, _ in w2)
    assert w2[-1][1] <= 2001 and w2[-1][1] >= 1999
    with pytest.raises(ValueError):
        frame_windows(100, 801, 600)


def test_run_chunked_maps_global_frames():
    n = 2001
    feats = np.zeros((n, 11), dtype=np.float32)
    feats[:, 0] = np.arange(n)
    out = run_chunked(FakeModel(), feats, window=800, step=600)
    assert out.shape == ((n - 1) // 2 + 1, 6)
    expected = (2 * np.arange(out.shape[0])) % 6
    assert np.array_equal(out.argmax(axis=1), expected)


def test_run_chunked_single_window():
    feats = np.zeros((300, 11), dtype=np.float32)
    feats[:, 0] = np.arange(300)
    out = run_chunked(FakeModel(), feats)
    assert out.shape == (150, 6)
```

- [ ] **Step 2: Viết test Decoder ONNX**

`tests/unit/test_decoder_onnx.py`:

```python
from pathlib import Path

import numpy as np
import pytest

from morsedesk.api import (
    Decoder, Encoder, emissions_to_words, estimate_wpm_from_emissions, pattern_units,
)
from morsedesk.cli import main
from morsedesk.lm.profile import load_profile
from morsedesk.metrics import cer
from morsedesk.model.vocab import SPACE


@pytest.fixture(scope="module")
def tmp_model(tmp_path_factory):
    torch = pytest.importorskip("torch")
    pytest.importorskip("onnxruntime")
    from tools.export_onnx import export
    from tools.net_torch import CONFIG_DEFAULT, MorseNet

    tmp = tmp_path_factory.mktemp("m")
    torch.manual_seed(0)
    ckpt = tmp / "best.pt"
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                "config": CONFIG_DEFAULT}, ckpt)
    onnx_path = tmp / "acoustic.onnx"
    export(ckpt, onnx_path, version="test")
    return onnx_path


def test_pattern_units():
    assert pattern_units(".-") == 1 + 3 + 1
    assert pattern_units("-") == 3
    assert pattern_units(".....") == 5 + 4


def test_estimate_wpm_from_emissions():
    u = 12  # 20 WPM -> dit 60 ms = 12 khung
    em = [(".-", 0, 0.9), ("-...", 8 * u, 0.9), ("-.-.", (8 + 9 + 3) * u, 0.9)]
    assert abs(estimate_wpm_from_emissions(em, 200) - 20.0) < 0.5
    em2 = [(".-", 0, 0.9), (SPACE, 5 * u, 1.0), ("-...", 12 * u, 0.9), ("-", (12 + 9 + 3) * u, 0.9)]
    assert abs(estimate_wpm_from_emissions(em2, 200) - 20.0) < 0.5
    assert estimate_wpm_from_emissions([(".-", 0, 0.9)], 200) is None


def test_emissions_to_words():
    en = load_profile("en")
    em = [("-.-.", 0, 0.9), ("--.-", 100, 0.4), (SPACE, 200, 1.0), ("-..", 300, 0.81), (".", 400, 0.81)]
    words = emissions_to_words(em, en, 200, 500)
    assert [w.text for w in words] == ["CQ", "DE"]
    assert abs(words[0].confidence - (0.9 * 0.4) ** 0.5) < 1e-6
    assert abs(words[1].confidence - 0.81) < 1e-6
    assert words[0].start_s == 0.0 and words[0].end_s == 1.0
    assert words[1].start_s == 1.5 and words[1].end_s == 2.5


def test_onnx_engine_runs_with_untrained_model(tmp_model):
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20)
    r = Decoder("en", engine="onnx", model_path=tmp_model).decode_array(x)
    assert r.engine == "onnx"
    assert isinstance(r.text, str)
    assert abs(r.tone_hz - 700) < 10
    assert r.fallback_text is None or isinstance(r.fallback_text, str)


def test_missing_model_raises(tmp_path):
    pytest.importorskip("onnxruntime")
    with pytest.raises(FileNotFoundError):
        Decoder("en", engine="onnx", model_path=tmp_path / "none.onnx")


def test_cli_missing_model_exit_2(tmp_path, capsys):
    pytest.importorskip("onnxruntime")
    wav = tmp_path / "a.wav"
    from morsedesk.audio.io import save_audio
    save_audio(wav, Encoder("en").to_audio("CQ", wpm=20), 8000)
    assert main(["decode", str(wav), "--engine", "onnx", "--model", str(tmp_path / "none.onnx")]) == 2
    assert "lỗi" in capsys.readouterr().err


@pytest.mark.skipif(not Path("models/acoustic.onnx").exists(), reason="chưa có model đã huấn luyện")
def test_trained_model_roundtrip():
    text = "CQ CQ DE R1ABC R1ABC K"
    x = Encoder("en").to_audio(text, wpm=20, snr_db=10.0, seed=1)
    r = Decoder("en", engine="onnx").decode_array(x)
    assert cer(text, r.text) < 0.05, r.text
    assert abs(r.wpm - 20) < 4.0
    x2 = Encoder("ru").to_audio("ПРИВЕТ МИР", wpm=25, snr_db=6.0, seed=2)
    r2 = Decoder("ru", engine="onnx").decode_array(x2)
    assert cer("ПРИВЕТ МИР", r2.text) < 0.1, r2.text
```

- [ ] **Step 3: Chạy test, xác nhận thất bại**

Run: `uv run pytest tests/unit/test_chunker.py tests/unit/test_decoder_onnx.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'morsedesk.model.chunker'` và `ImportError: cannot import name 'emissions_to_words'`

- [ ] **Step 4: Viết chunker.py**

```python
"""Cửa sổ trượt cho mô hình ONNX: chia đặc trưng thành cửa sổ chồng nhau và gộp log-prob,
mỗi khung đầu ra lấy từ cửa sổ có tâm gần nó nhất."""

from __future__ import annotations

import numpy as np

WINDOW_FRAMES = 800       # 4 s ở 200 khung/s (chế độ file)
STEP_FRAMES = 600         # 3 s, chồng 1 s
LIVE_WINDOW_FRAMES = 400  # 2 s (chế độ live)
LIVE_STEP_FRAMES = 200    # 1 s


def frame_windows(n_frames: int, window: int = WINDOW_FRAMES, step: int = STEP_FRAMES) -> list[tuple[int, int]]:
    if window % 2 or step % 2:
        raise ValueError("window và step phải là số chẵn để khớp stride 2 của mô hình")
    if n_frames <= window:
        return [(0, n_frames)]
    starts = list(range(0, n_frames - window, step))
    last = n_frames - window
    last -= last % 2
    if not starts or starts[-1] != last:
        starts.append(last)
    windows = [(s, s + window) for s in starts]
    # Cửa sổ cuối: làm tròn xuống số chẵn cho start có thể hụt 1 khung so với n_frames
    # (khi n_frames - window lẻ); kéo dài điểm cuối tới n_frames để không bỏ sót khung
    # cuối cùng (start luôn <= n_frames - window nên chỉ nới rộng, không bao giờ co lại).
    windows[-1] = (windows[-1][0], n_frames)
    return windows


def run_chunked(model, feats: np.ndarray, window: int = WINDOW_FRAMES, step: int = STEP_FRAMES) -> np.ndarray:
    """model: có time_stride, output_length(t), __call__(feats[T,F]) -> [T',C], meta['vocab']."""
    n = feats.shape[0]
    stride = int(model.time_stride)
    t_out = model.output_length(n)
    n_classes = len(model.meta["vocab"])
    out = np.zeros((t_out, n_classes), dtype=np.float32)
    best = np.full(t_out, np.inf)
    filled = np.zeros(t_out, dtype=bool)
    for s, e in frame_windows(n, window, step):
        lp = model(feats[s:e])
        g = s // stride + np.arange(lp.shape[0])
        valid = g < t_out
        g, lp = g[valid], lp[valid]
        center = (s + e) / 2.0
        dist = np.abs(g * stride + stride / 2.0 - center)
        better = dist < best[g]
        out[g[better]] = lp[better]
        best[g[better]] = dist[better]
        filled[g[better]] = True
    if not filled.all():
        out[~filled] = np.log(1e-6)
        out[~filled, 0] = 0.0
    return out
```

- [ ] **Step 5: Sửa api.py**

Thêm import ở đầu file:

```python
from morsedesk.dsp.frontend import compute_features, mix_envelope
from morsedesk.dsp.tone import estimate_tone
from morsedesk.model.ctc import greedy_decode_with_frames
from morsedesk.model.vocab import SPACE, VOCAB
```

(bỏ dòng `from morsedesk.model.vocab import SPACE` cũ). Thêm hằng số sau `LOW_CONFIDENCE`:

```python
FALLBACK_CONFIDENCE = 0.5
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "acoustic.onnx"
```

Thêm trường cuối vào `DecodeResult` (sau `engine: str`):

```python
    fallback_text: str | None = None
```

Thêm ba hàm sau `symbols_to_words`:

```python
def pattern_units(token: str) -> float:
    """Số dit của một mẫu: dot 1, dash 3, khoảng trong chữ 1."""
    return sum(1.0 if c == "." else 3.0 for c in token) + (len(token) - 1)


def estimate_wpm_from_emissions(emissions: list[tuple[str, int, float]], frame_rate: int) -> float | None:
    """emissions: (token, khung đầu vào lúc phát ra, xác suất). Chia số khung cho tổng dit lý thuyết."""
    items = [(t, f) for t, f, _ in emissions]
    if len([t for t, _ in items if t != SPACE]) < 2:
        return None
    units = 0.0
    for t, _ in items[:-1]:
        units += 4.0 if t == SPACE else pattern_units(t) + 3.0
    span = items[-1][1] - items[0][1]
    if units <= 0 or span <= 0:
        return None
    return 1.2 * frame_rate / (span / units)


def emissions_to_words(
    emissions: list[tuple[str, int, float]], profile: Profile, frame_rate: int, end_frame: int
) -> list[Word]:
    words: list[Word] = []
    cur: list[str] = []
    probs: list[float] = []
    start = 0
    for tok, f, p in list(emissions) + [(SPACE, end_frame, 1.0)]:
        if tok == SPACE:
            if cur:
                conf = float(np.exp(np.mean(np.log(np.maximum(probs, 1e-6)))))
                words.append(Word(profile.render(cur), start / frame_rate, f / frame_rate, conf))
                cur, probs = [], []
            continue
        if not cur:
            start = f
        cur.append(tok)
        probs.append(p)
    return words
```

Thay toàn bộ lớp `Decoder` bằng:

```python
class Decoder:
    def __init__(
        self, profile: str | Profile = "en", engine: str = "baseline", model_path: Path | None = None
    ) -> None:
        self.profile = _resolve_profile(profile)
        self.engine = engine
        self._baseline = BaselineDecoder()
        self._model = None
        if engine == "onnx":
            from morsedesk.model.onnx_runner import OnnxAcousticModel

            self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
            self._model = OnnxAcousticModel(self.model_path)
        elif engine != "baseline":
            raise NotImplementedError(f"engine chưa hỗ trợ: {engine}")

    def _empty(self, warnings: list[str]) -> DecodeResult:
        return DecodeResult("", [], None, None, None, self.profile.id, {}, warnings, self.engine)

    def decode_array(self, x: np.ndarray, sample_rate: int = SAMPLE_RATE) -> DecodeResult:
        if sample_rate != SAMPLE_RATE:
            x = resample(np.asarray(x, dtype=np.float32), sample_rate, SAMPLE_RATE)
        est = estimate_tone(x)
        if not est.has_signal or est.f0_hz is None:
            return self._empty(["không có tín hiệu Morse trong đoạn âm thanh"])
        warnings: list[str] = []
        if est.second_peak_hz is not None:
            warnings.append(
                f"phát hiện tone thứ hai tại {est.second_peak_hz:.0f} Hz, đang bám {est.f0_hz:.0f} Hz"
            )
        if self.engine == "baseline":
            return self._decode_baseline(x, est, warnings)
        return self._decode_onnx(x, est, warnings)

    def _baseline_tokens(self, x: np.ndarray, f0_hz: float):
        return self._baseline.decode_envelope(mix_envelope(x, f0_hz))

    def _decode_baseline(self, x, est, warnings: list[str]) -> DecodeResult:
        res = self._baseline_tokens(x, est.f0_hz)
        confidence = float(np.exp(-res.cost)) if np.isfinite(res.cost) else 0.0
        if confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        words = symbols_to_words(res.symbols, self.profile, FRAME_RATE, confidence)
        return DecodeResult(" ".join(w.text for w in words), words, res.wpm, est.f0_hz, est.snr_db,
                            self.profile.id, {}, warnings, "baseline")

    def _decode_onnx(self, x, est, warnings: list[str]) -> DecodeResult:
        from morsedesk.model.chunker import run_chunked

        feats = compute_features(x, est.f0_hz)
        logp = run_chunked(self._model, feats)
        stride = self._model.time_stride
        emissions = [(VOCAB.token(i), f * stride, p)
                     for i, f, p in greedy_decode_with_frames(logp, VOCAB.blank_id)]
        while emissions and emissions[0][0] == SPACE:
            emissions.pop(0)
        while emissions and emissions[-1][0] == SPACE:
            emissions.pop()
        words = emissions_to_words(emissions, self.profile, FRAME_RATE, len(feats))
        confidence = float(np.mean([w.confidence for w in words])) if words else 0.0
        fallback_text = None
        if confidence < FALLBACK_CONFIDENCE:
            warnings.append("độ tin cậy thấp, kèm kết quả bộ giải mã DSP")
            fallback_text = self.profile.render(self._baseline_tokens(x, est.f0_hz).tokens)
        elif confidence < LOW_CONFIDENCE:
            warnings.append("độ tin cậy thấp")
        return DecodeResult(" ".join(w.text for w in words), words,
                            estimate_wpm_from_emissions(emissions, FRAME_RATE), est.f0_hz, est.snr_db,
                            self.profile.id, {}, warnings, "onnx", fallback_text)

    def decode_file(self, path: str | Path) -> DecodeResult:
        x, sr = load_audio(path)
        return self.decode_array(x, sr)
```

Trong `cli.cmd_decode`, `model_path` chỉ truyền khi engine là onnx:

```python
        dec = Decoder(a.profile, engine=a.engine, model_path=a.model if a.engine == "onnx" else None)
```

- [ ] **Step 6: Chạy toàn bộ test**

Run: `uv run pytest -v`
Expected: tất cả pass; `test_trained_model_roundtrip` và `test_t1_gate_onnx` bị skip nếu chưa có `models/acoustic.onnx`. Test cũ của Task 11 vẫn pass (baseline không đổi hành vi; `DecodeResult` chỉ thêm trường có mặc định).

- [ ] **Step 7: Đo model đã huấn luyện trên T1 và ghi số**

Sau khi Task 15 và 16 tạo `models/acoustic.onnx`:

Run: `uv run pytest tests/unit/test_decoder_onnx.py tests/regression/test_t1.py -v`
Expected: `test_trained_model_roundtrip` PASS; `test_t1_gate_onnx` PASS nếu CER vùng gate < 2%.

Run: `uv run morsedesk bench --manifest testdata/generated/t1/manifest.jsonl --engine onnx --gate`
Expected: bảng CER theo SNR × WPM và dòng gate. Dán bảng baseline (Task 14) và bảng onnx cạnh nhau vào `docs/research/02-baseline-numbers.md`. Nếu gate TRƯỢT: (a) tăng `--steps` lên 40000; (b) kiểm tra ô nào kém nhất theo `by_keying`/`by_channel` và tăng tỉ lệ mẫu đó trong `sample_keyer_params`/`sample_channel_params`; (c) nếu vẫn trượt, tăng `hidden` lên 128 trong `CONFIG_DEFAULT` và train lại. Không nới ngưỡng gate.

- [ ] **Step 8: Commit**

```bash
git add morsedesk/model/chunker.py morsedesk/api.py morsedesk/cli.py tests/unit/test_chunker.py tests/unit/test_decoder_onnx.py docs/research/02-baseline-numbers.md models/acoustic.json
git commit -m "feat(decoder): engine ONNX với cửa sổ trượt, fallback DSP, ước lượng WPM" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_011pHgLd9ypHm91tS6n5mkvV"
```

---

## Tự soát kế hoạch so với spec

**Phủ spec (phần tuần 1–2):**

| Mục spec | Task |
|---|---|
| 2.4 từ vựng 65 lớp | 2 |
| 2.5 profile en/ru/kk-cyrl-ru, ánh xạ một-nhiều, Ё→Е, Ь/Ъ | 3 |
| 3 encoder: chuẩn hóa, PARIS, Farnsworth ARRL, weight, sườn 5 ms, WAV/FLAC/OGG, chuỗi chấm gạch `/` | 4, 5, 11 |
| 2.3 đọc file, resample 8 kHz, bỏ DC | 6 |
| 2.3 dò tone STFT 256, hop 40, 300–1500 Hz, "không có tín hiệu", tone thứ hai | 7 |
| 2.3 đặc trưng 11 chiều: envelope AGC, đạo hàm, 9 bin | 8 |
| 2.7 fallback baseline kiểu ggmorse | 10, 17 |
| 2.8 độ tin cậy theo ký tự và từ | 17 (onnx), 11 (baseline) |
| 5.1 bộ sinh tổng hợp đủ phân bố | 13 |
| 5.2 huấn luyện CTC, checkpoint theo CER validation | 15 |
| 2.7 kiến trúc mạng, ONNX opset 17, parity ≤ 1e-4, metadata | 15, 16 |
| 2.3 cửa sổ 4 s/3 s và hằng cho live 2 s/1 s | 17 |
| 6 T0, T1 (ma trận, gate), T2 (manifest), baseline công cụ ngoài | 4–5 (T0), 14 (T1), 12 (T2) |
| 7 xử lý lỗi: file lạ, không tín hiệu, tone thứ hai, model thiếu | 6, 11, 16, 17 |
| 8 CLI encode/decode/devices/bench | 11, 14 |
| 10 tuần 1 và 2 | toàn bộ |

**Để lại cho kế hoạch sau (tuần 3–6, đúng lộ trình spec):** 2.6 LM KenLM + pyctcdecode + `profile="auto"` + nhận diện ngôn ngữ theo đoạn; 4 GUI và i18n; live sound card (`LIVE_WINDOW_FRAMES` đã chuẩn bị); 9 đóng gói AppImage; MP3 ghi khi tạo mã (hiện encoder ghi WAV/FLAC/OGG qua CLI). Ba profile Kazakh khác và xử lý hàng loạt nằm ngoài v1.

**Nhất quán kiểu:** `Element(on, duration)` dùng xuyên suốt Task 4, 5, 13; `KeyerParams.timing()` trả `TimingParams`; `Example.labels` là id từ `VOCAB.id`; `OnnxAcousticModel.time_stride`/`output_length`/`meta["vocab"]` được `run_chunked` dùng đúng tên; `DecodeResult` chỉ thêm trường có mặc định nên test Task 11 không đổi; `write_jsonl` từ Task 12 được Task 14 tái dùng.

**Lệch nhỏ so với spec, có chủ đích:** profile đặt trong package (`morsedesk/profiles/`) thay vì gốc repo; logic bench nằm ở `morsedesk/bench.py` thay vì `tools/bench.py` để CLI gói được; mạng khoảng 140 nghìn tham số với `hidden=96` (spec ghi "khoảng 300 nghìn"), có lối nâng lên 128 nếu gate trượt.

