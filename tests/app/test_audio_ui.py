"""Giao diện với luồng thiết bị âm thanh + ba lỗi người dùng báo 27/09.

1. Từ dài hơn một dòng (`1232142345v23`) bị cắt ở mép phải băng Morse — chữ `v` biến mất.
2. Gõ thêm vào ô văn bản lúc đang phát làm mất khung sáng quanh chữ đang kêu -> khóa khi đang phát.
3. Đang phát rồi bấm Nghe -> app đơ: đang nghe thì không phát; driver kẹt thì báo, không treo; thoát
   được kể cả khi driver kẹt.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt

from morsedesk.api import Word
from morsedesk.app.encode_page import EncodePage
from morsedesk.app.settings import AppSettings
from morsedesk.app.widgets.morse_tape import MorseTape
from morsedesk.app.widgets.word_view import WordView
from morsedesk.app.worker import Player


def _encode_page(qtbot, tmp_path, width=900):
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = EncodePage(Player(), settings)
    qtbot.addWidget(page)
    page.resize(width, 700)
    page.show()
    return page


# ---- 1. từ dài ----
def test_long_word_wraps_inside_the_word_on_the_morse_tape(qtbot, tmp_path):
    page = _encode_page(qtbot, tmp_path)
    page.text_edit.setPlainText("1232142345v23 462 456 3245 62346 152434 32156 2134")
    qtbot.wait(10)
    tape = page.tape.tape
    width = tape.width()
    letters = [ch for w in tape.words() for ch, _ in w]
    assert "V" in letters and len(letters) == tape.item_count()
    for i in range(tape.item_count()):
        r = tape.item_rect(i)
        assert r.right() - 9 <= width, (i, r, width)        # không chữ nào vẽ ra ngoài mép phải
    first_word = [tape._items[i][1] for i in range(13)]     # 13 chữ của `1232142345V23`
    assert len(set(first_word)) >= 2                        # từ đầu nằm trên nhiều dòng
    assert tape._breaks                                     # có dấu nối cuối dòng


def test_tape_keeps_short_words_whole():
    tape = MorseTape()
    tape.resize(400, 100)
    tape.set_words([[("S", "..."), ("O", "---"), ("S", "...")]] * 6)
    ys = {}
    for _x, y, _ch, _p in tape._items:
        ys.setdefault(y, 0)
        ys[y] += 1
    assert all(n % 3 == 0 for n in ys.values())             # SOS không bao giờ bị ngắt giữa từ
    assert not tape._breaks


def test_word_view_wraps_a_word_longer_than_the_line(qtbot):
    view = WordView()
    qtbot.addWidget(view)
    view.resize(420, 300)
    view.show()
    digits = "1234567890" * 12
    view.set_words([Word("CQ", 0.0, 1.0, 1.0, []), Word(digits, 1.0, 9.0, 1.0, []), Word("K", 9.0, 9.5, 1.0, [])])
    qtbot.wait(10)
    canvas = view.canvas()
    pieces = canvas.word_pieces(1)
    assert len(pieces) >= 2 and "".join(t for _, t in pieces) == digits
    assert all(r.right() <= canvas.width() for r, _ in pieces)
    last, _ = pieces[-1]
    assert canvas.index_at(last.center()) == 1              # bấm vào mảnh sau vẫn là từ đó
    assert canvas.index_at(canvas.rects[2].center()) == 2


# ---- 2. khóa văn bản khi đang phát ----
def test_text_and_timing_are_locked_while_playing(qtbot, tmp_path, fake_sounddevice):
    page = _encode_page(qtbot, tmp_path)
    page.text_edit.setPlainText("SOS")
    page.farnsworth_check.setChecked(False)
    page.play_button.click()
    assert page.playback.playing and page.is_locked()
    assert page.text_edit.isReadOnly() and not page.charmap.isEnabled()
    assert not page.wpm_spin.isEnabled() and not page.profile_combo.isEnabled()
    assert page.lock_label.isVisible() and page.lock_label.text()
    page.text_edit.setFocus()
    qtbot.keyClicks(page.text_edit, "XYZ")                  # người dùng gõ: không ăn
    page._insert_char("Ә")                                  # bảng chữ: cũng không
    assert page.current_text() == "SOS"
    page.stop_button.click()
    assert not page.is_locked() and not page.text_edit.isReadOnly() and page.wpm_spin.isEnabled()
    assert not page.farnsworth_spin.isEnabled()             # ô số theo đúng ô đánh dấu của nó
    assert not page.lock_label.isVisible()


def test_lock_lifts_when_playback_ends_by_itself(qtbot, tmp_path, fake_sounddevice):
    page = _encode_page(qtbot, tmp_path)
    page.text_edit.setPlainText("E")
    page.play_button.click()
    stream = fake_sounddevice.OutputStream.instances[-1]
    while not stream.stopped_by_callback:
        stream.pump()
    page._tick_playback()
    assert not page.is_locked() and not page.text_edit.isReadOnly()


# ---- 3. một thiết bị âm thanh cho cả app ----
def test_listening_disables_play_everywhere_and_explains_why(qtbot, tmp_path, fake_sounddevice):
    page = _encode_page(qtbot, tmp_path)
    page.text_edit.setPlainText("SOS")
    page.play_button.click()
    assert page.playback.playing
    from morsedesk.audio.capture import AudioCapture

    cap = AudioCapture()
    cap.start()                                             # bấm Nghe: luồng thiết bị dừng tiếng đang phát
    page.set_listening(True)
    page._tick_playback()
    assert not page.playback.playing and not page.is_locked()
    assert not page.play_button.isEnabled() and "microphone" in page.play_button.toolTip()
    page.play()                                             # gọi thẳng (bấm chữ trên băng): từ chối, có lời
    assert page.banner.level == "warning" and "Stop listening" in page.banner.text()
    cap.stop()
    page.set_listening(False)
    assert page.play_button.isEnabled() and page.play_button.toolTip() == ""


def test_player_bar_is_blocked_while_listening_and_recovers(qtbot, fake_sounddevice):
    import numpy as np

    from morsedesk.app.widgets.player_bar import PlayerBar

    bar = PlayerBar()
    qtbot.addWidget(bar)
    bar.load(np.zeros(8000, dtype=np.float32), 8000)
    bar.play()
    assert bar.playback.playing
    bar.set_listening(True)
    bar.playback._engine_close()                           # như luồng thiết bị nhường micro
    bar._tick()
    assert not bar._timer.isActive() and not bar.play_button.isEnabled()
    bar.set_listening(False)
    assert bar.play_button.isEnabled()


def test_late_open_error_reaches_the_player_banner(qtbot, fake_sounddevice):
    import numpy as np

    from morsedesk.app.widgets.player_bar import PlayerBar
    from morsedesk.audio.playback import PlaybackError

    bar = PlayerBar()
    qtbot.addWidget(bar)
    got = []
    bar.error.connect(got.append)
    bar.load(np.zeros(8000, dtype=np.float32), 8000)
    bar.play()
    bar.playback._active = False                            # như lỗi mở tới muộn từ luồng thiết bị
    bar.playback.error = PlaybackError("the sound device is not responding (open output)", "stuck")
    bar._tick()
    assert got and "not responding" in got[0] and "restart the computer" in got[0]
    assert bar.play_button.isEnabled()                      # lỗi tạm thời: bấm lại được


def test_main_window_warns_when_the_sound_device_is_stuck(qtbot, tiny_lm_dir, tmp_path, monkeypatch):
    from morsedesk.app.live_worker import LiveWorker
    from morsedesk.app.main import I18N_DIR
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.worker import DecoderWorker
    from morsedesk.audio import engine as engine_mod

    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    live = LiveWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)      # không start
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    win = MainWindow(worker, Player(), settings, I18N_DIR, live=live)
    qtbot.addWidget(win)
    eng = engine_mod.default_engine()
    monkeypatch.setattr(eng, "stuck", lambda: "open output")
    win.check_audio_health()
    assert win.banner.level == "warning" and "not responding" in win.banner.text()
    monkeypatch.setattr(eng, "stuck", lambda: None)
    win.check_audio_health()
    assert win.banner.level is None
    live.listening.emit(True)                               # đang nghe: hai trang kia không phát
    assert win.decode_page.player._listening and win.encode_page._listening
    live.listening.emit(False)
    assert not win.decode_page.player._listening and not win.encode_page._listening


def test_exit_terminates_the_process_when_the_audio_thread_is_stuck(monkeypatch):
    """Người dùng phải giết app trong Task Manager: thoát không bao giờ được chờ driver mãi."""
    from morsedesk.app import main as app_main
    from morsedesk.audio import engine as engine_mod

    killed = []
    monkeypatch.setattr(app_main, "hard_exit", lambda code: killed.append(code))
    monkeypatch.setattr(engine_mod.default_engine(), "shutdown", lambda timeout: False)
    assert app_main.finish(0, None) == 0 and killed == [0]
    killed.clear()
    monkeypatch.setattr(engine_mod.default_engine(), "shutdown", lambda timeout: True)
    assert app_main.finish(0, None) == 0 and killed == []


def test_tape_letter_click_still_works_after_wrap(qtbot, tmp_path, monkeypatch):
    from morsedesk.audio import playback as pb

    started = []
    monkeypatch.setattr(pb.AudioPlayback, "play", lambda self, from_s=None: started.append(from_s))
    page = _encode_page(qtbot, tmp_path, width=700)
    page.text_edit.setPlainText("1234567890123")
    qtbot.wait(10)
    tape = page.tape.tape
    last = tape.item_count() - 1
    assert tape._items[last][1] > tape._items[0][1]          # chữ cuối ở dòng dưới
    qtbot.mouseClick(tape, Qt.MouseButton.LeftButton, pos=tape.item_rect(last).center().toPoint())
    assert len(started) == 1 and started[0] > 0


def test_listen_page_says_it_is_searching_and_explains_a_stuck_driver(qtbot, monkeypatch):
    """Người dùng 27/09 (dịch vụ âm thanh Windows chết): ô thiết bị trống, tưởng "không có micro". Nay:
    "đang tìm…", kẹt thì giải thích ngay trên trang; driver hồi lại thì danh sách hiện, lời báo tắt."""
    from concurrent.futures import Future

    from morsedesk.app import live_page as live_page_mod
    from morsedesk.audio import engine as engine_mod
    from tests.app.test_live_page import FakeLiveWorker

    fut: Future = Future()
    monkeypatch.setattr(live_page_mod, "input_devices", lambda: fut)
    page = live_page_mod.LivePage(FakeLiveWorker())
    qtbot.addWidget(page)
    assert page.device_combo.count() == 1 and "Looking for sound devices" in page.device_combo.itemText(0)
    assert not page.listen_button.isEnabled()
    eng = engine_mod.default_engine()
    monkeypatch.setattr(eng, "stuck", lambda: "query devices")
    page._poll_devices()
    assert page.banner.level == "warning" and "not responding" in page.banner.text()
    monkeypatch.setattr(eng, "stuck", lambda: None)
    fut.set_result([(3, "Microphone Array")])
    page._poll_devices()
    assert page.device_combo.itemText(0) == "Microphone Array" and page.listen_button.isEnabled()
    assert not page.banner.isVisible() or "not responding" not in page.banner.text()
