"""Nhãn dòng dự phòng phải nói đúng nguồn của nó.

Từ khi `Decoder` biết chọn bộ giải mã theo bằng chứng, dòng dự phòng có thể là kết quả của
**mô hình** (khi văn bản chính đến từ bộ DSP) chứ không còn luôn là kết quả DSP. Ghi sai nhãn
ở đây là nói dối người vận hành về thứ họ đang đọc.
"""

import pytest
from PySide6.QtWidgets import QApplication

from morsedesk.app.decode_page import DecodePage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def text_for(decoded_by: str) -> str:
    page = DecodePage.__new__(DecodePage)
    return DecodePage._fallback_caption(page, decoded_by, "CQ DE K")


def test_model_result_is_labelled_as_model(app):
    caption = text_for("dsp")
    assert "CQ DE K" in caption
    assert "DSP" not in caption.upper().replace("DSP DECODER", "")


def test_dsp_result_keeps_the_old_label(app):
    assert "DSP" in text_for("model").upper()
    assert "CQ DE K" in text_for("model")


def test_unknown_source_falls_back_to_the_neutral_label(app):
    assert "CQ DE K" in text_for("")
