# MorseDesk

Ứng dụng desktop Linux air-gap giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Spec: `docs/superpowers/specs/2026-09-18-morsedesk-design.md`.

## Chạy ứng dụng

| Nền tảng | Cách nhanh nhất |
|---|---|
| Windows | bấm đúp `MorseDesk.cmd` ở gốc kho — tự cài phụ thuộc lần đầu rồi mở giao diện |
| Windows (dòng lệnh) | `uv run morsedesk-gui` |
| Linux | `bash scripts/install_linux.sh dist/MorseDesk-x86_64.AppImage` một lần, rồi mở từ menu ứng dụng. Chép file rồi bấm đúp **không chạy**: file từ USB/Windows mất bit thực thi và trình quản lý file im lặng bỏ qua |

Model và ba mô hình ngôn ngữ nằm sẵn trong `models/` nên giao diện mở thẳng. Thiếu chúng thì
hộp thoại nêu đúng đường dẫn còn thiếu; muốn chạy không cần model nơ-ron thì thêm
`--engine baseline`.

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
- Tab Giải mã: mở hoặc kéo thả file (`.wav .flac .ogg .oga .mp3 .aiff .aif` — đúng `SUPPORTED_EXT`; thả nhiều file thì chỉ nhận file đầu), chọn ngôn ngữ bản tin (Tự động/Anh/Nga/Kazakh), bật/tắt mô hình ngôn ngữ; từ tô màu theo tin cậy (xanh ≥ 0,8, vàng ≥ 0,5, đỏ dưới), spectrogram 0–2 kHz với vạch tone, xuất TXT/JSON. File tới **1 giờ**; thanh tiến trình hiện phần trăm theo số cửa sổ đã xử lý và nút **Hủy** dừng lần giải mã đang chạy.
- Tab Tạo mã: văn bản → chuỗi chấm gạch, bảng ký tự Cyrillic và 9 chữ Kazakh, WPM/Farnsworth/weight/tone/nhiễu, Nghe thử (sounddevice), Lưu WAV/FLAC/OGG. Định dạng lưu: WAV/FLAC/OGG/OGA/AIFF/AIF, và MP3 khi máy có bộ mã hóa (xem tab Cài đặt). Văn bản mà audio ước tính dài hơn 1 giờ (cùng trần với tab Giải mã) thì Nghe thử và Lưu bị tắt kèm cảnh báo.
- Ngôn ngữ giao diện đổi ngay bằng ba lá cờ trên thanh công cụ (không ảnh hưởng tới bảng mã giải mã); lưu trong QSettings. Sửa bản dịch trong `morsedesk/app/i18n/translations.json` rồi chạy `uv run python tools/build_i18n.py` để sinh lại `.ts/.qm`.
- Thanh phát ở trang Giải mã: nghe lại chính file vừa giải mã, từ đang nghe được viền xanh, bấm một từ thì nghe từ chỗ đó. Chỉ bật sau khi giải mã xong; đọc lại file từ đĩa nên không đụng vào kết quả giải mã.
- Tab Nghe: giải mã trực tiếp từ card âm thanh — thác nước tần số, chip từ theo độ tin cậy, WPM/tone/SNR, chữ xám = còn có thể đổi, chữ thường = đã chốt. Bảng mã mặc định `auto`, cần khoảng 8 ký tự mới nhận đúng. Chất lượng kém đường file 3,1 điểm CER (đo trên 40 clip).
- Tab Cài đặt: engine đang dùng, xuất MP3 đi đường nào (libsndfile / ffmpeg ngoài / không có, kèm cách khắc phục), các định dạng ghi trực tiếp được, và đường dẫn file log. Trang chỉ đọc.
- Log: `~/.local/share/morsedesk/logs/morsedesk.log` trên Linux (theo chuẩn XDG, tôn trọng `XDG_DATA_HOME`); trên Windows theo `QStandardPaths.AppDataLocation`.
- Font: `uv run python tools/fetch_fonts.py` tải DejaVu Sans và Noto Sans vào `morsedesk/app/fonts/` (không commit). Ứng dụng tự nạp và đặt làm font mặc định, để máy Linux tối giản vẫn hiện đủ Ә Ғ Қ Ң Ө Ұ Ү Һ І.

## Bản ghi thật và chất lượng đo được (tuần 5)

- Bộ T2 gồm bản ghi thật: `uv run python tools/fetch_t2.py page --source arrl --profile en --index-url https://www.arrl.org/code-practice-files` rồi `uv run python tools/fetch_t2.py build`. Dữ liệu vào `testdata/private/t2/` (không commit). Các nguồn khác: `commons` (API Wikimedia), `local` (file tự thu), `synth` (bù tiếng Nga/Kazakh, đánh dấu `synthetic`).
- Số đo ngày 23/09/2026 (model E9 v0.3.0, cửa sổ 12 s): T1 tổng hợp **8,99 %** CER, bộ dev cùng ma trận khác seed **10,38 %** (sai số mỗi bộ ±1 điểm) — gần như toàn bộ phần còn lại nằm ở kênh `qsb`; bản ghi thật ARRL **3,93 %**, riêng dải 18–40 WPM **1,52 %** (đo 22/09) (đạt yêu cầu A2 của spec); T0 roundtrip audio sạch **CER = 0 trên cả 21 ô** (đạt D2). Chi tiết và cách tái lập: `docs/research/02-baseline-numbers.md`.
- Bộ giải mã được chọn theo bằng chứng đo từ chính clip: tín hiệu sạch hơn dải huấn luyện của model thì lấy kết quả bộ DSP, còn lại dùng model (`morsedesk/dsp/selection.py`). `DecodeResult.decoded_by` cho biết đường nào đã sinh ra văn bản.

## Đóng gói AppImage (tuần 6)

```bash
docker build -f packaging/Dockerfile.build -t morsedesk-build .
docker run --rm -v "$PWD":/src morsedesk-build bash scripts/build_appimage.sh
# -> dist/MorseDesk-x86_64.AppImage (146 MB) và dist/SHA256SUMS

docker build -f packaging/Dockerfile.test -t morsedesk-test .
docker run --rm -v "$PWD":/work morsedesk-test bash /work/scripts/test_appimage.sh
```

- Dựng trong Ubuntu 22.04 để liên kết với glibc cũ nhất được hỗ trợ; đã kiểm chạy trên **22.04
  và 24.04** sạch (ảnh chụp trong `dist/` và `dist2404/`).
- Ảnh kiểm **cố ý không cài** 8 thư viện xcb mà tài liệu rà soát liệt kê — nếu cửa sổ mở được ở
  đó thì gói đã mang theo đủ.
- Thư viện đồ họa `libEGL`/`libGL` **không** đóng gói: theo thông lệ AppImage chúng phải khớp
  driver của máy chạy, và mọi cài đặt Ubuntu có màn hình đều đã có.
- Model (`models/acoustic.onnx`) và ba mô hình ngôn ngữ được gói kèm nếu có mặt lúc dựng; thiếu
  thì ứng dụng hiện hộp thoại nêu đường dẫn còn thiếu rồi thoát mã 2 (`morsedesk/app/main.py`). Bản
  `dist/` hiện có dựng 22/09 với model v0.2.0 — dựng lại trước khi dùng.
