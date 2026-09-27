"""Trang Cài đặt: máy này làm được gì và mọi thứ nằm ở đâu.

Trên máy air-gap không tra cứu được ở đâu khác, nên trang này gom những thứ người dùng cần biết
trước khi bấm: engine và model đang chạy, mô hình ngôn ngữ nào có mặt, khả năng xuất MP3 (CP-06),
định dạng ghi được, thiết bị thu, và thư mục log (CP-15).

Chỉ đọc — mọi lựa chọn thật (ngôn ngữ, profile, engine) nằm ở thanh trên và các tab kia. Trang này
cố tình không cho sửa gì để không sinh ra một nguồn sự thật thứ hai. Bố cục dạng bảng số liệu hai
cột (nhãn nhỏ | giá trị), cùng họ với dải số đo của trang Giải mã.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.paths import log_directory
from morsedesk.audio.io import SUPPORTED_EXT, mp3_capability

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def model_parameters(hidden: int, feat_dim: int = 11, n_classes: int = 65) -> int:
    """Số tham số của MorseNet (3 Conv1d + BiGRU + Linear) theo `hidden` — đúng công thức của
    tools/net_torch.py, kiểm bằng test với con số 1 119 425 của model 0.4.0–0.6.0 (cùng kiến trúc)."""
    conv = (feat_dim * 32 * 5 + 32) + (32 * 64 * 5 + 64) + (64 * 64 * 5 + 64)
    gru = 2 * 3 * (hidden * 64 + hidden * hidden + 2 * hidden)
    linear = 2 * hidden * n_classes + n_classes
    return conv + gru + linear


def model_info(models_dir: Path = MODELS_DIR) -> tuple[str, int | None]:
    try:
        meta = json.loads((models_dir / "acoustic.json").read_text(encoding="utf-8"))
        return str(meta.get("version", "?")), model_parameters(int(meta["config"]["hidden"]))
    except (OSError, ValueError, KeyError):
        return "?", None


class SettingsPage(QWidget):
    def __init__(self, engine: str, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        # Báo cáo dạng văn bản: nguồn cho nút "Sao chép báo cáo" và cho test.
        self.report = QLabel(self)
        self.report.setWordWrap(True)
        self.report.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.report.hide()
        self.title = QLabel(self)
        self.title.setProperty("role", "section")
        self.panel = QFrame(self)
        self.panel.setProperty("panel", True)
        self.grid = QGridLayout(self.panel)
        self.grid.setContentsMargins(20, 16, 20, 16)
        self.grid.setHorizontalSpacing(28)
        self.grid.setVerticalSpacing(12)
        self.rows: list[tuple[QLabel, QLabel]] = []
        for r in range(7):
            cap, val = QLabel(self.panel), QLabel(self.panel)
            cap.setProperty("role", "caption")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.grid.addWidget(cap, r, 0, Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(val, r, 1)
            self.rows.append((cap, val))
        self.grid.setColumnStretch(1, 1)
        self.open_logs_button = QPushButton(self)
        self.copy_button = QPushButton(self)
        self.open_logs_button.clicked.connect(self._open_logs)
        self.copy_button.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.report_text()))
        actions = QHBoxLayout()
        actions.addWidget(self.open_logs_button)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        lay.addWidget(self.title)
        lay.addWidget(self.panel)
        lay.addLayout(actions)
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

    def _values(self) -> list[tuple[str, str]]:
        version, params = model_info()
        lm_dir = MODELS_DIR / "lm"
        lms = [f"{code.upper()} {(lm_dir / f'{code}.bin').stat().st_size / 1e6:.1f} MB"
               for code in ("en", "ru", "kk") if (lm_dir / f"{code}.bin").is_file()]
        try:
            from morsedesk.app.live_worker import input_devices

            devices = [name for _, name in input_devices()]
        except Exception:
            devices = []
        model_text = self.tr("version {v}").format(v=version)
        if params:
            model_text += ", " + self.tr("{n} parameters").format(n=f"{params:,}".replace(",", " "))
        return [
            (self.tr("Decoding engine"), self.engine_text()),
            (self.tr("Acoustic model"), model_text),
            (self.tr("Language models"), ", ".join(lms) if lms else self.tr("none found")),
            (self.tr("MP3 export"), self.mp3_line().split(":", 1)[-1].strip()),
            (self.tr("Formats written directly"), ", ".join(e for e in SUPPORTED_EXT if e != ".mp3")),
            (self.tr("Sound inputs"), "\n".join(devices) if devices else self.tr("none found")),
            (self.tr("Log file"), str(log_directory() / "morsedesk.log")),
        ]

    def engine_text(self) -> str:
        return {
            "onnx": self.tr("Neural network (ONNX) with the classic DSP decoder"),
            "baseline": self.tr("Classic DSP decoder only"),
            "deepcw": "DeepCW",
        }.get(self.engine, self.engine)

    def _open_logs(self) -> None:
        folder = log_directory()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def retranslate(self) -> None:
        self.report.setText(self.report_text())
        self.title.setText(self.tr("This computer"))
        for (cap, val), (c, v) in zip(self.rows, self._values(), strict=True):
            cap.setText(c)
            val.setText(v)
        self.open_logs_button.setText(self.tr("Open log folder"))
        self.copy_button.setText(self.tr("Copy report"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
