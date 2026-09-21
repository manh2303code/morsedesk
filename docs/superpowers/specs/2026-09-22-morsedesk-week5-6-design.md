# MorseDesk tuần 5–6: hoàn thiện v1

Ngày: 2026-09-22. Nền: `docs/superpowers/2026-09-21-rasoat-yeu-cau.md` (16 chốt kiểm),
`docs/research/04-pretrained-baselines.md` (mốc DeepCW), spec gốc `2026-09-18-morsedesk-design.md`.

## 1. Hai quyết định mới của người dùng

**1.1 Giấy phép không còn là ràng buộc.** Phần mềm dùng nội bộ 100%, chạy offline, không thương mại
hóa. Hệ quả:

- Bỏ **CP-04** (hồ sơ giấy phép bên thứ ba) và các điều khoản A7/A8 của bản rà soát.
- Dùng được thành phần AGPL và GPL: **DeepCW engine** (AGPL-3.0), `multimon-ng`, `fldigi`,
  `HamNoise`. `pyctcdecode`/`kenlm` cũng không còn bị chặn, nhưng vẫn không quay lại vì lý do kỹ
  thuật đã ghi ở spec tuần 3 mục 6.1 (kenlm cần biên dịch C++, pyctcdecode ghim numpy < 2 và không
  khớp ánh xạ mẫu→chữ một-nhiều).
- **CP-11** (đóng gói font) và **CP-16** (tám thư viện xcb) **không đổi**: đó là việc đóng gói cho
  đúng, không liên quan giấy phép.

**1.2 Ngưỡng gate giữ nguyên 2 % trên toàn vùng gate.** Vùng gate là SNR ≥ 0 dB và 10–35 WPM, gồm
mọi kênh (sạch, QSB, QRM, QRN, MP3) và mọi kiểu gõ. Hiện 26,45 %.

Tôi đã nêu rủi ro: mốc đo được cho thấy DeepCW, model pretrain tốt nhất tìm được, cũng chỉ đạt
23,70 % trên T1 và 47,0 % riêng ô QSB. Người dùng đã nghe và giữ nguyên ngưỡng. Kế hoạch dưới đây
nhắm đúng 2 % và đi theo thang thí nghiệm có thứ tự lợi ích/chi phí. Lập luận cho việc 2 % **có thể**
đạt được: **chưa ai từng huấn luyện cho đúng điều kiện QSB của T1**. DeepCW không hề thấy QSB lúc
huấn luyện mà vẫn hơn E3 15 điểm ở ô đó; một model được tăng cường đúng độ khó, cộng chuẩn hóa AGC
phù hợp và dữ liệu thật, còn nhiều dư địa chưa khai thác.

Nếu chạy hết thang thí nghiệm mà gate vẫn đỏ, sản phẩm giao ra là **bảng số đầy đủ theo từng ô** kèm
khuyến nghị, để người dùng quyết định, chứ không tự hạ ngưỡng.

**1.3 DeepCW dùng cả hai cách.** Vừa làm engine cho profile `en`, vừa làm nguồn gán nhãn cho bản ghi
thật để chưng cất sang model 65 lớp của mình.

## 2. Mục tiêu tuần 5

| Nhánh | Nội dung | Chốt kiểm đóng lại |
|---|---|---|
| A. Chất lượng | engine `deepcw`, bộ T2 thật, gán nhãn giả, chưng cất, tăng cường QSB, AGC, model lớn hơn, chạy lại gate | CP-01, CP-02, CP-03, CP-13 |
| B. Giao diện | chế độ live, trang Cài đặt, nút Hủy, tiến trình phần trăm, dịch cảnh báo lõi, xuất MP3, đuôi `.aif`/`.oga`, đường dẫn log | CP-06 → CP-10, CP-14, CP-15 |
| C. Nền tảng | chạy toàn bộ trên Ubuntu 22.04 và 24.04 | CP-05 |

Tuần 6 dành cho đóng gói (CP-11, CP-16), kiểm VM offline, T3 live loopback, tài liệu và demo.

## 3. Nhánh A — chất lượng giải mã

### 3.1 Engine `deepcw`

`tools/bench_pretrained.py` đã có toàn bộ tiền xử lý đúng và đã kiểm chứng (23,70 % trên T1). Nâng
phần lõi của nó thành module sản phẩm:

- `morsedesk/model/deepcw.py`: `DeepCwModel(model_path, meta_path)` với `load()`, `log_probs(x, sr)`
  và `decode_greedy(...)`. Tiền xử lý: `scipy.signal.resample_poly` về 3200 Hz (**không** dùng nội
  suy tuyến tính — đo được kém 5 điểm), STFT `fft_length`/`hop_length` theo metadata, lấy đúng dải
  bin `400–1200 Hz`, chuẩn hóa `log1p`.
- **Không lọc dải quanh tone.** Đã thử ở bước đo: lọc dải oracle làm CER xấu đi còn 64–73 % vì model
  chuẩn hóa `log1p` tuyệt đối. Lợi thế QRM của model mình không chuyển sang được cho DeepCW.
- `models/deepcw/model.onnx` + `model.onnx.json` (gitignored như `acoustic.onnx`), tải bằng
  `tools/fetch_deepcw.py`. `startup.check_models` kiểm thêm khi engine là `deepcw`.
- `Decoder(profile, engine="deepcw")` chỉ hợp lệ với profile `en`; profile khác ném lỗi rõ ràng
  (bảng chữ DeepCW chỉ có A–Z, 0–9, `, . / ?` và dấu cách).
- `tools/bench_pretrained.py` import từ module mới, không giữ bản sao logic.

Beam + LM trên đầu ra DeepCW: bảng chữ của nó **là chữ Latin**, nên beam ký tự với LM `en` của mình
áp thẳng được, không cần qua tầng mẫu chấm gạch. Làm thành một task riêng có đo trước/sau; giữ nếu
cải thiện, bỏ nếu không.

### 3.2 Bộ T2 bản ghi thật

`tools/fetch_t2.py` tải và dựng manifest cùng định dạng T1 (`path`, `text`, `profile`, `wpm`,
`source`, `license`):

| Nguồn | Nội dung | Ghi chú |
|---|---|---|
| ARRL W1AW code practice | MP3 + text 11 tốc độ, 5–40 WPM | dùng nội bộ, để trong `testdata/private/` (gitignored) |
| Wikimedia Commons | các bản ghi CW có chú thích | giấy phép tự do |
| SRAA tag CW | 5 file, tự chép đáp án | |
| Tự sinh bằng `ebook2cw` nếu có | tiếng Nga và Kazakh | bù chỗ trống: không có bản ghi thật hai thứ tiếng này |

Đo baseline trên T2 (**CP-13**): model của mình, DeepCW, `ggmorse`, `pycw`, `multimon-ng`. Ghi vào
`docs/research/04-pretrained-baselines.md`.

### 3.3 Gán nhãn giả và chưng cất

- `tools/pseudo_label.py`: chạy DeepCW trên bản ghi thật **không có đáp án**, giữ đoạn có độ tin cậy
  cao (trung bình posterior lớn nhất mỗi khung ≥ ngưỡng, mặc định 0,9), xuất manifest huấn luyện.
- **Nhãn cứng, không chưng cất mềm.** Lý do: tần số khung khác nhau (DeepCW hop 48 @ 3200 Hz =
  15 ms; mình hop 40 @ 8000 Hz = 5 ms), chưng cất posterior mềm phải nội suy theo thời gian và dễ
  sai lệch; nhãn cứng đi qua đúng đường CTC sẵn có. Ánh xạ: chữ Latin của DeepCW → mẫu chấm gạch →
  lớp trong bảng 65 của mình, dùng chính `profile.letter_to_pattern`.
- Trộn vào tập huấn luyện với trọng số cấu hình được; ghi tỉ lệ dữ liệu thật/tổng hợp vào metadata
  của run.

### 3.4 Thang thí nghiệm nhắm ngưỡng 2 %

Chạy theo thứ tự, mỗi bước đo trên T1 và T2, dừng sớm nếu đạt:

| # | Thí nghiệm | Giả thuyết | Chi phí |
|---|---|---|---|
| E6 | Tăng cường QSB đúng độ khó T1 (sâu tới 20 dB, chu kỳ 2–8 s) và tăng trọng số lấy mẫu | Ô QSB là ~1/5 clip nhưng ~1/2 tổng lỗi; DeepCW cho thấy còn 15 điểm | 1 đêm huấn luyện |
| E7 | AGC tau 0,3–0,5 s hoặc CMVN theo bin thay chuẩn hóa theo cửa sổ 4 s | Chu kỳ fade 4 s trùng đúng cửa sổ nên chuẩn hóa hiện tại vô hiệu | 1 đêm |
| E8 | Nhiễu thật HamNoise thay AWGN tổng hợp | Nhiễu sóng ngắn thật khác AWGN; giấy phép nay không chặn | 1 đêm |
| E9 | Model lớn hơn: hidden 192, hoặc thêm khối Conv 2-D trên phổ trước BiGRU | E3 bão hòa ở TER 22 %; DeepCW ~3,7 M tham số so với 200 k của mình | 2 đêm |
| E10 | Thêm dữ liệu thật đã gán nhãn giả (3.3) | Khoảng cách tổng hợp ↔ thật chưa từng đo được | 1 đêm |

Mỗi thí nghiệm là một run trong `runs/`, đo bằng `tools/eval_run.py`, ghi một dòng vào
`docs/research/03-model-experiments.md`. Giữ lợi thế tone-lock ở ô QRM: không đổi sang phổ toàn băng.

## 4. Nhánh B — giao diện còn thiếu

### 4.1 Chế độ live (spec gốc mục 4)

- `morsedesk/audio/capture.py`: `list_input_devices()` và `AudioCapture(device, block_ms=100)` bọc
  `sounddevice.InputStream`, đẩy khối vào `queue.Queue`, đếm số khối bị bỏ khi tràn.
- `morsedesk/api.py`: `StreamDecoder(profile, engine, ...)` giữ bộ đệm trượt. Mỗi lần nhận đủ audio
  mới thì giải mã lại cửa sổ đuôi và **chỉ phát ra những từ đã ổn định** (kết thúc trước mép chồng
  lấn), nên từ không nhảy qua lại. Cửa sổ 8 giây, chồng lấn 2 giây.
- **Kiến trúc thread:** giữ nguyên `DecoderWorker` cho file (đang chạy đúng, đã có test), thêm
  `LiveWorker(QThread)` riêng cũng theo mẫu hàng đợi chặn. Hai thread độc lập, mỗi thread một vòng
  `queue.get()`, không cần event loop và không có queued slot call giữa chúng. Đây là lựa chọn ít
  rủi ro nhất so với chuyển sang `moveToThread`, vốn phải viết lại phần đã kiểm chứng.
- Trang Giải mã thêm nguồn "Thiết bị thu": combo thiết bị, nút Bắt đầu/Dừng, waterfall cuộn, đếm
  khối bị bỏ trên `StatsBar`.

### 4.2 Trang Cài đặt (tab thứ ba)

Profile mặc định; thiết bị thu và phát mặc định; thư mục xuất; bật/tắt fallback DSP; hiển thị khả
năng xuất MP3 dò được lúc khởi động; nhắc lại ngôn ngữ giao diện (combo trên thanh công cụ vẫn giữ,
đã có test). Lưu bằng `QSettings` qua `AppSettings`.

### 4.3 Các chốt kiểm nhỏ

| Chốt | Việc |
|---|---|
| CP-08 | Tiến trình phần trăm theo số cửa sổ đã xử lý; `DecoderWorker` phát `progress(done, total)` |
| CP-09 | Nút Hủy: cờ hủy hợp tác kiểm trong vòng lặp cửa sổ của `chunker`, dừng dưới 1 giây |
| CP-10 | Cảnh báo của lõi và thông điệp `Player` đi qua bảng mã + `tr()` như nhóm lỗi worker |
| CP-06 | Xuất MP3: libsndfile có lame thì ghi thẳng, không thì gọi `ffmpeg` ngoài, không có thì báo rõ; khả năng hiện trong Cài đặt |
| CP-07 | `save_audio` ghi được mọi đuôi trong `SUPPORTED_EXT`, hoặc thu hẹp `SUPPORTED_EXT` cho đúng khả năng thật |
| CP-14 | Bỏ trần 20 phút: giải mã theo luồng cho file tới 1 giờ, có tiến trình và nút Hủy (dùng chung với CP-08/CP-09) |
| CP-15 | Chốt đường dẫn log theo Qt và sửa spec gốc mục 7 cho khớp |

## 5. Nhánh C — nền tảng đích

Chạy `pytest`, `ruff`, `build_i18n --check`, và mở `morsedesk-gui` trên **Ubuntu 22.04** và
**24.04** x86_64, không phải chỉ 26.04 như hiện nay. Ghi kết quả và mọi gói hệ thống phải cài thêm
vào `docs/research`. Đây là đầu vào trực tiếp cho danh sách đóng gói tuần 6.

## 6. Tuần 6 — đóng gói và chốt

- Container Ubuntu 22.04 (`packaging/Dockerfile.build`, glibc 2.35) → PyInstaller 6 onedir →
  AppImage bằng `appimagetool`. `AppRun` đặt `QT_QPA_PLATFORM_PLUGIN_PATH` và `QT_PLUGIN_PATH`.
- Gói kèm: Python 3.11, PySide6 (plugin xcb **và** wayland), **tám thư viện xcb** ở CP-16,
  `libportaudio2`, libsndfile 1.2.2, onnxruntime, numpy/scipy, `models/`, `profiles/`, `.qm`, và
  **font DejaVu Sans + Noto Sans** đặt làm font ứng dụng (CP-11).
- Mục tiêu dưới 400 MB; kiểm không có lời gọi mạng bằng `strace -f -e trace=network` trên VM sạch;
  kèm `SHA256SUMS`.
- T3: phát file qua thiết bị loopback, so kết quả live với kết quả file, lệch CER dưới 1 điểm.
- Tài liệu người dùng và kịch bản demo.

## 7. Điều kiện ra tuần 5

1. `uv run pytest` xanh trên Windows và Ubuntu; `ruff` sạch; `build_i18n --check` sạch.
2. Engine `deepcw` chạy được cho profile `en`, có test, có số đo trên T1 và T2.
3. Bộ T2 có trong `testdata/private/` kèm manifest và bảng số baseline năm công cụ.
4. Thang thí nghiệm E6–E10 chạy xong, mỗi bước có một dòng số trong `03-model-experiments.md`.
5. `uv run pytest -m gate`: đạt, hoặc có bảng số theo từng ô kèm khuyến nghị cho người dùng quyết.
6. Chế độ live chạy: mở thiết bị, hiện chữ theo thời gian thực, đếm khối bỏ, dừng sạch.
7. Trang Cài đặt đủ năm mục, lưu và nạp lại đúng.
8. CP-06 đến CP-10, CP-14, CP-15 đóng, mỗi cái có test.
9. Toàn bộ chạy trên Ubuntu 22.04 và 24.04.

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Ngưỡng 2 % không đạt dù chạy hết thang thí nghiệm | Mỗi thí nghiệm đo riêng theo ô nên biết chính xác còn kẹt ở đâu; báo cáo bằng số, không tự hạ ngưỡng |
| ARRL đổi đường tải hoặc chặn | Có ba nguồn thay thế; nếu hỏng hết thì sinh bằng `ebook2cw` và ghi rõ là dữ liệu tổng hợp |
| Gán nhãn giả kéo theo lỗi của DeepCW vào model mình | Chỉ giữ đoạn tin cậy ≥ 0,9; đo riêng run có và không có dữ liệu giả (E10 so với E9) |
| Live nhảy chữ hoặc trễ | Chỉ phát ra từ đã ổn định ngoài mép chồng lấn; đo lệch với kết quả file ở T3 |
| Hai thread cùng giữ `Decoder` gây tranh chấp | `LiveWorker` tạo `Decoder` riêng; `LMStore` và ONNX session dùng chung ở mức chỉ đọc |
| Thiết bị thu không có trên máy CI/WSL | Test dùng module `sounddevice` giả như `fake_sounddevice` đã làm ở tuần 4 |
