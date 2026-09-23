"""Bộ T2 bản ghi thật: tải, dựng manifest, và cổng chất lượng theo nguồn (CP-02, CP-13, CP-03).

T1 do chính bảng mã của mình sinh ra, nên mọi số đo trên nó đều có thể đang tự khen. T2 là bản
ghi thật (ARRL W1AW, Wikimedia Commons, file tự thu) kèm đáp án, cộng phần tổng hợp bù chỗ
trống cho tiếng Nga và Kazakh — phần tổng hợp được đánh dấu `synthetic` để không trộn lẫn.
"""

from pathlib import Path

from morsedesk import bench
from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio
from tools import fetch_t2
from tools.make_t2_manifest import build_manifest, write_jsonl

INDEX_HTML = """
<html><body>
<a href="/files/morse/260303_5WPM.mp3">5 WPM</a>
<a href="/files/morse/260303_5WPM.txt">text</a>
<a href="/files/morse/260303_20WPM.mp3">20 WPM</a>
<a href="/files/morse/260303_20WPM.txt">text</a>
<a href="/files/morse/no_text_40WPM.mp3">40 WPM</a>
<a href="https://example.org/other.html">khác</a>
</body></html>
"""


def test_discover_pairs_matches_audio_with_same_stem_text():
    pairs = fetch_t2.discover_pairs(INDEX_HTML, "https://www.arrl.org/code-practice-files")
    assert len(pairs) == 3
    assert pairs[0] == ("https://www.arrl.org/files/morse/260303_5WPM.mp3",
                        "https://www.arrl.org/files/morse/260303_5WPM.txt")
    assert pairs[2][1] is None


def test_build_manifest_records_license(tmp_path):
    save_audio(tmp_path / "a_20WPM.wav", Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    (tmp_path / "a_20WPM.txt").write_text("CQ DE K", encoding="utf-8")
    rows = build_manifest(tmp_path, source="arrl", profile_id="en", license_id="ARRL nội bộ")
    assert rows[0]["license"] == "ARRL nội bộ"


def test_fetch_t2_local_then_build(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    save_audio(src / "qso_18WPM.wav", Encoder("en").to_audio("CQ DE K", wpm=18), 8000)
    (src / "qso_18WPM.txt").write_text("CQ DE K", encoding="utf-8")
    root = tmp_path / "t2"
    assert fetch_t2.main(["--root", str(root), "local", "--source", "sraa", "--profile", "en",
                          "--dir", str(src)]) == 0
    assert (root / "sraa" / "_meta.json").exists()
    assert fetch_t2.main(["--root", str(root), "build"]) == 0
    rows = bench.load_rows(root / "manifest.jsonl")
    assert len(rows) == 1
    assert rows[0]["source"] == "sraa" and rows[0]["wpm"] == 18.0 and rows[0]["text"] == "CQ DE K"
    assert rows[0]["license"] and Path(rows[0]["path"]).exists()
    assert rows[0]["synthetic"] is False


def test_fetch_t2_synth_falls_back_to_encoder(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_t2.shutil, "which", lambda name: None)   # không có ebook2cw
    root = tmp_path / "t2"
    assert fetch_t2.main(["--root", str(root), "synth", "--source", "ebook2cw", "--profile", "ru",
                          "--n", "2", "--seed", "3"]) == 0
    wavs = sorted((root / "ebook2cw").glob("*.wav"))
    assert len(wavs) == 2 and all(w.with_suffix(".txt").exists() for w in wavs)
    assert fetch_t2.main(["--root", str(root), "build"]) == 0
    rows = bench.load_rows(root / "manifest.jsonl")
    assert len(rows) == 2 and all(r["profile"] == "ru" and r["synthetic"] for r in rows)
    assert all(r["wpm"] is not None for r in rows)


def test_source_gate_uses_per_source_threshold():
    rows = [
        {"source": "arrl", "cer": 0.01, "wer": 0.02},
        {"source": "arrl", "cer": 0.01, "wer": 0.02},
        {"source": "sraa", "cer": 0.15, "wer": 0.30},
    ]
    g = bench.source_gate(rows)
    assert g["arrl"]["n"] == 2 and g["arrl"]["ok"] and g["arrl"]["max_cer"] == 0.02
    assert not g["sraa"]["ok"] and g["sraa"]["max_cer"] == 0.10
    assert bench.source_gate(rows, {"sraa": 0.2})["sraa"]["ok"]


def test_bench_run_reports_by_source_on_t2_shaped_manifest(tmp_path, capsys):
    src = tmp_path / "raw"
    src.mkdir()
    save_audio(src / "a_20WPM.wav", Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    (src / "a_20WPM.txt").write_text("CQ DE K", encoding="utf-8")
    manifest = tmp_path / "m.jsonl"
    write_jsonl(build_manifest(src, source="arrl", profile_id="en", license_id="x"), manifest)
    summary, ok = bench.run(manifest, "baseline", None, tmp_path / "r", None, False, 0.02,
                            t2_gate=True)
    assert summary["by_source"]["arrl"]["n"] == 1
    assert summary["source_gate"]["arrl"]["max_cer"] == 0.02
    assert "T2 arrl" in capsys.readouterr().out
    assert isinstance(ok, bool)


ARRL_HTML = """
<html><body>
<a href="/files/file/Morse/260303_20WPM.mp3">20 WPM</a>
<a href="/files/file/Morse/260303_20.txt">text</a>
<a href="/files/file/Morse/260303_5WPM.mp3">5 WPM</a>
<a href="/files/file/Morse/260303_5.txt">text</a>
</body></html>
"""


def test_discover_pairs_matches_arrl_naming_without_wpm_suffix():
    """Trang thật của ARRL đặt tên audio `..._20WPM.mp3` nhưng text `..._20.txt`.

    Khớp stem y hệt thì bỏ sót toàn bộ 11 cặp — đo được khi chạy thật ngày 22/09.
    """
    pairs = fetch_t2.discover_pairs(ARRL_HTML, "https://www.arrl.org/code-practice-files")
    assert len(pairs) == 2
    assert all(t is not None for _, t in pairs)
    assert pairs[0] == ("https://www.arrl.org/files/file/Morse/260303_20WPM.mp3",
                        "https://www.arrl.org/files/file/Morse/260303_20.txt")


def test_exact_stem_still_wins_over_normalised_match():
    html = """
    <a href="/f/x_20WPM.mp3">a</a>
    <a href="/f/x_20WPM.txt">đúng</a>
    <a href="/f/x_20.txt">suy ra</a>
    """
    pairs = fetch_t2.discover_pairs(html, "https://e.org/i")
    assert pairs[0][1] == "https://e.org/f/x_20WPM.txt"


def test_kazakh_reference_keeps_the_letters_the_decoder_is_expected_to_restore():
    """Đáp án Kazakh phải là СӘЛЕМ, không phải bản viết phẳng САЛЕМ.

    Ә và А cùng mã `.-`, nên `text` (đi qua mẫu chấm gạch) luôn phẳng. Model có LM trả đúng СӘЛЕМ;
    chấm theo bản phẳng từng làm CER Kazakh của T2 là 9,34 % thay vì 4,08 %.
    """
    from tools.make_t2_manifest import clean_reference, original_reference

    raw = "Рахмет, сәлем! ҚАЗАҚСТАН <SK>"
    assert clean_reference(raw, "kk-cyrl-ru") == "РАХМЕТ, САЛЕМ! КАЗАКСТАН <SK>"
    assert original_reference(raw, "kk-cyrl-ru") == "РАХМЕТ, СӘЛЕМ! ҚАЗАҚСТАН <SK>"
    # Tiếng Anh: hai bản phải trùng khít, kể cả prosign, để số ARRL không đổi.
    en = "cq de w1aw <AR> test 5nn"
    assert original_reference(en, "en") == clean_reference(en, "en")


def test_manifest_rows_carry_text_original(tmp_path):
    (tmp_path / "a_12WPM.wav").write_bytes(b"")
    (tmp_path / "a_12WPM.txt").write_text("СӘЛЕМ ӘЛЕМ", encoding="utf-8")
    row = build_manifest(tmp_path, "synth", "kk-cyrl-ru")[0]
    assert row["text"] == "САЛЕМ АЛЕМ" and row["text_original"] == "СӘЛЕМ ӘЛЕМ"
    assert bench.reference_text(row, "onnx", lm=True) == "СӘЛЕМ ӘЛЕМ"
