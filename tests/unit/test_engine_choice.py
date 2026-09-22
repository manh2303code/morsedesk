"""Chọn kết quả DSP thay cho mô hình khi tín hiệu nằm ngoài dải huấn luyện (bằng chứng T2).

Trên 10 bản ghi thật của ARRL (SNR 49–143 dB), thứ hạng đảo ngược hẳn so với T1: bộ DSP 4,0 %,
DeepCW 8,0 %, mô hình của mình 24,2 %. Trên T1 (SNR -6..20 dB) thì ngược lại: mô hình 20,21 %,
DSP 35,12 %. Nên không engine nào thắng ở mọi nơi, và việc chọn phải dựa trên bằng chứng đo
được từ chính clip: SNR ngoài dải huấn luyện **và** timing khớp tới mức bộ DSP đáng tin.
"""

from morsedesk.dsp.selection import DSP_MAX_TIMING_COST, SNR_OUT_OF_RANGE_DB, prefer_dsp


def test_prefers_dsp_only_when_both_conditions_hold():
    assert prefer_dsp(snr_db=60.0, timing_cost=0.003)
    assert not prefer_dsp(snr_db=60.0, timing_cost=0.5)      # sạch nhưng nhịp gõ lộn xộn
    assert prefer_dsp(snr_db=60.0, timing_cost=0.0523)       # bản 5 WPM của ARRL
    assert not prefer_dsp(snr_db=12.0, timing_cost=0.003)    # trong dải huấn luyện: tin mô hình
    assert not prefer_dsp(snr_db=12.0, timing_cost=0.5)


def test_thresholds_match_the_measured_populations():
    """Ngưỡng phải bám số đo, không phải số chọn bừa.

    SNR là thứ tách hai đám đông (T1 cao nhất 22 dB, T2 thấp nhất 49 dB). Chi phí timing là
    lưới an toàn cho ca chưa có trong bộ đo — rất sạch nhưng gõ tay lệch nhịp — nên phải đủ
    rộng để giữ cả mười bản ghi ARRL (cao nhất 0,0523) mà vẫn loại nhịp thực sự hỗn loạn.
    """
    assert 25.0 < SNR_OUT_OF_RANGE_DB < 49.0
    assert 0.0523 < DSP_MAX_TIMING_COST < 0.15


def test_missing_measurements_never_pick_dsp():
    assert not prefer_dsp(snr_db=None, timing_cost=0.003)
    assert not prefer_dsp(snr_db=60.0, timing_cost=None)
    assert not prefer_dsp(snr_db=float("nan"), timing_cost=0.003)
    assert not prefer_dsp(snr_db=60.0, timing_cost=float("inf"))


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
