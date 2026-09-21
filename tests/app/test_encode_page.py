from PySide6.QtCore import QSettings

import morsedesk.app.worker as wk
from morsedesk.app.encode_page import FORMATS, MAX_MINUTES, EncodePage, unsupported_chars
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import MAX_SECONDS, Player
from morsedesk.audio.io import load_audio
from morsedesk.constants import SAMPLE_RATE
from morsedesk.lm.profile import load_profile


def _page(qtbot, tmp_path):
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = EncodePage(Player(), settings)
    qtbot.addWidget(page)
    page.show()
    return page


def test_unsupported_chars():
    en = load_profile("en")
    assert unsupported_chars("CQ DE K", en) == []
    assert unsupported_chars("Sәlem, mir! <SK>", en) == ["Ә"]
    assert unsupported_chars("héllo", en) == ["É"]


def test_morse_string_updates_and_warns(qtbot, tmp_path):
    page = _page(qtbot, tmp_path)
    assert not page.play_button.isEnabled() and not page.save_button.isEnabled()
    page.text_edit.setPlainText("SOS")
    assert page.morse_view.toPlainText() == "... --- ..."
    assert page.warn_label.isHidden() and page.play_button.isEnabled() and page.save_button.isEnabled()
    page.text_edit.setPlainText("CQ DE Ә")
    assert page.morse_view.toPlainText() == "-.-. --.- / -.. ."
    assert not page.warn_label.isHidden() and "Ә" in page.warn_label.text()
    page.profile_combo.setCurrentIndex(page.profile_combo.findData("kk-cyrl-ru"))
    # "CQ DE" là chữ Latin: hồ sơ kk-cyrl-ru chỉ ánh xạ chữ Cyrillic (xem letter_to_pattern),
    # nên đổi sang profile này khiến C/Q/D/E trở thành ký tự không hỗ trợ (trước đó, dưới
    # profile en, chỉ "Ә" không hỗ trợ) trong khi "Ә" thì ngược lại được hỗ trợ; văn bản không
    # đổi nên vẫn kiểm tra đúng tinh thần ban đầu của test: đổi profile → cập nhật lại morse_view
    # và warn_label mà không cần gõ lại chữ.
    assert not page.warn_label.isHidden() and page.morse_view.toPlainText() == ".-"
    assert page.charmap.isVisibleTo(page) and page.charmap._row2.isVisibleTo(page)
    page.profile_combo.setCurrentIndex(page.profile_combo.findData("en"))
    assert page.charmap.isHidden()


def test_charmap_inserts_at_cursor(qtbot, tmp_path):
    page = _page(qtbot, tmp_path)
    page.profile_combo.setCurrentIndex(page.profile_combo.findData("ru"))
    page.text_edit.setPlainText("ПРИВЕТ")
    page.text_edit.moveCursor(page.text_edit.textCursor().MoveOperation.End)
    next(b for b in page.charmap.buttons() if b.text() == "Ы").click()
    assert page.text_edit.toPlainText() == "ПРИВЕТЫ"
    assert page.morse_view.toPlainText().split(" ")[-1] == "-.--"


def test_save_writes_audio_with_expected_duration(qtbot, tmp_path):
    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("PARIS")
    page.wpm_spin.setValue(20)
    out = tmp_path / "paris.wav"
    page.save_to(out)
    x, sr = load_audio(out)
    assert sr == 8000
    assert abs(len(x) / sr - (0.6 + 43 * 0.06)) < 0.15    # PARIS = 43 dit (không có khoảng từ cuối) ở 20 WPM + 2×0,3 s đệm
    assert page.banner.level is None
    for ext in (".flac", ".ogg"):
        page.format_combo.setCurrentIndex(page.format_combo.findData(ext))
        page.save_to(tmp_path / f"paris{ext}")
        assert (tmp_path / f"paris{ext}").exists() and page.banner.level is None
    assert [ext for _, ext in FORMATS] == [".wav", ".flac", ".ogg"]


def test_farnsworth_and_noise_change_audio(qtbot, tmp_path):
    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("PARIS PARIS")
    base = page.build_audio()
    page.farnsworth_check.setChecked(True)
    page.farnsworth_spin.setValue(8)
    slow = page.build_audio()
    assert len(slow) > len(base) * 1.5
    page.farnsworth_check.setChecked(False)
    page.snr_check.setChecked(True)
    page.snr_spin.setValue(0)
    noisy = page.build_audio()
    assert len(noisy) == len(base) and float(abs(noisy - base).mean()) > 0.01


def test_play_and_stop_use_player(qtbot, tmp_path, monkeypatch):
    import sounddevice as sd

    calls = []
    monkeypatch.setattr(sd, "play", lambda x, sr, **kw: calls.append(("play", sr)))
    monkeypatch.setattr(sd, "stop", lambda: calls.append(("stop",)))
    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("E")
    page.play_button.click()
    assert ("play", 8000) in calls and page.banner.level is None
    page.stop_button.click()
    assert calls[-1] == ("stop",)

    def boom(x, sr, **kw):
        raise sd.PortAudioError("no device")

    monkeypatch.setattr(sd, "play", boom)
    page.play_button.click()
    assert page.banner.level == "warning" and "no device" in page.banner.text()
    assert wk.Player is Player


def test_estimate_seconds_matches_built_audio(qtbot, tmp_path):
    """Ước lượng không dựng audio phải khớp `build_audio()` trong sai số 10 %."""
    page = _page(qtbot, tmp_path)
    page.wpm_spin.setValue(20)
    page.text_edit.setPlainText("PARIS")
    est = page.estimate_seconds()
    real = len(page.build_audio()) / SAMPLE_RATE
    assert abs(est - real) <= 0.1 * real
    assert page.play_button.isEnabled() and page.save_button.isEnabled()
    assert page.banner.level is None
    page.text_edit.setPlainText("   ")
    assert page.estimate_seconds() == 0.0


def test_text_over_duration_limit_disables_audio_without_building_it(qtbot, tmp_path, monkeypatch):
    """Văn bản dài: chặn ở khâu ước lượng, không bao giờ gọi `build_audio()`."""
    page = _page(qtbot, tmp_path)
    calls = []
    monkeypatch.setattr(page, "build_audio", lambda: calls.append(1))
    page.wpm_spin.setValue(20)
    page.text_edit.setPlainText("PARIS " * 1000)          # ~ 50 phút ở 20 WPM
    assert page.estimate_seconds() > MAX_SECONDS
    assert not page.play_button.isEnabled() and not page.save_button.isEnabled()
    assert page.banner.level == "warning" and str(MAX_MINUTES) in page.banner.text()
    page.play_button.click()
    page.save_button.click()
    assert calls == []
    page.text_edit.setPlainText("SOS")                    # về dưới ngưỡng -> bật lại, xóa banner
    assert page.play_button.isEnabled() and page.save_button.isEnabled()
    assert page.banner.level is None
