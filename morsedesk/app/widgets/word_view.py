"""Hiển thị các từ giải mã, nền theo độ tin cậy, tooltip thời điểm; click từ phát start_s."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget

from morsedesk.api import FALLBACK_CONFIDENCE, Word
from morsedesk.app.widgets.flow_layout import FlowLayout

WORD_GOOD = 0.8
COLOR_GOOD, COLOR_MID, COLOR_LOW = "#c8f0c8", "#fff2b3", "#f7c6c6"
# Ba màu nền trên đều nhạt, nên phải ghim màu chữ tối thay vì để widget lấy màu chữ của
# bảng màu hệ thống: ở giao diện tối của Windows/KDE màu đó là trắng, cho tương phản
# 1,25:1 (đo trên ảnh chụp thật) tức là không đọc được.
TEXT_COLOR = "#1a1a1a"


def confidence_color(c: float) -> str:
    """Màu nền theo ngưỡng tin cậy: xanh lá (>=WORD_GOOD), vàng (>=FALLBACK_CONFIDENCE), đỏ nhạt."""
    if c >= WORD_GOOD:
        return COLOR_GOOD
    if c >= FALLBACK_CONFIDENCE:
        return COLOR_MID
    return COLOR_LOW


class WordLabel(QLabel):
    """Một từ đã giải mã; click chuột trái phát `clicked(start_s)`."""

    clicked = Signal(float)

    def __init__(self, word: Word, parent=None) -> None:
        super().__init__(word.text, parent)
        self.word = word
        self.setStyleSheet(
            f"QLabel {{ background:{confidence_color(word.confidence)}; color:{TEXT_COLOR}; "
            "padding:3px 6px; border-radius:4px; font-size:16pt; }"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retranslate()

    def retranslate(self) -> None:
        self.setToolTip(
            self.tr("confidence {conf:.2f} · {start:.2f}–{end:.2f} s").format(
                conf=self.word.confidence, start=self.word.start_s, end=self.word.end_s
            )
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.word.start_s)
        super().mousePressEvent(event)


class WordView(QWidget):
    """Danh sách từ đã giải mã, xếp theo FlowLayout; rỗng thì hiện placeholder."""

    word_clicked = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = FlowLayout(self, margin=6, spacing=6)
        self._labels: list[WordLabel] = []
        self._placeholder = QLabel(self)
        self._placeholder.setStyleSheet("color: gray;")
        self._layout.addWidget(self._placeholder)
        self.retranslate()

    def set_placeholder(self, text: str) -> None:
        """Đặt văn bản hiện khi chưa có từ nào (gọi lại sau mỗi lần dịch nếu cần tùy biến)."""
        self._placeholder.setText(text)

    def set_words(self, words: list[Word]) -> None:
        """Thay toàn bộ danh sách từ hiển thị bằng `words`."""
        self.clear()
        self._placeholder.setVisible(not words)
        for w in words:
            lb = WordLabel(w, self)
            lb.clicked.connect(self.word_clicked.emit)
            self._layout.addWidget(lb)
            self._labels.append(lb)
        self._layout.invalidate()

    def clear(self) -> None:
        """Xóa toàn bộ nhãn từ, quay về trạng thái placeholder."""
        for lb in self._labels:
            self._layout.removeWidget(lb)
            lb.setParent(None)
            lb.deleteLater()
        self._labels = []
        self._placeholder.setVisible(True)

    def labels(self) -> list[WordLabel]:
        return list(self._labels)

    def retranslate(self) -> None:
        self._placeholder.setText(self.tr("Open an audio file to decode."))
        for lb in self._labels:
            lb.retranslate()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
