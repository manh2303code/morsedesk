import json

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("onnxruntime")

from tools import make_t1  # noqa: E402
from tools.eval_run import evaluate_run, lm_ready, markdown_row, summarize  # noqa: E402
from tools.net_torch import CONFIG_DEFAULT, MorseNet  # noqa: E402


def test_evaluate_run_writes_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(make_t1, "SNR_GATE", [20.0])
    monkeypatch.setattr(make_t1, "WPM_GATE", [20.0])
    monkeypatch.setattr(make_t1, "KEYING", ("machine",))
    monkeypatch.setattr(make_t1, "CHANNELS", ("clean",))
    make_t1.generate_matrix(tmp_path / "t1", full=False, clips=2)
    run = tmp_path / "runs" / "x"
    run.mkdir(parents=True)
    torch.manual_seed(0)
    torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 7, "val_ter": 0.4,
                "config": dict(CONFIG_DEFAULT, feature_mode="window")}, run / "best.pt")
    s = evaluate_run(run, tmp_path / "t1" / "manifest.jsonl", name="x", with_lm=False, models_dir=tmp_path / "models")
    assert (tmp_path / "models" / "eval_x.onnx").exists() and (run / "t1_summary.json").exists()
    saved = json.loads((run / "t1_summary.json").read_text(encoding="utf-8"))
    assert saved["name"] == "x" and saved["train_step"] == 7 and saved["feature_mode"] == "window"
    assert saved["n_rows"] == 2 and saved["lm"] is None
    g = saved["greedy"]
    assert g["gate_cer"] >= 0.0 and g["n"] == 2                     # model chưa train: CER có thể > 100%
    assert set(g["by_profile"]) <= {"en", "ru", "kk-cyrl-ru"} and g["by_profile"]
    assert "SNR\\WPM" in g["pivot"]
    row = markdown_row(s)
    assert row.startswith("| x | 96 | window | 7 | 40.00% |") and row.count("|") == 9
    assert not lm_ready(tmp_path / "no-lm")
    assert summarize([])["n"] == 0
