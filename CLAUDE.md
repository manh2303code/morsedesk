# MorseDesk

Ứng dụng desktop Linux **air-gap** giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Người dùng là người Việt: **trả lời bằng tiếng Việt, giữ đủ dấu**. Chữ trong giao diện, mã nguồn
và tài liệu thì theo ngôn ngữ đã dùng ở đó.

## Quy tắc số một: số đo quyết định, không phải lập luận

Dự án này đã nhiều lần đi ngược trực giác, và lần nào cũng chỉ phát hiện được nhờ đo. Trước khi
áp dụng bất cứ thay đổi nào ảnh hưởng chất lượng:

1. Chạy **toàn bộ T1** (500 clip tổng hợp) — không phải một lát cắt.
2. Chạy **T2** (bản ghi ARRL thật) — dữ liệu duy nhất không do chính mình sinh ra.
3. Chỉ CER trên T1/T2 mới dùng để quyết định. **Chỉnh tham số thì chỉnh trên bộ dev** (xem mục
   "Nhiễu đo" cuối file), T1 chỉ để xác nhận.

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

## Đã thử và BỊ SỐ ĐO BÁC BỎ

**Cột "cửa sổ" là bắt buộc đọc.** Mọi kết luận đo ở cửa sổ suy luận **4 s** (trước 23/09) đều
đáng ngờ: ba model từng bị tuyên "BỊ LOẠI" ở 4 s đã được đo lại ở 12 s và kết luận đảo chiều
(bảng dưới). Chỉ những dòng đo ở **12 s** mới là bác bỏ chắc chắn.

| Hướng | Kết quả | Cửa sổ | Còn đứng? |
|---|---|---|---|
| E13 cửa sổ lúc huấn luyện khớp cửa sổ suy luận | 11,46 % so với 10,87 % | 12 s | **có** |
| E15 clip huấn luyện dài 8–20 s | 11,01 % so với 10,87 % | 12 s | **có** |
| **LocalAgreement-2** cho chế độ live | 38,41 % so với 17,31 % khi chốt ngay | 12 s | **có** |
| `skip_silent_windows` ở **chế độ file** | 13,28 % so với 9,70 % | 12 s | **có** |
| Nội suy ranh giới dưới khung | T1 35,12 % → 40,73 % (bộ DSP) | không dùng cửa sổ | **có** |
| Chỉnh lại trọng số beam cho E9 (33 cấu hình `alpha`/`char_bonus`/`beta`/`lexicon_bonus`, chọn trên dev, xác nhận trên T1) | không cấu hình nào tốt hơn chắc chắn; 14 cấu hình hạ `alpha` hoặc `char_bonus` **xấu hơn chắc chắn**; `lexicon_bonus` 0 xấu hơn | 12 s | **có** — giữ 0,3 / 1,25 |
| Lexicon rộng hơn (1000/5000 từ) | 18,13 % / 18,23 % so với 18,19 % | 4 s | chưa đo lại |
| Nới `min_prob` 1e-3 → 1e-4 | 0,15 điểm, gấp đôi thời gian | 4 s | chưa đo lại |
| Huấn luyện khớp tone ước lượng | 0,36 điểm | 4 s | chưa đo lại |

### Từng bị loại oan — đo lại ở cửa sổ 12 s (23/09)

| Lượt | Kết luận cũ (4 s) | **Đo lại (12 s)** | Ý nghĩa |
|---|---|---|---|
| **E9** hidden 256 | "BỊ LOẠI", 28,44 % | **9,70 %** | model đang dùng, tốt nhất dự án |
| **E6** `--qsb-hard` | "BỊ LOẠI", 35,67 % | **10,92 %**, qsb 43,97 % | ngang E3; hướng `qsb` CHƯA bị bác bỏ |
| **E11** đuôi SNR sạch | "BỊ LOẠI", 26,80 % | **10,88 %** | ngang E3 |
| E10, E12 | "đã dừng" | chỉ chạy **2 000** bước | **chưa từng được trả lời**, không phải bị bác bỏ |

`runs/E10` (hidden 256 + đuôi SNR sạch) **khác** "E10" trong spec tuần 5–6 §3.4 (dữ liệu thật gán
nhãn giả). Cái sau chưa bao giờ được làm — `tools/pseudo_label.py` không tồn tại. E8 (nhiễu thật
HamNoise) cũng chưa chạy.

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
- **GC vòng của Python chỉ chạy ở luồng giao diện** (`app/gc_guard.py`, cài trong `create_app`;
  test: fixture ở `tests/app/conftest.py`). GC tự động chạy ở luồng nào đang cấp phát — luồng giải
  mã, luồng nghe, callback PortAudio — và gom luôn widget rác ở đó: widget bị hủy sai luồng, timer
  0 ms của bố cục văn bản bắn vào vùng nhớ đã giải phóng (access violation trong
  `QEventDispatcherWin32::event`) hoặc treo cứng (worker giữ mutex Qt chờ GIL, luồng chính giữ GIL
  chờ mutex). Đã bắt được cả hai bằng `lldb` ngày 24/09. Đừng bật lại `gc` trong ứng dụng.

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
| `models/acoustic.onnx` | CTC 65 lớp, hidden 384, 4,5 MB, 1 119 425 tham số (E16 v0.4.0) | 65 lớp là **cả ký tự** (`.-`, `-...`), không phải từng chấm gạch |
| `models/lm/{en,ru,kk}.bin` | n-gram ký tự bậc 6, 41 MB | **bảng đếm thống kê, không phải nơ-ron**; chấm cùng đáp án gốc thì đáng ~3,9 điểm CER (T1 13,57 → 9,70 %), riêng Kazakh ~8,5 điểm |
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
  Khoảng cách còn lại nằm ở **nhiễu** (qsb 38 % trên cả T1 lẫn dev, sau bản sửa 23/09), không ở tham số tín hiệu.

### Nghiên cứu
Quét GitHub/paper/diễn đàn trước khi tự mò — nhưng **research xong vẫn phải đo trên dữ liệu của
mình**. Trong một phiên đã có hai kết luận research không sống sót: LocalAgreement-2 (họ mất 0,9
điểm WER, ta mất 21 điểm CER) và chi phí khởi động onefile (tài liệu nói chậm 3×, đo thật chênh
1,56 giây).

### Giao diện
- **Tài liệu trong ứng dụng chứa số đo.** `morsedesk/app/docs/{about,technical}_{en,ru,kk}.html` ghi số
  tham số model, CER T1/dev/T2, tốc độ, bộ nhớ. Đổi model hay số đo thì sửa CẢ SÁU file (số trong bản
  Nga/Kazakh dùng dấu phẩy thập phân và `&nbsp;` phân nhóm). `tests/app/test_about.py` kiểm ba bản dịch
  cùng mục, cùng số bảng/hàng, và bảng mã Kazakh khớp profile — nhưng KHÔNG kiểm từng con số.
- Hiển thị bằng QTextBrowser (tập con HTML/CSS của Qt): `line-height` nhân lên khoảng dòng sẵn có của
  font (145 % ra gần gấp đôi), widget bề rộng cố định trong layout dọc khống chế bề rộng cả cột trừ khi
  thêm căn lề. Chụp `packaging/shots.py` rồi nhìn ảnh sau mỗi lần sửa.
- Logo sinh bằng `packaging/make_icon.py`; test so từng byte PNG trong repo với bộ sinh.
- **Stylesheet toàn ứng dụng không được đặt `font-family`/`font-size` cho `QWidget`**: nó đè mọi
  `setFont` của mã (chuỗi Morse mất chữ đơn cách, số đo mất kiểu mặt đồng hồ). Font đặt bằng
  `QApplication.setFont`. Nút nhỏ kích thước cố định (bàn phím chữ Kirin) phải tự đặt `padding: 0`
  — phần đệm 14 px của nút thường cắt mất nửa chữ.
- Hình học logo nằm ở `branding.LOGO_LARGE/LOGO_SMALL`, dùng chung cho biểu tượng (SDF), màn hình
  chờ và trang Giới thiệu (QPainter). Ở 16–24 px ba dấu phải tách rời — có test đếm khối.
- Tiến trình giải mã là thang 1000 chia theo tầng (`progress.STAGE_*`); beam/LM báo mỗi 100
  khung. Đổi tỉ trọng thời gian (vd. beam nhanh lên) thì đo lại và chỉnh các mốc.
- Heredoc bash rất dài có dấu nháy đơn trong mã Python có lúc làm công cụ Bash báo lỗi cú pháp:
  ghi script ra file tạm rồi chạy.
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
- Tiến trình con hiện **màn hình chờ động trước** (tiêu đề "MorseDesk splash"), rồi mới tới cửa
  sổ chính "MorseDesk". Script kiểm tìm cửa sổ theo tiêu đề; đóng màn hình chờ giữa chừng là hủy
  khởi động (Qt không tính cửa sổ kiểu SplashScreen là "cửa sổ cuối", nên phải tự thoát).
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

Model **E16 v0.4.0** (hidden 384, 1 119 425 tham số, fading nặng; thay E9 ngày 23/09 — thắng chắc chắn trên dev và T1, không xấu trên T2), cửa sổ 12 s, beam `alpha` 0,3 / `char_bonus` 1,25. Hai bộ tổng hợp cùng ma trận:

| | tổng | clean | mp3 | qrm | qrn | qsb |
|---|---|---|---|---|---|---|
| T1 (seed 1000) | **7,78 %** | 1,64 | 1,44 | 1,69 | 1,54 | 32,61 |
| dev (seed 500000) | **8,07 %** | 2,56 | 3,05 | 2,70 | 2,73 | 29,31 |

T2 **1,62 %** (bản ghi ARRL thật 0,95 %, 18–40 WPM không sai ký tự nào; trước 23/09 báo 3,93 % vì đáp án Kazakh bị viết phẳng — xem 02-baseline-numbers). **Không kênh nào qua cổng 2 % một cách chắc chắn** — trên T1 bốn kênh
chạm dưới 2 % nhưng dev độc lập cho 2,6–3,1 %.

### Nhiễu đo — đọc trước khi tin một con số

- Sai số chuẩn (bootstrap) của CER tổng 500 clip ≈ **±1 điểm**; từng kênh (100 clip) **±0,5–2,8**;
  từng ô kênh × SNR (20 clip) tới **±7**. Chênh lệch dưới mức đó giữa hai bộ clip là không có nghĩa.
- **So hai cấu hình thì so GHÉP CẶP trên cùng clip** (`tools/paired_compare.py`) — nhiễu triệt tiêu,
  sai số của hiệu chỉ còn ~0,2 điểm.
- **Chỉnh tham số trên bộ dev, xác nhận trên T1.** T1 đã bị dùng để chọn E9, chọn cửa sổ và chỉnh
  `alpha` trước đây, nên số T1 có phần lạc quan (T1 9,70 % so với dev 12,25 %). Dựng dev:
  `uv run python tools/make_t1.py --out testdata/generated/t1dev --seed-base 500000`.
- **Thử nhiều cấu hình thì may rủi tự sinh ra "người thắng".** 33 cấu hình trên dev, tốt nhất là
  −0,34 điểm — sang T1 còn −0,01.
- **`bench` chấm greedy và LM theo HAI đáp án khác nhau**: greedy theo văn bản đã render qua bảng mã
  (Ә gộp thành А, dễ hơn), LM theo văn bản gốc. So hai cột đó trong `t1_summary.json` là so lệch. Chấm
  cùng đáp án gốc thì LM thắng mọi ngôn ngữ: greedy → LM là 13,57 → 9,70 % (T1) và 16,14 → 12,25 %
  (dev); Kazakh −8,5 điểm. `test_t1_lm_not_worse_than_greedy` mắc đúng lệch này.

### `qsb` — vật lý chỉ ở SNR thấp

T1 dùng fade đúng 20 dB chu kỳ 4 s. Ở SNR 20 dB đáy fade chỉ xuống 0 dB, mà clean@0 dB giải được
**~3 %** (T1 3,3, dev 3,2 — lặp lại). qsb@20 dB từng là **14,2 % (T1) và 42,0 % (dev)** — lỗi
**xử lý**, và **đã sửa (23/09)**: nhánh "chi phí timing < 0,02" của `dsp/selection.py` tin bộ DSP
khi bộ DSP đã XÓA cả đoạn chìm dưới ngưỡng — những gì nó đọc được thì khớp lưới hoàn hảo nên chi
phí vẫn thấp. Quy tắc mới `dsp_is_complete`: chỉ lấy DSP khi văn bản DSP ≥ 0,9 độ dài văn bản mô
hình. qsb@20 dB nay **5,3 % (T1), 6,8 % (dev)**; tổng T1 9,79 → 8,99, dev 12,25 → 10,38 (cả hai có
ý nghĩa, so ghép cặp); T2 không đổi. **Đừng bỏ hẳn nhánh chi phí timing** ("chỉ tin DSP khi SNR >
30"): thắng nhiều hơn trên dữ liệu tổng hợp nhưng T2 3,93 → 12,64 %. Ở 0–6 dB đáy fade xuống
−14…−20 dB, dưới nền nhiễu thật: cổng 2 % trên toàn ô `qsb` gần như chắc chắn **không bộ giải mã nào
đạt** (DeepCW 47 %). Spec tuần 5–6 §1.2: khi đó giao bảng số theo ô để người dùng quyết.

**Spec §7 "không bịa chữ" — đã đóng phần lớn (23/09).** Trước đó 81/81 đầu vào KHÔNG có Morse đều ra
chữ, kể cả im lặng số (`T`), sóng mang (`73`), nhiễu trắng (`SEE`). Hai bản sửa: (1) `fallback_tone_hz`
không đoán tone khi dải không có năng lượng; (2) `MIN_CLIP_CONFIDENCE = 0.15` ở `api.py` — độ tin cậy
trung bình cả clip dưới mức đó thì trả rỗng + `NO_SIGNAL`, vẫn giữ tone/SNR đã đo. Chọn trên dev, xác
nhận trên T1: T1 9,70 → 9,79 %, dev và T2 không đổi, 120/120 lần chạy nhiễu hết bịa chữ.
**Đừng tắt đường đoán tone** để "đúng chữ spec": nó cứu 39 clip `qsb` mỗi bộ, đáng 3,5 điểm CER.
**Giới hạn còn lại:** tín hiệu đánh phím TUẦN HOÀN hoàn hảo (nhiễu điều biên đều) ra `EEEE` với độ tin
cậy ~0,99 — về đường bao nó chính là Morse chữ E. Test cũ kiểm §7 bằng `engine="baseline"` nên không bắt
được việc engine `onnx` bịa chữ; test mới chạy trên `onnx`.

**Đóng gói (dựng lại 24/09, model v0.4.0 + giao diện mới + màn hình chờ động + GC luồng giao diện).** Windows `dist/MorseDesk.exe` một file
139 MB (`scripts/build_windows.ps1`); Linux `dist/MorseDesk-x86_64.AppImage` 148 MB. Kiểm: chạy
`scripts/test_windows_exe.ps1` TRƯỚC (nó sinh mẫu `dist/selftest/`), rồi `scripts/test_appimage.sh`
— cả hai đòi `--self-test` ra văn bản giống hệt mã nguồn. Đổi model thì phải dựng lại CẢ HAI.
Docker Desktop có lúc báo "running" mà máy ảo đã chết (lỗi 500): `docker desktop restart` — train
trong WSL vẫn sống qua lần khởi động lại đó (đã thử 23/09).

Chưa làm: T3 live so với file lệch **3,1 điểm** (spec đòi dưới 1); trang Nghe chưa hiện bộ đếm khối
bị bỏ (spec tuần 5–6 §7.6); đo chế độ nghe qua micro thật. CP-12 (soát bản Kazakh) KHÔNG còn là
nhãn cho người dùng: 24/09 người dùng quyết bỏ mọi chữ "bản nháp/жоба" — tác giả là người Kazakh.
