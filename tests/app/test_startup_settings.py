from pathlib import Path

from PySide6.QtCore import QSettings

from morsedesk.app.settings import UI_LANGUAGES, AppSettings, default_language
from morsedesk.app.startup import check_models, missing_models_message


def test_check_models_lists_missing_in_order(tmp_path, tiny_lm_dir):
    missing = check_models(tmp_path / "acoustic.onnx", tmp_path / "lm", engine="onnx")
    names = [p.name for p in missing]
    assert names == ["acoustic.onnx", "acoustic.json", "en.bin", "kk.bin", "ru.bin"]
    assert check_models(tmp_path / "acoustic.onnx", tiny_lm_dir, engine="baseline") == []
    (tmp_path / "acoustic.onnx").write_bytes(b"x")
    (tmp_path / "acoustic.json").write_text("{}", encoding="utf-8")
    assert check_models(tmp_path / "acoustic.onnx", tiny_lm_dir, engine="onnx") == []
    assert check_models(None, None, engine="baseline") == [] or all(p.name.endswith(".bin") for p in check_models(None, None, engine="baseline"))


def test_missing_models_message_mentions_paths_and_help(tmp_path):
    msg = missing_models_message([tmp_path / "acoustic.onnx", tmp_path / "lm" / "en.bin"])
    assert "acoustic.onnx" in msg and "en.bin" in msg
    assert "export_onnx" in msg and "README" in msg


def test_default_language_priority():
    assert UI_LANGUAGES == ("en", "ru", "kk")
    assert default_language("kk", "ru", "en_US") == "kk"
    assert default_language("xx", "ru", "en_US") == "ru"
    assert default_language(None, "zz", "kk_KZ") == "kk"
    assert default_language(None, None, "ru_RU") == "ru"
    assert default_language(None, None, "vi_VN") == "en"
    assert default_language(None, None, "C") == "en"


def test_app_settings_roundtrip(tmp_path):
    qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s = AppSettings(settings=qs)
    assert s.ui_language is None
    assert s.last_dir == str(Path.home())
    s.ui_language = "ru"
    s.last_dir = str(tmp_path)
    s2 = AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    assert s2.ui_language == "ru" and s2.last_dir == str(tmp_path)
    s2.clear()
    assert AppSettings(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)).ui_language is None
