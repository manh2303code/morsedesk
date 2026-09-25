"""Khối Tín hiệu (3D / phổ 2D) của trang Giải mã và trang Nghe — người dùng 25/09:

- khung 12 s BÁM con trỏ, đèn ở GIỮA; chỉ nửa khung đầu và nửa khung cuối thì đèn đi từ mép vào
  giữa và từ giữa ra mép; phần đã nghe bên trái, phần chưa nghe chìm bên phải;
- kéo / lăn để lướt về trước, về sau (thôi bám tới khi bấm "theo con trỏ", bấm phát, bấm vào biểu đồ);
- bấm vào biểu đồ để nghe từ chỗ đó;
- trang Nghe cùng cách, nhưng "cuối" là bây giờ (đèn ở mép phải), và chỉ nghe lại khi đã dừng thu.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from morsedesk.api import Encoder, Word
from morsedesk.app.widgets.ridge3d import SUBMERGED, Ridge3DView
from morsedesk.app.widgets.signal_columns import (
    COL_S,
    LEAD,
    MAX_TILES,
    TILE_COLS,
    FileColumns,
    Levels,
    LiveColumns,
    columns_db,
    span_needed,
)
from morsedesk.app.widgets.signal_panel import SignalPanel
from morsedesk.app.widgets.signal_view import WINDOW_S, Timeline
from morsedesk.constants import SAMPLE_RATE


def _noise_tone(seconds: float, hz: float = 700.0, seed: int = 1) -> np.ndarray:
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    gate = (np.floor(t / 0.2) % 2 == 0)
    rng = np.random.default_rng(seed)
    return (0.5 * np.sin(2 * np.pi * hz * t) * gate + 0.01 * rng.standard_normal(n)).astype(np.float32)


# ---------- khung nhìn ----------
def test_follow_pins_the_beam_in_the_middle_except_the_first_and_last_half_window():
    tl = Timeline()
    tl.reset(0.0, 60.0, fit=True)
    for cursor, t0, frac in ((3.0, 0.0, 0.25), (6.0, 0.0, 0.5), (30.0, 24.0, 0.5), (54.0, 48.0, 0.5),
                             (57.0, 48.0, 0.75), (60.0, 48.0, 1.0)):
        tl.set_cursor(cursor)
        assert tl.t0() == pytest.approx(t0) and tl.frac(cursor) == pytest.approx(frac), cursor


def test_short_file_fits_the_window_and_live_keeps_now_at_the_right_edge():
    tl = Timeline()
    tl.reset(0.0, 4.0, fit=True)
    assert tl.span() == pytest.approx(4.0)
    tl.reset(0.0, 0.0, fit=False)                  # trang Nghe: khung 12 s ngay từ đầu
    tl.update(hi=5.0, cursor=5.0)
    assert tl.window() == (0.0, WINDOW_S) and tl.frac(5.0) == pytest.approx(5 / 12)
    tl.update(hi=30.0, cursor=30.0)
    assert tl.window() == pytest.approx((18.0, 30.0)) and tl.frac(30.0) == pytest.approx(1.0)


def test_panning_detaches_and_follow_brings_it_back():
    tl = Timeline()
    tl.reset(0.0, 60.0)
    tl.set_cursor(30.0)
    seen = []
    tl.follow_changed.connect(seen.append)
    tl.pan(-5.0)
    assert not tl.following() and tl.t0() == pytest.approx(19.0) and seen == [False]
    tl.set_cursor(31.0)                            # đang phát tiếp: khung đứng yên chỗ người dùng xem
    assert tl.t0() == pytest.approx(19.0)
    tl.pan(-100.0)
    assert tl.t0() == 0.0                          # kẹp ở đầu
    tl.set_follow(True)
    assert tl.following() and tl.t0() == pytest.approx(25.0)
    short = Timeline()
    short.reset(0.0, 4.0)
    short.pan(-1.0)                                # file ngắn hơn khung: không có gì để lướt
    assert short.following()


# ---------- phổ theo cột ----------
def test_file_columns_are_the_same_across_tiles_and_as_live():
    """Cùng một lưới cột: tính theo ô (file) = tính một lượt = tính theo khối 100 ms (trực tiếp)."""
    x = _noise_tone(TILE_COLS * COL_S * 2.3)
    fc = FileColumns(x)
    whole = fc.columns(0, fc.n_cols)
    seg = np.concatenate([np.zeros(LEAD, np.float32), x, np.zeros(span_needed(1), np.float32)])
    direct = columns_db(seg, fc.n_cols)
    assert np.allclose(whole, direct, atol=1e-3)
    across = fc.columns(TILE_COLS - 5, TILE_COLS + 5)             # vắt qua ranh hai ô
    assert np.allclose(across, direct[:, TILE_COLS - 5:TILE_COLS + 5], atol=1e-3)
    assert np.isnan(fc.columns(-3, 0)).all() and np.isnan(fc.columns(fc.n_cols, fc.n_cols + 2)).all()
    live = LiveColumns(60.0)
    for i in range(0, len(x), 800):
        live.push(x[i:i + 800])
    lo, hi = live.col_range()
    assert np.allclose(live.columns(lo, hi), direct[:, lo:hi], atol=0.05)      # float16


def test_column_j_holds_the_sound_of_its_own_32_ms():
    x = np.zeros(3 * SAMPLE_RATE, np.float32)
    s0, s1 = SAMPLE_RATE, int(1.5 * SAMPLE_RATE)
    x[s0:s1] = 0.5 * np.sin(2 * np.pi * 700 * np.arange(s1 - s0) / SAMPLE_RATE)
    db = FileColumns(x).columns(0, int(3 / COL_S))
    tone = db[int(round(700 / 31.25))]
    on = np.flatnonzero(tone > tone.max() - 6)            # mép dấu = nửa công suất
    assert abs(on[0] * COL_S - 1.0) <= COL_S and abs((on[-1] + 1) * COL_S - 1.5) <= COL_S


def test_file_tiles_are_bounded():
    fc = FileColumns(np.zeros(int((MAX_TILES + 6) * TILE_COLS * COL_S * SAMPLE_RATE), np.float32))
    for k in range(MAX_TILES + 5):
        fc.columns(k * TILE_COLS, k * TILE_COLS + 1)
    assert len(fc._tiles) <= MAX_TILES


def test_live_history_is_bounded_and_replayable():
    live = LiveColumns(keep_s=2.0)
    x = _noise_tone(5.0)
    for i in range(0, len(x), 800):
        live.push(x[i:i + 800])
    lo, hi = live.col_range()
    assert hi - lo == live.keep_cols and live.now_s == pytest.approx(5.0)
    start, audio = live.recording()
    assert start == pytest.approx(3.0, abs=COL_S) and len(audio) == pytest.approx(2 * SAMPLE_RATE, abs=256)
    assert np.allclose(audio[:100], x[len(x) - len(audio):][:100], atol=1e-3)
    n = live.written
    live.clear(keep_time=True)                     # nút Xóa giữa phiên: mốc thời gian giữ nguyên
    assert live.written == n and live.col_range() == (n, n) and len(live.recording()[1]) == 0


def test_levels_keep_noise_low_and_clean_files_crisp():
    rng = np.random.default_rng(3)
    noise = 10 * np.log10(rng.exponential(1.0, (17, 400)) + 1e-12)
    assert float(np.median(Levels.of(noise, 20.0, 30.0).scale(noise, 1.3))) < 0.2    # như cảnh 3D
    clean = np.full((17, 400), -120.0)
    clean[8, 100:150] = 30.0
    clean[7, 100:150] = 0.0                        # đuôi Hann -30 dB
    z = Levels.of(clean, 20.0, 30.0).scale(clean)
    assert z[8, 120] == 1.0 and z[7, 120] == 0.0 and z[0, 0] == 0.0


# ---------- cảnh 3D: chọn điểm, đèn, chuột ----------
def _view(qtbot, z):
    w = Ridge3DView()
    qtbot.addWidget(w)
    w.resize(900, 300)
    n = z.shape[1]
    w.set_surface(z, np.linspace(0, 1, n), np.arange(n) * 0.1, np.linspace(950, 450, z.shape[0]),
                  np.full(z.shape, 12.0, np.float32))
    return w


def _screen(w, row, col, frac=0.5):
    n_rows, n_cols = w.surface().shape
    left, width, base, amp = w._row_geometry(row / (n_rows - 1))
    return QPoint(int(round(left + width * w.xs()[col])),
                  int(round(base - w.heights(w.surface())[row, col] * amp * frac)))


def test_pick_respects_occlusion_and_hover_describes_the_point(qtbot):
    z = np.zeros((17, 120), np.float32)
    z[16, 40:60] = 1.0                             # khối cao ở dải trước cùng
    z[3, 80:100] = 1.0                             # khối ở dải sau
    w = _view(qtbot, z)
    p = _screen(w, 16, 50)
    assert w.cell_at(p.x(), p.y()) == (16, 50)
    p = _screen(w, 3, 90)
    assert w.cell_at(p.x(), p.y()) == (3, 90)
    p = _screen(w, 8, 20)
    r, c = w.cell_at(p.x(), p.y())                 # nền phẳng: không có khe chết
    assert abs(r - 8) <= 1 and abs(c - 20) <= 1
    assert w.cell_at(450, 2) is None
    got = []
    w.describe = lambda t, hz, rel: got.append((t, hz, rel)) or [("x", "value")]
    w.hover_at(_screen(w, 16, 50))
    assert got[-1] == pytest.approx((5.0, 450.0, 12.0)) and w.readout.lines() == [("x", "value")]
    w.hover_at(None)
    assert w.hover() is None and w.readout.isHidden()


def test_heard_part_rises_and_the_rest_sinks_even_with_the_beam_off_screen(qtbot):
    w = _view(qtbot, np.ones((4, 101), np.float32))
    w.set_playhead(0.5)
    h = w.heights(w.surface())
    assert np.allclose(h[:, :48], 1.0) and np.allclose(h[:, 51:], SUBMERGED)
    w.set_playhead(1.7)                            # đèn đã qua khỏi khung (người dùng lướt lùi)
    assert np.allclose(w.heights(w.surface()), 1.0)
    w.set_playhead(-0.4)                           # đèn chưa tới khung (lướt tới trước)
    assert np.allclose(w.heights(w.surface()), SUBMERGED)
    w.set_playhead(None)
    assert np.allclose(w.heights(w.surface()), 1.0)


def _mouse(w, kind, pos, buttons):
    ev = QMouseEvent(kind, QPointF(pos), w.mapToGlobal(QPointF(pos)), Qt.MouseButton.LeftButton,
                     buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w, ev)


def test_drag_pans_click_seeks_wheel_scrolls(qtbot):
    from PySide6.QtGui import QWheelEvent

    z = np.zeros((17, 120), np.float32)
    w = _view(qtbot, z)
    pans, seeks = [], []
    w.pan_requested.connect(pans.append)
    w.seek_requested.connect(seeks.append)
    left, width, base, _ = w._row_geometry(1.0)
    a = QPoint(int(left + width * 0.5), int(base - 5))
    _mouse(w, QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton)
    _mouse(w, QEvent.Type.MouseButtonRelease, a, Qt.MouseButton.NoButton)
    assert pans == [] and seeks and abs(seeks[-1] - 0.5) < 0.02            # bấm = nghe từ đó
    _mouse(w, QEvent.Type.MouseButtonPress, a, Qt.MouseButton.LeftButton)
    b = QPoint(a.x() + int(width * 0.25), a.y())
    _mouse(w, QEvent.Type.MouseMove, b, Qt.MouseButton.LeftButton)
    _mouse(w, QEvent.Type.MouseButtonRelease, b, Qt.MouseButton.NoButton)
    assert len(seeks) == 1 and sum(pans) == pytest.approx(-0.25, abs=0.01)  # kéo sang phải = xem lùi
    ev = QWheelEvent(QPointF(a), w.mapToGlobal(QPointF(a)), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(w, ev)
    assert pans[-1] > 0                            # lăn xuống = về sau


# ---------- khối Tín hiệu ----------
@pytest.fixture
def panel(qtbot):
    p = SignalPanel()
    qtbot.addWidget(p)
    p.resize(1000, 320)
    p.show()
    x = Encoder("en").to_audio("CQ CQ DE R1ABC R1ABC K QTH MOSCOW " * 2, wpm=20, snr_db=15, seed=2)
    p.set_source(FileColumns(x), fit=True)
    p.set_tone(700.0)
    p.set_words([Word("CQ", 0.3, 1.2, 0.9), Word("MOSCOW", 20.0, 22.0, 0.9)])
    return p


def test_playback_follows_with_the_beam_in_the_middle(panel):
    dur = panel.timeline.data_range()[1]
    assert dur > 30
    panel.play_position(20.0, True)
    panel.flush()
    assert panel.timeline.window() == pytest.approx((14.0, 26.0))
    assert panel.ridge.playhead() == pytest.approx(0.5)
    panel.play_position(2.0, True)                 # nhảy về đầu (thanh trượt): đèn ở 1/6 khung
    panel.flush()
    assert panel.ridge.playhead() == pytest.approx(2.0 / 12.0)
    panel.play_position(None, False)               # dừng/nghe hết: cả cảnh sáng đều
    panel.flush()
    assert panel.ridge.playhead() is None


def test_user_scroll_holds_until_play_or_jump_and_the_button_shows(panel):
    panel.play_position(20.0, True)
    panel.ridge.pan_requested.emit(-0.5)           # kéo lùi nửa khung
    assert not panel.timeline.following() and not panel.follow_button.isHidden()
    assert panel.timeline.t0() == pytest.approx(8.0)
    panel.play_position(20.05, True)               # đang phát tiếp: khung giữ chỗ đang xem
    panel.flush()
    assert panel.timeline.t0() == pytest.approx(8.0)
    assert panel.ridge.playhead() == pytest.approx((20.05 - 8.0) / 12.0)
    panel.follow_button.click()
    assert panel.timeline.following() and panel.follow_button.isHidden()
    panel.strip.pan_requested.emit(0.3)
    panel.play_position(30.0, True)                # nhảy (bấm từ / thanh trượt): bám lại
    assert panel.timeline.following() and panel.timeline.frac(30.0) == pytest.approx(0.5)
    panel.strip.pan_requested.emit(0.3)
    panel.play_position(30.05, False)
    panel.play_position(30.1, True)                # bấm phát lại sau khi tạm dừng: bám lại
    assert panel.timeline.following()


def test_click_asks_to_play_from_that_moment_in_both_views(panel):
    got = []
    panel.seek_requested.connect(got.append)
    panel.play_position(20.0, True)
    panel.flush()
    panel.ridge.seek_requested.emit(0.25)
    panel.view_2d_button.click()
    panel.strip.seek_requested.emit(0.75)
    assert got == pytest.approx([14.0 + 3.0, 14.0 + 9.0])
    assert panel.strip.cursor() == pytest.approx(0.5)            # 2D: cùng khung, cùng con trỏ


def test_hover_names_the_word_frequency_level_and_time(panel):
    lines = panel._describe(20.5, 705.4, 18.2)
    assert lines[0] == ("MOSCOW", "word") and lines[1] == ("705 Hz", "value")
    assert "+18" in lines[2][0] and lines[3] == ("20.50 s", "muted")
    assert panel._describe(10.0, 700.0, 0.0)[0][1] == "value"          # giữa hai từ: không có từ


def test_render_budget_coalesces_automatic_updates(panel, qtbot):
    """Con trỏ tự chạy mà khung vẽ đắt: gộp nhịp, vẽ trễ một chút theo trạng thái mới nhất; thao
    tác của người dùng thì vẽ ngay."""
    panel.play_position(20.0, True)
    panel.flush()
    panel.ridge.last_paint_ms = 60.0               # giả như một khung 3D tốn 60 ms
    n = panel.render_count
    panel.play_position(20.05, True)
    panel.play_position(20.10, True)
    assert panel.render_count == n and panel._defer.isActive()
    qtbot.waitUntil(lambda: panel.render_count == n + 1, timeout=1000)
    assert panel.ridge.playhead() == pytest.approx(0.5) and panel.timeline.cursor() == pytest.approx(20.10)
    panel.ridge.pan_requested.emit(-0.1)
    assert panel.render_count == n + 2             # kéo: vẽ ngay


def test_only_the_visible_view_is_built(panel):
    panel.play_position(20.0, True)
    panel.flush()
    assert panel.ridge.surface().size and not panel.strip.has_image()
    panel.hide()
    n = panel.render_count
    panel.play_position(21.0, True)
    panel.flush()
    assert panel.render_count == n                 # trang bị che: không dựng gì


# ---------- trang Giải mã ----------
def test_decode_page_click_on_the_chart_plays_from_there(qtbot, tiny_lm_dir, tmp_path, wav_cq, monkeypatch):
    from tests.app.test_decode_page import _page, _wait_idle

    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        page.resize(1100, 800)
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.load_file(wav_cq)
        qtbot.waitUntil(lambda: page.result is not None, timeout=5000)
        _wait_idle(qtbot, page)
        calls = []
        monkeypatch.setattr(page.player, "seek", lambda t: calls.append(("seek", t)))
        monkeypatch.setattr(page.player, "play", lambda: calls.append(("play",)))
        page.signal_panel.timeline.pan(1.0)
        page.ridge.seek_requested.emit(0.5)
        t = page.signal_panel.timeline.time_at(0.5)
        assert calls == [("seek", pytest.approx(t)), ("play",)]
        assert page.signal_panel.timeline.following()
        z = page.ridge.surface()
        r, c = divmod(int(z.argmax()), z.shape[1])
        page.ridge.hover_at(_screen(page.ridge, r, c, frac=0.6))
        lines = page.ridge.readout.lines()
        assert lines and lines[0][1] == "word" and lines[0][0] in page.result.text.split()
    finally:
        worker.stop()


# ---------- trang Nghe ----------
@pytest.fixture
def live(qtbot, monkeypatch):
    from tests.app.test_live_page import _page

    page, worker = _page(qtbot, monkeypatch)
    page.resize(1100, 800)
    page.show()
    return page, worker


def _feed(worker, x):
    for i in range(0, len(x), 800):
        worker.block_ready.emit(x[i:i + 800])


def test_live_follows_now_at_the_right_edge_and_can_look_back(live):
    page, worker = live
    worker.listening.emit(True)
    _feed(worker, _noise_tone(5.0))
    panel = page.signal_panel
    panel.flush()
    assert panel.timeline.window() == (0.0, WINDOW_S)
    assert panel.ridge.playhead() == pytest.approx(panel.timeline.frac(page.columns.written * COL_S))
    _feed(worker, _noise_tone(15.0, seed=2))
    panel.flush()
    now = page.columns.written * COL_S
    assert panel.timeline.window()[1] == pytest.approx(now) and panel.ridge.playhead() == pytest.approx(1.0)
    panel.ridge.pan_requested.emit(-0.5)           # xem lại 6 s trước
    assert not panel.timeline.following() and panel.follow_button.text() == "Back to live"
    t0 = panel.timeline.t0()
    _feed(worker, _noise_tone(1.0, seed=3))
    assert panel.timeline.t0() == pytest.approx(t0)        # âm thanh vẫn vào nhưng khung giữ chỗ
    panel.follow_button.click()
    assert panel.timeline.window()[1] == pytest.approx(page.columns.written * COL_S)


def test_live_click_moves_the_view_while_listening_and_replays_after_stop(live, monkeypatch):
    page, worker = live
    worker.listening.emit(True)
    _feed(worker, _noise_tone(20.0))
    calls = []
    monkeypatch.setattr(page.player, "seek", lambda t: calls.append(("seek", t)))
    monkeypatch.setattr(page.player, "play", lambda: calls.append(("play",)))
    page.signal_panel.seek_requested.emit(4.0)     # đang thu: KHÔNG phát ra loa (micro thu lại)
    assert calls == [] and not page.signal_panel.timeline.following()
    assert page.signal_panel.timeline.t0() == pytest.approx(0.0)
    worker.listening.emit(False)
    assert page.player.isVisibleTo(page) and page.player.playback.duration_s == pytest.approx(20.0, abs=0.1)
    page.signal_panel.seek_requested.emit(4.0)
    assert calls == [("seek", pytest.approx(4.0)), ("play",)]
    page.word_view.word_clicked.emit(7.5)          # bấm một từ: cũng nghe từ đó
    assert calls[-2] == ("seek", pytest.approx(7.5))
    worker.listening.emit(True)                    # thu lại: thanh phát ẩn
    assert page.player.isHidden()


def test_live_clear_mid_session_keeps_the_time_base(live):
    page, worker = live
    worker.listening.emit(True)
    _feed(worker, _noise_tone(3.0))
    n = page.columns.written
    page.clear()
    assert page.columns.written == n and page.columns.col_range() == (n, n)
    page.listen_button.setChecked(True)
    page._on_listen_clicked()
    assert page.columns.written == 0


# ---------- ba file mẫu ----------
@pytest.mark.parametrize("lang", ["en", "ru", "kk"])
def test_hello_samples_are_pure_morse(lang):
    """Người dùng 25/09: mẫu "Xin chào" phải thuần Morse, không nhiễu — khoảng lặng là số 0 tuyệt
    đối, chỉ một tone 700 Hz."""
    import soundfile as sf

    from morsedesk.app.decode_page import SAMPLE_FILES, SAMPLES_DIR

    x, sr = sf.read(str(SAMPLES_DIR / SAMPLE_FILES[lang]), dtype="int16")
    assert sr == SAMPLE_RATE
    assert np.all(x[: int(0.29 * sr)] == 0) and np.all(x[-int(0.29 * sr):] == 0)
    assert (np.abs(x.astype(np.int32)) == 0).mean() > 0.3
    spec = np.abs(np.fft.rfft(x.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    assert abs(freqs[spec.argmax()] - 700.0) < 2.0
    assert spec[np.abs(freqs - 700.0) > 400.0].max() < spec.max() * 1e-3
