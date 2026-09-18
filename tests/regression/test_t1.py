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
