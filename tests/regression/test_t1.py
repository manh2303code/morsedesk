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
    assert all("text_original" in r and r["text_original"] for r in rows)
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


@pytest.mark.gate
@pytest.mark.skipif(not Path("models/acoustic.onnx").exists(), reason="chưa có model ONNX (Task 17)")
def test_t1_gate_onnx():
    manifest = Path("testdata/generated/t1/manifest.jsonl")
    if not manifest.exists():
        pytest.skip("chạy: uv run python tools/make_t1.py")
    # gate greedy (lm=False); gate LM ở test_t1_lm_not_worse_than_greedy_and_language_acc
    results = bench.evaluate(
        bench.load_rows(manifest), engine="onnx", model_path=Path("models/acoustic.onnx"), lm=False
    )
    ok, mean_cer, n = bench.gate(results)
    assert ok, f"CER vùng gate = {mean_cer:.4f} trên {n} clip, ngưỡng 0.02"


LM_FILES = [Path("models/lm") / f for f in ("en.bin", "ru.bin", "kk.bin")]


@pytest.mark.gate
@pytest.mark.skipif(not Path("models/acoustic.onnx").exists() or not all(p.exists() for p in LM_FILES),
                    reason="cần models/acoustic.onnx và models/lm/{en,ru,kk}.bin")
def test_t1_lm_not_worse_than_greedy_and_language_acc():
    manifest = Path("testdata/generated/t1/manifest.jsonl")
    if not manifest.exists():
        pytest.skip("chạy: uv run python tools/make_t1.py")
    rows = bench.load_rows(manifest)
    model = Path("models/acoustic.onnx")
    greedy = bench.evaluate(rows, engine="onnx", model_path=model, lm=False)
    with_lm = bench.evaluate(rows, engine="onnx", model_path=model, lm=True)
    from morsedesk.metrics import cer as _cer

    for pid in ("en", "ru", "kk-cyrl-ru"):
        # cùng tham chiếu với LM: kk chấm greedy theo text_original (greedy không thể sinh Ә/Ғ/...)
        g_rows = [r for r in greedy if r.get("profile") == pid]
        g = sum(_cer(r.get("text_original") or r["text"], r["hyp"]) for r in g_rows) / len(g_rows)
        w = bench.aggregate(with_lm, "profile")[pid]["cer"]
        assert w <= g + 1e-9, (
            f"{pid}: LM {w:.4f} > greedy {g:.4f}"
            " (kk-cyrl-ru: LM được chấm theo text_original, tham chiếu khắt khe hơn)"
        )
    auto = bench.evaluate(rows, engine="onnx", model_path=model, profile_override="auto")
    acc = bench.language_accuracy(auto)
    assert acc is not None and acc >= 0.95, f"language_acc = {acc:.3f}"


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


def test_aggregate_sorts_numeric_keys():
    rows = [{"snr": s, "cer": 0.1, "wer": 0.2} for s in (10.0, 3.0, 0.0, 20.0)]
    assert list(bench.aggregate(rows, "snr").keys()) == ["0.0", "3.0", "10.0", "20.0"]


@pytest.mark.gate
@pytest.mark.skipif(not Path("models/deepcw/model.onnx").exists(),
                    reason="chưa có models/deepcw/model.onnx (tools/fetch_deepcw.py)")
def test_deepcw_engine_on_t1_en_subset():
    """Engine deepcw phải đạt lại mốc đo qua `Decoder` thật: CER <= 24 % trên 167 clip profile
    en của T1 v2 (lm=False; giá trị đo được 22,80 %, khớp mốc 22,86 % của
    docs/research/04-pretrained-baselines.md đo bằng tools/bench_pretrained.py).

    Trước khi sửa, đi qua `Decoder` cho 27,23 % vì cổng `estimate_tone()` trả "" cho 15/167 clip
    (SNR 0-3 dB, phần lớn kênh qsb) trước khi `DeepCwModel` kịp chạy. DeepCW nghe cả dải
    400-1200 Hz và không dùng ước lượng tone, nên cổng đó nay không áp cho engine này
    (`Decoder.decode_array`). Chi tiết: .superpowers/sdd/qa-task-2-report.md.
    """
    manifest = Path("testdata/generated/t1/manifest.jsonl")
    if not manifest.exists():
        pytest.skip("chạy: uv run python tools/make_t1.py")
    rows = [r for r in bench.load_rows(manifest) if r.get("profile") == "en"]
    results = bench.evaluate(rows, engine="deepcw", lm=False)
    mean = sum(r["cer"] for r in results) / len(results)
    assert mean <= 0.24, f"CER deepcw trên {len(results)} clip en = {mean:.4f}, mốc đo được 0.2280"
