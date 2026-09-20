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
- Đo trên T1: `uv run morsedesk bench --manifest testdata/generated/t1/manifest.jsonl --engine onnx --gate` (thêm `--no-lm` hoặc `--profile-override auto`); đo một run huấn luyện: `uv run python tools/eval_run.py --run runs/<run> --name <run>`. Số đo hiện tại: `docs/research/02-baseline-numbers.md`, `docs/research/03-model-experiments.md`.
