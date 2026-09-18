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
