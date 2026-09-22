"""Tín hiệu phát ra có đúng chuẩn ITU-R M.1677-1 không — đo trên chính audio sinh ra.

Ba thứ quyết định việc một máy thu khác (người nghe, hay phần mềm khác) đọc được bản tin:
tỉ lệ thời gian, tần số tone, và dạng sườn lên/xuống. Test này đo cả ba từ dạng sóng thật chứ
không tin vào tham số đã đặt.
"""

import numpy as np
import pytest

from morsedesk.api import Encoder
from morsedesk.constants import SAMPLE_RATE


def envelope_runs(x: np.ndarray, thr: float = 0.5) -> list[tuple[bool, int]]:
    """Các đoạn bật/tắt của bao biên độ, tính bằng số mẫu.

    Bao biên độ lấy bằng biến đổi Hilbert chứ không phải `abs(x)`: sóng sin đi qua 0 hai lần mỗi
    chu kỳ nên `abs` dao động mạnh và cắt vụn mỗi dấu thành nhiều đoạn. Ngưỡng 50 % là điểm đo
    độ dài phần tử theo thông lệ, và với sườn đối xứng thì nó trả đúng độ dài danh nghĩa.
    """
    from scipy.signal import hilbert

    env = np.abs(hilbert(np.asarray(x, dtype=np.float64)))
    mask = env > thr * env.max()
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    bounds = [0, *change.tolist(), len(mask)]
    return [(bool(mask[bounds[i]]), bounds[i + 1] - bounds[i]) for i in range(len(bounds) - 1)]


@pytest.mark.parametrize("wpm", [12, 20, 30])
def test_dit_length_matches_the_paris_standard(wpm):
    """PARIS: một dit = 1,2 / WPM giây. Đây là định nghĩa WPM mà mọi máy thu dùng."""
    x = Encoder("en").to_audio("EEE", wpm=wpm)          # ba dit, hai khoảng trong chữ
    marks = [n for on, n in envelope_runs(x) if on]
    assert len(marks) == 3, marks
    dit_s = float(np.median(marks)) / SAMPLE_RATE
    assert abs(dit_s - 1.2 / wpm) < 0.1 * (1.2 / wpm), (dit_s, 1.2 / wpm)


def test_dash_is_three_dits_and_gaps_follow_one_three_seven():
    """Tỉ lệ 1:3 cho dấu và 1:3:7 cho khoảng lặng — lõi của chuẩn."""
    # "A A" = `.-` cách `.-` bằng khoảng từ. Trong mỗi chữ có khoảng 1 dit giữa chấm và gạch,
    # nên một chuỗi này đủ để thấy cả ba mức khoảng lặng mà chuẩn quy định.
    x = Encoder("en").to_audio("A A", wpm=20)
    runs = envelope_runs(x)
    marks = [n for on, n in runs if on]
    gaps = [n for i, (on, n) in enumerate(runs) if not on and 0 < i < len(runs) - 1]
    dit = min(marks)
    assert abs(max(marks) / dit - 3.0) < 0.25, [m / dit for m in marks]
    ratios = sorted(g / dit for g in gaps)
    assert abs(ratios[0] - 1.0) < 0.3, ratios      # khoảng trong chữ
    assert abs(ratios[-1] - 7.0) < 0.8, ratios     # khoảng giữa từ


@pytest.mark.parametrize("tone", [500.0, 700.0, 1000.0])
def test_tone_frequency_is_what_was_asked(tone):
    x = Encoder("en").to_audio("T", wpm=20, tone_hz=tone)
    seg = x[len(x) // 3: 2 * len(x) // 3]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    peak = float(np.fft.rfftfreq(len(seg), 1 / SAMPLE_RATE)[int(np.argmax(spec))])
    assert abs(peak - tone) < 8.0, (peak, tone)


def test_edges_are_shaped_not_square():
    """Sườn vuông sinh click lan ra cả băng (key clicks) — bản tin sẽ chèn lên kênh bên cạnh.

    Đo bằng năng lượng ngoài băng: một tín hiệu có sườn được làm mềm phải tập trung gần tone.
    """
    x = Encoder("en").to_audio("EEEEE", wpm=30, tone_hz=700.0)
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / SAMPLE_RATE)
    near = spec[(freqs > 600) & (freqs < 800)].sum()
    far = spec[(freqs > 1200) | (freqs < 200)].sum()
    assert far / near < 0.01, far / near


def test_amplitude_stays_inside_the_range():
    """Không được clip: mẫu ngoài [-1, 1] sẽ méo khi ghi file 16 bit."""
    x = Encoder("en").to_audio("CQ CQ DE R1ABC K", wpm=25)
    assert float(np.max(np.abs(x))) <= 1.0
    assert float(np.max(np.abs(x))) > 0.3, "biên độ quá nhỏ thì tỉ số tín hiệu trên nhiễu kém"


@pytest.mark.parametrize("wpm", [12, 20, 30, 40])
def test_ramp_does_not_eat_into_element_length(wpm):
    """Sườn phải cưỡi lên ranh giới, không nằm gọn trong dấu.

    Sườn raised-cosine đặt hoàn toàn bên trong đoạn bật làm mọi dấu ngắn đi đúng một `ramp` khi
    đo ở 50 % biên độ, và mọi khoảng lặng dài thêm chừng ấy. Với `ramp` 5 ms cố định, ở 30 WPM
    (dit 40 ms) điều đó đẩy tỉ lệ dah/dit từ 3,00 lên 3,29 — đủ để một máy thu đo tỉ lệ thấy
    lệch. Sườn đối xứng qua ranh giới đưa tỉ lệ về 3,01 ở cả 20 lẫn 40 WPM.

    Đo trên các phần tử Ở GIỮA bản tin: phần tử đầu và cuối clip không có khoảng lặng kề để
    sườn cưỡi lên, nên chúng vẫn ngắn nửa sườn. Điều đó không ảnh hưởng máy thu, vốn đồng bộ
    theo tỉ lệ giữa các phần tử chứ không theo hai phần tử ngoài cùng.
    """
    x = Encoder("en").to_audio("PARIS PARIS PARIS", wpm=wpm)
    marks = [n for on, n in envelope_runs(x) if on][1:-1]
    nominal = 1.2 / wpm * SAMPLE_RATE
    dits = [m for m in marks if m < 2 * nominal]
    dahs = [m for m in marks if m >= 2 * nominal]
    assert dits and dahs, marks
    dit, dah = float(np.median(dits)), float(np.median(dahs))
    assert abs(dit - nominal) < 0.03 * nominal, (dit, nominal)
    assert abs(dah / dit - 3.0) < 0.05, dah / dit


@pytest.mark.gate
@pytest.mark.parametrize("ext", [".wav", ".flac", ".ogg", ".mp3", ".aiff", ".oga"])
def test_message_survives_every_container(tmp_path, ext):
    """Bản tin ghi ra file rồi đọc lại phải giải đúng — kể cả qua nén mất dữ liệu.

    Đây là điều kiện để "gửi đi được": người nhận mở file bằng bất kỳ định dạng nào trong danh
    sách cũng phải đọc ra đúng bản tin. OGG nén xuống 10 KB và MP3 xuống 25 KB so với WAV 162 KB
    mà vẫn CER 0 %.
    """
    from pathlib import Path

    from morsedesk.api import Decoder
    from morsedesk.audio.io import load_audio, save_audio
    from morsedesk.metrics import cer

    if not Path("models/acoustic.onnx").is_file():
        pytest.skip("cần models/acoustic.onnx")
    text = "CQ CQ DE R1ABC K"
    path = tmp_path / f"bantin{ext}"
    save_audio(path, Encoder("en").to_audio(text, wpm=20), SAMPLE_RATE)
    y, sr = load_audio(path)
    assert cer(text, Decoder("en", engine="onnx").decode_array(y, sr).text) == 0.0
