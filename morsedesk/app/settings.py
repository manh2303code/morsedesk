"""Cài đặt người dùng tối thiểu của tuần 4: ngôn ngữ giao diện và thư mục gần nhất (QSettings)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

UI_LANGUAGES = ("en", "ru", "kk")


def default_language(explicit: str | None, saved: str | None, locale_name: str) -> str:
    """explicit hợp lệ > saved hợp lệ > tiền tố locale kk/ru > en."""
    for cand in (explicit, saved):
        if cand in UI_LANGUAGES:
            return cand
    prefix = (locale_name or "").split("_")[0].lower()
    return prefix if prefix in ("kk", "ru") else "en"


class AppSettings:
    def __init__(self, org: str = "MorseDesk", app: str = "MorseDesk", settings: QSettings | None = None) -> None:
        self._s = settings if settings is not None else QSettings(org, app)

    @property
    def ui_language(self) -> str | None:
        v = self._s.value("ui/language", None)
        return str(v) if v else None

    @ui_language.setter
    def ui_language(self, code: str) -> None:
        self._s.setValue("ui/language", code)
        self._s.sync()

    @property
    def last_dir(self) -> str:
        return str(self._s.value("paths/last_dir", str(Path.home())))

    @last_dir.setter
    def last_dir(self, path: str) -> None:
        self._s.setValue("paths/last_dir", path)
        self._s.sync()

    def clear(self) -> None:
        self._s.clear()
        self._s.sync()
