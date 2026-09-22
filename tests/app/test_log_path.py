"""Đường dẫn log phải đúng spec mục 7: `~/.local/share/morsedesk/logs/` trên Linux.

Qt `AppDataLocation` trả `~/.local/share/MorseDesk/MorseDesk` vì nó ghép cả tên tổ chức lẫn tên
ứng dụng, nên không dùng thẳng được cho nền tảng đích (CP-15). Trên các nền tảng khác — chỉ dùng
để chạy test trên máy dev Windows — vẫn theo Qt.
"""

from pathlib import Path

import pytest

from morsedesk.app.main import log_directory, setup_logging


def test_linux_follows_xdg_default(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert log_directory() == tmp_path / ".local" / "share" / "morsedesk" / "logs"


def test_linux_respects_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert log_directory() == tmp_path / "data" / "morsedesk" / "logs"


def test_non_linux_uses_qt_location(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    assert log_directory().name == "logs"


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_setup_logging_creates_directory_and_attaches_handler(monkeypatch, tmp_path, platform):
    import logging

    monkeypatch.setattr("sys.platform", platform)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr("morsedesk.app.main.log_directory", lambda: tmp_path / "logs")
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        setup_logging()
        assert (tmp_path / "logs").is_dir()
        assert any(getattr(h, "baseFilename", "").endswith("morsedesk.log") for h in root.handlers)
    finally:
        for h in root.handlers:
            if h not in before:
                h.close()
        root.handlers[:] = before
