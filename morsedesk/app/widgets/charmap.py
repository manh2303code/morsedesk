"""Bảng bấm ký tự Cyrillic và 9 chữ Kazakh cho trang tạo mã."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from morsedesk.app.widgets.flow_layout import FlowLayout

CYRILLIC = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
KAZAKH_EXTRA = "ӘҒҚҢӨҰҮҺІ"


class CharMap(QWidget):
    """Hai hàng nút ký tự (Cyrillic, Kazakh riêng); ẩn theo profile đang chọn."""

    char_clicked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cyr: list[QPushButton] = []
        self._kk: list[QPushButton] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        row1, row2 = QWidget(self), QWidget(self)
        f1, f2 = FlowLayout(row1, spacing=2), FlowLayout(row2, spacing=2)
        for ch in CYRILLIC:
            self._cyr.append(self._button(ch, row1, f1))
        for ch in KAZAKH_EXTRA:
            self._kk.append(self._button(ch, row2, f2))
        self._row2 = row2
        lay.addWidget(row1)
        lay.addWidget(row2)
        self.set_profile("en")

    def _button(self, ch: str, parent: QWidget, layout: FlowLayout) -> QPushButton:
        b = QPushButton(ch, parent)
        b.setFixedSize(36, 32)
        # Phím nhỏ: phần đệm 14 px của nút thường (theme) cắt mất nửa chữ Kirin — đã thấy trên ảnh chụp.
        b.setStyleSheet("QPushButton { padding: 0px; font-size: 11pt; font-weight: 600; }")
        b.clicked.connect(lambda _=False, c=ch: self.char_clicked.emit(c))
        layout.addWidget(b)
        return b

    def set_profile(self, profile_id: str) -> None:
        """Ẩn cả bảng khi `en`; nhóm chữ Kazakh chỉ hiện khi `kk-cyrl-ru`."""
        self.setVisible(profile_id != "en")
        self._row2.setVisible(profile_id == "kk-cyrl-ru")

    def buttons(self) -> list[QPushButton]:
        return self._cyr + self._kk
