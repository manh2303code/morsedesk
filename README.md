# MorseDesk

Ứng dụng desktop Linux air-gap giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Spec: `docs/superpowers/specs/2026-09-18-morsedesk-design.md`.

## Thiết lập môi trường dev

```bash
uv sync --all-extras          # tạo .venv với Python 3.11 và cài mọi phụ thuộc
uv run pytest                 # chạy test (bỏ qua test đánh dấu gate)
uv run morsedesk --help
```

Tùy chọn: cài `ffmpeg` (ví dụ `scoop install ffmpeg`) để bộ sinh dữ liệu tạo được biến thể MP3.

`uv run pytest -m gate` chạy các test cần model đã huấn luyện (`models/acoustic.onnx`) một khi file đó tồn tại; mặc định các test này bị loại khỏi `uv run pytest`.

## Giải mã bằng model ONNX và mô hình ngôn ngữ (tuần 3)

- Model âm thanh mặc định là `models/acoustic.onnx` (không commit; xuất từ checkpoint bằng `uv run python tools/export_onnx.py --checkpoint runs/<run>/best.pt --out models/acoustic.onnx`). Giải mã: `uv run morsedesk decode file.wav --engine onnx` (thêm `--no-lm` để giải mã greedy, `--beam N` để đổi độ rộng beam).
- `--profile` mặc định là `auto` (nhận diện ngôn ngữ theo đoạn) và cần ba mô hình ngôn ngữ `models/lm/{en,ru,kk}.bin` (không commit). Dựng chúng trên máy dev: `uv run python tools/fetch_corpus.py --lang en|ru|kk` → `uv run python tools/normalize_corpus.py --profile <id> --lang <lang> --in corpus/raw/<lang> --out-dir corpus` → `bash tools/build_lm.sh 6` trong WSL Ubuntu (cài KenLM, chỉ dùng lúc dev) → `uv run python tools/arpa_to_bin.py --arpa corpus/<lang>.arpa --profile <id> --out models/lm/<lang>.bin --holdout corpus/<lang>.holdout.txt`. Không có KenLM: `uv run python tools/train_small_lm.py --profile <id> --text corpus/<lang>.txt --out models/lm/<lang>.bin`. Nguồn và giấy phép corpus: `models/lm/LICENSES.md`.
- Chưa có LM: `Decoder(profile, engine="onnx")` nạp LM **mặc định** (`lm=True`) nên thiếu `models/lm/*.bin` sẽ ném `FileNotFoundError`, và `profile="auto"` luôn cần đủ ba LM. Giải mã khi không có LM: `morsedesk decode file.wav --profile en` (engine baseline, không đụng tới LM) hoặc `morsedesk decode file.wav --profile en --engine onnx --no-lm` (greedy CTC). `Decoder.lm_available(lm_dir=None)` trả `True` khi đủ LM cho mọi profile — GUI/CLI dùng nó để quyết định có bật `auto` và beam+LM hay không.
- Đo trên T1: `uv run morsedesk bench --manifest testdata/generated/t1/manifest.jsonl --engine onnx --gate` (thêm `--no-lm` hoặc `--profile-override auto`); đo một run huấn luyện: `uv run python tools/eval_run.py --run runs/<run> --name <run>`. Số đo hiện tại: `docs/research/02-baseline-numbers.md`, `docs/research/03-model-experiments.md`.

## Giao diện đồ họa (tuần 4)

- Chạy: `uv run morsedesk-gui` (cần `models/acoustic.onnx` và `models/lm/{en,ru,kk}.bin`; thiếu file → hộp thoại nêu đường dẫn và thoát mã 2). Tham số: `--model`, `--lm-dir`, `--engine baseline` (dev, không cần ONNX), `--lang en|ru|kk`.
- Tab Giải mã: mở hoặc kéo thả file (`.wav .flac .ogg .mp3 .aiff`), chọn ngôn ngữ bản tin (Tự động/Anh/Nga/Kazakh), bật/tắt mô hình ngôn ngữ; từ tô màu theo tin cậy (xanh ≥ 0,8, vàng ≥ 0,5, đỏ dưới), spectrogram 0–2 kHz với vạch tone, xuất TXT/JSON. File dài hơn 20 phút chưa hỗ trợ.
- Tab Tạo mã: văn bản → chuỗi chấm gạch, bảng ký tự Cyrillic và 9 chữ Kazakh, WPM/Farnsworth/weight/tone/nhiễu, Nghe thử (sounddevice), Lưu WAV/FLAC/OGG.
- Ngôn ngữ giao diện đổi ngay bằng combo trên thanh công cụ (English, Русский, Қазақша bản nháp); lưu trong QSettings. Sửa bản dịch trong `morsedesk/app/i18n/translations.json` rồi chạy `uv run python tools/build_i18n.py` để sinh lại `.ts/.qm`.
- Log: `%APPDATA%\MorseDesk\MorseDesk\logs\morsedesk.log` (Windows, tức `C:\Users\<user>\AppData\Roaming\MorseDesk\MorseDesk\logs\`) hoặc `~/.local/share/MorseDesk/MorseDesk/logs/` (Linux): `QStandardPaths.AppDataLocation` lồng cả tên tổ chức lẫn tên ứng dụng.
