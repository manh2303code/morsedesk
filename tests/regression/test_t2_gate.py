"""Cổng chất lượng trên bản ghi THẬT (CP-02).

Bộ T2 nằm ở `testdata/private/` (gitignored) nên test tự bỏ qua khi máy chưa tải; dựng bằng
`uv run python tools/fetch_t2.py page --source arrl --profile en --index-url
https://www.arrl.org/code-practice-files` rồi `... build`.

Ngưỡng đặt theo số đo ngày 22/09 (engine `onnx`, 180 giây đầu mỗi bản, trung bình 4,0 %) cộng
biên độ, để bắt hồi quy chứ không phải để ép tiến bộ.
"""

import json
from pathlib import Path

import pytest

from morsedesk.api import Decoder
from morsedesk.audio.io import load_audio
from morsedesk.metrics import cer

MANIFEST = Path("testdata/private/t2/manifest.jsonl")
SECONDS = 180
MAX_MEAN_CER = 0.08          # đo được 4,0 %; gấp đôi làm biên
MAX_SINGLE_CER = 0.25        # bản 5 WPM đo 14,1 % là ca xấu nhất


def arrl_rows() -> list[dict]:
    if not MANIFEST.is_file():
        pytest.skip("chưa có bộ T2; xem docstring")
    rows = [json.loads(ln) for ln in MANIFEST.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rows = [r for r in rows if r.get("source") == "arrl" and Path(r["path"]).is_file()]
    if not rows:
        pytest.skip("bộ T2 chưa có bản ghi ARRL nào")
    return rows


@pytest.mark.gate
def test_real_recordings_stay_under_the_measured_level():
    if not Path("models/acoustic.onnx").is_file():
        pytest.skip("cần models/acoustic.onnx")
    import soundfile as sf

    dec = Decoder("en", engine="onnx")
    scores: dict[str, float] = {}
    for r in arrl_rows():
        x, sr = load_audio(Path(r["path"]))
        total = sf.info(r["path"]).duration
        ref = r["text"][: max(1, int(len(r["text"]) * SECONDS / total))]
        scores[Path(r["path"]).stem] = cer(ref, dec.decode_array(x[: SECONDS * 8000], sr).text)
    mean = sum(scores.values()) / len(scores)
    worst = max(scores, key=scores.get)
    assert mean <= MAX_MEAN_CER, (mean, scores)
    assert scores[worst] <= MAX_SINGLE_CER, (worst, scores[worst])
