import json

import pytest

from morsedesk import bench
from morsedesk.api import Decoder, Encoder, hypothesis_to_words
from morsedesk.audio.io import save_audio
from morsedesk.cli import build_parser, main
from morsedesk.encode.text import text_to_tokens
from morsedesk.lm.alphabet import LMAlphabet
from morsedesk.lm.beam import beam_search
from morsedesk.lm.ngram import save_bin, train_small
from morsedesk.lm.profile import load_profile
from morsedesk.model.vocab import VOCAB
from tests.helpers import lattice_from_tokens
from tools.make_t2_manifest import write_jsonl

P = {pid: load_profile(pid) for pid in ("en", "ru", "kk-cyrl-ru")}
CORPUS = {
    "en": ["CQ CQ DE K", "THE QUICK BROWN FOX", "HELLO WORLD", "CQ DE K"],
    "ru": ["ПРИВЕТ МИР", "ВСЕМ ПРИВЕТ", "ДОБРОЕ УТРО"],
    "kk-cyrl-ru": ["СӘЛЕМ ӘЛЕМ", "РАХМЕТ", "ҚАЙЫРЛЫ ТАҢ"],
}


class FakeAcousticModel:
    time_stride = 2
    meta = {"vocab": VOCAB.tokens}

    def output_length(self, t):
        return (t - 1) // 2 + 1

    def __call__(self, feats):
        raise AssertionError("_log_probs phải được thay trong test")


@pytest.fixture(scope="module")
def lm_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("lm")
    for pid, lines in CORPUS.items():
        lm = train_small(lines, LMAlphabet.for_profile(P[pid]), order=4)
        save_bin(lm, d / P[pid].lm.split("/")[-1])
    return d


def patch_lattice(monkeypatch, text, pid):
    lat = lattice_from_tokens(text_to_tokens(text, P[pid]), gap=8)
    monkeypatch.setattr(Decoder, "_log_probs", lambda self, x, f0: (lat, 2 * len(lat)))
    return lat


def test_auto_requires_lm_files_and_rejects_no_lm(tmp_path):
    with pytest.raises(FileNotFoundError, match="en.bin"):
        Decoder("auto", lm_dir=tmp_path)
    with pytest.raises(ValueError, match="auto"):
        Decoder("auto", lm=False)


def test_forced_profile_baseline_needs_no_lm(tmp_path):
    r = Decoder("en", lm_dir=tmp_path).decode_array(Encoder("en").to_audio("CQ DE K", wpm=20))
    assert r.text == "CQ DE K" and r.language == "en" and r.language_scores == {}


def test_baseline_auto_picks_profile_by_lm(lm_dir):
    x = Encoder("ru").to_audio("ПРИВЕТ МИР", wpm=20)
    r = Decoder("auto", engine="baseline", lm_dir=lm_dir).decode_array(x)
    assert r.language == "ru" and r.text == "ПРИВЕТ МИР"
    assert set(r.language_scores) == set(P) and r.language_scores["ru"] == max(r.language_scores.values())


def test_baseline_auto_recovers_kazakh_letters(lm_dir):
    """Baseline + auto đi qua detect_tokens: beam chọn được Ә nên kk không còn đổ về ru."""
    x = Encoder("kk-cyrl-ru").to_audio("СӘЛЕМ ӘЛЕМ", wpm=20)
    r = Decoder("auto", engine="baseline", lm_dir=lm_dir).decode_array(x)
    assert r.language == "kk-cyrl-ru" and r.text == "СӘЛЕМ ӘЛЕМ"
    assert r.language_scores["kk-cyrl-ru"] == max(r.language_scores.values())
    assert [w.text for w in r.words] == ["СӘЛЕМ", "ӘЛЕМ"]


def test_lm_available(lm_dir, tmp_path):
    assert Decoder.lm_available(lm_dir) is True
    assert Decoder.lm_available(tmp_path / "trống") is False


def test_onnx_beam_lm_recovers_kazakh_letters(monkeypatch, lm_dir):
    patch_lattice(monkeypatch, "СӘЛЕМ ӘЛЕМ", "kk-cyrl-ru")
    x = Encoder("kk-cyrl-ru").to_audio("СӘЛЕМ ӘЛЕМ", wpm=20)
    dec = Decoder("kk-cyrl-ru", engine="onnx", acoustic_model=FakeAcousticModel(), lm_dir=lm_dir)
    r = dec.decode_array(x)
    assert r.text == "СӘЛЕМ ӘЛЕМ" and r.engine == "onnx" and r.language == "kk-cyrl-ru"
    assert [w.text for w in r.words] == ["СӘЛЕМ", "ӘЛЕМ"]
    assert all(w.confidence > 0.8 for w in r.words) and r.words[0].end_s <= r.words[1].start_s
    assert r.fallback_text is None and r.language_scores == {}
    greedy = Decoder("kk-cyrl-ru", engine="onnx", acoustic_model=FakeAcousticModel(), lm=False, lm_dir=lm_dir)
    assert greedy.decode_array(x).text == "САЛЕМ АЛЕМ"


def test_onnx_auto_detects_language(monkeypatch, lm_dir):
    patch_lattice(monkeypatch, "ПРИВЕТ МИР", "ru")
    x = Encoder("ru").to_audio("ПРИВЕТ МИР", wpm=20)
    r = Decoder("auto", engine="onnx", acoustic_model=FakeAcousticModel(), lm_dir=lm_dir, beam=8).decode_array(x)
    assert r.language == "ru" and r.text == "ПРИВЕТ МИР"
    assert set(r.language_scores) == set(P)
    assert r.wpm is not None
    d = json.loads(r.to_json())
    assert d["language"] == "ru"


def test_hypothesis_to_words_timing_and_offset():
    hyp = beam_search(lattice_from_tokens(text_to_tokens("CQ DE", P["en"]), gap=4, lead=0), P["en"], None)[0]
    words = hypothesis_to_words(hyp, frame_rate=200, stride=2, end_frame=100, offset=10)
    assert [w.text for w in words] == ["CQ", "DE"]
    assert words[0].start_s == (10 + 0) * 2 / 200                 # token đầu ở khung 0 của đoạn
    assert words[1].end_s == 100 / 200


def test_cli_defaults_and_flags(tmp_path, lm_dir, capsys):
    a = build_parser().parse_args(["decode", "x.wav"])
    assert a.profile == "auto" and a.beam == 64 and not a.no_lm and a.lm_dir is None
    b = build_parser().parse_args(["bench", "--manifest", "m.jsonl", "--profile-override", "auto", "--no-lm"])
    assert b.profile_override == "auto" and b.no_lm
    wav = tmp_path / "ru.wav"
    save_audio(wav, Encoder("ru").to_audio("ПРИВЕТ МИР", wpm=20), 8000)
    assert main(["decode", str(wav), "--lm-dir", str(lm_dir)]) == 0
    assert capsys.readouterr().out.strip() == "ПРИВЕТ МИР"
    assert main(["decode", str(wav), "--no-lm"]) == 2                  # auto + --no-lm
    assert "lỗi" in capsys.readouterr().err
    assert main(["decode", str(wav), "--lm-dir", str(tmp_path / "none")]) == 2   # thiếu LM
    assert "en.bin" in capsys.readouterr().err


def test_bench_language_acc_and_reference_text(tmp_path, lm_dir):
    rows = []
    for i, (text, pid) in enumerate((("CQ DE K", "en"), ("ПРИВЕТ МИР", "ru"), ("РАХМЕТ", "kk-cyrl-ru"))):
        wav = tmp_path / f"{i}.wav"
        save_audio(wav, Encoder(pid).to_audio(text, wpm=20), 8000)
        rows.append({"path": str(wav), "text": text, "text_original": text, "profile": pid,
                     "snr": 20.0, "wpm": 20.0, "keying": "machine", "channel": "clean",
                     "channel_actual": "clean", "seed": i})
    manifest = tmp_path / "m.jsonl"
    write_jsonl(rows, manifest)
    kk_row = {"text": "САЛЕМ", "text_original": "СӘЛЕМ", "profile": "kk-cyrl-ru"}
    assert bench.reference_text(kk_row, "baseline", True) == "САЛЕМ"
    assert bench.reference_text(kk_row, "onnx", True) == "СӘЛЕМ"
    assert bench.reference_text(kk_row, "onnx", False) == "САЛЕМ"
    assert bench.reference_text({"text": "A", "profile": "en"}, "onnx", True) == "A"
    res = bench.evaluate(bench.load_rows(manifest), engine="baseline", profile_override="auto", lm_dir=lm_dir)
    assert [r["language"] for r in res] == ["en", "ru", "kk-cyrl-ru"]
    assert all(r["language_correct"] for r in res) and all(r["ref"] == r["text"] for r in res)
    assert bench.language_accuracy(res) == 1.0
    forced = bench.evaluate(bench.load_rows(manifest), engine="baseline", lm_dir=lm_dir)
    assert all(r["language_correct"] is None for r in forced) and bench.language_accuracy(forced) is None
    summary, ok = bench.run(manifest, "baseline", None, tmp_path / "r", None, False, 0.02,
                            profile_override="auto", lm_dir=lm_dir)
    assert summary["language_acc"] == 1.0 and summary["profile_override"] == "auto" and ok


def test_bench_cli_reports_argument_error(tmp_path, capsys):
    """'auto' + --no-lm -> ValueError trong Decoder: cmd_bench in 'lỗi: ...' và trả 2, không traceback."""
    wav = tmp_path / "0.wav"
    save_audio(wav, Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    manifest = tmp_path / "m.jsonl"
    write_jsonl([{"path": str(wav), "text": "CQ DE K", "profile": "en", "snr": 20.0, "wpm": 20.0,
                  "keying": "machine", "channel": "clean", "channel_actual": "clean", "seed": 0}],
                manifest)
    assert main(["bench", "--manifest", str(manifest), "--out-dir", str(tmp_path / "r"),
                 "--profile-override", "auto", "--no-lm"]) == 2
    assert "lỗi" in capsys.readouterr().err
    assert main(["bench", "--manifest", str(manifest), "--out-dir", str(tmp_path / "r"),
                 "--profile-override", "auto", "--lm-dir", str(tmp_path / "trống")]) == 2
    assert "en.bin" in capsys.readouterr().err


def test_auto_reports_empty_language_when_nothing_decoded(monkeypatch, lm_dir):
    """Lưới toàn blank -> không segment nào có profile_id -> language rỗng, language_scores rỗng."""
    lat = lattice_from_tokens([], gap=0, lead=60)
    monkeypatch.setattr(Decoder, "_log_probs", lambda self, x, f0: (lat, 2 * 60))
    x = Encoder("en").to_audio("E", wpm=20)
    dec = Decoder("auto", engine="onnx", acoustic_model=FakeAcousticModel(), lm_dir=lm_dir, beam=4)
    r = dec.decode_array(x)
    assert r.text == "" and r.language == "" and r.language_scores == {}


def test_language_correct_none_without_profile(tmp_path, lm_dir):
    """Hàng manifest thiếu khóa 'profile' -> không rõ nhãn đúng -> language_correct None, không phải False."""
    wav = tmp_path / "0.wav"
    save_audio(wav, Encoder("en").to_audio("CQ DE K", wpm=20), 8000)
    rows = [{"path": str(wav), "text": "CQ DE K", "snr": 20.0, "wpm": 20.0,
             "keying": "machine", "channel": "clean", "channel_actual": "clean", "seed": 0}]
    manifest = tmp_path / "m.jsonl"
    write_jsonl(rows, manifest)
    res = bench.evaluate(bench.load_rows(manifest), engine="baseline", profile_override="auto", lm_dir=lm_dir)
    assert res[0]["language_correct"] is None
    assert bench.language_accuracy(res) is None
