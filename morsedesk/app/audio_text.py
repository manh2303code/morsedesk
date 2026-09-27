"""Thông điệp (dịch được) về thiết bị âm thanh, dùng chung cho mọi trang và cửa sổ chính.

Lõi (audio/engine.py) báo lỗi bằng tiếng Anh kỹ thuật; người vận hành cần biết CHUYỆN GÌ xảy ra và
PHẢI LÀM GÌ, bằng ngôn ngữ giao diện của họ.
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from morsedesk.audio.engine import STUCK_TEXT


class AudioText(QObject):
    def stuck(self) -> str:
        return self.tr("The sound device is not responding (the system audio service or the sound driver is stuck). Playback and listening are paused; everything else keeps working. If sound does not come back within a minute or two, restart the computer.")

    def busy(self) -> str:
        return self.tr("Listening is on. Stop listening before playing: the microphone would pick up the speaker.")

    def playback(self, err) -> str:
        """`err`: PlaybackError (có `kind`) hoặc chuỗi."""
        kind = getattr(err, "kind", "device")
        detail = str(err)
        if kind == "busy":
            return self.busy()
        if kind == "stuck" or STUCK_TEXT in detail:
            return self.stuck()
        if kind == "unavailable":
            return self.tr("No sound output on this computer: check that a sound card is present and that PortAudio (libportaudio2) is installed. Decoding files still works.")
        return self.tr("Cannot play the audio: {detail}").format(detail=detail)

    def capture(self, detail: str) -> str:
        """Thông điệp lỗi của luồng nghe (chuỗi từ LiveWorker.failed)."""
        if STUCK_TEXT in detail:
            return self.stuck()
        return self.tr("Listening failed: {detail}").format(detail=detail)
