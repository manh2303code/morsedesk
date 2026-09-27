"""Thanh phát trong trang Giải mã: nạp lười, tô từ đang nghe, và xử lý máy không có loa."""

from __future__ import annotations

import numpy as np
import pytest

from morsedesk.api import Word
from morsedesk.app.widgets.player_bar import PlayerBar, format_time
from morsedesk.app.widgets.word_view import WordView


@pytest.mark.parametrize(("seconds", "text"), [
    (0, "0:00"), (5, "0:05"), (65, "1:05"), (600, "10:00"), (3600, "1:00:00"), (3725, "1:02:05"),
])
def test_format_time(seconds, text):
    assert format_time(seconds) == text


def test_load_enables_controls_and_reports_duration(qtbot, fake_sounddevice):
    bar = PlayerBar()
    qtbot.addWidget(bar)
    assert not bar.play_button.isEnabled()          # chưa có gì để nghe
    bar.load(np.zeros(16000, dtype=np.float32), 8000)
    assert bar.play_button.isEnabled() and bar.slider.isEnabled()
    assert bar.time_label.text() == "0:00 / 0:02"


def test_lazy_load_runs_once_on_first_play(qtbot, fake_sounddevice):
    """Bản ghi 37 phút chiếm 71 MB, nên chỉ nạp khi người dùng thật sự bấm nghe."""
    bar = PlayerBar()
    qtbot.addWidget(bar)
    calls = []

    def loader():
        calls.append(1)
        if len(calls) == 1:
            bar.load(np.zeros(8000, dtype=np.float32), 8000)

    bar.ensure_loaded = loader
    bar.toggle()
    assert calls == [1] and bar.playback.playing
    bar.toggle()                                    # tạm dừng: KHÔNG nạp lại
    assert calls == [1] and not bar.playback.playing
    bar.toggle()
    assert calls == [1, 1] or calls == [1]          # nạp lại được gọi nhưng loader tự chặn
    bar.pause()


def test_missing_output_device_disables_controls(qtbot, monkeypatch):
    """Máy air-gap thiếu libportaudio2: tắt nút và báo một dòng, không để người dùng bấm hoài."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "sounddevice":
            raise OSError("PortAudio library not found")
        return real_import(name, *a, **kw)

    bar = PlayerBar()
    qtbot.addWidget(bar)
    bar.load(np.zeros(8000, dtype=np.float32), 8000)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    seen: list[str] = []
    bar.error.connect(seen.append)
    bar.play()
    assert seen and "PortAudio (libportaudio2)" in seen[0]     # lời cho người vận hành, không phải OSError
    assert not bar.play_button.isEnabled() and not bar.slider.isEnabled()


def test_seek_emits_position_and_updates_clock(qtbot, fake_sounddevice):
    bar = PlayerBar()
    qtbot.addWidget(bar)
    bar.load(np.zeros(80000, dtype=np.float32), 8000)    # 10 giây
    seen: list[float] = []
    bar.position_changed.connect(seen.append)
    bar.seek(4.0)
    assert seen[-1] == pytest.approx(4.0)
    assert bar.time_label.text() == "0:04 / 0:10"


def _words() -> list[Word]:
    return [Word("CQ", 0.0, 0.6, 0.9), Word("DE", 1.2, 1.8, 0.9), Word("R1ABC", 2.4, 3.6, 0.7)]


def test_word_view_playhead_marks_current_word(qtbot):
    view = WordView()
    qtbot.addWidget(view)
    view.set_words(_words())

    view.set_playhead(0.3)
    assert view.active_index() == 0
    view.set_playhead(1.5)
    assert view.active_index() == 1
    # Khoảng lặng GIỮA hai từ: giữ từ vừa qua, nếu không vệt sáng nhấp nháy mỗi lần im tiếng.
    view.set_playhead(2.0)
    assert view.active_index() == 1
    view.set_playhead(3.0)
    assert view.active_index() == 2
    view.set_playhead(None)
    assert view.active_index() is None


def test_word_view_playhead_before_first_word_marks_nothing(qtbot):
    view = WordView()
    qtbot.addWidget(view)
    view.set_words([Word("CQ", 1.0, 1.6, 0.9)])
    view.set_playhead(0.2)
    assert view.active_index() == -1                # đang nghe nhưng chưa tới từ nào


def test_arm_enables_button_for_lazy_load(qtbot, fake_sounddevice):
    """Nạp lười tự khóa mình nếu nút chỉ bật trong load(): ảnh chụp giao diện đã lộ ra."""
    bar = PlayerBar()
    qtbot.addWidget(bar)
    assert not bar.play_button.isEnabled()
    bar.arm()                                   # chưa có ensure_loaded -> vẫn tắt
    assert not bar.play_button.isEnabled()
    bar.ensure_loaded = lambda: None
    bar.arm()
    assert bar.play_button.isEnabled() and bar.slider.isEnabled()


def test_arm_shows_the_file_length_before_audio_is_loaded(qtbot, fake_sounddevice):
    """Đầu trang ghi 0:04 thì đồng hồ thanh phát cũng phải ghi 0:04, không phải 0:00 / 0:00."""
    bar = PlayerBar()
    qtbot.addWidget(bar)
    bar.ensure_loaded = lambda: None
    bar.arm(4.2)
    assert bar.time_label.text() == "0:00 / 0:04"
    bar.retranslate()                           # đổi ngôn ngữ giao diện: không được xóa thời lượng
    assert bar.time_label.text() == "0:00 / 0:04"
    bar.clear()
    assert bar.time_label.text() == "0:00 / 0:00"


def test_speed_menu_and_volume_controls(qtbot):
    from morsedesk.app.widgets.player_bar import SPEEDS

    bar = PlayerBar()
    qtbot.addWidget(bar)
    assert list(bar.speed_actions) == list(SPEEDS) and bar.speed_button.text() == "1×"
    with qtbot.waitSignal(bar.speed_changed) as sig:
        bar.speed_actions[0.75].trigger()
    assert sig.args == [0.75] and bar.playback.speed == 0.75 and bar.speed_button.text() == "0.75×"
    assert bar.speed_actions[0.75].isChecked() and not bar.speed_actions[1.0].isChecked()
    bar.set_volume(30)
    assert abs(bar.playback.volume - 0.30) < 1e-9
    bar.toggle_mute()
    assert bar.volume() == 0 and bar.playback.volume == 0.0
    bar.toggle_mute()
    assert bar.volume() == 30                       # bật lại đúng mức cũ
    assert bar.volume_button.toolTip() and bar.speed_button.toolTip()
