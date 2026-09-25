"""Khối "Tín hiệu" dùng chung cho trang Giải mã và trang Nghe: 3D hoặc phổ 2D, một khung thời gian.

Người dùng 25/09: trang Nghe phải "thiết kế tương tự như Decode — có option chọn 3D hay spectrogram,
và khi con trỏ chạy thì view cố định chạy theo", lướt được về trước/sau, bấm vào để nghe từ đó.
Nên hai trang dùng ĐÚNG một khối này; chỉ khác nguồn dữ liệu (`FileColumns` / `LiveColumns`) và
con trỏ (vị trí đang phát / bây giờ).

Tiết kiệm tài nguyên: chỉ biểu đồ ĐANG HIỆN được dựng và vẽ, và không vẽ gì khi trang bị che (tab
khác). Mức hiển thị tính cho cả nguồn (file: 16 ô rải đều; trực tiếp: 30 s gần nhất, tối đa mỗi
giây một lần), không tính lại theo từng khung nhìn.
"""

from __future__ import annotations

import time
from bisect import bisect_right

import numpy as np
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.widgets.hover_readout import Line
from morsedesk.app.widgets.ridge3d import Ridge3DView
from morsedesk.app.widgets.signal_columns import COL_S, FREQS, Levels, band_rows, peak_hz
from morsedesk.app.widgets.signal_strip import SignalStrip
from morsedesk.app.widgets.signal_view import Timeline, clock, time_ticks

# Dải động hiển thị. Tối thiểu: chỉ có nhiễu thì không kéo giãn thành núi. Tối đa cho 3D: file SẠCH
# (khoảng lặng số 0, như ba file mẫu) có nền -120 dB — chuẩn hóa từ đó thì đuôi phổ Hann cũng thành
# đồi; 30 dB ~ khoảng cách đỉnh-nền mỗi bin của bản tin SNR 15 dB.
RIDGE_RANGE_DB = (20.0, 30.0)
STRIP_RANGE_DB = (20.0, 50.0)
REL_CAP_DB = 60.0           # "dB trên nền" trong ô số đo: file sạch không nói "+154 dB"
RIDGE_GAMMA = 1.3
LEVELS_EVERY_S = 1.0        # trang Nghe: tính lại mức và tone tự tìm tối đa mỗi giây
LIVE_LEVELS_S = 30.0
DEFAULT_TONE_HZ = 700.0
RECENTER_TONE_HZ = 8.0      # tone bộ giải mã báo: ổn định, dời dải ngay khi lệch quá 8 Hz
RECENTER_PEAK_HZ = 23.0     # đỉnh phổ tự tìm: nhảy theo nhiễu, chỉ dời khi lệch ~3/4 bin
JUMP_S = 0.75               # con trỏ nhảy xa hơn chừng này giữa hai nhịp (kéo thanh trượt): bám lại
# Ngân sách vẽ khi con trỏ tự chạy (đang phát / đang thu): biểu đồ chiếm tối đa 25 % một lõi. Khung
# đắt (3D ~10 ms) thì giãn nhịp cho vừa (~25 hình/s), khung rẻ (2D ~2 ms) chạy đủ nhịp thanh phát.
# Thao tác của người dùng (kéo, bấm, đổi 3D/2D) luôn vẽ ngay.
RENDER_DUTY = 0.25
MAX_DEFER_MS = 120


class SignalPanel(QWidget):
    seek_requested = Signal(float)          # người dùng bấm vào biểu đồ tại giây này

    def __init__(self, live: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.live = live
        self.live_now = False                # trang Nghe đang thu: con trỏ = bây giờ
        self.timeline = Timeline(parent=self)
        self.ridge = Ridge3DView(self)
        self.strip = SignalStrip(self)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.ridge)
        self.stack.addWidget(self.strip)
        self.title = QLabel(self)
        self.title.setProperty("role", "section")
        # Cách dùng ghi thẳng cạnh tiêu đề, KHÔNG làm tooltip: tooltip trên biểu đồ sẽ đè lên ô số
        # đo hiện khi rê chuột.
        self.hint = QLabel(self)
        self.hint.setProperty("role", "caption")
        self.follow_button = QPushButton(self)
        self.follow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.follow_button.setStyleSheet("QPushButton { padding: 3px 12px; font-size: 9pt; }")
        self.follow_button.hide()
        self.view_3d_button = QPushButton(self)
        self.view_2d_button = QPushButton(self)
        self._view_group = QButtonGroup(self)
        for i, b in enumerate((self.view_3d_button, self.view_2d_button)):
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("QPushButton { padding: 3px 12px; font-size: 9pt; }")
            self._view_group.addButton(b, i)
        self.view_3d_button.setChecked(True)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 4)
        head.addWidget(self.title)
        head.addSpacing(10)
        head.addWidget(self.hint)
        head.addStretch(1)
        head.addWidget(self.follow_button)
        head.addSpacing(6)
        head.addWidget(self.view_3d_button)
        head.addWidget(self.view_2d_button)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(head)
        lay.addWidget(self.stack, 1)

        self._source = None
        self._sample: np.ndarray | None = None
        self._band_levels: Levels | None = None
        self._full_levels: Levels | None = None
        self._levels_at = 0.0
        self._decoder_tone: float | None = None
        self._center: float | None = None
        self._words: list = []
        self._starts: list[float] = []
        self._dim_ahead = True
        self._was_playing = False
        self._last_t: float | None = None
        self.unit_s, self.unit_hz = "s", "Hz"
        self.render_count = 0                # cho đo đạc: số lần dựng biểu đồ
        self.build_ms = 0.0                  # thời gian dựng dữ liệu lần gần nhất
        self._throttled = False
        self._last_render_at = 0.0
        self._defer = QTimer(self)
        self._defer.setSingleShot(True)
        self._defer.timeout.connect(self.refresh)

        self.timeline.changed.connect(self._on_timeline_changed)
        self.timeline.follow_changed.connect(lambda _on: self._sync_follow_button())
        self._view_group.idClicked.connect(self._show_view)
        self.follow_button.clicked.connect(lambda: self.timeline.set_follow(True))
        for view in (self.ridge, self.strip):
            view.pan_requested.connect(lambda f: self.timeline.pan(f * self.timeline.span()))
            view.seek_requested.connect(lambda f: self.seek_requested.emit(self.timeline.time_at(f)))
            view.describe = self._describe
        self.retranslate()

    # ---- nguồn và nội dung ----
    def set_source(self, source, fit: bool = True) -> None:
        """Nguồn mới (None = trống). File: khung co bằng file nếu file ngắn hơn 12 s."""
        self._source = source
        self._sample = None
        self._band_levels = self._full_levels = None
        self._levels_at = 0.0
        self._decoder_tone = None
        self._center = None
        self._words, self._starts = [], []
        if source is None:
            self.timeline.reset(0.0, 0.0, fit)
            return
        lo, hi = source.col_range()
        if not self.live:
            self._sample = source.sample()
            self._move_center(peak_hz(self._sample), RECENTER_PEAK_HZ)   # tới khi biết tone giải mã
        self._was_playing, self._last_t = False, None
        self.timeline.reset(lo * COL_S, hi * COL_S, fit)

    def source(self):
        return self._source

    def set_tone(self, hz: float | None) -> None:
        """Tone bộ giải mã bám: tâm dải 3D ±250 Hz và vạch tone của phổ 2D."""
        if not hz:
            return
        old = self._decoder_tone
        self._decoder_tone = float(hz)
        moved = self._move_center(self._decoder_tone, RECENTER_TONE_HZ)
        if moved:
            if self._sample is not None:
                self._band_levels = None                    # file: tính lại mức cho dải mới
            else:
                self._levels_at = 0.0                       # trực tiếp: tính lại ở khối tới
        # Bộ giải mã báo tone mỗi lần giải (~2 lần/s) và gần như không đổi: chỉ vẽ lại khi dải 3D dời
        # hay vạch tone trên phổ 2D dời thấy được.
        if moved or (self.stack.currentWidget() is self.strip and (old is None or abs(old - hz) > 1.0)):
            self.refresh()

    def set_words(self, words) -> None:
        self._words = sorted(words, key=lambda w: w.start_s)
        self._starts = [w.start_s for w in self._words]
        if self.stack.currentWidget() is self.strip:
            self.refresh()

    def set_cursor(self, t: float | None, dim_ahead: bool = True) -> None:
        """Vị trí đang phát (None = không phát): khung bám theo nếu đang ở chế độ bám."""
        self._dim_ahead = dim_ahead
        self.timeline.set_cursor(t)

    def play_position(self, t: float | None, playing: bool) -> None:
        """Con trỏ của thanh phát. Vừa bấm phát, hay con trỏ nhảy (kéo thanh trượt, bấm từ): khung
        bám lại — người dùng lướt đi xem chỗ khác rồi bấm phát thì phải thấy chỗ đang phát."""
        jump = t is not None and self._last_t is not None and abs(t - self._last_t) > JUMP_S
        if t is not None and ((playing and not self._was_playing) or jump):
            self.timeline.set_follow(True)
        self._was_playing, self._last_t = playing, t
        self._throttled = True
        self.set_cursor(t)

    def extend(self) -> None:
        """Trang Nghe: nguồn vừa có thêm cột. Đang thu thì con trỏ = bây giờ (khung bám mép phải)."""
        src = self._source
        if src is None:
            return
        lo, hi = src.col_range()
        now = time.monotonic()
        if now - self._levels_at >= LEVELS_EVERY_S:
            self._levels_at = now
            recent = src.recent(LIVE_LEVELS_S)
            if self._decoder_tone is None:
                self._move_center(peak_hz(recent[:, -int(12.0 / COL_S):]), RECENTER_PEAK_HZ)
            self._full_levels = Levels.of(recent, *STRIP_RANGE_DB)
            self._band_levels = Levels.of(recent[band_rows(self.center())], *RIDGE_RANGE_DB)
        self._throttled = True
        if self.live_now:
            self._dim_ahead = False
            self.timeline.update(lo * COL_S, hi * COL_S, cursor=hi * COL_S)
        else:
            self.timeline.update(lo * COL_S, hi * COL_S)

    def center(self) -> float:
        return self._center if self._center is not None else DEFAULT_TONE_HZ

    def _move_center(self, target: float | None, limit: float) -> bool:
        if target is None:
            return False
        if self._center is None or abs(target - self._center) > limit:
            self._center = float(target)
            return True
        return False

    def _levels(self, rows: np.ndarray | None) -> Levels | None:
        if self._sample is not None:                        # file: mức của cả file, tính một lần
            if rows is not None and self._band_levels is None:
                self._band_levels = Levels.of(self._sample[rows], *RIDGE_RANGE_DB)
            if rows is None and self._full_levels is None:
                self._full_levels = Levels.of(self._sample, *STRIP_RANGE_DB)
        return self._band_levels if rows is not None else self._full_levels

    # ---- dựng biểu đồ đang hiện ----
    def _show_view(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()                       # lúc bị che không vẽ gì: bù ngay khi hiện lại

    def _on_timeline_changed(self) -> None:
        """Con trỏ tự chạy: giữ ngân sách vẽ (gộp các nhịp dồn dập, vẽ theo trạng thái mới nhất)."""
        if self._throttled:
            self._throttled = False
            view = self.stack.currentWidget()
            cost_s = (getattr(view, "last_paint_ms", 0.0) + self.build_ms) / 1000.0
            wait = self._last_render_at + cost_s / RENDER_DUTY - time.perf_counter()
            if wait > 0.001:
                if not self._defer.isActive():
                    self._defer.start(min(MAX_DEFER_MS, int(wait * 1000) + 1))
                return
        self.refresh()

    def flush(self) -> None:
        """Vẽ ngay khung đang hoãn (nếu có) — cho test và ảnh chụp."""
        if self._defer.isActive():
            self.refresh()

    def refresh(self) -> None:
        self._defer.stop()
        self._sync_follow_button()
        src = self._source
        view = self.stack.currentWidget()
        if src is None:
            self.ridge.clear()
            self.strip.clear()
            return
        if not self.isVisible():
            return
        self.render_count += 1
        started = time.perf_counter()
        self._last_render_at = started
        t0, t1 = self.timeline.window()
        span = t1 - t0
        c0, c1 = int(np.floor(t0 / COL_S)), int(np.ceil(t1 / COL_S))
        db = src.columns(c0, max(c1, c0 + 1))
        times = (np.arange(c0, c0 + db.shape[1]) + 0.5) * COL_S
        xs = (times - t0) / span
        cursor = self.timeline.cursor()
        ph = None if cursor is None else (cursor - t0) / span
        ticks = time_ticks(t0, span, self.unit_s)
        missing = ~np.isfinite(db)
        if view is self.ridge:
            rows = band_rows(self.center())
            lv = self._levels(rows)
            band = db[rows]
            if lv is None:
                z = np.zeros(band.shape, np.float32)
                rel = np.full(band.shape, np.nan, np.float32)
            else:
                z = lv.scale(band, RIDGE_GAMMA)
                rel = lv.above_floor(band, REL_CAP_DB)
                rel[missing[rows]] = np.nan
            self.ridge.front_ticks = ticks
            self.ridge.depth_label = self.tr("{tone} Hz ± 250 Hz").format(tone=f"{self.center():.0f}")
            self.ridge.set_playhead(ph)
            self.ridge.set_surface(z, np.clip(xs, 0.0, 1.0), times, FREQS[rows], rel)
        else:
            lv = self._levels(None)
            if lv is None:
                z = np.zeros(db.shape, np.float32)
                rel = np.full(db.shape, np.nan, np.float32)
            else:
                z = lv.scale(db)
                rel = lv.above_floor(db, REL_CAP_DB)
                rel[missing] = np.nan
            s = self.strip
            s.ticks = ticks
            s.hz_unit = self.unit_hz
            s.tone_hz = self._decoder_tone or (self.center() if self.live else None)
            i0 = bisect_right(self._starts, t0)
            i1 = bisect_right(self._starts, t1)
            s.words = [((w.start_s - t0) / span, w.text) for w in self._words[i0:i1]]
            s.dim_ahead = self._dim_ahead
            s.set_cursor(ph)
            s.set_image(z, xs, times, FREQS, rel)
        self.build_ms = (time.perf_counter() - started) * 1000.0

    # ---- ô số đo ----
    def _describe(self, t: float, hz: float, rel: float) -> list[Line]:
        lines: list[Line] = []
        i = bisect_right(self._starts, t) - 1
        if 0 <= i < len(self._words) and self._words[i].start_s <= t <= self._words[i].end_s:
            lines.append((self._words[i].text, "word"))
        lines.append((f"{hz:.0f} {self.unit_hz}", "value"))
        lines.append((self.tr("{db:+.0f} dB above noise").format(db=rel), "value"))
        if self.live and self.live_now:
            ago = max(0.0, self.timeline.data_range()[1] - t)
            lines.append((self.tr("{t:.1f} s ago").format(t=ago), "muted"))
        else:
            lines.append((clock(t, self.unit_s), "muted"))
        return lines

    def _sync_follow_button(self) -> None:
        show = (self._source is not None and not self.timeline.following()
                and (self.timeline.cursor() is not None or self.live_now))
        self.follow_button.setVisible(show)
        self.follow_button.setText(self.tr("Back to live") if self.live and self.live_now
                                   else self.tr("Follow playback"))

    def retranslate(self) -> None:
        self.unit_s, self.unit_hz = self.tr("s"), self.tr("Hz")
        self.view_3d_button.setText(self.tr("3D"))
        self.view_2d_button.setText(self.tr("Spectrogram"))
        self.view_3d_button.setToolTip(self.tr("Show the signal as a 3D landscape"))
        self.view_2d_button.setToolTip(self.tr("Show the signal as a spectrogram"))
        self.follow_button.setToolTip(self.tr("The view follows the sound again"))
        self.hint.setText(self.tr("Drag or scroll to look back; click to replay after you stop")
                          if self.live else self.tr("Drag or scroll to move, click to listen from there"))
        self._sync_follow_button()
        if self._source is not None:
            self.refresh()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
