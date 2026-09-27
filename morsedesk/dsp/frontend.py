"""Đặc trưng 11 chiều ở 200 khung/giây quanh tone đã dò.

Cột 0: log-envelope sau AGC; cột 1: đạo hàm cột 0; cột 2..10: 9 bin log-phổ quanh f0.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi, sosfiltfilt

from morsedesk.constants import FEAT_DIM, FRAME_RATE, HOP, SAMPLE_RATE
from morsedesk.dsp.stft import stft_power
from morsedesk.dsp.tone import estimate_tone
from morsedesk.dsp.windowing import STEP_FRAMES, WINDOW_FRAMES, frame_windows


@dataclass(frozen=True)
class FrontendConfig:
    lowpass_hz: float = 200.0
    agc_tau_s: float = 1.0
    n_bins: int = 9
    agc_init_s: float = 1.0     # đoạn đầu dùng khởi tạo mức nền AGC


def window_cfg(agc_tau_s: float = 1.0) -> FrontendConfig:
    """Cấu hình đặc trưng cho chế độ cửa sổ; `agc_tau_s` đến từ metadata của model đang dùng."""
    return FrontendConfig(agc_tau_s=agc_tau_s, agc_init_s=0.5)


WINDOW_CFG = window_cfg()


# Chia khối cho `mix_envelope`. Bản tính một lượt dựng liên tiếp `t`, bộ trộn phức, tín hiệu
# phức, hai nhánh I/Q và envelope — tất cả float64 và dài bằng cả clip — nên clip 20 phút chiếm
# 768 MB và file 60 phút đẩy cả lượt giải mã lên 5,4 GB (CP-14). Khối 60 giây giữ bộ nhớ ở mức
# hằng số; phần chồng lấn để `sosfiltfilt` không để lại vết ở chỗ nối.
ENVELOPE_CHUNK_SECONDS = 60.0
ENVELOPE_OVERLAP_SECONDS = 1.0


def _envelope_samples(x: np.ndarray, f0_hz: float, sample_rate: int, sos, start: int) -> np.ndarray:
    """|I+jQ| sau khi trộn xuống băng gốc và lọc thấp, cho một đoạn bắt đầu ở mẫu `start`.

    Pha của bộ trộn lấy theo chỉ số TUYỆT ĐỐI, nếu không hai khối liền nhau sẽ lệch pha và
    envelope gãy ở chỗ nối.
    """
    t = (np.arange(len(x), dtype=np.float64) + start) / sample_rate
    y = x.astype(np.float64) * np.exp(-2j * np.pi * f0_hz * t)
    yi = sosfiltfilt(sos, y.real)
    yq = sosfiltfilt(sos, y.imag)
    return np.sqrt(yi * yi + yq * yq)


def mix_envelope(
    x: np.ndarray, f0_hz: float, sample_rate: int = SAMPLE_RATE, lowpass_hz: float = 200.0,
    chunk_seconds: float = ENVELOPE_CHUNK_SECONDS,
) -> np.ndarray:
    """Trộn xuống băng gốc phức tại f0, lọc thấp, |I+jQ|, trung bình mỗi HOP mẫu.

    Khung t được căn giữa tại mẫu t*HOP, giống stft_power: pad env với HOP//2 mẫu 0
    ở đầu (và HOP mẫu 0 ở cuối để đủ cho khung cuối) rồi lấy trung bình từng khung
    HOP mẫu, sao cho khung t phủ [t*HOP - HOP//2, t*HOP + HOP//2).

    `chunk_seconds=0.0` tắt chia khối; chỉ dùng để test đối chiếu với bản một lượt.
    """
    n = len(x)
    n_frames = n // HOP
    if n_frames == 0:
        return np.zeros(0)
    sos = butter(4, lowpass_hz, btype="low", fs=sample_rate, output="sos")
    chunk = int(chunk_seconds * sample_rate)
    if chunk <= 0 or n <= chunk:
        env = _envelope_samples(x, f0_hz, sample_rate, sos, 0)
    else:
        pad = int(ENVELOPE_OVERLAP_SECONDS * sample_rate)
        env = np.empty(n, dtype=np.float64)
        for start in range(0, n, chunk):
            stop = min(start + chunk, n)
            lo = max(0, start - pad)
            hi = min(n, stop + pad)
            piece = _envelope_samples(x[lo:hi], f0_hz, sample_rate, sos, lo)
            env[start:stop] = piece[start - lo: start - lo + (stop - start)]
    env_p = np.pad(env, (HOP // 2, HOP))
    return env_p[: n_frames * HOP].reshape(n_frames, HOP).mean(axis=1)


def _ema(v: np.ndarray, alpha: float, init: float) -> np.ndarray:
    b = np.array([alpha])
    a = np.array([1.0, -(1.0 - alpha)])
    zi = lfilter_zi(b, a) * init
    out, _ = lfilter(b, a, v, zi=zi)
    return out


def agc_log(env: np.ndarray, frame_rate: int = FRAME_RATE, tau_s: float = 1.0, init_s: float = 1.0) -> np.ndarray:
    """log(envelope) trừ mức nền trượt, chia độ lệch chuẩn trượt; kẹp về [-6, 6]."""
    if len(env) == 0:
        return np.zeros(0)
    log_env = np.log(env + 1e-6)
    alpha = 1.0 / (tau_s * frame_rate)
    head = log_env[: max(1, min(len(log_env), int(round(init_s * frame_rate))))]
    mean = _ema(log_env, alpha, float(np.mean(head)))
    dev = log_env - mean
    var = _ema(dev * dev, alpha, float(np.mean(dev[: len(head)] ** 2)))
    out = dev / (np.sqrt(np.maximum(var, 0.0)) + 0.1)
    return np.clip(out, -6.0, 6.0)


def spectral_bins(
    x: np.ndarray, f0_hz: float, n_bins: int = 9, sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    n_frames = len(x) // HOP
    if n_frames == 0:
        return np.zeros((0, n_bins), dtype=np.float32)
    power, freqs = stft_power(x, sample_rate=sample_rate)
    bin_hz = float(freqs[1] - freqs[0])
    k0 = int(round(f0_hz / bin_hz))
    half = n_bins // 2
    ks = np.clip(np.arange(k0 - half, k0 - half + n_bins), 0, len(freqs) - 1)
    logp = np.log10(power[ks, :] + 1e-12).T            # [T, n_bins]
    med = float(np.median(logp))
    scale = float(np.percentile(logp, 95)) - med + 1e-3
    return ((logp - med) / scale).astype(np.float32)


def compute_features(
    x: np.ndarray,
    f0_hz: float,
    sample_rate: int = SAMPLE_RATE,
    cfg: FrontendConfig | None = None,
) -> np.ndarray:
    if cfg is None:
        cfg = FrontendConfig()
    n_frames = len(x) // HOP
    if n_frames == 0:
        return np.zeros((0, FEAT_DIM), dtype=np.float32)
    env = mix_envelope(x, f0_hz, sample_rate, cfg.lowpass_hz)
    a = agc_log(env, FRAME_RATE, cfg.agc_tau_s, cfg.agc_init_s)
    d = np.diff(a, prepend=a[0] if len(a) else 0.0)
    bins = spectral_bins(x, f0_hz, cfg.n_bins, sample_rate)
    feats = np.concatenate([a[:, None], d[:, None], bins], axis=1).astype(np.float32)
    assert feats.shape == (n_frames, FEAT_DIM), feats.shape
    return feats


DEFAULT_F0_HZ = 700.0


@dataclass
class Window:
    start_sample: int
    end_sample: int
    f0_hz: float
    feats: np.ndarray
    has_signal: bool
    pad_head: int = 0           # khung đệm (nhiễu nền) ở đầu `feats`, cắt bỏ sau khi chạy model
    pad_tail: int = 0           # ... và ở cuối

    @property
    def start_frame(self) -> int:
        return self.start_sample // HOP

    @property
    def end_frame(self) -> int:
        return self.end_sample // HOP


def background_noise_std(seg: np.ndarray, f0_hz: float, sample_rate: int = SAMPLE_RATE) -> float:
    """Độ lệch chuẩn nhiễu trắng nền, đo ở dải tần TRÁNH XA tone.

    Không lấy mức của khung yên nhất: sóng mang liên tục không có khung yên nào, và nhiễu đệm khi đó
    bằng cả biên độ sóng mang -> chỗ nối trông như nhấn phím, model đọc ra 'A' (test §7 bắt được).
    Nhiễu trắng phương sai s2 cho E|X_k|^2 = N s2 và |X_k|^2 phân phối mũ, nên s2 = trung vị / (N ln 2).
    """
    seg = np.asarray(seg, dtype=np.float64)
    n = len(seg)
    if n < 256:
        return 0.0
    spec = np.abs(np.fft.rfft(seg)) ** 2
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    keep = (freqs > 200.0) & (freqs < 0.45 * sample_rate) & (np.abs(freqs - f0_hz) > 250.0)
    if keep.sum() < 16:
        return 0.0
    return float(np.sqrt(np.median(spec[keep]) / (n * np.log(2.0))))


def pad_with_noise_floor(seg: np.ndarray, head: int, tail: int, seed: int = 0,
                         f0_hz: float = DEFAULT_F0_HZ, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Đệm `head`/`tail` mẫu hai đầu bằng nhiễu trắng cùng mức nhiễu nền của chính đoạn đó.

    Lúc huấn luyện khoảng lặng luôn có nhiễu kênh, và âm thanh đi vào model lúc giải mã cũng luôn
    có nhiễu (tín hiệu quá sạch được trộn nhiễu về 20 dB): đệm bằng nhiễu cùng mức là giống lúc học
    nhất. Mức nhiễu đo ngoài dải tone (background_noise_std). Hạt giống cố định theo vị trí cửa sổ
    nên cùng file luôn cho cùng kết quả.
    """
    seg = np.asarray(seg, dtype=np.float32)
    if head <= 0 and tail <= 0:
        return seg
    sigma = background_noise_std(seg, f0_hz, sample_rate)
    rng = np.random.default_rng(int(seed) & 0x7FFFFFFF)
    a = (rng.standard_normal(max(0, head)) * sigma).astype(np.float32)
    b = (rng.standard_normal(max(0, tail)) * sigma).astype(np.float32)
    return np.concatenate([a, seg, b])


def compute_features_windowed(
    x: np.ndarray,
    f0_hint: float | None = None,
    sample_rate: int = SAMPLE_RATE,
    window_frames: int = WINDOW_FRAMES,
    step_frames: int = STEP_FRAMES,
    cfg: FrontendConfig | None = None,
    pad_frames: int = 0,
) -> list[Window]:
    """Dò tone và chuẩn hóa đặc trưng trong từng cửa sổ; tone cửa sổ không có tín hiệu lấy từ
    cửa sổ trước, rồi f0_hint, rồi DEFAULT_F0_HZ. Chỉ dùng với sample_rate = SAMPLE_RATE.

    `pad_frames` > 0: đặc trưng tính trên cửa sổ đã đệm nhiễu nền ở mép GIÁP CỬA SỔ KHÁC (xem
    WINDOW_PAD_FRAMES); phần đầu ra ở đó bị cửa sổ bên cạnh che, nên cắt bỏ an toàn. Hai mép của
    CHÍNH `x` không đệm: model hay phát ký tự đầu tiên ngay khung đầu ra số 0, đệm rồi cắt là mất
    chữ; và đo 24/09 đệm cả file hai đầu làm T1 xấu 1,76 điểm (clip ngắn vốn đã có khoảng lặng).
    Nhờ vậy clip <= 12 s (một cửa sổ) giải mã y hệt trước. Tone vẫn dò trên phần tín hiệu thật.
    Mặc định 0 để đường huấn luyện không đổi."""
    cfg = cfg or WINDOW_CFG
    n_frames = len(x) // HOP
    if n_frames == 0:
        return []
    x = np.asarray(x, dtype=np.float32)
    windows: list[Window] = []
    carry = f0_hint
    for s, e in frame_windows(n_frames, window_frames, step_frames):
        seg = x[s * HOP:e * HOP]
        est = estimate_tone(seg, sample_rate)
        has_signal = bool(est.has_signal and est.f0_hz is not None)
        if has_signal:
            carry = float(est.f0_hz)
        f0 = carry if carry is not None else DEFAULT_F0_HZ
        head = pad_frames if (pad_frames and s > 0) else 0
        tail = pad_frames if (pad_frames and e < n_frames) else 0
        feats = compute_features(pad_with_noise_floor(seg, head * HOP, tail * HOP, seed=s, f0_hz=f0,
                                                      sample_rate=sample_rate),
                                 f0, sample_rate, cfg)
        windows.append(Window(s * HOP, e * HOP, f0, feats, has_signal, head, tail))
    return windows


STEADY_KEY_FRACTION = 0.9


def key_down_fraction(seg: np.ndarray, f0_hz: float, sample_rate: int = SAMPLE_RATE) -> float:
    """Tỉ lệ khung mà đường bao tại tone vượt nửa mức đỉnh (phân vị 99). Morse thật nhấn phím
    ~40–60 % thời gian; sóng mang liên tục gần 1,0; nhiễu thuần (Rayleigh) ~0,3."""
    env = mix_envelope(np.asarray(seg, dtype=np.float32), f0_hz, sample_rate)
    if len(env) == 0:
        return 0.0
    top = float(np.percentile(env, 99))
    return float(np.mean(env > 0.5 * top)) if top > 0 else 0.0


def repad_window(x: np.ndarray, w: Window, n_frames: int, pad_frames: int,
                 cfg: FrontendConfig | None = None, sample_rate: int = SAMPLE_RATE,
                 inner_start: bool = False) -> Window:
    """Tính lại đặc trưng của cửa sổ `w` với đệm nhiễu nền ở mép GIÁP CỬA SỔ KHÁC (không đệm hai
    đầu của chính `x`). Cùng tone, cùng cfg như lần tính đầu.

    `inner_start`: đầu `x` cũng là mép trong — bộ đệm chế độ nghe đã cắt phần đầu nên bắt đầu GIỮA tín
    hiệu. Đo 27/09: bộ đệm 9 s nằm trọn trong một dãy số liền, không đệm thì model ra rỗng (cổng
    NO_SIGNAL) và mất cả đuôi bản tin; đệm thì đọc đúng `7060192` với độ tin cậy 1,0.

    Trả nguyên `w` khi không có mép nào để đệm (clip một cửa sổ) hoặc khi cửa sổ là sóng mang
    liên tục (tone bật >= STEADY_KEY_FRACTION thời gian — không có nhịp phím): đệm cho AGC một
    nền yên để so, và sóng mang 20 s đang ra độ tin cậy 0,11 (bị cổng chặn) thành 'A' 0,17."""
    cfg = cfg or WINDOW_CFG
    s, e = w.start_frame, w.end_frame
    head = pad_frames if (s > 0 or inner_start) else 0
    tail = pad_frames if e < n_frames else 0
    if not (head or tail):
        return w
    seg = np.asarray(x[w.start_sample:w.end_sample], dtype=np.float32)
    if key_down_fraction(seg, w.f0_hz, sample_rate) >= STEADY_KEY_FRACTION:
        return w
    padded = pad_with_noise_floor(seg, head * HOP, tail * HOP, seed=s, f0_hz=w.f0_hz, sample_rate=sample_rate)
    return Window(w.start_sample, w.end_sample, w.f0_hz, compute_features(padded, w.f0_hz, sample_rate, cfg),
                  w.has_signal, head, tail)


def stitch_windows(windows: list[Window], n_frames: int) -> np.ndarray:
    """Ghép đặc trưng các cửa sổ theo khung: khung t lấy từ cửa sổ có tâm gần t + 0,5 nhất."""
    out = np.zeros((n_frames, FEAT_DIM), dtype=np.float32)
    best = np.full(n_frames, np.inf)
    for w in windows:
        s, e = w.start_frame, w.end_frame
        idx = np.arange(s, min(e, n_frames))
        dist = np.abs(idx + 0.5 - (s + e) / 2.0)
        better = dist < best[idx]
        out[idx[better]] = w.feats[: len(idx)][better]
        best[idx[better]] = dist[better]
    return out
