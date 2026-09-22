"""Cảnh báo của lõi phải đi kèm MÃ để giao diện dịch được (CP-10).

Lõi viết thông điệp bằng tiếng Việt cho CLI và log. Giao diện có ba ngôn ngữ en/ru/kk, nên nếu
banner ghép thẳng `result.warnings` thì người dùng Nga nhận được câu tiếng Việt. Mỗi cảnh báo vì
vậy mang thêm `DecodeWarning(code, params)`; giao diện tra mã sang chuỗi nguồn tiếng Anh rồi để
Qt dịch, còn CLI vẫn in nguyên văn tiếng Việt.
"""

import numpy as np
import pytest

from morsedesk.api import Decoder
from morsedesk.warnings import WARNING_TEXTS, DecodeWarning, WarningCode


def test_every_code_has_an_english_source_string():
    for code in WarningCode:
        assert code.value in WARNING_TEXTS
        assert WARNING_TEXTS[code.value].isascii(), code


def test_no_signal_carries_a_code():
    res = Decoder("en", engine="baseline").decode_array(np.zeros(8000, dtype=np.float32))
    assert res.warnings and res.warning_codes
    assert [w.code for w in res.warning_codes] == [WarningCode.NO_SIGNAL.value]
    assert len(res.warning_codes) == len(res.warnings)


def test_codes_and_texts_stay_aligned_for_real_audio():
    from tests.helpers import make_morse

    x, _ = make_morse("CQ DE R1ABC K", profile_id="en", wpm=20)
    res = Decoder("en", engine="baseline").decode_array(x)
    assert len(res.warning_codes) == len(res.warnings)
    for w in res.warning_codes:
        assert w.code in WARNING_TEXTS


def test_render_substitutes_parameters():
    w = DecodeWarning(WarningCode.SECOND_TONE.value, {"second_hz": 850.0, "tracked_hz": 600.0})
    text = WARNING_TEXTS[w.code].format(**w.params)
    assert "850" in text and "600" in text


def test_json_export_keeps_both_forms():
    import json

    res = Decoder("en", engine="baseline").decode_array(np.zeros(8000, dtype=np.float32))
    data = json.loads(res.to_json())
    assert data["warnings"] == res.warnings
    assert data["warning_codes"][0]["code"] == WarningCode.NO_SIGNAL.value


@pytest.mark.parametrize("lang", ["ru", "kk"])
def test_translations_exist_for_every_warning(lang):
    """Mỗi chuỗi nguồn phải có bản dịch, và bản dịch không được là chính chuỗi tiếng Anh."""
    import json
    from pathlib import Path

    table = json.loads(
        (Path("morsedesk/app/i18n/translations.json")).read_text(encoding="utf-8")
    )[lang]
    for code in WarningCode:
        src = WARNING_TEXTS[code.value]
        assert src in table, f"thiếu bản dịch {lang}: {src}"
        assert table[src] != src, f"bản dịch {lang} chưa dịch: {src}"


def test_gui_sources_match_the_core_table():
    """Bảng literal trong giao diện phải phủ đúng WarningCode và khớp từng ký tự với lõi.

    Hai bảng buộc phải trùng lặp: lõi không phụ thuộc Qt, còn `pyside6-lupdate` chỉ trích được
    literal. Test này là thứ giữ chúng không trôi khỏi nhau.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from morsedesk.app.decode_page import DecodePage

    app = QApplication.instance() or QApplication([])
    sources = DecodePage._warning_sources(DecodePage.__new__(DecodePage))
    assert set(sources) == {c.value for c in WarningCode}
    for code, text in sources.items():
        assert text == WARNING_TEXTS[code], code
    _ = app
