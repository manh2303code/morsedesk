"""Thác nước tần số chạy thời gian thực: nhìn thấy tín hiệu trước khi đọc được chữ.

Khác với biểu đồ phổ ở trang Giải mã — thứ vẽ một lần cho cả file đã có sẵn — widget này nhận
từng khối audio đang vào và đẩy cột mới sang bên phải, phần cũ cuộn dần sang trái. Người vận
hành nhìn vào đây để biết ngay ba điều mà dòng chữ không nói được:

- có tín hiệu trong không khí hay chỉ là nhiễu (vệt ngang rõ hay mặt nhiễu phẳng)
- tone đang ở đâu, có trôi không (vệt lên xuống)
- nhịp gõ (vạch dài vạch ngắn nhìn thấy được, như phím đàn chạy)

Cuộn bằng cách dịch mảng numpy rồi đổ sang QImage một lần, chứ không vẽ từng ô bằng QPainter:
ở 10 cột mỗi giây và vài trăm cột trên màn hình, vẽ từng ô sẽ ăn hết một lõi.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from morsedesk.app.theme import spectrum_rgb
from morsedesk.constants import SAMPLE_RATE

MAX_HZ = 2000.0         # trên dải này Morse nghiệp vụ không dùng tới
N_BINS = 128            # số hàng của thác nước
N_COLS = 600            # bề rộng lịch sử; ở 10 cột/giây là khoảng một phút
# Dải hiển thị tính TƯƠNG ĐỐI so với nền nhiễu của chính cột, không phải hằng số tuyệt đối.
# Mức dB tuyệt đối của một khối phụ thuộc hoàn toàn vào độ lợi của card âm thanh và vị trí núm
# vặn: đo được -102..+40 dB trên cùng một clip, nên bất kỳ cặp trần/sàn cố định nào cũng sẽ sai
# ở máy khác. Lấy phân vị 25 làm nền rồi trải DB_RANGE dB phía trên thì thác nước tự thích nghi.
DB_RANGE = 45.0
NOISE_PCT = 25
FFT_SIZE = 512


class WaterfallView(QWidget):
    """Thác nước tần số cuộn liên tục; `push(block)` mỗi khi có audio mới."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, parent=None) -> None:
        super().__init__(parent)
        self.sample_rate = int(sample_rate)
        self.setMinimumHeight(160)
        self._data = np.zeros((N_BINS, N_COLS), dtype=np.float32)   # dB đã chuẩn hóa 0..1
        self._pending = np.zeros(0, dtype=np.float32)
        self._tone_hz: float | None = None
        self._window = np.hanning(FFT_SIZE).astype(np.float32)
        # Chỉ giữ các bin dưới MAX_HZ rồi gộp về N_BINS hàng: phổ đầy đủ mịn hơn mức mắt phân
        # biệt được trên 160 px, mà lại tốn bộ nhớ và thời gian đổ ảnh.
        freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / self.sample_rate)
        keep = freqs <= MAX_HZ
        self._keep = keep
        self._bin_of = np.clip(
            (freqs[keep] / MAX_HZ * (N_BINS - 1)).astype(int), 0, N_BINS - 1)

    def set_tone(self, hz: float | None) -> None:
        """Vạch ngang đánh dấu tone bộ giải mã đang bám."""
        self._tone_hz = hz
        self.update()

    def clear(self) -> None:
        self._data[:] = 0.0
        self._pending = np.zeros(0, dtype=np.float32)
        self._tone_hz = None
        self.update()

    def push(self, block) -> np.ndarray:
        """Thêm một khối audio; mỗi FFT_SIZE mẫu thành một cột mới.

        Trả các cột mới (0..1, [N_BINS, n], hàng 0 = 0 Hz) để cảnh 3D trực tiếp dùng lại, khỏi
        tính FFT lần thứ hai.
        """
        b = np.asarray(block, dtype=np.float32).reshape(-1)
        if not len(b):
            return np.zeros((N_BINS, 0), np.float32)
        self._pending = np.concatenate([self._pending, b]) if len(self._pending) else b
        cols = []
        while len(self._pending) >= FFT_SIZE:
            frame = self._pending[:FFT_SIZE] * self._window
            self._pending = self._pending[FFT_SIZE:]
            power = np.abs(np.fft.rfft(frame)) ** 2
            db = 10.0 * np.log10(power[self._keep] + 1e-12)
            # Khởi tạo bằng SÀN dB, không phải 0: giá trị dB ở đây đều âm (-70..-5), nên
            # `maximum` với 0 sẽ giữ nguyên 0 ở mọi bin và cả thác nước thành một mảng vàng đặc.
            floor = float(np.percentile(db, NOISE_PCT))
            col = np.full(N_BINS, floor, dtype=np.float32)
            np.maximum.at(col, self._bin_of, db)        # gộp bin: lấy đỉnh, không lấy trung bình
            cols.append(np.clip((col - floor) / DB_RANGE, 0.0, 1.0))
        if not cols:
            return np.zeros((N_BINS, 0), np.float32)
        new = np.stack(cols, axis=1)
        n = min(new.shape[1], N_COLS)
        self._data = np.roll(self._data, -n, axis=1)
        self._data[:, -n:] = new[:, -n:]
        self.update()
        return new

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        try:
            w, h = max(1, self.width()), max(1, self.height())
            rgb = spectrum_rgb(self._data[::-1])        # hàng 0 = tần số cao ở trên; bảng màu chung
            img = QImage(rgb.tobytes(), N_COLS, N_BINS, N_COLS * 3, QImage.Format.Format_RGB888)
            p.drawImage(self.rect(), img)
            if self._tone_hz:
                y = h - int(h * min(self._tone_hz, MAX_HZ) / MAX_HZ)
                pen = QPen(QColor(245, 165, 36, 200))      # màu đèn tín hiệu, như cảnh 3D
                pen.setWidth(1)
                p.setPen(pen)
                p.drawLine(0, y, w, y)
                p.drawText(6, max(12, y - 4), f"{self._tone_hz:.0f} Hz")
            # Thang tần số bên trái: không có nó thì thác nước chỉ là hình trang trí.
            p.setPen(QPen(QColor(230, 230, 230, 150)))
            for hz in (500, 1000, 1500):
                y = h - int(h * hz / MAX_HZ)
                p.drawLine(0, y, 6, y)
                p.drawText(9, y + 4, f"{hz}")
        finally:
            p.end()

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(200, 160)


def tone_from_block(block, sample_rate: int = SAMPLE_RATE) -> float | None:
    """Tần số đỉnh của một khối, dùng khi bộ giải mã chưa kịp báo tone nào."""
    b = np.asarray(block, dtype=np.float32).reshape(-1)
    if len(b) < FFT_SIZE:
        return None
    frame = b[:FFT_SIZE] * np.hanning(FFT_SIZE).astype(np.float32)
    power = np.abs(np.fft.rfft(frame)) ** 2
    freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / sample_rate)
    keep = (freqs > 100.0) & (freqs <= MAX_HZ)
    if not keep.any():
        return None
    idx = int(np.argmax(power[keep]))
    return float(freqs[keep][idx])
