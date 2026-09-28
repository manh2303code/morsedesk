"""Tầng cấu trúc điện văn mạng CW (morsedesk/traffic.py) — T7, 28/09: nhóm dính liền, lần đánh hỏng trước `?`,
số viết tắt, bảng Kirin, văn bản thường không bị đụng."""

from __future__ import annotations

from morsedesk.api import Word
from morsedesk.lm.profile import load_profile
from morsedesk.numbers import letters_of
from morsedesk.traffic import regroup, traffic_words

EN = load_profile("en")
RU = load_profile("ru")


def run(text: str, prof=EN) -> str:
    letters, spaces = [], []
    for wi, w in enumerate(text.split()):
        for k, c in enumerate(letters_of(w)):
            letters.append(c)
            spaces.append(k == 0 and wi > 0)
    pats = [prof.letter_to_pattern.get(c) or prof.prosign_to_pattern.get(c) for c in letters]
    rg = regroup(letters, pats, spaces)
    return "".join((" " if s and i else "") + c for i, (c, s) in enumerate(zip(rg.letters, rg.spaces, strict=True)))


def test_glued_groups_split_and_cut_numbers_expanded():
    """Đúng dạng lỗi của T7 file 1: `67A3TD3D6746` là ba nhóm `6713 0838 6746`. Mào đầu không bị đụng."""
    out = run("GYHM DE NJWY NR 015 CK 31 RMKS 8981 8836 = 67A3TD3D6746 7UU376DA3TND <AR>")
    assert out == "GYHM DE NJWY NR 015 CK 31 RMKS 8981 8836 = 6713 0838 6746 7223 7681 3098 <AR>"


def test_botched_group_before_query_stays_short():
    """`NAA3U7 ?` = nhóm 9113 rồi lần đánh hỏng `U7` báo bằng `?`: không kéo lệch các nhóm sau."""
    out = run("RMKS 1234 = 4A4D A437 NAA3U7 ? U736 U567 <AR>")
    assert out == "RMKS 1234 = 4148 1437 9113 U7 ? 2736 2567 <AR>"


def test_model_words_merged_when_they_tile_groups():
    """Mô hình tách sai chỗ (`76 7A3TT4U543`, `3AN D`): ghép rồi chia lại theo nhóm 4."""
    out = run("RMKS 1234 = 5620 76 7A3TT4U543 3AN D 1360 <AR>")
    assert out == "RMKS 1234 = 5620 7671 3004 2543 3198 1360 <AR>"


def test_trailing_fragment_kept_separate():
    """Mảnh ngắn mô hình đã tách riêng (trước `<AR>`) không bị nhét vào nhóm đủ."""
    out = run("RMKS 1234 = 3956 7 ? 7263 A <AR>")
    assert out == "RMKS 1234 = 3956 7 ? 7263 A <AR>"


def test_cyrillic_detected_by_pattern():
    """352 bị tự nhận là tiếng Nga: `РМКС` cùng mẫu với RMKS, `Д`/`Н`/`А`/`У` là số viết tắt theo mẫu."""
    out = run("РМКС 6229 = 3АНД 1360 НУАД1839 3016", RU)
    assert out == "РМКС 6229 = 3198 1360 9218 1839 3016"


def test_group_length_follows_the_message():
    """Nhóm 5 (như trạm số) nếu mô hình đa số tách nhóm 5."""
    out = run("RMKS 12345 = 67890 12345 67890 1234567890 <AR>")
    assert out == "RMKS 12345 = 67890 12345 67890 12345 67890 <AR>"


def test_plain_text_and_non_net_numbers_untouched():
    for text in ("CQ CQ DE UA9ABC 5NN TU 73", "RMKS HELLO WORLD THIS IS PLAIN TEXT", "75675 75675 84758 847588475"):
        assert run(text) == text


def test_structure_marks_stand_alone():
    assert run("RMKS 1069 1915 1178 1408 0974= 6A3U D3U7 <AR>") == "RMKS 1069 1915 1178 1408 0974 = 6132 8327 <AR>"


def test_words_rebuilt_with_letter_times():
    """Từ mới lấy thời điểm từng chữ; mép từ gốc giữ nguyên, độ tin cậy lấy thấp nhất."""
    def w(text, t0, conf):
        return Word(text, t0, t0 + 0.1 * len(text), conf, [(c, t0 + 0.1 * k) for k, c in enumerate(text)])
    words = [w("RMKS", 0.0, 0.99), w("1234", 1.0, 0.98), w("=", 2.0, 0.99), w("67A3TD3D", 3.0, 0.7)]
    out = traffic_words(words, EN)
    assert [x.text for x in out] == ["RMKS", "1234", "=", "6713", "0838"]
    a, b = out[3], out[4]
    assert a.start_s == 3.0 and abs(a.end_s - 3.4) < 1e-9 and abs(b.start_s - 3.4) < 1e-9
    assert abs(b.end_s - words[3].end_s) < 1e-9
    assert a.chars[1] == ("7", 3.1) and a.confidence == 0.7
    assert traffic_words([w("HELLO", 0.0, 0.9)], EN) is None


def test_to_between_remark_groups_is_a_word():
    """Cả 3 file T7 có `TO` giữa các nhóm RMKS; mô hình dính nó vào số (`8981TO8836`, T = số 0 viết tắt)."""
    assert run("RMKS 8981TO8836 8417 8047 = 6713 <AR>") == "RMKS 8981 TO 8836 8417 8047 = 6713 <AR>"
    assert run("РМКС 6229 ТО5652И = 3198 1360 9218", RU) == "РМКС 6229 ТО 5652 И = 3198 1360 9218"


def test_whole_groups_split_from_stray_letters_but_odd_runs_kept():
    out = run("RMKS 1234 = 8104 3129 0401 7376 8732 8930 6781 5416 1345RNQSL ? K")
    assert out == "RMKS 1234 = 8104 3129 0401 7376 8732 8930 6781 5416 1345 RNQSL ? K"
    assert run("RMKS 1234 = 5620 DN5S4 2713 <AR>") == "RMKS 1234 = 5620 DN5S4 2713 <AR>"
