import json

import numpy as np
import pytest

from morsedesk.api import Decoder, Encoder
from morsedesk.constants import FEAT_DIM, FRAME_RATE, HOP
from morsedesk.dsp.frontend import (
    WINDOW_CFG,
    FrontendConfig,
    Window,
    agc_log,
    compute_features,
    compute_features_windowed,
    stitch_windows,
)
from morsedesk.dsp.tone import estimate_tone
from morsedesk.dsp.windowing import STEP_FRAMES, WINDOW_FRAMES, frame_windows
from morsedesk.model import chunker
from morsedesk.model.chunker import run_chunked, run_chunked_audio
from tests.helpers import make_morse


class PassThroughModel:
    """Trả đặc trưng lấy mẫu stride 2 làm 'log-prob' để kiểm plumbing gộp cửa sổ."""
    time_stride = 2
    meta = {"vocab": list(range(FEAT_DIM))}
    feature_mode = "window"

    def output_length(self, t):
        return (t - 1) // 2 + 1

    def __call__(self, feats):
        return np.asarray(feats[::2], dtype=np.float32)


def test_chunker_reexports_windowing():
    assert chunker.WINDOW_FRAMES == WINDOW_FRAMES == 1600 and chunker.STEP_FRAMES == STEP_FRAMES == 400
    assert chunker.frame_windows is frame_windows
    assert WINDOW_CFG == FrontendConfig(agc_init_s=0.5) and FrontendConfig().agc_init_s == 1.0


def test_agc_init_seconds_changes_only_start():
    env = np.concatenate([np.full(100, 0.01), np.full(900, 1.0)])   # đổi mức trong giây đầu
    a1 = agc_log(env, init_s=1.0)                                     # khởi tạo từ 200 khung (trộn hai mức)
    a2 = agc_log(env, init_s=0.5)                                     # khởi tạo từ 100 khung (chỉ mức thấp)
    assert a1.shape == a2.shape == (1000,)
    assert not np.allclose(a1[:100], a2[:100])
    assert np.allclose(a1[-100:], a2[-100:], atol=0.05)               # EMA tau 1 s hội tụ sau ~4 s


def test_windowed_shapes_tone_and_carry_over():
    x, _ = make_morse("PARIS PARIS PARIS PARIS PARIS", wpm=20, tone_hz=650.0, pad_s=0.0)   # ~13 s
    n_frames = len(x) // HOP
    wins = compute_features_windowed(x)
    assert [(w.start_frame, w.end_frame) for w in wins] == frame_windows(n_frames)
    for w in wins:
        assert isinstance(w, Window)
        assert w.feats.shape == (w.end_frame - w.start_frame, FEAT_DIM) and w.feats.dtype == np.float32
        assert w.has_signal and abs(w.f0_hz - 650.0) < 15.0
    rng = np.random.default_rng(0)
    # Đuôi nhiễu phải dài hơn một cửa sổ, nếu không cửa sổ cuối vẫn còn dính tín hiệu và
    # không kiểm được nhánh "không có tín hiệu". Tính theo hằng số để không vỡ khi đổi cửa sổ.
    noise_s = WINDOW_FRAMES / FRAME_RATE + 2.0
    noise = rng.normal(0, 0.01, size=int(noise_s * 8000)).astype(np.float32)
    wins2 = compute_features_windowed(np.concatenate([x, noise]))
    tail = wins2[-1]
    assert not tail.has_signal and abs(tail.f0_hz - wins2[-2].f0_hz) < 1e-9        # mang tone cửa sổ trước
    short_noise = noise[: int(WINDOW_FRAMES / FRAME_RATE * 8000) - 8000]           # dưới 1 cửa sổ
    only_noise = compute_features_windowed(short_noise, f0_hint=720.0)
    assert len(only_noise) == 1 and not only_noise[0].has_signal and only_noise[0].f0_hz == 720.0
    assert compute_features_windowed(noise)[0].f0_hz == 700.0
    assert compute_features_windowed(np.zeros(10, np.float32)) == []


def test_stitch_windows_nearest_center_and_shape():
    x, _ = make_morse("PARIS PARIS PARIS PARIS", wpm=20, pad_s=0.0)
    n_frames = len(x) // HOP
    wins = compute_features_windowed(x)
    st = stitch_windows(wins, n_frames)
    assert st.shape == (n_frames, FEAT_DIM) and st.dtype == np.float32
    w0, w1 = wins[0], wins[1]
    mid = (w0.start_frame + w0.end_frame) // 2
    assert np.allclose(st[mid], w0.feats[mid - w0.start_frame])
    late = w1.end_frame - 1 if len(wins) == 2 else (w1.start_frame + w1.end_frame) // 2
    assert np.allclose(st[late], w1.feats[late - w1.start_frame])
    assert np.allclose(stitch_windows([], 5), np.zeros((5, FEAT_DIM), np.float32))


def test_windowed_renormalizes_deep_fade():
    loud, _ = make_morse("PARIS PARIS PARIS", wpm=20, pad_s=0.0)      # ~7,4 s
    quiet = 0.01 * loud                                                # QSB sâu -40 dB ở nửa sau
    x = np.concatenate([loud, quiet]).astype(np.float32)
    n_frames = len(x) // HOP
    clip = compute_features(x, 700.0)
    win = stitch_windows(compute_features_windowed(x, f0_hint=700.0), n_frames)
    tail = slice(-1000, None)                            # 5 s cuối: chỉ thuộc các cửa sổ hoàn toàn yên
    center_bin = 2 + 4                                   # cột bin phổ giữa (9 bin từ cột 2)
    on = clip[tail, 0] > 0.5                             # khung "bật" theo AGC (AGC thích nghi, dùng làm mặt nạ)
    assert on.sum() > 50
    assert win[tail, center_bin][on].mean() > clip[tail, center_bin][on].mean() + 0.3
    assert np.all(np.isfinite(win))


def test_run_chunked_audio_matches_stitched_features():
    x, _ = make_morse("PARIS PARIS PARIS PARIS", wpm=20, pad_s=0.0)
    n_frames = len(x) // HOP
    logp, n = run_chunked_audio(PassThroughModel(), x, f0_hint=700.0)
    assert n == n_frames and logp.shape == ((n_frames - 1) // 2 + 1, FEAT_DIM)
    wins = compute_features_windowed(x, f0_hint=700.0)
    st = stitch_windows(wins, n_frames)
    # điểm tham chiếu khác nhau 0,5 khung (2g+1 khi gộp, t+0,5 khi ghép) nên bỏ ±3 khung quanh ranh giới cửa sổ
    centers = [(w.start_frame + w.end_frame) / 2.0 for w in wins]
    bounds = [(a + b) / 2.0 for a, b in zip(centers[:-1], centers[1:], strict=True)]
    g = np.arange(logp.shape[0])
    far = np.all([np.abs(2 * g + 1 - b) > 3 for b in bounds], axis=0) if bounds else np.ones_like(g, bool)
    assert far.sum() > 0.9 * len(g)
    assert np.allclose(logp[far], st[::2][far], atol=1e-6)
    same = run_chunked(PassThroughModel(), st)
    assert np.allclose(same[far], logp[far], atol=1e-6)


@pytest.fixture(scope="module")
def tmp_models(tmp_path_factory):
    torch = pytest.importorskip("torch")
    pytest.importorskip("onnxruntime")
    from tools.export_onnx import export
    from tools.net_torch import CONFIG_DEFAULT, MorseNet

    tmp = tmp_path_factory.mktemp("m")
    torch.manual_seed(0)
    out = {}
    for mode in ("clip", "window"):
        ckpt = tmp / f"{mode}.pt"
        cfg = dict(CONFIG_DEFAULT, feature_mode=mode)
        torch.save({"state_dict": MorseNet(**CONFIG_DEFAULT).state_dict(), "step": 1, "val_ter": 0.5,
                    "config": cfg}, ckpt)
        onnx_path = tmp / f"{mode}.onnx"
        export(ckpt, onnx_path, version="test")
        out[mode] = onnx_path
    return out


def test_export_writes_feature_mode_and_runner_reads_it(tmp_models):
    from morsedesk.model.onnx_runner import OnnxAcousticModel

    for mode, path in tmp_models.items():
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        assert meta["feature_mode"] == mode and meta["config"]["hidden"] == 96
        m = OnnxAcousticModel(path)
        assert m.feature_mode == mode and m.hidden == 96


def test_decoder_picks_path_by_feature_mode(tmp_models, monkeypatch):
    calls = []
    orig = chunker.run_chunked_windows

    def spy(*a, **k):
        calls.append("windows")
        return orig(*a, **k)

    monkeypatch.setattr(chunker, "run_chunked_windows", spy)
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20)
    r = Decoder("en", engine="onnx", model_path=tmp_models["window"], lm=False).decode_array(x)
    assert calls == ["windows"] and r.engine == "onnx"
    calls.clear()
    Decoder("en", engine="onnx", model_path=tmp_models["clip"], lm=False).decode_array(x)
    assert calls == []


def test_window_mode_decodes_when_global_tone_estimate_fails(tmp_models):
    """Clip ~21 s gần như toàn nhiễu: cổng tone toàn clip đóng nhưng cửa sổ 4 s vẫn dò ra tone.

    "CQ DE K" ở 25 WPM dài 2,9 s (dài hơn 1,5 s để bản tin nằm gọn trong một cửa sổ);
    18 s nhiễu ở đầu là mức vừa đủ để `estimate_tone` toàn clip trả has_signal=False.
    """
    morse, _ = make_morse("CQ DE K", wpm=25, tone_hz=700.0, pad_s=0.0)
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.01, size=18 * 8000).astype(np.float32)
    x = np.concatenate([noise, morse, rng.normal(0, 0.01, size=4000).astype(np.float32)])
    assert not estimate_tone(x).has_signal                    # cổng tone toàn clip đóng
    assert sum(w.has_signal for w in compute_features_windowed(x)) >= 1
    r = Decoder("en", engine="onnx", model_path=tmp_models["window"], lm=False).decode_array(x)
    assert r.tone_hz is not None and abs(r.tone_hz - 700.0) < 20.0
    assert not any("không có tín hiệu" in w for w in r.warnings)
    assert r.snr_db is None                                   # không có ước lượng toàn clip để báo SNR
    # Chế độ 'clip' không có cửa sổ để dò lại, nên rơi vào đường đoán tone theo đỉnh phổ: vẫn
    # chạy model (bỏ cuộc là chắc chắn CER 1,0) nhưng phải nói rõ là đang đoán.
    clip = Decoder("en", engine="onnx", model_path=tmp_models["clip"], lm=False).decode_array(x)
    assert clip.tone_hz is not None
    assert any("đang đoán theo đỉnh phổ" in w for w in clip.warnings)
    assert not any("không có tín hiệu" in w for w in clip.warnings)
    # Chế độ 'window' dò được tone thật từ một cửa sổ nên KHÔNG mang cảnh báo đoán.
    assert not any("đang đoán theo đỉnh phổ" in w for w in r.warnings)
