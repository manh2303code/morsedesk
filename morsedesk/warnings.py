"""Mã cảnh báo của lõi giải mã, để giao diện dịch được (CP-10).

Lõi viết thông điệp bằng tiếng Việt cho CLI và log, nhưng giao diện có ba ngôn ngữ en/ru/kk.
Ghép thẳng thông điệp của lõi vào banner thì người dùng Nga nhận được câu tiếng Việt, nên mỗi
cảnh báo mang thêm một mã ổn định và tham số của nó. Giao diện tra mã trong `WARNING_TEXTS` để
lấy chuỗi nguồn tiếng Anh rồi để Qt dịch; `tools/build_i18n.py --check` canh bảng dịch.

Mã là chuỗi chứ không phải chỉ số, nên thêm bớt cảnh báo không làm hỏng file JSON đã xuất.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class WarningCode(StrEnum):
    NO_SIGNAL = "no_signal"
    GUESSED_TONE = "guessed_tone"
    SECOND_TONE = "second_tone"
    LOW_CONFIDENCE = "low_confidence"
    LOW_CONFIDENCE_WITH_DSP = "low_confidence_with_dsp"
    KEY_CLICKS = "key_clicks"


# Chuỗi nguồn tiếng Anh cho giao diện. Phải khớp từng ký tự với khóa trong
# `morsedesk/app/i18n/translations.json`, vì Qt tra bản dịch theo chính chuỗi nguồn.
WARNING_TEXTS: dict[str, str] = {
    WarningCode.NO_SIGNAL.value: "No Morse signal found in this audio.",
    WarningCode.GUESSED_TONE.value:
        "Tone not detected clearly; guessing from the spectral peak, so the result may be wrong.",
    WarningCode.SECOND_TONE.value:
        "A second tone was found at {second_hz:.0f} Hz; tracking {tracked_hz:.0f} Hz.",
    WarningCode.LOW_CONFIDENCE.value: "Low confidence.",
    WarningCode.LOW_CONFIDENCE_WITH_DSP.value: "Low confidence; the DSP decoder result is shown too.",
    WarningCode.KEY_CLICKS.value:
        "Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: MorseDesk decodes "
        "Morse sent as a tone (radio CW); key clicks cannot be decoded yet.",
}

# Thông điệp tiếng Việt cho CLI và log, giữ đúng câu chữ đã dùng từ trước.
WARNING_TEXTS_VI: dict[str, str] = {
    WarningCode.NO_SIGNAL.value: "không có tín hiệu Morse trong đoạn âm thanh",
    WarningCode.GUESSED_TONE.value:
        "không dò được tone rõ, đang đoán theo đỉnh phổ; kết quả có thể sai",
    WarningCode.SECOND_TONE.value:
        "phát hiện tone thứ hai tại {second_hz:.0f} Hz, đang bám {tracked_hz:.0f} Hz",
    WarningCode.LOW_CONFIDENCE.value: "độ tin cậy thấp",
    WarningCode.LOW_CONFIDENCE_WITH_DSP.value: "độ tin cậy thấp, kèm kết quả bộ giải mã DSP",
    WarningCode.KEY_CLICKS.value:
        "chỉ nghe thấy tiếng click, không có tone Morse; nếu là phím điện báo thì loại này chưa giải được",
}


@dataclass(frozen=True)
class DecodeWarning:
    code: str
    params: dict[str, float] = field(default_factory=dict)

    def vi(self) -> str:
        """Thông điệp tiếng Việt cho CLI và log."""
        return WARNING_TEXTS_VI[self.code].format(**self.params)

    def source(self) -> str:
        """Chuỗi nguồn tiếng Anh, đã thay tham số — giao diện đưa qua `tr()` trước khi thay."""
        return WARNING_TEXTS[self.code].format(**self.params)


def warn(code: WarningCode, **params: float) -> DecodeWarning:
    return DecodeWarning(code.value, dict(params))
