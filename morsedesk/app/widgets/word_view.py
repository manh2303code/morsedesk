"""Hiển thị các từ giải mã, nền theo độ tin cậy, tooltip thời điểm; click từ phát start_s."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget

from morsedesk.api import FALLBACK_CONFIDENCE, Word
from morsedesk.app.widgets.flow_layout import FlowLayout

WORD_GOOD = 0.8
# Nền tối (giao diện "thiết bị đo"): nền chip là màu độ tin cậy pha đậm vào nền đêm, chữ sáng,
# và một gạch chân màu tươi mang thông tin chính — đọc được cả khi liếc nhanh.
COLOR_GOOD, COLOR_MID, COLOR_LOW = "#1E4634", "#4A3E17", "#4E2323"
UNDERLINE = {COLOR_GOOD: "#46C47A", COLOR_MID: "#E0B341", COLOR_LOW: "#F26B5B"}
# Ghim màu chữ thay vì để widget lấy màu chữ của bảng màu hệ thống: bản đầu từng ra chữ trắng
# trên nền nhạt (1,25:1, đo trên ảnh chụp thật). Test kiểm từng cặp nền/chữ đạt 4,5:1.
TEXT_COLOR = "#E6ECF7"
# Viền của từ đang phát: màu đèn tín hiệu, đủ nổi trên cả ba nền.
ACTIVE_BORDER = "#F5A524"


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
        self._active = False
        self._apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retranslate()

    def _apply_style(self) -> None:
        # Từ đang nghe được đánh dấu bằng VIỀN chứ không bằng màu nền: nền đã mang thông tin độ
        # tin cậy, đổi nó đi là xóa mất thông tin đó ngay lúc người dùng cần soi nhất.
        bg = confidence_color(self.word.confidence)
        border = ACTIVE_BORDER if self._active else "transparent"
        self.setStyleSheet(
            f"QLabel {{ background:{bg}; color:{TEXT_COLOR}; padding:3px 8px 1px 8px; "
            f"border-radius:6px; border:2px solid {border}; border-bottom:3px solid {UNDERLINE[bg]}; "
            f"font-size:17pt; font-weight:600; }}"
        )

    def set_active(self, flag: bool) -> None:
        """Đánh dấu (hoặc bỏ đánh dấu) đây là từ con trỏ phát đang chạy qua."""
        if flag != self._active:
            self._active = flag
            self._apply_style()

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

    def __init__(self, parent=None, live: bool = False) -> None:
        super().__init__(parent)
        self._live = live               # trang Nghe có câu gợi ý riêng, không phải "mở file"
        self._layout = FlowLayout(self, margin=6, spacing=6)
        self._labels: list[WordLabel] = []
        self._placeholder = QLabel(self)
        self._placeholder.setProperty("role", "hint")
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

    def set_playhead(self, t_s: float | None) -> None:
        """Tô từ chứa mốc thời gian `t_s`; `None` để bỏ tô hết.

        Con trỏ hay rơi vào khoảng lặng GIỮA hai từ (mỗi từ chỉ chiếm start_s..end_s). Khi đó
        giữ nguyên từ vừa qua thay vì bỏ trắng, nếu không vệt sáng sẽ nhấp nháy mỗi lần im lặng.
        """
        if t_s is None:
            for lb in self._labels:
                lb.set_active(False)
            return
        active = None
        for lb in self._labels:
            if lb.word.start_s <= t_s:
                active = lb           # từ cuối cùng đã bắt đầu tính tới mốc này
            else:
                break
        for lb in self._labels:
            lb.set_active(lb is active)

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
        self._placeholder.setText(self.tr("Words appear here as they are heard.") if self._live
                                  else self.tr("Open an audio file to decode."))
        for lb in self._labels:
            lb.retranslate()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
