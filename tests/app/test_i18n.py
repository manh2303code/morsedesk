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
            for field in ("{v}", "{lang}", "{text}", "{exts}", "{ext}", "{chars}", "{path}", "{conf:.2f}"):
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
        assert w.language_combo.currentData() == "kk"
        assert w.set_language("en") and w.tabs.tabText(0) == "Decode"
        assert not w.set_language("xx")
        w.language_combo.setCurrentIndex(w.language_combo.findData("ru"))
        assert w.current_language == "ru" and w.tabs.tabText(1) == "Кодирование"
    finally:
        w.set_language("en")
        QCoreApplication.processEvents()
        w.close()
