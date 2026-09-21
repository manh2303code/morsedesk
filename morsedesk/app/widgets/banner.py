"""Thanh thông báo đỏ (lỗi) hoặc vàng (cảnh báo) có nút đóng."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

_STYLE = {
    "error": "background:#f7c6c6; border:1px solid #c0392b; color:#5a0000;",
    "warning": "background:#fff2b3; border:1px solid #b7950b; color:#4a3b00;",
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
        lay.setContentsMargins(8, 4, 4, 4)
        lay.addWidget(self._label, 1)
        lay.addWidget(self.close_button, 0)
        self.hide()

    def _show(self, level: str, text: str) -> None:
        self.level = level
        self._label.setText(text)
        self.setToolTip("")     # người gọi tự đặt tooltip sau; không để sót tooltip của lần trước
        self.setStyleSheet(f"Banner {{ {_STYLE[level]} }}")
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
