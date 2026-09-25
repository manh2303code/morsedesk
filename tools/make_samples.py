"""Sinh ba file mẫu "Xin chào" mà trang Giải mã nạp sẵn theo ngôn ngữ giao diện.

Người dùng mở ứng dụng lần đầu thấy ngay một bản tin thật được giải mã — phổ 3D, số đo, chữ —
thay vì một màn hình trống. Mỗi file là lời chào bằng chính ngôn ngữ giao diện đang chọn.

KHÔNG nhiễu (người dùng 25/09: "chuẩn nhất có thể, chỉ có thuần Morse"): sine liên tục pha, sườn
raised-cosine 5 ms, nhịp PARIS đúng danh nghĩa; khoảng lặng là số 0 tuyệt đối (PCM 16 bit). Trước đó
có nhiễu SNR 15 dB "để cảnh 3D có chất liệu thật". Đã kiểm ở chế độ tự nhận ngôn ngữ: cả ba ra đúng
nguyên văn và đúng ngôn ngữ (tests/app/test_about.py canh việc này, cùng việc file sạch thật).

    uv run python tools/make_samples.py
"""

from __future__ import annotations

from pathlib import Path

from morsedesk.api import Encoder
from morsedesk.audio.io import save_audio

OUT = Path(__file__).resolve().parents[1] / "morsedesk" / "app" / "samples"
SAMPLES = {
    "en": ("en", "HELLO"),
    "ru": ("ru", "ЗДРАВСТВУЙТЕ"),
    "kk": ("kk-cyrl-ru", "СӘЛЕМЕТСІЗ БЕ"),
}
WPM, TONE_HZ = 18, 700


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for ui_lang, (profile, text) in SAMPLES.items():
        x = Encoder(profile).to_audio(text, wpm=WPM, tone_hz=TONE_HZ, snr_db=None)
        path = OUT / f"hello_{ui_lang}.wav"
        save_audio(path, x, 8000)
        print(f"{path.name}: {text} ({len(x) / 8000:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
