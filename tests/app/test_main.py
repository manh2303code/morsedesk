from PySide6.QtCore import QSettings

import morsedesk.app.main as app_main
from morsedesk.app.main import build_parser, create_app, main
from morsedesk.app.settings import AppSettings


def test_parser_defaults():
    a = build_parser().parse_args([])
    assert a.engine == "onnx" and a.model is None and a.lm_dir is None and a.lang is None


def test_main_exits_2_when_models_missing(tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(app_main, "show_missing_dialog", lambda msg: shown.append(msg))
    rc = main(["--model", str(tmp_path / "none.onnx"), "--lm-dir", str(tmp_path)])
    assert rc == 2 and shown and "none.onnx" in shown[0] and "en.bin" in shown[0]


def test_create_app_builds_window_with_language(qtbot, tiny_lm_dir, tmp_path, monkeypatch):
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(app_main, "load_settings", lambda: settings)
    args = build_parser().parse_args(["--engine", "baseline", "--lm-dir", str(tiny_lm_dir), "--lang", "ru"])
    app, window = create_app(args)
    qtbot.addWidget(window)
    try:
        assert window.current_language == "ru" and settings.ui_language == "ru"
        assert window.tabs.count() == 2
        assert window.language_combo.currentData() == "ru"
        assert window.decode_page is not None and window.worker.isRunning()
        from morsedesk.app.encode_page import EncodePage

        assert isinstance(window.encode_page, EncodePage)
    finally:
        window.close()
    assert not window.worker.isRunning()
