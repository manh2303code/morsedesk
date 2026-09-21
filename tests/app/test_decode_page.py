import json
from pathlib import Path

from PySide6.QtCore import QSettings

from morsedesk.app.decode_page import PROFILE_CHOICES, DecodePage
from morsedesk.app.settings import AppSettings
from morsedesk.app.worker import DecodeRequest, DecoderWorker


def _page(qtbot, tiny_lm_dir, tmp_path):
    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    worker.start()
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    page = DecodePage(worker, settings)
    qtbot.addWidget(page)
    page.show()
    return worker, page


def test_load_file_decodes_and_fills_widgets(qtbot, tiny_lm_dir, tmp_path, wav_cq):
    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        assert [page.profile_combo.itemData(i) for i in range(page.profile_combo.count())] == list(PROFILE_CHOICES)
        assert not page.decode_button.isEnabled()
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.load_file(wav_cq)
        qtbot.waitUntil(lambda: page.result is not None, timeout=5000)
        assert page.result.text == "CQ DE K"
        assert [lb.text() for lb in page.word_view.labels()] == ["CQ", "DE", "K"]
        assert "WPM" in page.stats.text() and page.stats.language_label("en") in page.stats.text()
        assert page.spectrogram.image.image is not None and page.spectrogram.tone_line.isVisible()
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
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.profile_combo.setCurrentIndex(PROFILE_CHOICES.index("en"))
        qtbot.waitUntil(lambda: page.result is not None and page.result.language == "en", timeout=5000)
        assert page.current_request().profile_id == "en"
        with qtbot.waitSignal(worker.result_ready, timeout=60000):
            page.lm_check.setChecked(False)
        assert page.current_request().use_lm is False
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
        assert "bad.wav" in page.banner.text() and page.decode_button.isEnabled()
        assert page.word_view.labels() == []
    finally:
        worker.stop()


def test_warnings_go_to_banner_and_fallback_visible(qtbot, tiny_lm_dir, tmp_path):
    import numpy as np

    from morsedesk.api import DecodeResult, Word
    from morsedesk.app.worker import Spectrogram

    worker, page = _page(qtbot, tiny_lm_dir, tmp_path)
    try:
        r = DecodeResult("A", [Word("A", 0.0, 0.2, 0.3)], None, 700.0, None, "", {}, ["độ tin cậy thấp"], "onnx", "B")
        page.on_result(r, Spectrogram.from_audio(np.zeros(800, np.float32)), str(tmp_path / "x.wav"))
        assert page.banner.level == "warning" and "độ tin cậy thấp" in page.banner.text()
        assert not page.fallback_label.isHidden() and "B" in page.fallback_label.text()
        assert page.stats.language_label("") in page.stats.text()
    finally:
        worker.stop()
