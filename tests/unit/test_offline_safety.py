"""Ứng dụng không được nói chuyện với mạng — đây là phần mềm chạy trên máy air-gap.

Kiểm bằng hai cách bổ sung nhau: quét mã nguồn tìm thư viện mạng, và chặn thật socket rồi chạy
một lượt mã hóa + giải mã đầy đủ. Cách thứ hai bắt được cả những lời gọi mà cách thứ nhất bỏ sót.
"""

import socket
from pathlib import Path

import numpy as np
import pytest

CORE = Path("morsedesk")
NETWORK_MODULES = ("urllib", "requests", "httpx", "http.client", "socket", "ftplib",
                   "telnetlib", "smtplib", "xmlrpc", "aiohttp")


def python_files() -> list[Path]:
    # `app/` và lõi; `tools/` cố ý được phép dùng mạng (tải corpus, model, bộ T2, font).
    return sorted(p for p in CORE.rglob("*.py") if "__pycache__" not in str(p))


def test_no_network_library_is_imported_anywhere_in_the_app():
    offenders: dict[str, list[str]] = {}
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        hits = [m for m in NETWORK_MODULES
                if f"import {m}" in text or f"from {m}" in text]
        if hits:
            offenders[str(path)] = hits
    assert not offenders, offenders


def test_a_full_encode_decode_round_trip_makes_no_connection(monkeypatch):
    """Chặn hẳn socket rồi chạy thật: bất kỳ lời gọi nào cũng thành lỗi ngay."""
    def forbidden(*args, **kwargs):
        raise AssertionError("ứng dụng đã thử mở kết nối mạng")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    from morsedesk.api import Decoder, Encoder

    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    assert isinstance(x, np.ndarray) and len(x) > 0
    out = Decoder("en", engine="baseline").decode_array(x)
    assert out.text == "CQ DE K", out.text


@pytest.mark.gate
def test_the_neural_engine_also_stays_offline(monkeypatch):
    if not Path("models/acoustic.onnx").is_file():
        pytest.skip("cần models/acoustic.onnx")

    def forbidden(*args, **kwargs):
        raise AssertionError("ứng dụng đã thử mở kết nối mạng")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    from morsedesk.api import Decoder, Encoder

    x = Encoder("en").to_audio("CQ DE K", wpm=20)
    assert Decoder("en", engine="onnx").decode_array(x).text == "CQ DE K"
