"""Chọn kết quả DSP thay cho mô hình khi tín hiệu nằm ngoài dải huấn luyện (bằng chứng T2).

Trên 10 bản ghi thật của ARRL (SNR 49–143 dB), thứ hạng đảo ngược hẳn so với T1: bộ DSP 4,0 %,
DeepCW 8,0 %, mô hình của mình 24,2 %. Trên T1 (SNR -6..20 dB) thì ngược lại: mô hình 20,21 %,
DSP 35,12 %. Nên không engine nào thắng ở mọi nơi, và việc chọn phải dựa trên bằng chứng đo
được từ chính clip: SNR ngoài dải huấn luyện **và** timing khớp tới mức bộ DSP đáng tin.
"""

from morsedesk.dsp.selection import DSP_MAX_TIMING_COST, SNR_OUT_OF_RANGE_DB, prefer_dsp


def test_two_independent_branches_lead_to_the_dsp():
    assert prefer_dsp(snr_db=60.0, timing_cost=0.003)        # cả hai nhánh cùng đúng
    assert prefer_dsp(snr_db=60.0, timing_cost=0.0523)       # bản 5 WPM của ARRL: nhánh SNR
    assert prefer_dsp(snr_db=12.0, timing_cost=0.003)        # nhánh timing, SNR tầm thường
    assert not prefer_dsp(snr_db=60.0, timing_cost=0.5)      # sạch nhưng nhịp gõ lộn xộn
    assert not prefer_dsp(snr_db=12.0, timing_cost=0.5)      # không nhánh nào đúng


def test_thresholds_match_the_measured_populations():
    """Ngưỡng phải bám số đo, không phải số chọn bừa.

    SNR là thứ tách hai đám đông (T1 cao nhất 22 dB, T2 thấp nhất 49 dB). Chi phí timing là
    lưới an toàn cho ca chưa có trong bộ đo — rất sạch nhưng gõ tay lệch nhịp — nên phải đủ
    rộng để giữ cả mười bản ghi ARRL (cao nhất 0,0523) mà vẫn loại nhịp thực sự hỗn loạn.
    """
    assert 25.0 < SNR_OUT_OF_RANGE_DB < 49.0
    assert 0.0523 < DSP_MAX_TIMING_COST < 0.15


def test_missing_timing_cost_never_picks_dsp():
    """Chi phí timing là phép đo bắt buộc; thiếu nó thì không có cơ sở nào để đổi đường.

    SNR thiếu thì khác: nhánh timing vẫn đứng vững một mình, vì chi phí thấp nghĩa là bộ DSP đã
    phân đoạn được tín hiệu — bằng chứng ấy không cần SNR xác nhận.
    """
    assert not prefer_dsp(snr_db=60.0, timing_cost=None)
    assert not prefer_dsp(snr_db=60.0, timing_cost=float("inf"))
    assert not prefer_dsp(snr_db=None, timing_cost=0.5)
    assert prefer_dsp(snr_db=None, timing_cost=0.003)
    assert prefer_dsp(snr_db=float("nan"), timing_cost=0.003)


def test_ambiguous_patterns_always_keep_the_model():
    """Bảng Kazakh có 9 mẫu giải ra hai chữ (`.-` là А hoặc Ә); chọn đúng là việc của LM."""
    assert not prefer_dsp(snr_db=60.0, timing_cost=0.003, has_ambiguous_tokens=True)
    assert prefer_dsp(snr_db=60.0, timing_cost=0.003, has_ambiguous_tokens=False)


def test_profiles_with_ambiguity_are_the_ones_we_expect():
    """Chốt lại số mẫu mơ hồ của từng bảng: nếu bảng đổi, test này phải được đọc lại."""
    from morsedesk.lm.profile import load_profile

    counts = {pid: sum(1 for v in load_profile(pid).map.values() if len(v) > 1)
              for pid in ("en", "ru", "kk-cyrl-ru")}
    assert counts == {"en": 0, "ru": 1, "kk-cyrl-ru": 9}, counts


def test_clean_kazakh_roundtrip_uses_the_language_model_to_pick_letters():
    """Tín hiệu sạch + bảng có mẫu mơ hồ: lấy phân đoạn của DSP nhưng để LM chọn chữ.

    Bảng Kazakh giải `.-` ra А hoặc Ә. Bỏ hẳn đường DSP ở đây thì mất phân đoạn chính xác mà
    tín hiệu sạch cho không; lấy DSP mà không hỏi LM thì luôn ra lựa chọn đầu. Hai ô 15 và 25
    WPM của bộ T0 hỏng đúng vì điều đó (spec D2 yêu cầu CER = 0 trên audio sạch).
    """
    from pathlib import Path

    import pytest as _pytest

    from morsedesk.api import Decoder, Encoder
    from morsedesk.metrics import cer

    if not Path("models/acoustic.onnx").is_file() or not Path("models/lm/kk.bin").is_file():
        _pytest.skip("cần models/acoustic.onnx và models/lm/kk.bin")
    text = "СӘЛЕМ ӘЛЕМ"
    dec = Decoder("kk-cyrl-ru", engine="onnx")
    for wpm in (15, 25):
        got = dec.decode_array(Encoder("kk-cyrl-ru").to_audio(text, wpm=wpm)).text
        assert cer(text, got) == 0.0, (wpm, got)


def test_very_low_timing_cost_alone_is_enough():
    """Timing khớp gần hoàn hảo là bằng chứng đủ, không cần SNR cao đi kèm.

    Đo trên 461 clip T1 có tín hiệu: chỉ dùng mô hình cho 15,73 %; thêm nhánh "chi phí timing
    dưới 0,02" thì còn 14,95 % và 101 clip chuyển sang bộ DSP. Nới tới 0,05 lại xấu đi thành
    18,48 %, nên ngưỡng phải nằm hẳn dưới mức đó.

    Ca lộ ra điều này: một clip SNR 12,8 dB mà bộ DSP đọc đúng nguyên văn còn mô hình sai 8 %.
    """
    assert prefer_dsp(snr_db=12.8, timing_cost=0.0)        # timing hoàn hảo, SNR tầm thường
    assert prefer_dsp(snr_db=5.0, timing_cost=0.015)
    assert not prefer_dsp(snr_db=5.0, timing_cost=0.03)    # chưa đủ khớp, giữ mô hình
    assert prefer_dsp(snr_db=60.0, timing_cost=0.03)       # sạch hơn dải huấn luyện thì vẫn lấy


def test_low_cost_branch_still_respects_ambiguity():
    assert not prefer_dsp(snr_db=12.8, timing_cost=0.0, has_ambiguous_tokens=True)


def test_dsp_output_with_patterns_outside_the_table_is_rejected():
    """Bộ DSP có thể sinh mẫu không tồn tại trong bảng khi tín hiệu nhiễu.

    Trên clip nhiễu, phân đoạn sai đẻ ra những chuỗi như `.--..` hay `..-.-` — không mẫu nào
    trong ba bảng có chúng. Đem đi tra bảng thì vỡ với `KeyError`; đo trên T1 là 67/500 clip.
    Một kết quả chứa mẫu như vậy tự nó đã nói rằng bộ DSP đọc sai, nên phải giữ đường mô hình.
    """
    from morsedesk.dsp.selection import dsp_result_usable
    from morsedesk.lm.profile import load_profile
    from morsedesk.model.vocab import SPACE

    profile = load_profile("en")
    assert dsp_result_usable([".-", "-...", SPACE, "-.-"], profile)
    assert not dsp_result_usable([".-", ".--..", SPACE], profile)
    assert not dsp_result_usable(["..-.-"], profile)
    assert dsp_result_usable([], profile)


# --- Chi phí timing thấp KHÔNG có nghĩa là bộ DSP đã đọc HẾT tín hiệu (23/09) ---------------------
# Trên tín hiệu fading, bộ DSP (ngưỡng cố định) đọc hoàn hảo đoạn mạnh và bỏ trống đoạn chìm; chi
# phí timing chỉ tính trên phần nó đọc được nên vẫn < 0,02. Đo trên dev: qsb@20 dB đi đường DSP
# 10 clip CER 72,5 %, đường model 10 clip CER 11,5 %.

from morsedesk.dsp.selection import DSP_MIN_LENGTH_RATIO, dsp_is_complete  # noqa: E402


def test_dsp_that_drops_a_chunk_is_not_complete():
    assert dsp_is_complete("CQ DE R1ABC K", "CQ DE R1ABC K")
    assert not dsp_is_complete("R1ABC K", "CQ DE R1ABC K")          # mất cả đoạn đầu
    assert dsp_is_complete("CQ DE R1ABC", "CQ DE R1ABC K")          # thiếu 1/11 ký tự: vẫn tin
    assert dsp_is_complete("CQDER1ABCK", "CQ DE R1ABC K")           # dấu cách không tính
    assert dsp_is_complete("CQ", "")                                # không có gì để so


def test_length_ratio_is_the_measured_one():
    """0,7 / 0,8 cho cùng kết quả trên dev, 0,9 / 0,95 tốt hơn một chút và y hệt nhau."""
    assert 0.85 <= DSP_MIN_LENGTH_RATIO <= 0.95


def test_decoder_ignores_a_confident_but_truncated_dsp_reading(monkeypatch):
    """Tất định: bộ DSP trả chi phí rất thấp nhưng thiếu cả đoạn đầu -> phải lấy kết quả model."""
    from pathlib import Path

    import pytest

    if not Path("models/acoustic.onnx").exists() or not Path("models/lm/en.bin").exists():
        pytest.skip("cần model đã huấn luyện và models/lm/en.bin")
    from morsedesk.api import Decoder, Encoder
    from morsedesk.dsp.baseline import BaselineResult, Symbol

    text = "CQ CQ DE R1ABC K"
    x = Encoder("en").to_audio(text, wpm=20, snr_db=12.0, seed=2)
    d = Decoder("en", engine="onnx")
    truncated = BaselineResult(
        symbols=[Symbol(t, 0, 1) for t in (".-.", ".----", ".-", "-...", "-.-.", " ", "-.-")],
        unit_frames=12.0, threshold=0.5, cost=0.001)                 # "R1ABC K", timing hoàn hảo
    monkeypatch.setattr(d, "_baseline_tokens", lambda *a, **k: truncated)
    r = d.decode_array(x)
    assert r.decoded_by == "model", r.text
    assert r.text.startswith("CQ"), r.text
