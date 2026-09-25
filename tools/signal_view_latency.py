"""Đo độ trễ và tải CPU của khối Tín hiệu (cảnh 3D / phổ 2D) khi nghe lại và khi nghe trực tiếp.

Người dùng 25/09: "khi test phải kiểm tra độ trễ để điều chỉnh hợp lý". Chạy đúng đường của ứng dụng
(SignalPanel + FileColumns/LiveColumns, vòng sự kiện Qt thật, đồng hồ thật), không gọi âm thanh:

- nghe lại: một QTimer theo nhịp thanh phát đẩy con trỏ `t = đồng hồ` vào `play_position`;
- nghe trực tiếp: một QTimer 100 ms đẩy khối âm thanh như LiveWorker (khối của AudioCapture).

Đo mỗi cấu hình: số hình/giây thực vẽ, thời gian vẽ một hình, % một lõi CPU của cả tiến trình, và
độ trễ hình = lúc hình vẽ XONG trừ thời điểm của dữ liệu mà hình đó hiện (nghe lại: vị trí con trỏ;
trực tiếp: lúc khối mới nhất tới). Mặc định dùng nền "offscreen" (không bật cửa sổ); vẽ vẫn là
QPainter phần mềm như trên màn hình thật, thiếu mỗi bước chép lên màn hình (~1 ms).

    uv run python tools/signal_view_latency.py [--seconds 8] [--tick-ms 50] [--onscreen]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=8.0, help="thời lượng mỗi cấu hình")
    ap.add_argument("--tick-ms", type=int, nargs="*", default=[33, 50], help="nhịp thanh phát cần thử")
    ap.add_argument("--onscreen", action="store_true", help="vẽ lên màn hình thật thay vì offscreen")
    args = ap.parse_args()
    if not args.onscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from morsedesk.api import Encoder, Word
    from morsedesk.app.fonts import apply_application_font
    from morsedesk.app.theme import stylesheet
    from morsedesk.app.widgets.signal_columns import FileColumns, LiveColumns
    from morsedesk.app.widgets.signal_panel import SignalPanel

    apply_application_font()
    app.setStyleSheet(stylesheet())
    text = "CQ CQ DE R1ABC R1ABC K QTH MOSCOW RST 599 NAME IVAN HW CPY BK TNX FER CALL 73 SK"
    x = Encoder("en").to_audio(text, wpm=20, tone_hz=700, snr_db=12, seed=3)
    x = np.tile(x, 4)                                 # ~3 phút: đủ dài để khung trôi suốt lượt đo
    words = [Word(w, 0.3 + i * 2.5, 0.3 + i * 2.5 + 2.0, 0.9) for i, w in enumerate(text.split() * 4)]

    def run(panel, view: str, seconds: float, driver) -> dict:
        (panel.view_3d_button if view == "3d" else panel.view_2d_button).click()
        target = panel.ridge if view == "3d" else panel.strip
        lags: list[float] = []
        paints: list[float] = []
        orig = target.paintEvent

        def hooked(ev):
            orig(ev)
            shown = getattr(panel, "_shown_at", None)
            if shown is not None:
                lags.append((time.perf_counter() - shown) * 1000.0)
                panel._shown_at = None
            paints.append(target.last_paint_ms)
        target.paintEvent = hooked
        # "dữ liệu mà hình hiện" = thời điểm dữ liệu ấy CÓ (con trỏ / khối), gắn vào lúc dựng hình
        orig_refresh = panel.refresh

        def refresh_hook():
            orig_refresh()
            panel._shown_at = panel._data_at
        panel.refresh = refresh_hook
        panel.timeline.changed.disconnect()
        panel.timeline.changed.connect(panel._on_timeline_changed)
        panel._defer.timeout.disconnect()
        panel._defer.timeout.connect(panel.refresh)
        n0 = panel.render_count
        cpu0, wall0 = time.process_time(), time.perf_counter()
        driver(seconds)
        cpu = (time.process_time() - cpu0) / (time.perf_counter() - wall0) * 100.0
        frames = panel.render_count - n0
        target.paintEvent = orig
        panel.refresh = orig_refresh
        return {"fps": frames / seconds, "paint": float(np.median(paints)) if paints else 0.0,
                "build": panel.build_ms, "cpu": cpu,
                "lag": float(np.median(lags)) if lags else float("nan"),
                "lag95": float(np.percentile(lags, 95)) if lags else float("nan")}

    def spin(seconds: float) -> None:
        """Chạy vòng sự kiện Qt thật (như app.exec) trong `seconds` giây."""
        from PySide6.QtCore import QEventLoop

        loop = QEventLoop()
        QTimer.singleShot(int(seconds * 1000), loop.quit)
        loop.exec()

    rows = []
    for size in ((1180, 330), (1880, 470)):         # khối Tín hiệu ở cửa sổ mặc định / toàn màn hình 1080p
        # ---- nghe lại ----
        for tick in args.tick_ms:
            for view in ("3d", "2d"):
                panel = SignalPanel(live=False)
                panel.resize(*size)
                panel.show()
                panel.set_source(FileColumns(x), fit=True)
                panel.set_tone(700.0)
                panel.set_words(words)
                start = [0.0]
                timer = QTimer()
                timer.setTimerType(Qt.TimerType.PreciseTimer)      # như thanh phát
                timer.setInterval(tick)

                def tick_fn(panel=panel, start=start):
                    t = 20.0 + time.perf_counter() - start[0]
                    panel._data_at = time.perf_counter()
                    panel.play_position(t, True)
                timer.timeout.connect(tick_fn)

                def drive(seconds, timer=timer, start=start):
                    start[0] = time.perf_counter()
                    timer.start()
                    spin(seconds)
                    timer.stop()
                panel._data_at = time.perf_counter()
                r = run(panel, view, args.seconds, drive)
                rows.append((f"nghe lại {view} {size[0]}x{size[1]} nhịp {tick} ms", r))
                panel.close()
        # ---- nghe trực tiếp ----
        for view in ("3d", "2d"):
            panel = SignalPanel(live=True)
            panel.resize(*size)
            panel.show()
            cols = LiveColumns(600.0)
            panel.set_source(cols, fit=False)
            panel.live_now = True
            pos = [0]
            for _ in range(150):                        # 15 s có sẵn: khung đã trôi
                cols.push(x[pos[0]:pos[0] + 800])
                pos[0] += 800
            panel.extend()
            timer = QTimer()
            timer.setTimerType(Qt.TimerType.PreciseTimer)
            timer.setInterval(100)

            def block_fn(panel=panel, cols=cols, pos=pos):
                panel._data_at = time.perf_counter()
                if cols.push(x[pos[0]:pos[0] + 800]):
                    panel.extend()
                pos[0] += 800
            timer.timeout.connect(block_fn)

            def drive(seconds, timer=timer):
                timer.start()
                spin(seconds)
                timer.stop()
            panel._data_at = time.perf_counter()
            r = run(panel, view, args.seconds, drive)
            rows.append((f"trực tiếp {view} {size[0]}x{size[1]} khối 100 ms", r))
            panel.close()

    print(f"{'cấu hình':42s} {'hình/s':>7s} {'vẽ ms':>6s} {'dựng ms':>7s} {'CPU %':>6s} {'trễ ms':>7s} {'p95':>6s}")
    for name, r in rows:
        print(f"{name:42s} {r['fps']:7.1f} {r['paint']:6.1f} {r['build']:7.1f} {r['cpu']:6.1f} "
              f"{r['lag']:7.1f} {r['lag95']:6.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
