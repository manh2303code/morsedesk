"""Cảnh 3D trang Nghe quét trái sang phải, và rê chuột trên mọi biểu đồ tín hiệu (người dùng 25/09).

- Cảnh 3D trực tiếp: đầu ghi đi từ trái sang phải rồi quay lại, cảnh đứng yên (trước đó cuộn ra sau).
- Rê chuột trên cảnh 3D, thác nước, phổ 2D: ô số đo nói từ ở đó, tần số, mức trên nền, thời điểm.
- Trang Nghe: điểm đang xem ở biểu đồ này được đánh dấu ở biểu đồ kia (cùng mốc giây).
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPoint

from morsedesk.api import Encoder, Word
from morsedesk.app.widgets.live_sweep import (
    COL_SAMPLES,
    FRAME_HOP,
    HALF_BINS,
    N_COLS,
    N_FFT,
    SWEEP_S,
    LiveSweep,
)
from morsedesk.app.widgets.ridge3d import REL_CAP_DB, Ridge3DView
from morsedesk.constants import SAMPLE_RATE


def _keyed_tone(hz: float, seconds: float, seed: int = 1) -> np.ndarray:
    """Tone bật/tắt đều 0,2 s trên nền nhiễu nhỏ — đủ để có đỉnh phổ rõ và khối rõ."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    gate = (np.floor(t / 0.2) % 2 == 0).astype(np.float32)
    rng = np.random.default_rng(seed)
    return (0.5 * np.sin(2 * np.pi * hz * t) * gate + 0.003 * rng.standard_normal(n)).astype(np.float32)


def _columns_for(n_samples: int) -> int:
    need = COL_SAMPLES + N_FFT - FRAME_HOP
    return 0 if n_samples < need else (n_samples - need) // COL_SAMPLES + 1


# ---------- dữ liệu cảnh quét ----------
def test_sweep_writes_left_to_right_and_wraps():
    sw = LiveSweep()
    assert sw.playhead() is None and sw.scene().z.shape == (2 * HALF_BINS + 1, N_COLS)
    x = _keyed_tone(900.0, 5.0)
    for i in range(0, len(x), 800):                       # khối 100 ms như AudioCapture
        sw.push(x[i:i + 800])
    n = _columns_for(len(x))
    assert sw.written == n and sw.cursor() == n
    assert sw.playhead() == pytest.approx(n / (N_COLS - 1))
    z = sw.scene().z
    assert z[:, :n].max() > 0.9 and np.all(z[:, n:] == 0.0)     # chưa ghi tới: phẳng
    # Qua hết một lượt: đầu ghi quay về trái, phần bên phải là lượt trước.
    y = _keyed_tone(900.0, SWEEP_S, seed=2)
    for i in range(0, len(y), 800):
        sw.push(y[i:i + 800])
    total = _columns_for(len(x) + len(y))
    assert sw.written == total and sw.cursor() == total % N_COLS
    k_new, k_old = sw.cursor() - 1, sw.cursor() + 5
    assert sw.column_time(k_new) == pytest.approx((total - 0.5) * COL_SAMPLES / SAMPLE_RATE)
    assert sw.column_time(k_old) == pytest.approx((total - N_COLS + 5.5) * COL_SAMPLES / SAMPLE_RATE)
    for k in (0, k_new, k_old, N_COLS - 1):
        assert sw.column_of(sw.column_time(k)) == k        # giây <-> ô đi hai chiều
    assert sw.column_of(0.0) is None                       # đã bị ghi đè


def test_sweep_band_follows_the_tone():
    """Chưa có tone từ bộ giải mã: dải ±250 Hz đặt quanh đỉnh phổ; bộ giải mã báo tone thì theo nó."""
    sw = LiveSweep()
    x = _keyed_tone(1100.0, 3.0)
    sw.push(x)
    assert abs(sw.center_hz() - 1100.0) <= sw.bin_hz
    sc = sw.scene()
    assert sc.freqs_hz[0] > sc.freqs_hz[-1]                 # hàng 0 = tần số cao nhất (sau cùng)
    assert sc.freqs_hz[0] - sc.freqs_hz[-1] == pytest.approx(2 * HALF_BINS * sw.bin_hz)
    sw.set_tone(1105.0)                                     # lệch nhỏ: không dời dải
    before = sw.center_hz()
    sw.set_tone(1108.0)
    assert sw.center_hz() == before
    sw.set_tone(600.0)
    assert sw.center_hz() == 600.0


def test_noise_only_stays_low():
    """Chỉ có nhiễu: không kéo giãn thành núi (dải tối thiểu 20 dB)."""
    sw = LiveSweep()
    sw.push(np.random.default_rng(3).standard_normal(3 * SAMPLE_RATE).astype(np.float32) * 0.01)
    assert float(np.median(sw.scene().z)) < 0.2


def test_clear_mid_session_keeps_the_time_base():
    """Nút Xóa giữa phiên: bộ giải mã vẫn đếm giây tiếp, nên mốc thời gian phải giữ nguyên."""
    sw = LiveSweep()
    sw.push(_keyed_tone(700.0, 3.0))
    n = sw.written
    sw.clear(keep_time=True)
    assert sw.written == n and np.all(sw.scene().z == 0.0)
    sw.clear()
    assert sw.written == 0


# ---------- chọn điểm dưới chuột trên cảnh 3D ----------
def _view(qtbot, z):
    w = Ridge3DView()
    qtbot.addWidget(w)
    w.resize(900, 300)
    w.set_surface(z)
    return w


def _screen(w, row, col, frac=0.5):
    n_rows, n_cols = w.surface().shape
    left, width, base, amp = w._row_geometry(row / (n_rows - 1))
    return QPoint(int(round(left + width * col / (n_cols - 1))),
                  int(round(base - w.heights(w.surface())[row, col] * amp * frac)))


def test_pick_respects_occlusion(qtbot):
    """Khối cao ở dải trước che dải sau: điểm trên khối thuộc dải trước; ngoài khối thì thuộc dải
    thấy được bên dưới; trên trời thì không có gì."""
    z = np.zeros((17, 120), np.float32)
    z[16, 40:60] = 1.0                                      # khối cao ở dải trước cùng
    z[3, 80:100] = 1.0                                      # khối ở dải sau
    w = _view(qtbot, z)
    assert w.cell_at(*_xy(_screen(w, 16, 50))) == (16, 50)
    assert w.cell_at(*_xy(_screen(w, 3, 90))) == (3, 90)
    r, c = w.cell_at(*_xy(_screen(w, 8, 20)))               # nền phẳng: không có khe chết
    assert abs(r - 8) <= 1 and abs(c - 20) <= 1
    assert w.cell_at(450, 2) is None


def _xy(p: QPoint) -> tuple[int, int]:
    return p.x(), p.y()


def test_hover_shows_readout_and_signals(qtbot):
    z = np.zeros((17, 120), np.float32)
    z[16, 40:60] = 1.0
    w = _view(qtbot, z)
    w.describe = lambda r, c: [(f"row {r}", "value"), (f"col {c}", "muted")]
    seen = []
    w.hover_changed.connect(seen.append)
    w.hover_at(_screen(w, 16, 50))
    assert w.hover() == (16, 50) and seen[-1] == (16, 50)
    assert w.readout.lines() == [("row 16", "value"), ("col 50", "muted")]
    w.hover_at(None)
    assert w.hover() is None and seen[-1] is None and w.readout.isHidden()


def test_sweep_shape_sinks_the_old_sweep_and_leaves_a_gap(qtbot):
    w = _view(qtbot, np.ones((4, 101), np.float32))
    w.ahead_level, w.gap_width, w.rise_width = 0.35, 0.05, 0.004
    w.set_playhead(0.5)
    h = w.heights(w.surface())
    assert np.allclose(h[:, :49], 1.0)                      # lượt đang ghi: đủ cao
    assert np.allclose(h[:, 50:55], 0.0)                    # khe trống ngay trước đầu ghi
    assert np.allclose(h[:, 56:], 0.35)                     # lượt trước: hạ thấp, vẫn thấy hình


# ---------- trang Nghe ----------
@pytest.fixture
def live(qtbot, monkeypatch):
    from tests.app.test_live_page import _page

    page, worker = _page(qtbot, monkeypatch)
    page.resize(1100, 800)
    page.show()
    return page, worker


def test_live_3d_sweeps_with_the_audio(live):
    page, worker = live
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20, tone_hz=720.0, snr_db=20, seed=4)
    for i in range(0, len(x), 800):
        worker.block_ready.emit(x[i:i + 800])
    assert page.ridge.surface().shape == (2 * HALF_BINS + 1, N_COLS)
    assert page.ridge.playhead() == pytest.approx(page.sweep.playhead())
    assert "± 250" in page.ridge.depth_label
    assert page.ridge.front_ticks[0][1].startswith("0") and page.ridge.front_ticks[-1][0] == 1.0


def test_live_hover_links_the_two_charts_and_names_the_word(live):
    from tests.app.test_live_page import _update

    page, worker = live
    x = Encoder("en").to_audio("CQ CQ DE R1ABC", wpm=20, tone_hz=720.0, snr_db=20, seed=4)
    for i in range(0, len(x), 800):
        worker.block_ready.emit(x[i:i + 800])
    words = [Word("CQ", 0.0, 4.0, 0.97)]
    worker.stats_ready.emit(_update(words, []))
    sc = page._scene
    r, c = divmod(int(sc.z.argmax()), sc.z.shape[1])
    page.ridge.hover_at(_screen(page.ridge, r, c, frac=0.6))
    r, c = page.ridge.hover()                               # ô THẤY được (dải trước có thể che)
    t = page.sweep.column_time(c)
    assert t is not None and t < 4.0
    lines = page.ridge.readout.lines()
    assert lines[0] == ("CQ", "word") and any("Hz" in s for s, _ in lines)
    assert any("above noise" in s for s, _ in lines) and any("ago" in s for s, _ in lines)
    mark_t, mark_hz = page.waterfall.marker()               # thác nước chỉ đúng điểm đó
    assert mark_t == pytest.approx(t) and mark_hz == pytest.approx(float(sc.freqs_hz[r]))
    page.ridge.hover_at(None)
    assert page.waterfall.marker() is None
    # Ngược lại: rê trên thác nước ở chỗ còn trên cảnh 3D -> cảnh 3D hiện dấu cùng giây.
    wf = page.waterfall
    y = int(wf.height() * (1 - 720.0 / 2000.0))
    wf.hover_at(QPoint(wf.width() - 3, y))
    t2, hz2 = wf.hover()
    assert wf.readout.lines() and abs(hz2 - 720.0) < 30
    row, col = page.ridge.marker()
    assert col == page.sweep.column_of(t2) and row is not None
    wf.hover_at(None)
    assert page.ridge.marker() is None


def test_live_clear_button_keeps_time_but_start_resets(live):
    page, worker = live
    worker.block_ready.emit(_keyed_tone(700.0, 3.0))
    n, cols = page.sweep.written, page.waterfall._cols_total
    page.clear()
    assert page.sweep.written == n and page.waterfall._cols_total == cols
    assert page.waterfall.point_at(page.waterfall.width() - 2, 10) is None   # đã xóa: không có số đo
    page.listen_button.setChecked(True)
    page._on_listen_clicked()
    assert page.sweep.written == 0 and page.waterfall._cols_total == 0


# ---------- trang Giải mã ----------
def test_spectrogram_hover_readout(qtbot):
    from morsedesk.app.widgets.spectrogram import SpectrogramView
    from morsedesk.app.worker import Spectrogram

    v = SpectrogramView()
    qtbot.addWidget(v)
    v.resize(800, 300)
    v.show()
    x = Encoder("en").to_audio("E E", wpm=20, tone_hz=700.0)
    v.set_spectrogram(Spectrogram.from_audio(x))
    qtbot.wait(50)
    got = []
    v.describe = lambda t, hz, rel: got.append((t, hz, rel)) or [(f"{hz:.0f} Hz", "value")]
    v.hover_at(0.33, 700.0)                                 # giữa chấm E đầu tiên (đệm 0,3 s)
    t, hz, rel = got[-1]
    assert v.hover() is not None and v.hover_v.isVisible() and v.readout.lines()
    assert abs(t - 0.33) < 0.05 and abs(hz - 700.0) < 20 and rel == pytest.approx(REL_CAP_DB, abs=6)
    v.hover_at(None)
    assert v.hover() is None and not v.hover_v.isVisible() and v.readout.isHidden()


def test_decode_3d_hover_names_the_decoded_word(qtbot, tiny_lm_dir, tmp_path, wav_cq):
    from tests.app.test_decode_page import _page, _wait_idle

    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        page.resize(1100, 800)
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.load_file(wav_cq)
        qtbot.waitUntil(lambda: page.result is not None, timeout=5000)
        _wait_idle(qtbot, page)
        ridge = page.ridge
        z = ridge.surface()
        r, c = divmod(int(z.argmax()), z.shape[1])
        ridge.hover_at(_screen(ridge, r, c, frac=0.6))
        lines = ridge.readout.lines()
        assert lines and lines[0][1] == "word" and lines[0][0] in page.result.text.split()
        assert lines[-1][0].endswith(" s")
    finally:
        worker.stop()


# ---------- ba file mẫu ----------
@pytest.mark.parametrize("lang", ["en", "ru", "kk"])
def test_hello_samples_are_pure_morse(lang):
    """Người dùng 25/09: mẫu "Xin chào" phải thuần Morse, không nhiễu — khoảng lặng là số 0 tuyệt
    đối, chỉ một tone 700 Hz."""
    import soundfile as sf

    from morsedesk.app.decode_page import SAMPLE_FILES, SAMPLES_DIR

    x, sr = sf.read(str(SAMPLES_DIR / SAMPLE_FILES[lang]), dtype="int16")
    assert sr == SAMPLE_RATE
    assert np.all(x[: int(0.29 * sr)] == 0) and np.all(x[-int(0.29 * sr):] == 0)   # đệm đầu/cuối
    silent = np.abs(x.astype(np.int32)) == 0
    assert silent.mean() > 0.3                             # các khoảng lặng giữa dấu cũng là số 0
    spec = np.abs(np.fft.rfft(x.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    assert abs(freqs[spec.argmax()] - 700.0) < 2.0
    far = spec[np.abs(freqs - 700.0) > 400.0]
    assert far.max() < spec.max() * 1e-3                   # xa tone > 400 Hz: dưới 60 dB
