"""Độ tin cậy của một từ -> "trên bộ đo, từ ở mức này đúng khoảng X %".

Bảng ĐO bằng `tools/calibrate_confidence.py` (giải lại T4 bản ghi thật, dev-OOV và 54 bản tin 2
phút, ở chế độ file và chế độ nghe, rồi so từng từ với đáp án) và lưu ở data/. Không có bảng (bản
dựng thiếu file) thì tooltip chỉ bỏ dòng phần trăm — không bịa con số.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CALIBRATION_PATH = Path(__file__).resolve().parent / "data" / "confidence_calibration.json"
MIN_WORDS = 30          # khoảng có ít từ hơn thì con số quá nhiễu để nói ra


@lru_cache(maxsize=4)
def _table(mode: str, path: str = str(CALIBRATION_PATH)) -> tuple[tuple[float, float, float], ...]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    rows = []
    for b in data.get(mode, []):
        if b.get("accuracy") is not None and b.get("n", 0) >= MIN_WORDS:
            rows.append((float(b["min"]), float(b["max"]), float(b["accuracy"])))
    return tuple(rows)


def expected_accuracy(confidence: float, live: bool = False) -> float | None:
    """Tỉ lệ từ đúng (0..1) đo được ở khoảng tin cậy chứa `confidence`; None nếu chưa đo."""
    for lo, hi, acc in _table("live" if live else "file"):
        if lo <= confidence < hi or (hi >= 1.0 and confidence >= lo):
            return acc
    return None
