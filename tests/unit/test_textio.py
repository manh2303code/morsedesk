import io
import sys

from morsedesk.textio import force_utf8_streams


def test_force_utf8_streams_reconfigures_cp1252(monkeypatch):
    buf = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(buf, encoding="cp1252", write_through=True))
    force_utf8_streams()
    print("ПРИВЕТ tham số")
    sys.stdout.flush()
    result = buf.getvalue().decode("utf-8")
    assert "ПРИВЕТ tham số" in result


def test_force_utf8_streams_tolerates_streams_without_reconfigure(monkeypatch):
    class Dummy:
        def write(self, s):
            return len(s)

    monkeypatch.setattr(sys, "stdout", Dummy())
    force_utf8_streams()   # không được ném lỗi
