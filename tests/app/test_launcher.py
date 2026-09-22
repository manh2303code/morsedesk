"""Kịch bản bấm đúp trên Windows phải chạy được mà không cần biết dòng lệnh.

Người vận hành — và cả người viết mã khi quay lại sau vài tuần — không nên phải nhớ `uv run
morsedesk-gui`. File `.cmd` ở gốc kho là lối vào một cú bấm.
"""

from pathlib import Path

LAUNCHER = Path("MorseDesk.cmd")


def test_launcher_exists_at_the_repo_root():
    assert LAUNCHER.is_file()


def test_launcher_uses_crlf():
    """`cmd.exe` không đọc nổi kịch bản kết thúc dòng bằng LF — nó báo lỗi ở dòng đầu tiên."""
    data = LAUNCHER.read_bytes()
    assert b"\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_launcher_handles_a_missing_uv_and_a_missing_venv():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "where uv" in text, "phải kiểm uv trước khi gọi"
    assert "uv sync" in text, "lần chạy đầu phải tự cài phụ thuộc"
    assert "morsedesk-gui" in text
    assert "pause" in text, "lỗi phải dừng lại cho người dùng đọc, không đóng cửa sổ ngay"


def test_launcher_runs_from_its_own_folder():
    """Bấm đúp từ Explorer đặt thư mục làm việc ở nơi khác, nên phải tự `cd`."""
    assert 'cd /d "%~dp0"' in LAUNCHER.read_text(encoding="utf-8")
