import numpy as np
import pytest

from morsedesk.data.channel import (
    DEFAULT_SAMPLING,
    HARD_QSB_SAMPLING,
    ChannelSampling,
    sample_channel_params,
)
from morsedesk.data.synth import SynthConfig, SynthGenerator


def test_default_sampling_is_bit_identical_to_old_behaviour():
    a = sample_channel_params(np.random.default_rng(7))
    b = sample_channel_params(np.random.default_rng(7), DEFAULT_SAMPLING)
    c = sample_channel_params(np.random.default_rng(7), ChannelSampling())
    assert a == b == c
    assert DEFAULT_SAMPLING == ChannelSampling(0.4, (5.0, 30.0), (2.0, 20.0))


def test_hard_qsb_narrows_period_and_raises_rate():
    rng = np.random.default_rng(0)
    rows = [sample_channel_params(rng, HARD_QSB_SAMPLING) for _ in range(400)]
    fading = [r for r in rows if r.qsb_depth_db > 0]
    assert 0.5 < len(fading) / len(rows) < 0.7        # ~60 % clip có QSB (mặc định 40 %)
    assert all(2.0 <= r.qsb_period_s <= 8.0 for r in rows)
    assert all(10.0 <= r.qsb_depth_db <= 24.0 for r in fading)


def test_synth_config_passes_sampling_through():
    gen = SynthGenerator(SynthConfig(channel_sampling=HARD_QSB_SAMPLING, mp3_enabled=False))
    for seed in range(5):
        ex = gen.generate(seed)
        assert 2.0 <= ex.channel.qsb_period_s <= 8.0


def test_train_sampling_for_flag():
    pytest.importorskip("torch")
    from tools import train

    assert train.sampling_for(True) is HARD_QSB_SAMPLING
    assert train.sampling_for(False) is None
