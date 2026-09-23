"""Thanh phát audio: nghe lại chính file vừa giải mã, và cho biết đang nghe tới đâu.

Vì sao cần: khi bộ giải mã đọc sai một chỗ, cách duy nhất để biết lỗi nằm ở tín hiệu hay ở model
là **nghe lại đúng đoạn đó**. Không có thanh này thì người dùng phải mở file bằng ứng dụng khác
rồi tự dò, mà máy đích air-gap có khi không có ứng dụng nào khác.

Vị trí phát được phát ra qua `position_changed` để trang giải mã tô từ đang nghe — chữ chạy theo
tiếng, đúng kiểu các máy thu Morse trên thị trường.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from morsedesk.audio.playback import AudioPlayback, PlaybackError

TICK_MS = 50            # 20 lần/giây: con trỏ mượt mà không ngốn CPU đáng kể
SLIDER_STEPS = 1000     # thanh trượt làm việc bằng số nguyên; 1000 nấc đủ mịn cho clip 1 giờ


BUTTON_PX = 40
ICON_INK = "#1A1206"        # hình trên nền vàng đèn tín hiệu (9,6:1)


def media_icon(kind: str, px: int = 18) -> QIcon:
    """Biểu tượng ▶ / ❚❚ vẽ bằng QPainter: sắc nét ở mọi tỉ lệ màn hình và không phụ thuộc font
    có glyph ▶ hay không (Noto Sans không có; ký tự thay thế trông lệch cỡ)."""
    icon = QIcon()
    for scale in (1, 2):
        size = px * scale
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ICON_INK))
        if kind == "play":
            # tam giác lệch phải một chút: về thị giác, tâm tam giác nằm ở trọng tâm, không ở giữa hộp
            p.drawPolygon(QPolygonF([QPointF(size * 0.26, size * 0.12), QPointF(size * 0.90, size * 0.50),
                                     QPointF(size * 0.26, size * 0.88)]))
        else:
            w = size * 0.26
            p.drawRoundedRect(QRectF(size * 0.16, size * 0.12, w, size * 0.76), w * 0.3, w * 0.3)
            p.drawRoundedRect(QRectF(size * 0.58, size * 0.12, w, size * 0.76), w * 0.3, w * 0.3)
        p.end()
        pm.setDevicePixelRatio(scale)
        icon.addPixmap(pm)
    return icon


def format_time(seconds: float) -> str:
    """`m:ss`, hoặc `h:mm:ss` khi quá một giờ (trần thời lượng của app là 1 giờ)."""
    s = max(0, int(seconds))
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


class PlayerBar(QWidget):
    """Nút phát/tạm dừng, thanh trượt, đồng hồ. Tự ẩn khi máy không có thiết bị phát."""

    position_changed = Signal(float)        # giây, phát ~20 lần/giây khi đang chạy
    error = Signal(str)                     # thông điệp lỗi thiết bị, để trang hiện banner

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.playback = AudioPlayback()
        self._seeking = False               # đang kéo thanh trượt: đừng để timer giật nó về
        # Trang chủ quản gán hàm này để nạp audio ngay trước lần phát đầu. Nạp lười vì một bản
        # ghi 37 phút chiếm 71 MB, và phần lớn lần giải mã người dùng chỉ đọc chữ chứ không nghe.
        # Dùng hook thay vì nối thêm slot vào `clicked`: slot nối sau sẽ chạy SAU `toggle`, tức
        # là nạp xong thì đã lỡ mất lần bấm.
        self.ensure_loaded = None

        # Nút tròn có biểu tượng thay cho chữ "Play": nhận ra ngay mà không phải đọc, ở bất kỳ ngôn
        # ngữ giao diện nào. Chữ vẫn có trong tooltip và tên trợ năng (trình đọc màn hình).
        self.play_button = QPushButton(self)
        self.play_button.setCheckable(False)
        self.play_button.setEnabled(False)
        self.play_button.setFixedSize(BUTTON_PX, BUTTON_PX)
        self.play_button.setIconSize(QSize(18, 18))
        self.play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_button.setStyleSheet(
            f"QPushButton {{ background: #F5A524; border: none; border-radius: {BUTTON_PX // 2}px;"
            f" padding: 0px; }}"
            "QPushButton:hover { background: #FFB846; }"
            "QPushButton:focus { border: 2px solid #E6ECF7; }"
            "QPushButton:disabled { background: #3A3320; }")
        self._icons = {"play": media_icon("play"), "pause": media_icon("pause")}
        self.play_button.clicked.connect(self.toggle)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setEnabled(False)
        self.slider.sliderPressed.connect(self._on_press)
        self.slider.sliderReleased.connect(self._on_release)
        self.slider.sliderMoved.connect(self._on_moved)

        self.time_label = QLabel("0:00 / 0:00", self)
        self.time_label.setMinimumWidth(110)
        self.time_label.setStyleSheet('font-family: "DejaVu Sans Mono"; color: #95A3BF;')
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.play_button)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.time_label)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self.retranslate()

    # ---- nạp và điều khiển ----
    def load(self, x, sample_rate: int) -> None:
        """Nạp audio vừa giải mã. Con trỏ về 0, chưa phát."""
        self.playback.load(x, sample_rate)
        has = self.playback.duration_s > 0
        self.play_button.setEnabled(has)
        self.slider.setEnabled(has)
        self.slider.setValue(0)
        self._update_labels()
        self.position_changed.emit(0.0)

    def arm(self, duration_s: float | None = None) -> None:
        """Bật nút phát khi CHƯA có audio nhưng có nguồn để nạp lười.

        `duration_s` (đọc từ đầu file, không cần giải mã) cho đồng hồ hiện `0:00 / 0:04` ngay,
        thay vì `0:00 / 0:00` lệch với thời lượng ghi ở đầu trang cho tới lần bấm phát đầu tiên.
        Audio nạp rồi thì đồng hồ theo audio thật.

        Thiếu bước này thì nạp lười tự khóa mình: nút chỉ bật trong `load()`, mà `load()` chỉ
        chạy khi người dùng bấm nút. Ảnh chụp giao diện mới lộ ra (nút xám, đồng hồ 0:00/0:00) —
        test không thấy vì nó gọi thẳng `ensure_loaded`.
        """
        if self.ensure_loaded is not None:
            self.play_button.setEnabled(True)
            self.slider.setEnabled(True)
        if duration_s and self.playback.duration_s <= 0:
            self.time_label.setText(f"{format_time(0.0)} / {format_time(duration_s)}")

    def clear(self) -> None:
        self.playback.stop()
        self._timer.stop()
        self.playback.load([], self.playback.sample_rate)
        self.play_button.setEnabled(False)
        self.slider.setEnabled(False)
        self.slider.setValue(0)
        self._update_labels()

    def toggle(self) -> None:
        if not self.playback.playing and self.ensure_loaded is not None:
            self.ensure_loaded()
        if self.playback.playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        try:
            self.playback.play()
        except PlaybackError as e:
            # Thiếu thiết bị phát là chuyện bình thường trên máy air-gap tối giản: báo một dòng
            # rồi tắt hẳn nút, chứ không để người dùng bấm mãi không thấy gì.
            self.play_button.setEnabled(False)
            self.slider.setEnabled(False)
            self.error.emit(str(e))
            return
        self._timer.start()
        self.retranslate()

    def pause(self) -> None:
        self.playback.pause()
        self._timer.stop()
        self._update_labels()
        self.retranslate()

    def seek(self, seconds: float) -> None:
        if self.ensure_loaded is not None:
            self.ensure_loaded()
        self.playback.seek(seconds)
        self._update_labels()
        self.position_changed.emit(self.playback.position_s)

    # ---- nội bộ ----
    def _on_press(self) -> None:
        self._seeking = True

    def _on_moved(self, value: int) -> None:
        self._update_labels(self._value_to_seconds(value))

    def _on_release(self) -> None:
        self._seeking = False
        self.seek(self._value_to_seconds(self.slider.value()))

    def _value_to_seconds(self, value: int) -> float:
        return self.playback.duration_s * (value / SLIDER_STEPS)

    def _tick(self) -> None:
        pos = self.playback.position_s
        if not self._seeking:
            dur = self.playback.duration_s
            self.slider.setValue(int(SLIDER_STEPS * pos / dur) if dur > 0 else 0)
        self._update_labels(pos)
        self.position_changed.emit(pos)
        if self.playback.finished:
            self._timer.stop()
            self.retranslate()

    def _update_labels(self, pos: float | None = None) -> None:
        p = self.playback.position_s if pos is None else pos
        self.time_label.setText(f"{format_time(p)} / {format_time(self.playback.duration_s)}")

    def retranslate(self) -> None:
        playing = self.playback.playing
        self.play_button.setText("")
        self.play_button.setIcon(self._icons["pause" if playing else "play"])
        self.play_button.setAccessibleName(self.tr("Pause") if playing else self.tr("Play"))
        self.play_button.setToolTip(
            self.tr("Pause playback") if playing else self.tr("Listen to the decoded audio"))
        self.slider.setToolTip(self.tr("Drag to jump to a moment"))
        self._update_labels()
