"""Trang Cài đặt: máy này làm được gì và mọi thứ nằm ở đâu.

Trên máy air-gap không tra cứu được ở đâu khác, nên trang này gom những thứ người dùng cần biết
trước khi bấm: engine đang chạy, khả năng xuất MP3 (CP-06), thư mục log (CP-15), và danh sách
định dạng ghi được.

Chỉ đọc — mọi lựa chọn thật (ngôn ngữ, profile, engine) nằm ở toolbar và hai tab kia. Trang này
cố tình không cho sửa gì để không sinh ra một nguồn sự thật thứ hai.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from morsedesk.app.paths import log_directory
from morsedesk.audio.io import SUPPORTED_EXT, mp3_capability


class SettingsPage(QWidget):
    def __init__(self, engine: str, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.report = QLabel(self)
        self.report.setWordWrap(True)
        self.report.setTextInteractionFlags(Qt.TextSelectableByMouse)   # chọn được để copy
        lay = QVBoxLayout(self)
        lay.addWidget(self.report)
        lay.addStretch(1)
        self.retranslate()

    def mp3_line(self) -> str:
        """Một dòng nêu xuất MP3 đi đường nào, hoặc thiếu gì nếu không đi được (CP-06)."""
        cap = mp3_capability()
        if cap == "libsndfile":
            return self.tr("MP3 export: available through libsndfile (built-in LAME).")
        if cap == "ffmpeg":
            return self.tr("MP3 export: available through the external ffmpeg command.")
        return self.tr(
            "MP3 export: NOT available. libsndfile here has no LAME encoder and ffmpeg is not on "
            "PATH; install ffmpeg or export another format."
        )

    def report_text(self) -> str:
        writable = ", ".join(e for e in SUPPORTED_EXT if e != ".mp3")
        return "\n\n".join([
            self.tr("Decoding engine: {engine}").format(engine=self.engine),
            self.mp3_line(),
            self.tr("Other formats written directly: {exts}").format(exts=writable),
            self.tr("Log file: {path}").format(path=log_directory() / "morsedesk.log"),
        ])

    def retranslate(self) -> None:
        self.report.setText(self.report_text())
