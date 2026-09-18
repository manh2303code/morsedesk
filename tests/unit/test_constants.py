from morsedesk import constants


def test_frame_rate_is_200():
    assert constants.FRAME_RATE == 200
    assert constants.SAMPLE_RATE == 8000
    assert constants.HOP == 40


def test_feature_dim():
    assert constants.FEAT_DIM == 11
