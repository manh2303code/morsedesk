"""Trang Giới thiệu: cho người không chuyên biết ứng dụng làm gì, mạnh ở đâu, giới hạn ở đâu.

Phần đầu (hero) là chỗ duy nhất của ứng dụng được "trang trí": nền hoàng hôn, logo, và tên
MORSEDESK viết bằng đèn tín hiệu — đúng mã Morse, không phải hoa văn. Lần đầu mở tab, các đèn
sáng lần lượt đúng nhịp 20 WPM rồi giữ sáng; đó là chuyển động duy nhất của trang. Phần thân là
tài liệu HTML theo ngôn ngữ giao diện; nút "Tài liệu kỹ thuật" mở cửa sổ tài liệu chi tiết.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from morsedesk import __version__
from morsedesk.app.branding import DUSK, DUSK_DEEP, LAMP, MIST, PAPER, app_icon, morse_elements
from morsedesk.app.reading import BODY_FONT, ReadingView, load_doc

MODEL_META = Path(__file__).resolve().parents[2] / "models" / "acoustic.json"
LAMP_OFF = "#34406A"        # đèn chưa sáng: đủ thấy hình, không tranh với đèn đã sáng
STRIP_TEXT = "MorseDesk"
DIT_MS = 60                 # 20 WPM theo PARIS: 1200 / 20


def model_version(meta_path: Path = MODEL_META) -> str:
    try:
        return str(json.loads(meta_path.read_text(encoding="utf-8")).get("version", "?"))
    except (OSError, ValueError):
        return "?"


class MorseStrip(QWidget):
    """Tên ứng dụng bằng đèn tín hiệu: dit là chấm tròn, dah là thanh bo tròn, đúng nhịp ITU."""

    def __init__(self, text: str = STRIP_TEXT, unit_px: float = 8.0, parent=None) -> None:
        super().__init__(parent)
        self.elements = morse_elements(text)
        self.unit_px = unit_px
        self.total_units = self.elements[-1][0] + self.elements[-1][1] if self.elements else 0.0
        self.lit = len(self.elements)             # mặc định sáng hết (test, ảnh chụp)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._played = False
        # Cao 1,3 đơn vị: chấm tròn tràn ra 0,15 đơn vị mỗi bên, khoảng 1 đơn vị giữa hai dấu vẫn
        # còn 0,7 — chấm cao 2 đơn vị (bản đầu) dính vào gạch bên cạnh.
        self.mark_h = unit_px * 1.3
        self.setFixedHeight(int(self.mark_h) + 2)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedWidth(int(self.total_units * unit_px) + 2)

    def play_once(self) -> None:
        """Sáng lần lượt theo đúng thời điểm của từng dấu; chỉ một lần mỗi phiên."""
        if self._played or not self.elements:
            return
        self._played = True
        self.lit = 0
        self._step = 0.0
        self._timer.start(DIT_MS)
        self.update()

    def finish(self) -> None:
        self._timer.stop()
        self.lit = len(self.elements)
        self.update()

    def _advance(self) -> None:
        self._step += 1.0
        while self.lit < len(self.elements) and self.elements[self.lit][0] < self._step:
            self.lit += 1
        self.update()
        if self.lit >= len(self.elements):
            self._timer.stop()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        h = self.mark_h
        for i, (start, length) in enumerate(self.elements):
            p.setBrush(QColor(LAMP if i < self.lit else LAMP_OFF))
            x = 1 + start * self.unit_px
            w = length * self.unit_px
            if length <= 1.0:
                # dit: chấm tròn đường kính bằng chiều cao dah, căn vào ô 1 đơn vị
                p.drawEllipse(QRectF(x + w / 2 - h / 2, 1, h, h))
            else:
                p.drawRoundedRect(QRectF(x, 1, w, h), h / 2, h / 2)
        p.end()


class AboutPage(QWidget):
    open_docs_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.language = "en"
        self.hero = QFrame(self)
        self.hero.setObjectName("aboutHero")
        self.hero.setStyleSheet(
            f"#aboutHero {{ background: {DUSK}; border-bottom: 3px solid {DUSK_DEEP}; }}"
            f"#aboutHero QLabel {{ background: transparent; }}"
        )
        self.logo = QLabel(self.hero)
        self.logo.setPixmap(app_icon().pixmap(QSize(76, 76)))
        self.logo.setFixedSize(76, 76)          # thiếu dòng này QLabel giãn ngang, đẩy cột chữ sang phải
        self.title = QLabel("MorseDesk", self.hero)
        tf = QFont(BODY_FONT)
        tf.setPointSizeF(24)
        tf.setWeight(QFont.Weight.Bold)
        self.title.setFont(tf)
        self.title.setStyleSheet(f"color: {PAPER};")
        self.tagline = QLabel(self.hero)
        self.tagline.setWordWrap(True)
        self.tagline.setMaximumWidth(620)       # ~70 ký tự mỗi dòng ở 11 pt
        gf = QFont(BODY_FONT)
        gf.setPointSizeF(11)
        self.tagline.setFont(gf)
        self.tagline.setStyleSheet(f"color: {MIST};")
        self.strip = MorseStrip(parent=self.hero)
        self.docs_button = QPushButton(self.hero)
        self.docs_button.setObjectName("docsButton")
        self.docs_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.docs_button.setStyleSheet(
            f"#docsButton {{ background: {LAMP}; color: {DUSK}; border: none; border-radius: 6px;"
            f" padding: 8px 18px; font-weight: 700; }}"
            f"#docsButton:hover {{ background: #FFB846; }}"
            f"#docsButton:focus {{ outline: none; border: 2px solid {PAPER}; }}"
        )
        self.docs_button.clicked.connect(self.open_docs_requested)
        self.version = QLabel(self.hero)
        self.version.setStyleSheet(f"color: {MIST};")

        text_col = QVBoxLayout()
        text_col.setSpacing(6)
        text_col.addWidget(self.title)
        text_col.addWidget(self.tagline)
        text_col.addSpacing(6)
        # Có căn lề thì widget bề rộng cố định KHÔNG còn giới hạn bề rộng tối đa của cả cột; thiếu
        # nó, Qt chia phần dư ra hai bên và cả hàng logo + chữ bị đẩy vào giữa hero.
        text_col.addWidget(self.strip, 0, Qt.AlignmentFlag.AlignLeft)
        top = QHBoxLayout()
        top.setSpacing(20)
        top.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(text_col, 1)
        actions = QHBoxLayout()
        actions.addSpacing(96)                  # thẳng hàng với cột chữ, không với logo
        actions.addWidget(self.docs_button)
        actions.addSpacing(16)
        actions.addWidget(self.version)
        actions.addStretch(1)
        hero_lay = QVBoxLayout(self.hero)
        hero_lay.setContentsMargins(28, 24, 28, 20)
        hero_lay.setSpacing(14)
        hero_lay.addLayout(top)
        hero_lay.addLayout(actions)

        self.body = ReadingView(self)
        self.body.anchorClicked.connect(self._on_link)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.hero)
        lay.addWidget(self.body, 1)
        self.retranslate()

    def set_language(self, code: str) -> None:
        self.language = code
        self.body.set_html(load_doc("about", code))

    def retranslate(self) -> None:
        self.tagline.setText(self.tr(
            "Turns Morse code audio into text in English, Russian and Kazakh, and text back "
            "into Morse. Nothing leaves this computer."))
        self.docs_button.setText(self.tr("Technical documentation"))
        self.version.setText(self.tr("Version {app}, acoustic model {model}").format(
            app=__version__, model=model_version()))
        self.body.set_html(load_doc("about", self.language))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.strip.play_once()

    def _on_link(self, url) -> None:
        if url.scheme() == "doc":
            self.open_docs_requested.emit()
