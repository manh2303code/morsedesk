import json
from pathlib import Path

from PySide6.QtCore import QSettings

from morsedesk.api import DecodeResult
from morsedesk.app.decode_page import MAX_MINUTES, PROFILE_CHOICES, DecodePage
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import FAILURE_CODES, DecodeRequest, DecoderWorker


def _page(qtbot, tiny_lm_dir, tmp_path):
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    worker.start()
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = DecodePage(worker, settings)
    qtbot.addWidget(page)
    page.show()
    return worker, page



def _result(text):
    return DecodeResult(text, [], None, None, None, "en", {}, [], "baseline")


def _wait_idle(qtbot, page):
    """busy(False) là tín hiệu xếp hàng đến SAU result_ready/failed; chờ nút Decode bật lại
    trước khi kiểm trạng thái điều khiển hoặc bấm nút, tránh race trong test."""
    qtbot.waitUntil(lambda: page.decode_button.isEnabled(), timeout=5000)

def test_load_file_decodes_and_fills_widgets(qtbot, tiny_lm_dir, tmp_path, wav_cq):
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        assert [page.profile_combo.itemData(i) for i in range(page.profile_combo.count())] == list(PROFILE_CHOICES)
        assert not page.decode_button.isEnabled()
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.load_file(wav_cq)
        qtbot.waitUntil(lambda: page.result is not None, timeout=5000)
        _wait_idle(qtbot, page)
        assert page.result.text == "CQ DE K"
        assert page.word_view.texts() == ["CQ", "DE", "K"]
        assert "WPM" in page.stats.text() and page.stats.language_label("en") in page.stats.text()
        assert page.signal_panel.source() is not None and page.ridge.surface().size
        page.view_2d_button.click()
        assert page.spectrogram.has_image() and page.spectrogram.tone_hz
        page.view_3d_button.click()
        assert page.decode_button.isEnabled() and page.banner.isHidden()
        assert page.path_label.text().endswith("cq.wav")
        assert page.settings.last_dir == str(wav_cq.parent)
        req = page.current_request()
        assert req == DecodeRequest(Path(wav_cq), "auto", True)
        page.export_txt(tmp_path / "out.txt")
        page.export_json(tmp_path / "out.json")
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "CQ DE K"
        assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["text"] == "CQ DE K"
    finally:
        worker.stop()


def test_changing_profile_or_lm_requests_again(qtbot, tiny_lm_dir, tmp_path, wav_ru):
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.load_file(wav_ru)
        qtbot.waitUntil(lambda: page.result is not None and page.result.language == "ru", timeout=5000)
        _wait_idle(qtbot, page)
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.profile_combo.setCurrentIndex(PROFILE_CHOICES.index("en"))
        qtbot.waitUntil(lambda: page.result is not None and page.result.language == "en", timeout=5000)
        _wait_idle(qtbot, page)
        assert page.current_request().profile_id == "en"
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.lm_check.setChecked(False)
        assert page.current_request().use_lm is False
        _wait_idle(qtbot, page)
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.decode_button.click()
    finally:
        worker.stop()


def test_failed_shows_error_banner_and_keeps_page_usable(qtbot, tiny_lm_dir, tmp_path):
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        bad = tmp_path / "bad.wav"
        bad.write_text("x", encoding="utf-8")
        with qtbot.waitSignal(worker.failed, timeout=30000):
            page.load_file(bad)
        qtbot.waitUntil(lambda: page.banner.level == "error", timeout=5000)
        _wait_idle(qtbot, page)
        assert "bad.wav" in page.banner.text() and page.decode_button.isEnabled()
        assert page.word_view.texts() == []
    finally:
        worker.stop()


def test_warnings_go_to_banner_and_fallback_visible(qtbot, tiny_lm_dir, tmp_path):
    import numpy as np

    from morsedesk.api import DecodeResult, Word
    from morsedesk.app.worker import Spectrogram

    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        # on_result giờ chỉ áp dụng kết quả khớp với file đang mở (self._path) -> đặt trước
        # để test không đụng tới đường dẫn thật (không cần load_file/giải mã thật).
        page._path = tmp_path / "x.wav"
        r = DecodeResult("A", [Word("A", 0.0, 0.2, 0.3)], None, 700.0, None, "", {}, ["độ tin cậy thấp"], "onnx", "B")
        page.on_result(r, Spectrogram.from_audio(np.zeros(800, np.float32)), str(tmp_path / "x.wav"))
        assert page.banner.level == "warning" and "độ tin cậy thấp" in page.banner.text()
        assert not page.fallback_label.isHidden() and "B" in page.fallback_label.text()
        assert page.stats.language_label("") in page.stats.text()
    finally:
        worker.stop()


def test_on_busy_blocks_drops_open_button_and_export(qtbot, tiny_lm_dir, tmp_path):
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        assert page.acceptDrops() and page.open_button.isEnabled()
        page.result = _result("A")
        page._set_has_result(True)
        exports = (page.copy_button, page.export_button, page.export_txt_action, page.export_json_action)
        assert all(b.isEnabled() for b in exports)
        page.on_busy(True)
        assert not page.acceptDrops() and not page.open_button.isEnabled()
        # Xuất/sao chép trong lúc giải mã file khác sẽ ghi nội dung cũ dưới tên file mới.
        assert not any(b.isEnabled() for b in exports)
        page.on_busy(False)
        assert page.acceptDrops() and page.open_button.isEnabled()
        assert all(b.isEnabled() for b in exports)      # khôi phục theo self.result
        page.result = None
        page.on_busy(True)
        page.on_busy(False)
        assert not any(b.isEnabled() for b in exports)
    finally:
        worker.stop()


def test_stale_result_for_replaced_file_is_ignored(qtbot, tiny_lm_dir, tmp_path, wav_cq):
    import numpy as np

    from morsedesk.api import DecodeResult, Word
    from morsedesk.app.worker import Spectrogram

    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.load_file(wav_cq)
        qtbot.waitUntil(lambda: page.result is not None, timeout=5000)
        _wait_idle(qtbot, page)
        words_before = page.word_view.texts()
        stats_before = page.stats.text()

        # Kết quả trễ của một file khác (vd. file A trả lời sau khi người dùng đã kéo-thả
        # file B) -> phải bị bỏ qua, không được vẽ đè lên UI của file đang mở.
        stale = DecodeResult("STALE", [Word("STALE", 0.0, 0.5, 0.9)], None, 700.0, None, "", {}, [], "onnx")
        page.on_result(stale, Spectrogram.from_audio(np.zeros(800, np.float32)), str(tmp_path / "other.wav"))
        assert page.word_view.texts() == words_before
        assert page.stats.text() == stats_before
        assert page.result.text == "CQ DE K"

        # Kết quả đúng của file đang mở thì phải được áp dụng bình thường.
        fresh = DecodeResult("FRESH", [Word("FRESH", 0.0, 0.5, 0.9)], None, 700.0, None, "", {}, [], "onnx")
        page.on_result(fresh, Spectrogram.from_audio(np.zeros(800, np.float32)), str(page._path))
        assert page.word_view.texts() == ["FRESH"]
        assert page.result.text == "FRESH"
    finally:
        worker.stop()


def test_auto_profile_locks_language_model_checkbox(qtbot, tiny_lm_dir, tmp_path):
    """`auto` + tắt LM là tổ hợp lõi từ chối; giao diện không được phép tạo ra nó."""
    # Worker cố tình không start(): test chỉ kiểm trạng thái widget, không cần giải mã thật.
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = DecodePage(worker, settings)
    qtbot.addWidget(page)
    page.show()
    page._path = tmp_path / "x.wav"
    assert page.profile_combo.currentData() == "auto"
    assert page.lm_check.isChecked() and not page.lm_check.isEnabled() and page.lm_check.toolTip()
    page.profile_combo.setCurrentIndex(PROFILE_CHOICES.index("en"))
    assert page.lm_check.isEnabled()
    page.lm_check.setChecked(False)
    assert page.current_request().use_lm is False
    page.profile_combo.setCurrentIndex(PROFILE_CHOICES.index("auto"))
    assert page.lm_check.isChecked() and not page.lm_check.isEnabled()
    assert page.current_request() == DecodeRequest(page._path, "auto", True)
    assert page.banner.level is None


def test_failed_builds_translated_message_per_code_and_skips_other_files(qtbot, tiny_lm_dir, tmp_path):
    """Banner dựng bằng tr() theo mã lỗi; chuỗi gốc chỉ nằm ở tooltip; lỗi của file khác bị bỏ qua."""
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        page._path = tmp_path / "x.wav"
        page.on_failed("too_long", "19.5", str(page._path))
        assert page.banner.level == "error" and page.banner.toolTip() == "19.5"
        assert "19.5" in page.banner.text() and str(MAX_MINUTES) in page.banner.text()
        assert "x.wav" in page.banner.text()
        seen = set()
        for code in FAILURE_CODES:
            page.on_failed(code, f"loi goc {code}", str(page._path))
            text = page.banner.text()
            if code != "too_long":      # too_long cố tình chèn detail (số phút) vào câu
                assert text and f"loi goc {code}" not in text      # không đổ chuỗi lõi vào banner
            assert page.banner.toolTip() == f"loi goc {code}"
            seen.add(text)
        assert len(seen) == len(FAILURE_CODES)                     # mỗi mã một thông điệp riêng
        before = page.banner.text()
        page.on_failed("internal", "cua file khac", str(tmp_path / "other.wav"))
        assert page.banner.text() == before and page.banner.toolTip() != "cua file khac"
    finally:
        worker.stop()


def test_export_reports_write_errors_in_banner(qtbot, tiny_lm_dir, tmp_path):
    """Ghi hỏng (đường dẫn là thư mục) phải cho banner đỏ, không chỉ traceback ra stderr."""
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        page._path = tmp_path / "x.wav"
        page.result = _result("CQ")
        blocked = tmp_path / "thu-muc"
        blocked.mkdir()
        assert page.export_txt(blocked) is False
        assert page.banner.level == "error" and blocked.name in page.banner.text()
        assert page.export_json(blocked) is False
        out = tmp_path / "ok.json"
        assert page.export_json(out) is True
        assert json.loads(out.read_text(encoding="utf-8"))["text"] == "CQ"
    finally:
        worker.stop()
