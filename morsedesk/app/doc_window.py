"""Cửa sổ tài liệu kỹ thuật, mở theo ngôn ngữ giao diện đang dùng.

Mục lục lấy từ chính tài liệu (mỗi `<a name>` đứng trước một `<h2>`), nên bản dịch tự có mục lục
đúng ngôn ngữ mà không phải khai báo lại. Vạch màu cạnh mỗi mục là màu tầng xử lý của mục đó —
cùng mã màu với tiêu đề trong tài liệu.
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass

from PySide6.QtCore import QMarginsF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPageLayout, QPageSize, QPdfWriter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.branding import DUSK, DUSK_DEEP, INK, LAMP, LAYER_COLORS, MIST, PAPER, app_icon
from morsedesk.app.reading import ReadingView, load_doc

_SECTION_RE = re.compile(
    r'<a name="([^"]+)"></a>\s*<h2(?:\s+class="([\w-]+)")?>(.*?)</h2>', re.S)
NEUTRAL = "#8792A8"


@dataclass(frozen=True)
class Section:
    anchor: str
    layer: str | None
    title: str


def sections(doc_html: str) -> list[Section]:
    out = []
    for anchor, layer, title in _SECTION_RE.findall(doc_html):
        text = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        out.append(Section(anchor, layer or None, " ".join(text.split())))
    return out


def _swatch(color: str) -> QIcon:
    pm = QPixmap(QSize(6, 22))
    pm.fill(QColor(color))
    return QIcon(pm)


class TechDocWindow(QWidget):
    def __init__(self, language: str = "en", parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowIcon(app_icon())
        self.resize(1080, 760)
        self.language = language

        header = QFrame(self)
        header.setObjectName("docHeader")
        header.setStyleSheet(
            f"#docHeader {{ background: {DUSK}; border-bottom: 3px solid {DUSK_DEEP}; }}"
            f"#docHeader QLabel {{ background: transparent; color: {PAPER}; }}"
        )
        logo = QLabel(header)
        logo.setPixmap(app_icon().pixmap(QSize(32, 32)))
        self.heading = QLabel(header)
        self.heading.setStyleSheet(f"color: {PAPER}; font-size: 13pt; font-weight: 700;")
        self.pdf_button = QPushButton(header)
        self.pdf_button.setObjectName("pdfButton")
        self.pdf_button.setStyleSheet(
            f"#pdfButton {{ background: transparent; color: {LAMP}; border: 1px solid {LAMP};"
            f" border-radius: 6px; padding: 6px 14px; font-weight: 600; }}"
            f"#pdfButton:hover {{ background: {LAMP}; color: {DUSK}; }}"
        )
        self.pdf_button.clicked.connect(self.save_pdf)
        self.status = QLabel(header)
        self.status.setStyleSheet(f"color: {MIST};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 10, 18, 10)
        hl.addWidget(logo)
        hl.addSpacing(8)
        hl.addWidget(self.heading)
        hl.addStretch(1)
        hl.addWidget(self.status)
        hl.addSpacing(10)
        hl.addWidget(self.pdf_button)

        self.toc = QListWidget(self)
        self.toc.setObjectName("docToc")
        self.toc.setIconSize(QSize(6, 22))
        # Tiêu đề Kazakh/Nga dài hơn tiếng Anh tới 40 %: không xuống dòng thì bị cắt cụt.
        self.toc.setWordWrap(True)
        self.toc.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.toc.setStyleSheet(
            f"#docToc {{ background: #E9EDF4; color: {INK}; border: none; padding-top: 12px; }}"
            f"#docToc::item {{ padding: 5px 10px; }}"
            f"#docToc::item:selected {{ background: {PAPER}; color: {INK}; }}"
        )
        self.toc.itemClicked.connect(self._jump)
        self.view = ReadingView(self)
        self.view.anchorClicked.connect(lambda url: self.view.scrollToAnchor(url.fragment()))

        split = QSplitter(self)
        split.addWidget(self.toc)
        split.addWidget(self.view)
        split.setStretchFactor(1, 1)
        split.setSizes([280, 800])
        split.setHandleWidth(1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(header)
        lay.addWidget(split, 1)
        self.set_language(language)

    def set_language(self, code: str) -> None:
        self.language = code
        doc = load_doc("technical", code)
        self.view.set_html(doc)
        self.toc.clear()
        for sec in sections(doc):
            color = LAYER_COLORS[sec.layer][0] if sec.layer in LAYER_COLORS else NEUTRAL
            item = QListWidgetItem(_swatch(color), sec.title)
            item.setData(Qt.ItemDataRole.UserRole, sec.anchor)
            self.toc.addItem(item)
        self.status.clear()
        self.retranslate()

    def retranslate(self) -> None:
        title = self.tr("MorseDesk technical reference")
        self.setWindowTitle(title)
        self.heading.setText(title)
        self.pdf_button.setText(self.tr("Save as PDF…"))

    def _jump(self, item: QListWidgetItem) -> None:
        self.view.scrollToAnchor(item.data(Qt.ItemDataRole.UserRole))

    def save_pdf(self, path: str | None = None) -> bool:
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, self.tr("Save as PDF…"), f"MorseDesk-technical-{self.language}.pdf",
                self.tr("PDF files (*.pdf)"))
            if not path:
                return False
        writer = QPdfWriter(path)
        writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                         QPageLayout.Orientation.Portrait, QMarginsF(15, 15, 15, 15),
                                         QPageLayout.Unit.Millimeter))
        writer.setTitle(self.windowTitle())
        doc = self.view.document().clone(self)
        doc.print_(writer)
        del writer                               # đóng file PDF ngay, trước khi báo đã lưu
        ok = os.path.exists(path) and os.path.getsize(path) > 0
        self.status.setText(self.tr("Saved {path}").format(path=path) if ok
                            else self.tr("Could not save {path}").format(path=path))
        return ok
