"""Kiểm tra model và LM trước khi mở cửa sổ (spec gốc §7: thiếu thì fail ngay)."""

from __future__ import annotations

from pathlib import Path

from morsedesk.api import DEFAULT_MODEL_PATH
from morsedesk.lm.profile import list_profiles, load_profile
from morsedesk.lm.store import default_lm_dir, lm_file_for


def check_models(model_path: Path | None, lm_dir: Path | None, engine: str = "onnx") -> list[Path]:
    """Danh sách file thiếu: ONNX + metadata (nếu engine onnx) rồi các .bin LM theo thứ tự profile."""
    missing: list[Path] = []
    # is_file() chứ không phải exists(): một thư mục tên `acoustic.onnx` từng lọt qua kiểm
    # tra, cửa sổ mở ra rồi mới chết ở lần giải mã đầu.
    if engine == "onnx":
        onnx = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        for p in (onnx, onnx.with_suffix(".json")):
            if not p.is_file():
                missing.append(p)
    lm_root = Path(lm_dir) if lm_dir else default_lm_dir()
    for pid in list_profiles():
        p = lm_file_for(load_profile(pid), lm_root)
        if not p.is_file():
            missing.append(p)
    return missing


def missing_models_message(missing: list[Path]) -> str:
    lines = ["Missing model files:"] + [f"  {p}" for p in missing] + [
        "",
        "Export the acoustic model: uv run python tools/export_onnx.py --checkpoint runs/<run>/best.pt --out models/acoustic.onnx",
        "Build the language models: see README (fetch_corpus, normalize_corpus, build_lm.sh, arpa_to_bin) or tools/train_small_lm.py",
        "Or start with --model/--lm-dir pointing to existing files.",
    ]
    return "\n".join(lines)
