import numpy as np
import pytest

torch = pytest.importorskip("torch")

from morsedesk.data.channel import clean
from morsedesk.data.keyer import machine
from morsedesk.data.synth import SynthConfig, SynthGenerator
from morsedesk.model.vocab import VOCAB
from tools.net_torch import CONFIG_DEFAULT, MorseNet, count_params, output_length
from tools.train import SynthDataset, collate, example_features, token_error_rate


def test_output_length_matches_conv():
    m = MorseNet()
    for t in (1, 2, 3, 100, 101, 800):
        y = m(torch.zeros(1, t, 11))
        assert y.shape == (1, output_length(t), len(VOCAB))
    assert 100_000 < count_params(m) < 400_000
    assert CONFIG_DEFAULT["n_classes"] == 65


def test_forward_is_log_softmax():
    y = MorseNet()(torch.zeros(2, 50, 11))
    assert torch.allclose(y.exp().sum(-1), torch.ones(2, output_length(50)), atol=1e-4)


def test_dataset_and_collate():
    gen = SynthGenerator(SynthConfig(min_seconds=2.0, max_seconds=3.0, mp3_enabled=False))
    ds = SynthDataset(gen, seed_start=0, n_items=3)
    items = list(ds)
    assert len(items) == 3
    feats, feat_lens, targets, target_lens, tokens = collate(items)
    assert feats.shape[0] == 3 and feats.shape[2] == 11
    assert feat_lens.tolist() == [output_length(len(it[0])) for it in items]
    assert int(target_lens.sum()) == len(targets)
    assert len(tokens) == 3


def test_overfit_tiny_batch_reduces_loss():
    torch.manual_seed(0)
    gen = SynthGenerator(SynthConfig(min_seconds=2.0, max_seconds=3.0, mp3_enabled=False))
    items = []
    for s in range(4):
        ex = gen.generate(s, profile_id="en", keyer=machine(25), channel=clean(30.0))
        items.append((torch.from_numpy(example_features(ex)), torch.tensor(ex.labels), ex.tokens))
    feats, feat_lens, targets, target_lens, _ = collate(items)
    model = MorseNet()
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    ctc = torch.nn.CTCLoss(blank=0, zero_infinity=True)
    losses = []
    for _ in range(60):
        logp = model(feats)
        loss = ctc(logp.transpose(0, 1), targets, feat_lens, target_lens)
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(float(loss))
    assert losses[-1] < 0.7 * losses[0], losses[::10]
    ter = token_error_rate(model, [(f, t) for f, _, t in items])
    assert 0.0 <= ter <= 1.5
