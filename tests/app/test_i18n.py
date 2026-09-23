import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, QTranslator

from morsedesk.app.main import I18N_DIR
from morsedesk.app.settings import AppSettings
from tools.build_i18n import SOURCES, fill_ts, tr_literals

ROOT = Path(__file__).resolve().parents[2]


def test_translation_table_covers_all_tr_literals():
    table = json.loads((I18N_DIR / "translations.json").read_text(encoding="utf-8"))
    literals = tr_literals(SOURCES)
    assert literals, "không tìm thấy chuỗi tr() nào"
    for lang in ("ru", "kk"):
        missing = sorted(s for s in literals if s not in table[lang])
        assert not missing, f"{lang} thiếu bản dịch: {missing}"
        for src, dst in table[lang].items():
            assert dst.strip(), f"{lang}: bản dịch rỗng cho {src!r}"
            for field in ("{v}", "{lang}", "{text}", "{exts}", "{ext}", "{chars}", "{path}", "{conf:.2f}", "{minutes}", "{limit}", "{detail}"):
                assert (field in src) == (field in dst), f"{lang}: {src!r} -> {dst!r} lệch placeholder {field}"


def test_ts_files_have_no_unfinished_and_qm_load():
    for lang in ("ru", "kk"):
        ts = (I18N_DIR / f"morsedesk_{lang}.ts").read_text(encoding="utf-8")
        assert 'type="unfinished"' not in ts
        tr = QTranslator()
        assert tr.load(str(I18N_DIR / f"morsedesk_{lang}.qm"))
        assert tr.translate("MainWindow", "Decode")
    assert QTranslator().translate("MainWindow", "Decode") == ""


def test_fill_ts_marks_translated(tmp_path):
    ts = tmp_path / "x.ts"
    ts.write_text('<?xml version="1.0" encoding="utf-8"?><!DOCTYPE TS><TS version="2.1" language="ru">'
                  '<context><name>C</name><message><source>Decode</source><translation type="unfinished"></translation></message>'
                  '<message><source>Zzz</source><translation type="unfinished"></translation></message></context></TS>',
                  encoding="utf-8")
    left = fill_ts(ts, {"Decode": "Декодирование"})
    out = ts.read_text(encoding="utf-8")
    assert left == 1 and "<translation>Декодирование</translation>" in out and out.count('type="unfinished"') == 1


def test_set_language_switches_ui_text(qtbot, tiny_lm_dir, tmp_path):
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.worker import DecoderWorker, Player

    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    w = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(w)
    try:
        assert w.tabs.tabText(0) == "Decode"
        assert w.set_language("ru") and w.tabs.tabText(0) == "Декодирование" and settings.ui_language == "ru"
        assert w.decode_page.lm_check.text() == "Использовать языковую модель"
        assert w.encode_page.play_button.text() == "Воспроизвести"
        assert w.set_language("kk") and w.tabs.tabText(0) == "Декодтау"
        assert w.language_bar.buttons["kk"].isChecked()
        assert w.set_language("en") and w.tabs.tabText(0) == "Decode"
        assert not w.set_language("xx")
        w.language_bar.buttons["ru"].click()        # bấm lá cờ như người dùng
        assert w.current_language == "ru" and w.tabs.tabText(1) == "Кодирование"
    finally:
        w.set_language("en")
        QCoreApplication.processEvents()
        w.close()


def test_translated_combos_grow_and_units_are_localised(qtbot, tiny_lm_dir, tmp_path, monkeypatch):
    """Ảnh chụp thật ở giao diện Nga cho thấy combo cắt mất 'Английский' và thanh chỉ số ghi
    'Тон 570 Hz' lẫn tiếng Anh. Kiểm cả hai: combo tự giãn theo nội dung, đơn vị đi qua tr()."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QComboBox

    import morsedesk.app.main as app_main
    from morsedesk.api import DecodeResult
    from morsedesk.app.settings import AppSettings

    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(app_main, "load_settings", lambda: settings)
    args = app_main.build_parser().parse_args(["--engine", "baseline", "--lm-dir", str(tiny_lm_dir)])
    app, window = app_main.create_app(args)
    qtbot.addWidget(window)
    try:
        combos = (window.decode_page.profile_combo, window.encode_page.profile_combo)
        for combo in combos:
            assert combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToContents
        result = DecodeResult("CQ", [], 20.0, 700.0, 12.0, "en", {}, [], "baseline")
        for code in ("en", "ru", "kk"):
            window.set_language(code)
            for combo in combos:
                fm = combo.fontMetrics()
                widest = max(fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
                assert combo.sizeHint().width() >= widest, (code, combo.sizeHint().width(), widest)
            window.decode_page.stats.set_result(result, 0.5)
            text = window.decode_page.stats.text()
            if code == "en":
                assert "Hz" in text and "dB" in text
            else:                                   # đơn vị phải theo ngôn ngữ, không lẫn tiếng Anh
                assert "Гц" in text and "дБ" in text and " Hz" not in text and " dB" not in text
    finally:
        window.close()


def test_player_bar_follows_the_ui_language(qtbot, tiny_lm_dir, tmp_path):
    """Nút thanh phát từng giữ chữ "Play" tiếng Anh trong giao diện Kazakh."""
    from morsedesk.app.main_window import MainWindow
    from morsedesk.app.worker import DecoderWorker, Player

    worker = DecoderWorker(engine="baseline", model_path=None, lm_dir=tiny_lm_dir)
    settings = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    w = MainWindow(worker, Player(), settings, I18N_DIR)
    qtbot.addWidget(w)
    try:
        # Nút là biểu tượng ▶; chữ nằm ở tên trợ năng và tooltip, và phải theo ngôn ngữ giao diện.
        assert w.set_language("kk") and w.decode_page.player.play_button.accessibleName() == "Ойнату"
        assert w.set_language("ru") and w.decode_page.player.play_button.accessibleName() == "Воспроизвести"
        assert not w.decode_page.player.play_button.icon().isNull()
    finally:
        w.set_language("en")
        QCoreApplication.processEvents()
        w.close()
