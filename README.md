# MorseDesk

Ứng dụng desktop Linux air-gap giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Spec: `docs/superpowers/specs/2026-09-18-morsedesk-design.md`.

## Thiết lập môi trường dev

```bash
uv sync --all-extras          # tạo .venv với Python 3.11 và cài mọi phụ thuộc
uv run pytest                 # chạy test
uv run morsedesk --help
```

Tùy chọn: cài `ffmpeg` (ví dụ `scoop install ffmpeg`) để bộ sinh dữ liệu tạo được biến thể MP3.
