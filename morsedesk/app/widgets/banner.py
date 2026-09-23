"""Thanh thông báo đỏ (lỗi) hoặc vàng (cảnh báo) có nút đóng."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

# (nền, viền nhấn, chữ) cho nền đêm. Bản cũ là nền pastel sáng của giao diện sáng và chỉ đặt `color`
# cho KHUNG: nhãn con ăn luật `QWidget { color: TEXT }` của theme nên ra chữ trắng trên nền vàng
# nhạt, 1,05:1 — gần như vô hình (ảnh chụp người dùng 24/09). Nay màu chữ đặt thẳng cho nhãn và
# nút, và tools/contrast_audit.py đo lại trên ảnh chụp thật.
COLORS = {
    "error": ("#3B1D24", "#F26B5B", "#FFD6D0"),       # chữ/nền 12,6:1
    "warning": ("#372C12", "#E0B341", "#FFE6A3"),     # chữ/nền 13,1:1
}


class Banner(QFrame):
    """Banner nằm ngang: nhãn văn bản + nút đóng "×"; ẩn khi không có nội dung."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.level: str | None = None
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self.close_button = QToolButton(self)
        self.close_button.setText("×")
        self.close_button.clicked.connect(self.clear)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 6, 6)
        lay.addWidget(self._label, 1)
        lay.addWidget(self.close_button, 0)
        self.hide()

    def _show(self, level: str, text: str) -> None:
        self.level = level
        self._label.setText(text)
        self.setToolTip("")     # người gọi tự đặt tooltip sau; không để sót tooltip của lần trước
        bg, accent, fg = COLORS[level]
        self.setStyleSheet(
            f"Banner {{ background: {bg}; border: 1px solid {accent}; border-left: 4px solid {accent};"
            f" border-radius: 6px; }}"
            f"Banner QLabel {{ color: {fg}; background: transparent; }}"
            f"Banner QToolButton {{ color: {fg}; background: transparent; border: none;"
            f" font-size: 13pt; padding: 0px 6px; }}"
            f"Banner QToolButton:hover {{ color: #FFFFFF; }}")
        self.show()

    def show_error(self, text: str) -> None:
        """Hiện banner đỏ với thông điệp lỗi `text`."""
        self._show("error", text)

    def show_warning(self, text: str) -> None:
        """Hiện banner vàng với thông điệp cảnh báo `text`."""
        self._show("warning", text)

    def clear(self) -> None:
        """Xóa nội dung và ẩn banner (cũng là handler của nút đóng)."""
        self.level = None
        self._label.setText("")
        self.setToolTip("")
        self.hide()

    def text(self) -> str:
        return self._label.text()
