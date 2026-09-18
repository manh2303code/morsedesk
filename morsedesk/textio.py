"""Tiện ích dòng chữ: ép stdout/stderr sang UTF-8 để in Cyrillic/tiếng Việt trên console cp1252."""

from __future__ import annotations

import sys


def force_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
