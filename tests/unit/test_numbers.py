"""Điện số (morsedesk/numbers.py): số viết tắt và nhóm độ dài cố định, CHỈ trong ngữ cảnh điện số.

Bộ đo thật: trạm số M01/M12/M14 (tools/real_numbers_eval.py, testdata/private/t5) — trước khi có
module này app sai 25 % chữ số, 42 % nhóm đúng; sau 18 % / 69 % (27/09).
"""

from __future__ import annotations

from morsedesk.api import Word, numbers_words
from morsedesk.lm.profile import load_profile
from morsedesk.numbers import analyze, letters_of, normalize_groups

EN = load_profile("en")
RU = load_profile("ru")


def norm(text: str, profile=EN) -> str:
    groups = [letters_of(g) for g in text.split()]
    out, _, _ = normalize_groups(groups, profile)
    return " ".join("".join(g) for g in out)


def test_cut_zero_in_number_station_traffic():
    """Trạm số M12 đánh 0 bằng một gạch dài (mẫu T): `153T4` phải là `15304`."""
    assert norm("284 39 284 39 74699 61769 33272 153T4 4845T 7T923 TT32T 92994") == \
        "284 39 284 39 74699 61769 33272 15304 48450 70923 00320 92994"


def test_header_count_with_cut_zero():
    assert norm("379 379 3T 3T = = 75675 75675 84758 84758 93849") == \
        "379 379 30 30 = = 75675 75675 84758 84758 93849"


def test_full_contest_cut_set():
    """Bộ viết tắt thi đấu: 1=A 2=U 3=V 5=E 7=B 8=D 9=N 0=T (4, 6 giữ nguyên)."""
    assert norm("12345 AUV4E 6BDNT 67890 11111 22222") == "12345 12345 67890 67890 11111 22222"


def test_cyrillic_cut_numbers_by_pattern():
    """Làm theo MẪU: Т Н А Nga cũng là `-` `-.` `.-`."""
    assert norm("74699 61769 153Т4 9Н1А2 33272", RU) == "74699 61769 15304 99112 33272"


def test_plain_text_and_callsigns_untouched():
    for text in ("CQ CQ DE UA9AB UA9AB K", "UR RST 599 5NN QTH MOSCOW", "TNX FER CALL 73 ES GL",
                 "UN7ABC DE R9T 5NN 001 TU"):
        assert norm(text) == " ".join(text.split()), text


def test_mixed_code_groups_untouched():
    """Đề thi SRR: nhóm chữ-số ngẫu nhiên; nhóm `Д088А` toàn chữ viết tắt được nhưng bản tin là nhóm mã."""
    srr = "1ЬБОУ 7Д32Е К2Л6Ь ГДСУ7 Б3ПОК Д9ЫД5 ДНЕ9Ь ПЗЩБ7 Д088А ВЗКБС 72А0Д ЖУХО8"
    assert not analyze([letters_of(g) for g in srr.split()], RU).numeric
    assert norm(srr, RU) == srr


def test_formatted_numbers_keep_their_letters():
    """Số có định dạng: `N`/`E` là Bắc/Đông, `T=` là chữ thật, `5NN` và lưới `EB84` không phải nhóm
    số cố định — chỉ nhóm TOÀN chữ số + chữ viết tắt mới được đổi (đo 27/09, kind=formatted)."""
    for text in ("42.6735N/512.9889E 38.5118N/756.4601E 7431-7181 T=12 (186) 17.345 MHZ",
                 "UN7ABC 5NN 123 EB84 5432Z 2024-05-17 10:45Z 5NN 042 DL3XYZ 5NN 777",
                 "NR 12345 QTC 12/345 NR 67890 QTC 7/123 T=05 T=72"):
        assert norm(text) == text, text
    # nhưng 0 = T vẫn đổi trong nhóm số thường, cả khi độ dài nhóm không cố định
    assert norm("NR 12345 QTC 12/345 NR 6789T 1T3 T=05") == "NR 12345 QTC 12/345 NR 67890 103 T=05"


def test_split_fragments_are_rejoined_between_full_groups():
    assert norm("54817 56370 4078 8 7 0729 84102 09384") == "54817 56370 40788 70729 84102 09384"
    assert norm("11998 67045 05 627 12611 80949 48057") == "11998 67045 05627 12611 80949 48057"


def test_fragments_not_rejoined_at_the_edges_or_when_they_do_not_tile():
    # đầu điện: 3 + 2 = 5 nhưng không nằm giữa hai nhóm đủ
    assert norm("284 39 284 39 74699 61769 33272 15304").startswith("284 39 284 39 ")
    # 3 + 3 không ghép khít 5
    assert norm("74699 61769 123 456 33272 15304 48450") == "74699 61769 123 456 33272 15304 48450"


def test_glued_groups_are_split():
    """Trạm đánh các nhóm sát nhau: khối 15 chữ số trong điện nhóm 5 -> ba nhóm."""
    assert norm("86135 81289 94988 015547591635022 22674 10345") == \
        "86135 81289 94988 01554 75916 35022 22674 10345"


def test_numbers_words_keep_timing():
    words = [Word(t, i * 5.0, i * 5.0 + 4.0, 0.9, [(c, i * 5.0 + k * 0.8) for k, c in enumerate(t)])
             for i, t in enumerate("74699 61769 153T4 4845T 33272".split())]
    out = numbers_words(words, EN)
    assert [w.text for w in out] == ["74699", "61769", "15304", "48450", "33272"]
    assert out[2].start_s == words[2].start_s and out[2].chars[3] == ("0", words[2].chars[3][1])
    assert numbers_words([Word("CQ", 0, 1, 0.9), Word("DE", 1, 2, 0.9)], EN) is None


def test_dsp_must_keep_the_group_structure():
    """Trạm M12 đánh nhóm sát nhau: DSP dính cả bản tin thành một khối (timing vẫn khớp lưới) — khi đó
    phải lấy kết quả mô hình."""
    from morsedesk.dsp.selection import dsp_keeps_words

    model = "86135 81289 94988 01554 75916 35022 05891 22674"
    assert not dsp_keeps_words("8613581289949880155475916350220589122674", model)
    assert dsp_keeps_words("86135 81289 94988 01554 75916 35022 05891 22674", model)
    assert dsp_keeps_words("CQ DE", "CQ DE K")                   # quá ít từ để phán xét


def test_auto_long_audio_does_not_split_groups():
    """Auto trên âm thanh > 30 s: trước 27/09 lưới bị cắt đều mỗi 30 s rồi ghép văn bản các đoạn, nhóm
    số nằm vắt qua chỗ cắt bị tách đôi. Nay văn bản giải cả lưới một lượt, giống hệt khi biết ngôn ngữ."""
    import pytest

    from morsedesk.api import DEFAULT_MODEL_PATH, Decoder, Encoder

    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip("cần models/acoustic.onnx")
    text = " ".join(f"{(k * 7919) % 100000:05d}" for k in range(1, 15))
    x = Encoder("en").to_audio(text, wpm=14, snr_db=15, seed=5)
    assert len(x) / 8000 > 45
    auto = Decoder("auto", engine="onnx", fallback=False).decode_array(x)
    en = Decoder("en", engine="onnx", fallback=False).decode_array(x)
    assert auto.text == en.text == text


def test_number_traffic_is_read_without_the_text_lm(monkeypatch, tmp_path):
    """LM văn bản kéo `(` mà mô hình đã nghe về `9` (đo 27/09: 21/202 nhóm `(…)` sai với LM, 4/202 khi
    đọc thẳng từ mô hình). Trong điện số văn bản lấy từ mô hình; LM chỉ còn chọn ngôn ngữ."""
    import numpy as np

    from morsedesk.api import Decoder, Encoder
    from morsedesk.encode.text import text_to_tokens
    from morsedesk.lm.alphabet import LMAlphabet
    from morsedesk.lm.beam import BeamParams, beam_search
    from morsedesk.lm.ngram import save_bin, train_small
    from morsedesk.model.vocab import VOCAB
    from tests.helpers import lattice_from_tokens
    from tests.unit.test_api_lm import FakeAcousticModel

    lm = train_small(["99 999 9 99 9999 99", "9 99 999 12345 67890"] * 20, LMAlphabet.for_profile(EN), order=4)
    save_bin(lm, tmp_path / EN.lm.split("/")[-1])
    text = "12345 67890 (737) 55512 44321"
    lat = lattice_from_tokens(text_to_tokens(text, EN), gap=8)
    paren, nine = VOCAB.id("-.--."), VOCAB.id("----.")
    f = int(np.argmax(lat[:, paren]))
    row = np.full(lat.shape[1], 1e-4)
    row[paren], row[nine] = 0.5, 0.45
    lat[f] = np.log(row / row.sum())
    # tiền đề: beam + LM đọc `(` thành `9`
    assert "9737" in "".join(beam_search(lat, EN, lm, BeamParams())[0].letters)
    monkeypatch.setattr(Decoder, "_log_probs", lambda self, x, f0, *a, **kw: (lat, 2 * len(lat)))
    dec = Decoder("en", engine="onnx", acoustic_model=FakeAcousticModel(), lm_dir=tmp_path,
                  fallback=False)
    assert dec.decode_array(Encoder("en").to_audio(text, wpm=20)).text == text
