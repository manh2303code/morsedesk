"""Đo độ lệch giữa vị trí giao diện dùng (karaoke, vệt quét 3D, con trỏ phổ) và chỗ ĐANG NGHE THẬT.

Chạy trên thiết bị phát thật, âm lượng 0 (không phát ra loa). Mỗi callback của PortAudio cho biết
thời điểm mẫu đầu khối sẽ tới loa (`outputBufferDacTime`); từ đó dựng lại "giây nào của file gốc
đang ra loa" ở bất kỳ thời điểm nào, rồi so với `position_s` mà giao diện đọc 20 lần/giây.

    uv run python tools/playback_sync.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from morsedesk.audio.playback import AudioPlayback  # noqa: E402


class _Probe(AudioPlayback):
    """Ghi lại, cho mỗi khối: lúc mẫu đầu tới loa, vị trí nguồn đầu/cuối khối."""

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self.blocks: list[tuple[float, float, float, int]] = []

    def _callback(self, outdata, frames, time_info, status) -> None:
        src0 = self._pos
        try:
            super()._callback(outdata, frames, time_info, status)
        finally:
            dac = float(getattr(time_info, "outputBufferDacTime", 0.0) or 0.0)
            self.blocks.append((dac, src0 / self.sample_rate, self._pos / self.sample_rate, frames))

    def heard(self, stream_time: float) -> float | None:
        """Giây của file gốc đang ra loa lúc `stream_time` (nội suy trong khối chứa thời điểm đó)."""
        for dac, s0, s1, frames in reversed(self.blocks):
            dur = frames / self.sample_rate
            if dac <= stream_time <= dac + dur:
                return s0 + (s1 - s0) * (stream_time - dac) / dur
        return None


def measure(rate: float, seconds: float = 6.0, sr: int = 8000) -> tuple[float, float, float]:
    x = (0.3 * np.sin(2 * np.pi * 700 * np.arange(int(sr * 60)) / sr)).astype(np.float32)
    pb = _Probe(sr)
    pb.load(x, sr)
    pb.set_volume(0.0)
    pb.set_speed(rate)
    pb.play()
    errs, seen = [], []
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        time.sleep(0.05)                                   # nhịp của thanh phát (TICK_MS)
        stream = pb._stream
        if stream is None:
            break
        now = stream.time
        truth = pb.heard(now)
        pos = pb.position_s
        if truth is not None:
            errs.append(pos - truth)
            seen.append((now, pos))
    pb.stop()
    e = np.array(errs[5:])                                 # bỏ vài nhịp đầu lúc stream khởi động
    # Độ mượt: vị trí tiến giữa hai lần đọc so với thời gian thực x tốc độ (1 = đều tuyệt đối).
    t, x_ = np.array(seen[5:]).T
    ratio = np.diff(x_) / (np.diff(t) * rate)
    return (float(np.mean(e)), float(np.percentile(np.abs(e), 95)), float(np.max(np.abs(e))),
            float(np.percentile(np.abs(ratio - 1.0), 95)))


def main() -> int:
    for rate in (0.5, 0.75, 1.0, 1.5, 2.0):
        mean, p95, worst, jerk = measure(rate)
        print(f"{rate:>4}×: lệch trung bình {1000 * mean:+6.0f} ms, |lệch| p95 {1000 * p95:5.0f} ms, "
              f"tệ nhất {1000 * worst:5.0f} ms (giây của file gốc; dương = hình đi TRƯỚC tiếng); "
              f"độ giật p95 {100 * jerk:.0f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
