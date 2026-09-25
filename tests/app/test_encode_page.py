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


def test_play_and_stop_use_player(qtbot, tmp_path, fake_sounddevice):
    sd = fake_sounddevice
    calls = sd.calls
    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("E")
    page.play_button.click()
    assert any(c[0] == "play" and c[2] == 8000 for c in calls) and page.banner.level is None
    page.stop_button.click()
    assert calls[-1] == ("stop",)

    def boom(x, sr, **kw):
        raise sd.PortAudioError("no device")

    sd.play = boom
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
    page.text_edit.setPlainText("PARIS " * 1400)          # ~ 70 phút ở 20 WPM, quá trần 60
    assert page.estimate_seconds() > MAX_SECONDS
    # văn bản dài: nút khóa NGAY, banner tới khi lần dựng gộp chạy (encode_page.DEBOUNCE_CHARS)
    assert not page.play_button.isEnabled() and not page.save_button.isEnabled()
    qtbot.waitUntil(lambda: page.banner.level == "warning", timeout=2000)
    assert str(MAX_MINUTES) in page.banner.text()
    assert not page.play_button.isEnabled() and not page.save_button.isEnabled()
    page.play_button.click()
    page.save_button.click()
    assert calls == []
    # Gọi thẳng API công khai (không qua nút đã bị vô hiệu) cũng không được dựng audio.
    page.play()
    page.save_to(tmp_path / "qua-dai.wav")
    assert calls == []
    assert not (tmp_path / "qua-dai.wav").exists()
    assert page.banner.level == "warning"
    page.text_edit.setPlainText("SOS")                    # về dưới ngưỡng -> bật lại, xóa banner
    assert page.play_button.isEnabled() and page.save_button.isEnabled()
    assert page.banner.level is None


def test_duration_limit_follows_timing_controls(qtbot, tmp_path):
    """Banner khuyên "nâng tốc độ" thì nâng WPM phải bật lại nút ngay, không đợi gõ thêm ký tự."""
    page = _page(qtbot, tmp_path)
    page.wpm_spin.setValue(10)
    page.text_edit.setPlainText("PARIS " * 700)
    assert page.estimate_seconds() > MAX_SECONDS
    assert not page.play_button.isEnabled()
    qtbot.waitUntil(lambda: page.banner.level == "warning", timeout=2000)
    page.wpm_spin.setValue(60)                      # làm đúng lời khuyên trong banner
    assert page.estimate_seconds() < MAX_SECONDS
    assert page.play_button.isEnabled() and page.save_button.isEnabled()
    assert page.banner.level is None
    page.wpm_spin.setValue(10)                      # chiều ngược lại cũng phải bắt kịp
    assert not page.play_button.isEnabled() and page.banner.level == "warning"


def test_farnsworth_above_wpm_errors_for_both_play_and_save(qtbot, tmp_path, fake_sounddevice):
    """Farnsworth > WPM: cả Nghe thử lẫn Lưu phải cho banner đỏ bằng tr(), không im lặng."""
    calls = fake_sounddevice.calls
    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("SOS")
    page.wpm_spin.setValue(10)
    page.farnsworth_check.setChecked(True)
    page.farnsworth_spin.setValue(30)
    page.play_button.click()
    assert page.banner.level == "error" and calls == []
    assert "farnsworth_wpm" not in page.banner.text()        # thông điệp của tr(), không phải chuỗi lõi
    assert "farnsworth_wpm" in page.banner.toolTip()
    page.banner.clear()
    out = tmp_path / "x.wav"
    page.save_to(out)
    assert page.banner.level == "error" and not out.exists()
    page.farnsworth_spin.setValue(5)                         # hợp lệ trở lại
    page.save_to(out)
    assert out.exists() and page.banner.level is None


def test_save_to_keeps_dots_in_file_names(qtbot, tmp_path):
    """with_suffix từng cắt "toc do 1.5 wpm" thành "toc do 1.wav" và đè file khác."""
    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("E")
    page.save_to(tmp_path / "toc do 1.5 wpm")
    assert (tmp_path / "toc do 1.5 wpm.wav").exists()
    assert not (tmp_path / "toc do 1.wav").exists()
    page.save_to(tmp_path / "a.b.wav")                       # đuôi đã đúng -> giữ nguyên
    assert (tmp_path / "a.b.wav").exists()
    page.format_combo.setCurrentIndex(page.format_combo.findData(".flac"))
    assert page.format_path(tmp_path / "a.b.wav") == tmp_path / "a.b.flac"   # đuôi audio -> thay
    assert page.format_path(tmp_path / "toc do 1.5 wpm") == tmp_path / "toc do 1.5 wpm.flac"


def test_long_text_typing_is_coalesced_and_play_flushes_it(qtbot, tmp_path, monkeypatch):
    """Gõ nhanh trên văn bản dài: không dựng lại chuỗi Morse ở từng phím (ảnh người dùng 25/09: giật
    rõ khi gõ, 60–300 ms mỗi phím) — gộp lại một lần; Nghe thử/Lưu thì dựng ngay phần đang chờ."""
    from morsedesk.app import encode_page as mod

    page = _page(qtbot, tmp_path)
    page.text_edit.setPlainText("PARIS " * (mod.DEBOUNCE_CHARS // 6 + 10))
    qtbot.waitUntil(lambda: not page._refresh_timer.isActive(), timeout=2000)
    calls = []
    real = page.refresh_morse
    monkeypatch.setattr(page, "refresh_morse", lambda: (calls.append(1), real()))
    page._refresh_timer.timeout.disconnect()
    page._refresh_timer.timeout.connect(page.refresh_morse)
    from PySide6.QtGui import QTextCursor

    page.text_edit.moveCursor(QTextCursor.MoveOperation.End)       # gõ ở cuối như người dùng
    for _ in range(25):
        page.text_edit.insertPlainText("E")
    assert calls == [] and not page.play_button.isEnabled()      # đang gộp: chưa dựng, nút khóa
    built = []
    monkeypatch.setattr(page, "build_audio", lambda: built.append(1) or __import__("numpy").zeros(8))
    monkeypatch.setattr(page.player, "play", lambda x, sr: None)
    page.play()                                                  # phát: dựng NGAY phần đang chờ
    assert calls == [1] and page.morse_view.toPlainText().endswith(". . . . .")
    assert not page._refresh_timer.isActive()


def test_tape_scrolls_instead_of_growing_the_window(qtbot, tmp_path):
    """Băng Morse nằm trong khung cuộn: bản tin dài KHÔNG được kéo chiều cao tối thiểu của trang
    (ảnh người dùng 25/09: cửa sổ bị kéo cao tới 22 624 px, xóa chữ thì khung nhập chiếm cả trang)."""
    page = _page(qtbot, tmp_path)
    page.resize(1200, 800)
    page.show()
    short = page.minimumSizeHint().height()
    page.text_edit.setPlainText("PARIS " * 900)
    page.flush_refresh()
    qtbot.wait(10)
    assert page.minimumSizeHint().height() <= short + 60
    assert page.tape.tape.height() > page.tape.viewport().height()     # nội dung dài hơn khung -> cuộn
    page.text_edit.setPlainText("")
    assert page.minimumSizeHint().height() <= short + 60
