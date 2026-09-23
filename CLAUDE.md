# MorseDesk

Ứng dụng desktop Linux **air-gap** giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Người dùng là người Việt: **trả lời bằng tiếng Việt, giữ đủ dấu**. Chữ trong giao diện, mã nguồn
và tài liệu thì theo ngôn ngữ đã dùng ở đó.

## Quy tắc số một: số đo quyết định, không phải lập luận

Dự án này đã nhiều lần đi ngược trực giác, và lần nào cũng chỉ phát hiện được nhờ đo. Trước khi
áp dụng bất cứ thay đổi nào ảnh hưởng chất lượng:

1. Chạy **toàn bộ T1** (500 clip tổng hợp) — không phải một lát cắt.
2. Chạy **T2** (bản ghi ARRL thật) — dữ liệu duy nhất không do chính mình sinh ra.
3. Chỉ CER trên T1/T2 mới dùng để quyết định.

```bash
PYTHONUTF8=1 uv run python tools/eval_run.py --run runs/E9 --name <tên>        # T1
PYTHONUTF8=1 uv run python -m morsedesk.cli bench \
  --manifest testdata/private/t2/manifest.jsonl --engine onnx --out-dir runs/<tên>   # T2
```

**`val_ter` KHÔNG so được giữa hai lượt huấn luyện khác seed** — tập validation sinh theo seed
của từng lượt, nên hai lượt chấm trên hai đề thi khác nhau. Đã sai hai lần (E9, E11) vì bỏ qua
điều này.

**Một model chỉ đo được tốt bằng pipeline dùng để chấm nó.** E9 bị ghi "BỊ LOẠI, CER 28,44 %",
rồi khi cửa sổ suy luận sửa từ 4 s sang 12 s, đúng checkpoint đó cho **9,70 %** và trở thành
model tốt nhất dự án. Khi khâu suy luận còn một lỗi lớn chưa biết, mọi so sánh giữa các model
đều mang lỗi đó và có thể đảo chiều hoàn toàn.

## Đã thử và BỊ SỐ ĐO BÁC BỎ — đừng làm lại

| Hướng | Kết quả |
|---|---|
| E6 tăng cường QSB mạnh hơn | 35,67 % so với 23,85 % |
| E11 đuôi SNR sạch trong dữ liệu huấn luyện | 26,80 % so với 20,21 % |
| E13 cửa sổ lúc huấn luyện khớp cửa sổ suy luận | 11,46 % so với 10,87 % |
| E15 clip huấn luyện dài 8–20 s | 11,01 % so với 10,87 % |
| Nội suy ranh giới dưới khung | T1 35,12 % → 40,73 % |
| Lexicon rộng hơn (1000/5000 từ) | 18,13 % / 18,23 % so với 18,19 % |
| Nới `min_prob` 1e-3 → 1e-4 | 0,15 điểm, gấp đôi thời gian |
| Huấn luyện khớp tone ước lượng | 0,36 điểm |
| **LocalAgreement-2** cho chế độ live | 38,41 % so với 17,31 % khi chốt ngay |
| `skip_silent_windows` ở **chế độ file** | 13,28 % so với 9,70 % |

**E9 (hidden 256) thì NGƯỢC LẠI: nó thắng.** Đừng đọc bảng trên thành "model lớn hơn không giúp".

## Lệnh hay dùng

```bash
uv sync --all-extras
PYTHONUTF8=1 uv run pytest -p no:warnings          # ~558 test; -p no:warnings để đọc được kết quả
PYTHONUTF8=1 uv run ruff check .
PYTHONUTF8=1 uv run python tools/build_i18n.py     # sau MỖI lần thêm/sửa chuỗi self.tr()
PYTHONUTF8=1 uv run morsedesk-gui
PYTHONUTF8=1 uv run python packaging/shots.py <thư mục>   # chụp mọi trang giao diện
```

Huấn luyện chạy trong WSL trên GPU (~0,05 s/bước, 30k bước ≈ 30 phút):

```bash
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" wsl.exe -d Ubuntu-26.04 -- \
  bash /mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh <tên> --steps 30000 --hidden 256 \
  --feature-mode window --seed 13 --workers 14 --device auto --no-mp3
```

## Kiến trúc: ranh giới phải giữ

- `morsedesk/` là **lõi, KHÔNG import Qt**. `morsedesk/app/` là Qt. Đường ranh này giữ cho CLI
  và bộ đo chạy được trên máy không có màn hình.
- `sounddevice` **import trễ trong hàm**, không bao giờ ở đầu module: máy air-gap thiếu
  `libportaudio2` thì `import sounddevice` ném ngay lúc nạp module và kéo sập cả CLI lẫn GUI.
- **Hai QThread độc lập**: `DecoderWorker` (file, một lượt dài, hủy được) và `LiveWorker` (nghe,
  vòng lặp không dứt). Không `moveToThread` cái này sang cái kia — một bản tin 37 phút đang giải
  sẽ chặn đứng dòng chữ đang chạy. Mỗi luồng giữ `Decoder` riêng vì `Decoder` không an toàn khi
  gọi song song.
- `StreamDecoder` (live) **bọc chính `api.Decoder`**, không sao chép logic giải mã. Nhờ đó mọi
  cải thiện chất lượng tự có mặt ở cả hai đường.

### Bốn tầng giải mã (số đo trên clip 15,8 s)

```
audio → dò tone 14 ms → dither nếu SNR>25dB → đặc trưng 11 chiều, cửa sổ 12 s/bước 2 s 42 ms
      → model CTC ONNX 12 ms → beam + LM n-gram ~520 ms → song song: bộ DSP 42 ms
      → dsp/selection.py chọn đường theo bằng chứng
```

**Beam + LM chiếm ~93 % thời gian, model chỉ ~2 %.** Muốn nhanh hơn thì tối ưu beam, không phải model.

### Model đang dùng

| | Là gì | Ghi chú |
|---|---|---|
| `models/acoustic.onnx` | CTC 65 lớp, hidden 256, 2,2 MB (E9 v0.3.0) | 65 lớp là **cả ký tự** (`.-`, `-...`), không phải từng chấm gạch |
| `models/lm/{en,ru,kk}.bin` | n-gram ký tự bậc 6, 41 MB | **bảng đếm thống kê, không phải nơ-ron**; đáng 1,05 điểm CER |
| `models/deepcw/model.onnx` | model ngoài, 15 MB | chỉ profile `en`, dùng đối chứng |

## Gotchas — mỗi dòng ở đây từng tốn thời gian thật

### Đo đạc và mô hình
- **Mismatch giữa lúc huấn luyện và lúc chạy là mỏ vàng.** Hai thắng lợi lớn nhất đều từ đó:
  SNR (train −6…25 dB, bản ghi thật 49–143 dB → thêm dither, CER 89,8 % → 28,9 %) và độ dài cửa
  sổ (clip train 4–12 s nhưng suy luận cắt 4 s → nới lên 12 s, 17,96 % → 10,87 %). Sửa ở khâu
  **suy luận** rẻ hơn huấn luyện lại hàng chục lần.
- **Mô hình đọc nhiễu nền thành chữ.** 30 giây nhiễu trắng thuần ra `WE ARE`. Nó chưa bao giờ
  được dạy nói "ở đây không có gì", còn AGC thì kéo nhiễu lên ngang tín hiệu. `skip_silent_windows`
  chặn được, nhưng **chỉ bật cho chế độ nghe** — ở chế độ file nó làm CER xấu 3,6 điểm.
- **Nhận diện bảng mã tự động cần ~8 ký tự.** Dưới ngưỡng đó `auto` đúng 66,7 %, và đoán sai bảng
  mã thì mọi ký tự sau đều sai. Đây đúng là tình cảnh những giây đầu một phiên nghe.
- Ở tín hiệu sạch, model **đã bão hòa**: mọi tần số 300–1500 Hz và mọi tốc độ 5–45 WPM đều CER 0 %.
  Khoảng cách còn lại nằm ở **nhiễu** (qsb 45,55 %), không ở tham số tín hiệu.

### Nghiên cứu
Quét GitHub/paper/diễn đàn trước khi tự mò — nhưng **research xong vẫn phải đo trên dữ liệu của
mình**. Trong một phiên đã có hai kết luận research không sống sót: LocalAgreement-2 (họ mất 0,9
điểm WER, ta mất 21 điểm CER) và chi phí khởi động onefile (tài liệu nói chậm 3×, đo thật chênh
1,56 giây).

### Giao diện
- **Ảnh chụp bắt lỗi mà test không bắt.** Ba lần trong một phiên: nút phát bị khóa vĩnh viễn, thác
  nước thành mảng vàng đặc, rồi thác nước phẳng lì. Sau mỗi thay đổi giao diện, chạy
  `packaging/shots.py` và **nhìn ảnh**.
- Nút bị `setEnabled(False)` **không phải bất biến** — phải chốt lại trong chính hàm thực thi.
- `QRawFont.supportsCharacter` nhận `str` trả `False` cho mọi ký tự ngoài Latin-1; phải truyền `ord(ch)`.
- `setStretchFactor` chỉ chia phần dư, **không quyết định kích thước ban đầu** — phải đặt cả
  `setSizes` lẫn `setMinimumHeight`.
- Chuyển tab theo **widget** (`tabs.indexOf(page)`), không theo chỉ số cứng: chèn một tab vào giữa
  làm sai mọi chỉ số mà không test nào canh.
- Không dùng emoji cờ 🇬🇧 — Linux tối giản thiếu font vùng miền sẽ hiện ra chữ "GB".

### Test
- **Test ghim hằng số phải tính theo hằng số đó**, đừng ghim số. Đổi `WINDOW_FRAMES` đã làm đỏ
  test đúng mã hai lần vì clip dựng sẵn ngắn hơn cửa sổ mới.
- **Fixture trùng tên che nhau**: `tests/app/conftest.py` từng có `fake_sounddevice` riêng che mất
  bản đầy đủ ở `tests/conftest.py`, làm test thấy một module giả thiếu `OutputStream`.
- Test GUI chờ `result_ready` rồi kiểm nút ngay sẽ **flaky** — `busy(False)` tới sau; phải chờ nút
  bật lại.
- Vét hàng đợi trong khi luồng còn chạy = vòng lặp vô hạn. `stop()` trước rồi mới vét.

### Công cụ và môi trường
- **Git Bash (MSYS) tự dịch đối số trông như đường dẫn POSIX**: `/mnt/c/...` tới tay `wsl.exe` đã
  thành `C:/Users/.../mnt/c/...`. Đặt `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"`.
- `PYTHONUTF8=1` cho **mọi** lệnh Python, nếu không `print` tiếng Việt vỡ với `UnicodeEncodeError`.
- `pytest` không có `-p no:warnings` thì cảnh báo torch che mất dòng kết quả.
- Dừng một background task **không giết tiến trình con**: script `sed` đang chạy đã kịp ghi đè
  hằng số sau khi task báo dừng. Kiểm lại file sau khi dừng.
- Script chạy trong container phải là **LF**, không CRLF (`.gitattributes` đã ép `*.sh`).
- `uv sync` trong container tạo `.venv` Linux đè venv Windows — đặt cả `UV_PROJECT_ENVIRONMENT`
  lẫn `VIRTUAL_ENV`.

### Đóng gói
- AppImage **đã là một file duy nhất**; runtime nhúng liên kết tĩnh nên **không cần libfuse2**.
- Nhưng file chép từ USB/Windows mất bit thực thi, và bấm đúp một file như vậy trong Nautilus
  **không làm gì và cũng không báo lỗi**. Dùng `scripts/install_linux.sh`.
- USB phải **ext4 hoặc exFAT, không FAT32**: FAT32 mount `showexec` nên `chmod +x` vĩnh viễn vô
  tác dụng.
- Windows onefile 134 MB khởi động 2,68 s so với onedir 315 MB khởi động 1,12 s. Lần chạy **đầu
  tiên mất 55 giây** vì Defender quét cả file.
- Onefile chạy **hai tiến trình** (cha bung, con chạy app) — `Start-Process -PassThru` trả tiến
  trình cha nên `MainWindowHandle` luôn 0, dễ tưởng app hỏng.

## Nơi tra số

| Cần gì | Ở đâu |
|---|---|
| Mọi con số CER/WER và vì sao | `docs/research/02-baseline-numbers.md` |
| Thí nghiệm model E0–E15 | `docs/research/03-model-experiments.md` |
| So với model có sẵn (DeepCW, QuartzNet) | `docs/research/04-pretrained-baselines.md` |
| Research realtime và đóng gói | `.superpowers/sdd/research-*.md` |
| Nhật ký từng task (gitignored) | `.superpowers/sdd/progress.md` |

## Hiện trạng

CER T1 **9,70 %**, T2 **3,93 %**. Bốn kênh sạch/mp3/qrm/qrn đều **dưới 3,3 %**, tức sát cổng 2 %
của spec; **toàn bộ khoảng cách còn lại nằm ở `qsb` (fading) 45,55 %** — đó là mục tiêu tiếp theo,
không phải chỗ nào khác.

Chưa làm: cổng 2 % (CP-01), người bản ngữ soát Kazakh (CP-12), benchmark LM thay thế (n-gram bậc 6
chưa bao giờ được so với lựa chọn khác), và đo chất lượng chế độ nghe qua micro thật — mọi số hiện
có đều từ tín hiệu tổng hợp sạch.
