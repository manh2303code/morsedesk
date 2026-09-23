"""Lớp phủ khi đang giải mã: vòng tiến trình lớn, tầng đang chạy, nút Hủy.

Yêu cầu người dùng: thay thanh tiến trình bằng vòng tròn hiện % theo thời gian thực, và CHỈ hiện
kết quả khi mô hình ngôn ngữ đã xong. Lớp phủ che vùng kết quả cũ trong lúc chạy, nên không ai đọc
nhầm kết quả của file trước là kết quả của file đang giải. Dòng chữ dưới vòng nói đang ở tầng nào,
theo đúng các mốc của `morsedesk.progress` — phần lâu nhất là mô hình ngôn ngữ, và người dùng nên
biết máy đang làm việc đó chứ không phải đang treo.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from morsedesk.app.theme import NIGHT
from morsedesk.app.widgets.progress_ring import ProgressRing
from morsedesk.progress import STAGE_ACOUSTIC, STAGE_LANGUAGE


class BusyOverlay(QWidget):
    def __init__(self, target: QWidget, parent=None) -> None:
        super().__init__(parent or target)
        self._target = target
        self.ring = ProgressRing(diameter=112, thickness=9, parent=self)
        self.stage_label = QLabel(self)
        self.stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage_label.setStyleSheet("font-size: 12pt; font-weight: 600;")
        self.hint_label = QLabel(self)
        self.hint_label.setProperty("role", "hint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        self._lay = QVBoxLayout(self)
        self._lay.addStretch(1)
        self._lay.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self._lay.addSpacing(14)
        self._lay.addWidget(self.stage_label)
        self._lay.addWidget(self.hint_label)
        self._lay.addSpacing(10)
        self._extra_at = self._lay.count()
        self._lay.addStretch(1)
        target.installEventFilter(self)
        self.hide()
        self._sync_geometry()
        self.retranslate()

    def add_widget(self, w: QWidget) -> None:
        """Thêm một widget dưới dòng chữ (vd. nút Hủy của trang)."""
        self._lay.insertWidget(self._extra_at, w, 0, Qt.AlignmentFlag.AlignHCenter)
        self._extra_at += 1

    def eventFilter(self, obj, event) -> bool:
        if obj is self._target and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._sync_geometry()
        return super().eventFilter(obj, event)

    def _sync_geometry(self) -> None:
        if self.parent() is self._target:
            self.setGeometry(self._target.rect())
        else:
            self.setGeometry(self._target.geometry())

    def start(self) -> None:
        self.ring.setRange(0, 0)
        self._sync_geometry()
        self.show()
        self.raise_()
        self.set_progress(0, 0)

    def stop(self) -> None:
        self.hide()

    def set_progress(self, done: int, total: int) -> None:
        if total <= 0:
            self.ring.setRange(0, 0)
            self.stage_label.setText(self.tr("Reading the signal…"))
            return
        self.ring.setRange(0, int(total))
        self.ring.setValue(max(0, min(int(done), int(total))))
        frac = done / total
        if frac < STAGE_ACOUSTIC[1]:
            self.stage_label.setText(self.tr("Reading the signal…"))
        elif frac < STAGE_LANGUAGE[1]:
            self.stage_label.setText(self.tr("Choosing the most likely text with the language model…"))
        else:
            self.stage_label.setText(self.tr("Finishing…"))

    def retranslate(self) -> None:
        self.hint_label.setText(self.tr("The result appears when the language model has finished."))
        if not self.stage_label.text():
            self.stage_label.setText(self.tr("Reading the signal…"))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        c = QColor(NIGHT)
        c.setAlpha(232)
        p.fillRect(self.rect(), c)
        p.end()
