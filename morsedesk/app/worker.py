"""Worker giải mã trong QThread (một Decoder-cache cho cả ứng dụng), spectrogram và phát thử."""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, Signal

from morsedesk.api import DEFAULT_MODEL_PATH, Decoder, DecodeResult
from morsedesk.audio.io import UnsupportedAudio, audio_info, load_audio
from morsedesk.constants import HOP, SAMPLE_RATE
from morsedesk.dsp.stft import stft_power
from morsedesk.lm.store import LMStore

log = logging.getLogger(__name__)

MAX_SECONDS = 20 * 60
MAX_COLUMNS = 4000
MAX_FREQ_HZ = 2000.0
DB_FLOOR = -60.0


@dataclass
class Spectrogram:
    power_db: np.ndarray   # [n_bins, n_cols] float32, dB tương đối trong [DB_FLOOR, 0]
    freqs_hz: np.ndarray   # [n_bins]
    times_s: np.ndarray    # [n_cols] giữa mỗi cột

    @classmethod
    def from_audio(
        cls, x: np.ndarray, sample_rate: int = SAMPLE_RATE, max_columns: int = MAX_COLUMNS
    ) -> Spectrogram:
        x = np.asarray(x, dtype=np.float32)
        n_frames = len(x) // HOP
        if n_frames == 0:
            return cls(np.zeros((0, 0), np.float32), np.zeros(0), np.zeros(0))
        power, freqs = stft_power(x, sample_rate=sample_rate)
        keep = freqs <= MAX_FREQ_HZ
        p = power[keep, :]
        db = 10.0 * np.log10(p + 1e-12)
        db = db - float(db.max())
        db = np.clip(db, DB_FLOOR, 0.0).astype(np.float32)
        times = (np.arange(db.shape[1]) * HOP + HOP / 2.0) / sample_rate
        if db.shape[1] > max_columns:
            factor = int(np.ceil(db.shape[1] / max_columns))
            n_pool = db.shape[1] // factor
            pooled = db[:, : n_pool * factor].reshape(db.shape[0], n_pool, factor).max(axis=2)
            times = times[: n_pool * factor].reshape(n_pool, factor).mean(axis=1)
            db = pooled
        return cls(db, freqs[keep].astype(np.float64), times.astype(np.float64))


@dataclass(frozen=True)
class DecodeRequest:
    path: Path
    profile_id: str
    use_lm: bool


class DecoderWorker(QThread):
    """Sở hữu mọi Decoder; UI chỉ gửi DecodeRequest và nhận signal.

    Hàng đợi độ dài 1: `request()` mới thay yêu cầu đang chờ (không giải mã song song).
    ONNX session và LM được tạo một lần trong `run()` rồi dùng chung cho mọi Decoder
    (cache theo `(profile_id, use_lm)`).
    """

    result_ready = Signal(object, object, str)   # DecodeResult, Spectrogram, path
    failed = Signal(str)
    busy = Signal(bool)

    def __init__(
        self, engine: str, model_path: Path | None, lm_dir: Path | None, parent=None
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.model_path = Path(model_path) if model_path else None
        self.lm_dir = Path(lm_dir) if lm_dir else None
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._decoders: dict[tuple[str, bool], Decoder] = {}
        self._acoustic = None
        self._store: LMStore | None = None

    # ---- gọi từ UI thread ----
    def request(self, req: DecodeRequest) -> None:
        while True:                                   # yêu cầu mới thay yêu cầu đang chờ
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put(req)

    def stop(self) -> None:
        self.request(None)  # type: ignore[arg-type]
        self.wait(10000)

    # ---- chạy trong thread ----
    def _decoder(self, req: DecodeRequest) -> Decoder:
        key = (req.profile_id, req.use_lm)
        if key not in self._decoders:
            if self._store is None:
                self._store = LMStore(self.lm_dir)
            if self.engine == "onnx" and self._acoustic is None:
                from morsedesk.model.onnx_runner import OnnxAcousticModel

                self._acoustic = OnnxAcousticModel(self.model_path or DEFAULT_MODEL_PATH)
            self._decoders[key] = Decoder(
                req.profile_id, engine=self.engine, model_path=self.model_path,
                lm=req.use_lm, lm_store=self._store, acoustic_model=self._acoustic,
            )
        return self._decoders[key]

    def _handle(self, req: DecodeRequest) -> None:
        path = Path(req.path)
        if not path.exists():
            raise FileNotFoundError(f"file not found: {path}")
        try:
            _, _, seconds = audio_info(path)
        except Exception as e:  # soundfile không đọc được (định dạng lạ, file hỏng)
            raise UnsupportedAudio(f"cannot read {path.name}: {e}") from e
        if seconds > MAX_SECONDS:
            raise ValueError(f"file is {seconds / 60:.1f} min long; this version supports up to 20 min")
        decoder = self._decoder(req)
        x, sr = load_audio(path)
        result: DecodeResult = decoder.decode_array(x, sr)
        spec = Spectrogram.from_audio(x, SAMPLE_RATE)
        self.result_ready.emit(result, spec, str(path))

    def run(self) -> None:
        while True:
            req = self._queue.get()
            if req is None:
                return
            self.busy.emit(True)
            try:
                self._handle(req)
            except (UnsupportedAudio, FileNotFoundError, ValueError) as e:
                self.failed.emit(str(e))
            except Exception as e:  # không để worker chết vì một file lạ
                log.exception("decode failed")
                self.failed.emit(f"internal error: {type(e).__name__}: {e}")
            finally:
                self.busy.emit(False)


class Player:
    """Phát thử qua sounddevice (không chặn); không có thiết bị thì trả thông điệp lỗi."""

    def play(self, x: np.ndarray, sample_rate: int) -> str | None:
        try:
            import sounddevice as sd

            sd.stop()   # phát lại từ đầu nếu bấm Nghe thử lần nữa khi đang phát
            sd.play(np.asarray(x, dtype=np.float32), sample_rate)
            return None
        except Exception as e:  # PortAudioError, OSError khi thiếu thiết bị/thư viện
            return f"cannot play audio: {e}"

    def stop(self) -> None:
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            pass
