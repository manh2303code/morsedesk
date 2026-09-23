"""Bề mặt đọc dùng chung cho trang Giới thiệu và tài liệu kỹ thuật.

Tài liệu là HTML trong `morsedesk/app/docs/<loại>_<ngôn ngữ>.html`, hiển thị bằng QTextBrowser
ngay trong ứng dụng. Không mở trình duyệt: máy air-gap có thể không có, và Firefox dạng snap trên
Ubuntu không đọc được file nằm trong thư mục tạm của AppImage hay thư mục ẩn trong $HOME.

Qt chỉ hiểu một tập con HTML/CSS (không flex, không bo góc), nên bố cục dựa vào bảng và màu nền
ô. CSS nằm ở đây, không nằm trong file HTML, để người dịch chỉ phải giữ nguyên thẻ và class.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QTextBrowser, QTextEdit

from morsedesk.app.branding import INK, LAYER_COLORS, PAPER, SLATE

DOCS_DIR = Path(__file__).resolve().parent / "docs"
DOC_LANGUAGES = ("en", "ru", "kk")

# Độ dài dòng ~75 ký tự ở cỡ chữ thân bài; bảng số liệu dùng chung bề rộng này.
# line-height của Qt nhân lên khoảng dòng SẴN CÓ của font (Noto Sans ~1,36 em), không phải cỡ chữ
# như trình duyệt: 145 % ra gần gấp đôi. 108 % là đủ thoáng.
MEASURE_PX = 700

BODY_FONT = "Noto Sans"
MONO_FONT = "DejaVu Sans Mono"


def _layer_css() -> str:
    rules = []
    for name, (strong, _light) in LAYER_COLORS.items():
        rules.append(f"h2.{name} {{ color: {strong}; }}")
        rules.append(f"span.c-{name} {{ color: {strong}; font-weight: 600; }}")
    return "\n".join(rules)


DOC_CSS = f"""
body {{ font-family: "{BODY_FONT}"; font-size: 10.5pt; color: {INK}; }}
h1 {{ font-size: 21pt; font-weight: 700; margin-top: 4px; margin-bottom: 6px; }}
h2 {{ font-size: 14.5pt; font-weight: 700; margin-top: 28px; margin-bottom: 8px; }}
h3 {{ font-size: 11.5pt; font-weight: 600; margin-top: 18px; margin-bottom: 6px; }}
p {{ margin-top: 0px; margin-bottom: 10px; line-height: 108%; }}
li {{ margin-bottom: 6px; }}
p.lead {{ font-size: 12pt; line-height: 108%; }}
p.meta, p.muted {{ color: {SLATE}; }}
p.formula {{ font-family: "{MONO_FONT}"; font-size: 9.5pt; color: {LAYER_COLORS["language"][0]};
            background-color: {LAYER_COLORS["language"][1]}; margin-left: 12px; }}
span.mono, span.morse, td.morse {{ font-family: "{MONO_FONT}"; }}
span.morse, td.morse {{ font-weight: 700; }}
.kk {{ font-weight: 700; }}
span.sure {{ color: #1E7A3E; font-weight: 700; }}
span.check {{ color: #946200; font-weight: 700; }}
span.doubt {{ color: #B3261E; font-weight: 700; }}
table.data {{ border-collapse: collapse; margin-bottom: 12px; }}
table.data td, table.data th {{ border: 1px solid #D5DCE8; }}
table.data th, table.flow th {{ background-color: #E6EBF3; font-weight: 600; text-align: left; }}
table.flow {{ border-collapse: collapse; margin-bottom: 12px; }}
table.flow td, table.flow th {{ border-bottom: 1px solid #D5DCE8; }}
table.facts {{ border-collapse: collapse; margin-bottom: 12px; }}
table.facts td {{ border-bottom: 1px solid #DDE3EE; }}
td.term {{ font-weight: 700; }}
.num {{ text-align: right; }}
table.note {{ margin-top: 4px; margin-bottom: 14px; }}
a {{ color: {LAYER_COLORS["signal"][0]}; }}
{_layer_css()}
"""


def doc_path(kind: str, language: str) -> Path:
    """File tài liệu theo ngôn ngữ giao diện; thiếu bản dịch thì rơi về tiếng Anh."""
    path = DOCS_DIR / f"{kind}_{language}.html"
    return path if path.exists() else DOCS_DIR / f"{kind}_en.html"


def load_doc(kind: str, language: str) -> str:
    return doc_path(kind, language).read_text(encoding="utf-8")


class ReadingView(QTextBrowser):
    """QTextBrowser nền giấy, dòng dài cố định và nằm GIỮA vùng hiển thị khi cửa sổ rộng."""

    def __init__(self, parent=None, measure: int = MEASURE_PX) -> None:
        super().__init__(parent)
        self._measure = measure
        self.setOpenLinks(False)              # bên dùng tự xử lý liên kết (mở tài liệu, cuộn tới mục)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.setLineWrapMode(QTextEdit.LineWrapMode.FixedPixelWidth)
        self.setLineWrapColumnOrWidth(measure)
        self.document().setDefaultStyleSheet(DOC_CSS)
        self.document().setDocumentMargin(28)
        pal = self.palette()
        # Màu cố định chứ không theo hệ thống: tài liệu có màu theo tầng, phải đọc được như nhau
        # dù Windows đang ở chế độ tối hay Ubuntu ở chế độ sáng.
        pal.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        pal.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        self.setPalette(pal)
        self.setStyleSheet(f"QTextBrowser {{ background: {PAPER}; color: {INK}; border: none; }}")

    def set_html(self, html: str) -> None:
        self.document().setDefaultStyleSheet(DOC_CSS)
        self.setHtml(html)

    def resizeEvent(self, event) -> None:
        # Căn giữa cột chữ: phần dư hai bên thành lề của vùng hiển thị.
        doc_width = self._measure + 2 * int(self.document().documentMargin())
        spare = max(0, self.width() - doc_width - self.verticalScrollBar().sizeHint().width())
        self.setViewportMargins(spare // 2, 14, 0, 0)     # 14 px: tiêu đề đầu không dính mép trên
        super().resizeEvent(event)
