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


def test_check_models_rejects_directories_named_like_model_files(tmp_path, tiny_lm_dir):
    """Thư mục tên `acoustic.onnx`/`en.bin` phải bị coi là thiếu (exists() đúng với thư mục)."""
    (tmp_path / "acoustic.onnx").mkdir()
    (tmp_path / "acoustic.json").mkdir()
    missing = check_models(tmp_path / "acoustic.onnx", tiny_lm_dir, engine="onnx")
    assert [p.name for p in missing] == ["acoustic.onnx", "acoustic.json"]
    lm_dir = tmp_path / "lm"
    lm_dir.mkdir()
    for name in ("en.bin", "kk.bin", "ru.bin"):
        (lm_dir / name).mkdir()
    assert [p.name for p in check_models(None, lm_dir, engine="baseline")] == ["en.bin", "kk.bin", "ru.bin"]


def test_last_dir_falls_back_when_setting_is_corrupt(tmp_path):
    """`paths/last_dir=@Invalid()` từng cho chuỗi "None" làm thư mục gợi ý."""
    ini = tmp_path / "broken.ini"
    ini.write_text("[paths]\nlast_dir=@Invalid()\n", encoding="utf-8")
    s = AppSettings(settings=QSettings(str(ini), QSettings.Format.IniFormat))
    assert s.last_dir == str(Path.home())
    s.last_dir = str(tmp_path)
    assert AppSettings(settings=QSettings(str(ini), QSettings.Format.IniFormat)).last_dir == str(tmp_path)
    qs = QSettings(str(ini), QSettings.Format.IniFormat)
    qs.setValue("paths/last_dir", "")
    qs.sync()
    assert AppSettings(settings=qs).last_dir == str(Path.home())
