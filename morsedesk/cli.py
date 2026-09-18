"""CLI: morsedesk encode | decode | devices."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from morsedesk import __version__
from morsedesk.api import Decoder, Encoder
from morsedesk.audio.io import UnsupportedAudio, save_audio
from morsedesk.encode.text import UnsupportedCharacter
from morsedesk.lm.profile import list_profiles


def _force_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="morsedesk", description="Giải mã và tạo mã Morse offline")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    enc = sub.add_parser("encode", help="văn bản -> chuỗi chấm gạch và file âm thanh")
    enc.add_argument("text")
    enc.add_argument("--profile", default="en", choices=list_profiles())
    enc.add_argument("--wpm", type=float, default=20.0)
    enc.add_argument("--farnsworth", type=float, default=None, help="tốc độ hiệu dụng Farnsworth")
    enc.add_argument("--weight", type=float, default=3.0)
    enc.add_argument("--tone", type=float, default=700.0)
    enc.add_argument("--snr", type=float, default=None, help="thêm nhiễu với SNR (dB) trong băng 500 Hz")
    enc.add_argument("--rate", type=int, default=8000)
    enc.add_argument("--out", type=Path, default=None, help="WAV/FLAC/OGG; bỏ trống thì chỉ in chấm gạch")
    enc.add_argument("--lenient", action="store_true", help="bỏ qua ký tự không hỗ trợ")

    dec = sub.add_parser("decode", help="file âm thanh -> văn bản")
    dec.add_argument("file", type=Path)
    dec.add_argument("--profile", default="en", choices=list_profiles() + ["auto"])
    dec.add_argument("--engine", default="baseline", choices=["baseline", "onnx"])
    dec.add_argument("--model", type=Path, default=Path("models/acoustic.onnx"))
    dec.add_argument("--json", action="store_true")

    sub.add_parser("devices", help="liệt kê thiết bị âm thanh")
    return p


def cmd_encode(a: argparse.Namespace) -> int:
    enc = Encoder(a.profile)
    try:
        print(enc.to_morse_string(a.text, strict=not a.lenient))
        if a.out is not None:
            x = enc.to_audio(a.text, a.wpm, a.farnsworth, a.weight, a.tone, a.rate, a.snr,
                             strict=not a.lenient)
            save_audio(a.out, x, a.rate)
            print(f"đã ghi {a.out} ({len(x) / a.rate:.2f} s)", file=sys.stderr)
    except UnsupportedCharacter as e:
        print(f"lỗi: {e}. Dùng --lenient để bỏ qua.", file=sys.stderr)
        return 2
    return 0


def cmd_decode(a: argparse.Namespace) -> int:
    try:
        dec = Decoder(a.profile, engine=a.engine, model_path=a.model)
        r = dec.decode_file(a.file)
    except (NotImplementedError, UnsupportedAudio, FileNotFoundError) as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 2
    print(r.to_json() if a.json else r.text)
    for w in r.warnings:
        print(f"cảnh báo: {w}", file=sys.stderr)
    return 0


def cmd_devices(a: argparse.Namespace) -> int:
    try:
        import sounddevice as sd
    except (ImportError, OSError) as e:
        print(f"không dùng được sounddevice: {e}", file=sys.stderr)
        return 2
    print(sd.query_devices())
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_streams()
    a = build_parser().parse_args(argv)
    return {"encode": cmd_encode, "decode": cmd_decode, "devices": cmd_devices}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
