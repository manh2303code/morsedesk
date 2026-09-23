"""Bộ gom rác vòng (cyclic GC) của Python chỉ được chạy ở luồng giao diện.

Python chạy GC ở BẤT KỲ luồng nào đang cấp phát khi vượt ngưỡng: luồng giải mã, luồng nghe, cả
luồng callback của PortAudio khi đang phát/thu. Nếu một vòng tham chiếu chứa đối tượng Qt của luồng
giao diện bị gom ở luồng khác, đối tượng bị hủy sai luồng: timer của nó (vd. `QBasicTimer` bố cục
văn bản, khoảng 0 ms) KHÔNG được gỡ khỏi bộ điều phối sự kiện — ở luồng không có bộ điều phối
thì còn không có cả cảnh báo — và lần bắn sau rơi vào vùng nhớ đã giải phóng: access violation
trong `QEventDispatcherWin32::event`. Shiboken chỉ tự dời việc hủy về luồng chính cho QWidget.

Cách chữa chuẩn (pyqtgraph `GarbageCollector`, PYSIDE-810): tắt GC tự động, rồi một QTimer ở luồng
giao diện tự gom theo đúng ngưỡng thế hệ mà GC tự động vẫn dùng. Refcount vẫn giải phóng tức thì
như cũ; chỉ phần gom vòng dời về luồng giao diện, trễ tối đa một nhịp timer.
"""

from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer

INTERVAL_MS = 500


class GuiThreadGC(QObject):
    """Tạo ở luồng giao diện; sống cùng `parent` (thường là QApplication)."""

    def __init__(self, parent: QObject | None = None, interval_ms: int = INTERVAL_MS) -> None:
        super().__init__(parent)
        self.threshold = gc.get_threshold()
        self._was_enabled = gc.isenabled()
        gc.disable()
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.check)
        self._timer.start()

    def check(self) -> int:
        """Gom như GC tự động sẽ gom (thế hệ trẻ trước), nhưng ở luồng này. Trả số vật đã gom."""
        c0, c1, c2 = gc.get_count()
        t0, t1, t2 = self.threshold
        if c0 <= t0:
            return 0
        if c1 > t1:
            return gc.collect(2 if c2 > t2 else 1)
        return gc.collect(0)

    def stop(self) -> None:
        self._timer.stop()
        if self._was_enabled:
            gc.enable()


def install(app: QObject) -> GuiThreadGC:
    """Cài một lần cho `app` (create_app có thể được gọi nhiều lần trong test)."""
    guard = getattr(app, "_morsedesk_gc_guard", None)
    if guard is None:
        guard = GuiThreadGC(app)
        app._morsedesk_gc_guard = guard
    return guard
