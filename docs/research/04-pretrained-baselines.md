# Mốc từ model pretrain bên ngoài trên T1 v2

Ngày đo: 2026-09-21. Mục đích: trả lời bằng số câu hỏi *T1 v2 khó tới mức nào* — nếu model
pretrain tốt nhất hiện có cũng kém ở các ô QSB / 0 dB thì bộ T1 quá khắt khe; nếu nó tốt hơn hẳn
thì chỗ phải sửa là cách sinh dữ liệu và huấn luyện của dự án.

> **Chỉ là thước đo.** DeepCW phát hành theo **AGPL-3.0**, nên model, trọng số và mã của họ
> **không** được nhúng, đóng gói hay phân phối cùng MorseDesk. Bản clone nằm ngoài repo (thư mục
> scratchpad của phiên làm việc); repo này chỉ chứa script đo (`tools/bench_pretrained.py`) —
> script đọc `model.onnx` từ đường dẫn truyền vào và không mang theo bất kỳ phần nào của DeepCW.

## Tóm tắt kết quả

| Hệ | CER T1 v2 (500 clip) | Ghi chú |
|---|---|---|
| **DeepCW** (pretrain, greedy) | **23.70 %** | 0,019 s/clip, onnxruntime CPU |
| E3 greedy (model dự án) | 26.45 % | `runs/E3/t1_summary.json` |
| E3 beam + LM | 25.27 % | như trên |
| MorseCodeToolkit QuartzNet 10x5 | 85.84 % | ngoài phân bố huấn luyện, xem mục riêng |

Số tổng gần nhau, nhưng đó là *trung bình bị che*. Tách theo kênh thì kết luận đảo chiều:

| Kênh | DeepCW | E3 greedy | E3 beam+LM | Nhận xét |
|---|---|---|---|---|
| clean | **7.06 %** | 17.87 % | 17.42 % | E3 kém 2,5× ở ô **dễ nhất** |
| qrn | **10.85 %** | 18.43 % | 17.07 % | |
| mp3 | **11.72 %** | 15.22 % | 14.90 % | |
| qsb | **47.00 %** | 62.34 % | 60.55 % | cả hai đều tệ, DeepCW vẫn hơn 15 điểm |
| qrm | 41.86 % | **18.41 %** | **16.40 %** | lợi thế thật của MorseDesk, xem giải thích bên dưới |
| **bỏ ô qrm** | **19.16 %** | 28.46 % | 27.48 % | |

Trên tập con `clean` + SNR ≥ 10 dB, **profile `en`** (n = 14), DeepCW đạt **1.02 %** — tức
**gate 2 % là đạt được** trên vùng dễ của T1. T1 không phải bộ test bất khả thi.

## 1. Phương pháp

### 1.1 DeepCW

| Mục | Giá trị |
|---|---|
| Repo | https://github.com/e04/deepcw-engine |
| Commit | `8e264d243bbd4467bd19f3f28292219405b47e0e` (2026-06-16) |
| Model | `model.onnx`, 15 139 839 byte, sha256 `ef120799457bca042d4690944f0faf93268eb4654e7f50f28784ad63bdc1fe02` |
| Giấy phép | AGPL-3.0-only |
| Web app tham khảo | https://github.com/e04/web-deep-cw-decoder commit `a07f8a6a8440ac4860b55452187fed59d88c6a9d` (2026-08-31) |

Tiền xử lý bám đúng `examples/python/decode_morse.py` và `model.onnx.json` của họ:

- mono, resample về **3200 Hz** (`sample_rate`);
- STFT `fft_length` = 256, `hop_length` = 48, cửa sổ Hann tuần hoàn, pad phản xạ 128 mẫu;
- lấy biên độ các bin trong **400–1200 Hz** → 65 bin (`12,5 Hz`/bin, bin 32…96);
- chuẩn hóa `log1p` (tuyệt đối, **không** CMVN);
- CTC greedy trên `log_probs`, 42 lớp (`,` `.` `/` `?` `0`–`9` `A`–`Z` khoảng trắng + blank 41).

Script trong repo vector hóa vòng lặp khung bằng `sliding_window_view` nhưng công thức y hệt; kết
quả trên clip mẫu trùng với script gốc (`+20db_25wpm_machine_clean_0.wav` → `TNX FER CALL UR`).

**Không có chế độ low/high trong bản engine phát hành.** README của web app nhắc "HIGH mode", nhưng
mã nguồn hiện tại chỉ có hai biến thể model tiếng Anh: `standard` (mặc định, 65 bin) và `narrow`
(5 bin, dùng cho pileup) — `narrow` là **một file model khác**, không nằm trong deepcw-engine.
Bản engine mở cũng dùng cấu hình khác web app (3200 Hz + `log1p` so với 9600 Hz + CMVN theo mẫu),
nghĩa là model công bố và model chạy trên deepcw.cc không phải một. Ta đo đúng bản công bố, ở chế
độ duy nhất nó có, với tiền xử lý chính xác nhất (xem 1.2).

### 1.2 Resample: đo hai cách

Ví dụ của họ nội suy tuyến tính, cố ý không lọc chống chồng phổ ("keep the example
dependency-light"). Với T1 (8000 Hz → 3200 Hz, Nyquist 1600 Hz) nhiễu trên 1600 Hz gập vào dải tín
hiệu và làm hỏng kết quả rõ rệt:

| Resampler | CER T1 | by_snr 0 dB |
|---|---|---|
| `scipy.signal.resample_poly` (up 2 / down 5, có lọc) | **23.70 %** | 28.30 % |
| nội suy tuyến tính như ví dụ gốc | 28.98 % | 51.11 % |

Mọi số DeepCW trong tài liệu này dùng `resample_poly` — đây là chế độ chính xác nhất đo được.

### 1.3 Tần số tone của T1 so với băng của DeepCW

`tools/make_t1.py` sinh tone theo `500 + (index * 97) % 600` với `seed = 1000 + index`, tức
**500–1099 Hz**. Script suy lại tone từ `seed` và đã kiểm chéo bằng đỉnh phổ FFT của từng clip
(sai số ≤ 1 Hz). Toàn bộ **500/500 clip nằm trong băng 400–1200 Hz** của DeepCW, nên không phải
tách kết quả theo tone trong/ngoài băng.

### 1.4 Remap Cyrillic

DeepCW chỉ xuất Latin. Kết quả cho profile `ru` và `kk-cyrl-ru` được chuyển
**chữ Latin → mẫu chấm-gạch → chữ của profile đích** bằng chính bảng của dự án
(`morsedesk.data.text.translit_via_patterns` với `morsedesk/profiles/en.yaml` làm nguồn). Ví dụ
thật từ `results.jsonl`: `DE GM` → `ДЕ ГМ`, `KUN KALA` → `КУН КАЛА`, `SWKZX` → `СВКЗЬ`.

Sàn lỗi không tránh được (ký tự tham chiếu mà 41 lớp của DeepCW không biểu diễn nổi sau remap):

| Profile | Tỉ lệ ký tự ngoài tầm | Ký tự |
|---|---|---|
| en | 1.17 % | `!` `"` `$` `'` `(` `)` `+` `-` `:` `;` `=` `@` `_` |
| kk-cyrl-ru | 3.10 % | `$` `&` `)` `+` `-` `:` `;` `<` `=` `>` `@` `K` `S` `_` `Ш` `Э` `Ю` |
| ru | 5.58 % | `!` `&` `'` `)` `+` `-` `:` `<` `=` `>` `@` `K` `S` `Ч` `Ш` `Э` `Ю` `Я` |

Nguồn sàn lỗi: (a) dấu câu ITU ngoài `, . / ?`; (b) `<SK>`, `<SOS>`, `<ERR>` viết dạng `<` `S` `K`
`>`; (c) các chữ Cyrillic có mẫu **không có trong bảng Latin 26 chữ** — `Ч` (`---.`), `Ш` (`----`),
`Ю` (`..--`), `Я` (`.-.-`), `Э` (`..-..`); `Ъ` dùng chung mẫu `-..-` với `Ь` nên render thành `Ь`.
Ngược lại `Щ` (`--.-`) **có** mẫu trùng `Q` nên remap được — không mất.
Trên toàn T1 là **3,24 %** (212/6552 ký tự): dù hoàn hảo, DeepCW cũng không xuống dưới mốc đó.
Đây là giới hạn từ vựng của DeepCW, không phải khuyết điểm của T1: từ vựng 65 lớp của MorseDesk
phủ hết mọi ký tự trong T1.

### 1.5 Chấm điểm

Dùng lại nguyên `morsedesk.metrics.cer/wer` và `morsedesk.bench.aggregate / pivot_snr_wpm / gate`,
tham chiếu là trường **`text`** (đã render qua profile) — giống hệt cách E3 greedy được chấm. Lưu ý
khi so: cột "E3 beam+LM" trong `runs/E3/t1_summary.json` chấm theo `text_original`
(`reference_text` đổi tham chiếu khi `engine == "onnx" and lm`), tức khắt khe hơn một chút ở
`kk-cyrl-ru`; cột "E3 greedy" mới là so sánh cùng luật với DeepCW.

Thời gian chạy: **9,7 s cho 500 clip = 0,019 s/clip** khi WAV đã nằm trong cache của hệ điều hành
(20,8 s = 0,042 s/clip ở lần chạy nguội đầu tiên) — onnxruntime 1.30.0 CPU, Python 3.11.15,
numpy 2.4.6, scipy 1.17.1. So sánh: E3 greedy 0,082 s/clip, E3 beam+LM 0,376 s/clip. Tức model
pretrain 15 MB vẫn **nhanh hơn** model 200k tham số của dự án trên cùng máy, vì nó chạy một lượt
CNN trên phổ 65 bin ở 3200 Hz còn E3 chạy BiGRU theo cửa sổ ở 200 khung/giây.

### 1.6 Cách chạy lại

```powershell
$sp = "<scratchpad>"
git clone https://github.com/e04/deepcw-engine "$sp\deepcw-engine"
uv venv "$sp\venv-bench" --python 3.11
uv pip install --python "$sp\venv-bench\Scripts\python.exe" `
    "numpy>=1.24" "onnxruntime>=1.17" scipy pyyaml "soundfile>=0.12"

$env:PYTHONUTF8 = "1"; $env:PYTHONPATH = "<worktree>"
& "$sp\venv-bench\Scripts\python.exe" tools\bench_pretrained.py `
    --model "$sp\deepcw-engine\model.onnx" --metadata "$sp\deepcw-engine\model.onnx.json" `
    --manifest C:\Users\Admin\morsedesk\testdata\generated\t1\manifest.jsonl `
    --out-dir runs\bench_deepcw --resampler poly
```

Phụ thuộc cài trong venv riêng ở scratchpad; `.venv` của repo, `pyproject.toml` và `uv.lock` không
bị đụng tới. Kết quả thô nằm ở `runs/bench_deepcw/` (thư mục gitignored, không commit).

## 2. DeepCW vs E3 theo từng chiều

Mỗi ô có n cân bằng: 100 clip/kênh, 100 clip/SNR, 125 clip/WPM, 100 clip/kiểu gõ,
~167 clip/profile.

### 2.1 Theo profile

| Profile | DeepCW | E3 greedy | E3 beam+LM | Δ (E3 greedy − DeepCW) |
|---|---|---|---|---|
| en | 22.86 % | 27.89 % | 23.67 % | +5.03 |
| ru | 23.66 % | 27.49 % | 26.45 % | +3.83 |
| kk-cyrl-ru | 24.59 % | 23.97 % | 25.69 % | −0.62 |

DeepCW đều hơn ở `en`/`ru` dù phải chịu sàn từ vựng 1,2–5,6 %. Riêng `kk-cyrl-ru` E3 nhỉnh hơn một
chút, phần lớn vì sàn 3,1 % của DeepCW.

### 2.2 Theo kênh — **ô quan trọng nhất**

| Kênh | DeepCW | E3 greedy | E3 beam+LM | Δ (E3 greedy − DeepCW) |
|---|---|---|---|---|
| clean | 7.06 % | 17.87 % | 17.42 % | **+10.81** |
| mp3 | 11.72 % | 15.22 % | 14.90 % | +3.50 |
| qrn | 10.85 % | 18.43 % | 17.07 % | +7.57 |
| qsb | 47.00 % | 62.34 % | 60.55 % | **+15.33** |
| qrm | 41.86 % | 18.41 % | 16.40 % | −23.45 |

**clean** là bằng chứng mạnh nhất: không fading, không nhiễu xung, không MP3 — E3 vẫn kém 2,5× so
với DeepCW. Khoảng cách này *không thể* giải thích bằng "T1 quá khó".

**qsb** vẫn là ô tệ nhất với cả hai, nhưng DeepCW hơn 15 điểm. Fading 20 dB / chu kỳ 4 s là học
được, chứ không phải giới hạn vật lý — E3 chưa được dạy.

**qrm là điểm mạnh thật của MorseDesk, không phải điểm yếu của DeepCW cần "sửa".** Ô QRM của T1 là
một trạm Morse thứ hai lệch +300 Hz, tức **nằm trong cùng băng 400–1200 Hz** mà ví dụ dòng lệnh
của DeepCW nghe toàn bộ. Web app DeepCW để người dùng khoanh tần số trên phổ trước khi giải mã;
bản CLI không có bước đó, nên nó phiên cả hai trạm. Ví dụ thật:
`ref='TNX FER'` → `hyp='F4OE TQLWTS IGYM'`, CER 2.00 (chèn nhiều hơn cả độ dài tham chiếu).
Frontend của MorseDesk khóa vào một bin tone nên miễn nhiễm. Kết luận: con số qrm của DeepCW là
**tạo tác của cách đo**, không dùng để so năng lực model; ngược lại 18,4 % của E3 là một lợi thế
kiến trúc đáng giữ.

Thử bù lại bằng lọc dải quanh tone thật (oracle, biquad RBJ 4 lần y như `applyBandpassFilter` của
web app) — **thất bại, làm tệ hơn nhiều**:

| Lọc dải quanh tone | CER toàn bộ | qrm |
|---|---|---|
| không lọc (dùng cho mọi số ở trên) | 23.70 % | 41.86 % |
| rộng 300 Hz | 64.39 % | 59.80 % |
| rộng 150 Hz | 73.16 % | 66.11 % |

Lý do: model engine chuẩn hóa `log1p` **tuyệt đối**, không CMVN, nên nó trông chờ nền nhiễu tự
nhiên trải khắp 65 bin; bóp băng làm phổ đầu vào gần như rỗng và lệch hẳn thống kê huấn luyện.
Đúng như vậy, nhánh narrow của web app dùng **model riêng** (5 bin) kèm CMVN. Ghi lại như một
đối chứng âm; cờ `--bandpass` giữ trong script để tái lập.

### 2.3 Theo SNR

| SNR | DeepCW | E3 greedy | E3 beam+LM | Δ (E3 greedy − DeepCW) |
|---|---|---|---|---|
| 0 dB | **28.30 %** | 40.81 % | 39.47 % | **+12.52** |
| 3 dB | 24.66 % | 27.55 % | 26.88 % | +2.89 |
| 6 dB | 22.25 % | 24.23 % | 22.72 % | +1.98 |
| 10 dB | 24.56 % | 23.65 % | 21.73 % | −0.91 |
| 20 dB | 18.72 % | 16.02 % | 15.54 % | −2.70 |

Ở 0 dB DeepCW hơn 12,5 điểm → ô 0 dB của T1 **không** phải bất khả thi; E3 tụt nhanh hơn hẳn khi
SNR giảm. Ở 10–20 dB DeepCW lại hơi kém hơn E3 — hoàn toàn do ô qrm kéo xuống (không lọc băng thì
QRM không yếu đi theo SNR) cộng với sàn từ vựng 3,24 %.

### 2.4 Theo WPM

| WPM | DeepCW | E3 greedy | E3 beam+LM |
|---|---|---|---|
| 12 | 29.01 % | 29.45 % | 30.16 % |
| 18 | 26.12 % | 27.05 % | 25.63 % |
| 25 | **17.88 %** | 26.56 % | 24.17 % |
| 35 | 21.78 % | 22.76 % | 21.11 % |

Cả hai đều kém nhất ở 12 WPM. Với DeepCW lý do rõ: 12 WPM trong 5–8 s chỉ chứa vài ký tự, mà CER
tính trên chuỗi tham chiếu ngắn (trung bình 13,1 ký tự, trung vị 12) thì một lỗi nhỏ đã thành vài
phần trăm — xem 2.6.

### 2.5 Theo kiểu gõ

| Kiểu gõ | DeepCW | E3 greedy | E3 beam+LM |
|---|---|---|---|
| machine | 18.13 % | 23.69 % | 22.74 % |
| drift | 20.64 % | 24.37 % | 23.13 % |
| jitter | 23.98 % | 26.70 % | 25.73 % |
| bug | 24.35 % | 28.11 % | 26.38 % |
| farnsworth | 31.40 % | 29.40 % | 28.36 % |

Thứ tự khó giống nhau, trừ **farnsworth**: đó là kiểu gõ duy nhất DeepCW thua E3. Khoảng cách chữ
giãn bất thường (WPM ký tự 12–18 nhưng tốc độ chữ chậm hơn nửa) không có trong phân bố huấn luyện
của DeepCW, còn dự án sinh nó từ đầu.

### 2.6 Pivot SNR × WPM

DeepCW (greedy, resample_poly, không lọc băng):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   21.21   31.82   27.69   32.46
    3.0   30.10   27.15   19.32   22.09
    6.0   27.64   21.15   15.52   24.71
   10.0   34.75   27.97   18.59   16.93
   20.0   31.38   22.50    8.29   12.72
```

E3 greedy (để so, từ `runs/E3/t1_summary.json`):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   41.56   43.01   40.34   38.34
    3.0   30.90   30.78   25.76   22.77
    6.0   27.87   26.05   23.06   19.95
   10.0   28.52   22.35   22.12   21.62
   20.0   18.39   13.07   21.51   11.10
```

Pivot của DeepCW **gồ ghề** vì mỗi ô chỉ 25 clip và 5 trong số đó là QRM (CER có thể > 100 % do
chèn). Đừng đọc từng ô; đọc theo kênh (2.2) đáng tin hơn nhiều.

Ảnh hưởng của độ dài tham chiếu và khoảng trắng, đo trên chính kết quả DeepCW:

| Lát cắt | CER |
|---|---|
| toàn bộ | 23.70 % |
| bỏ hết khoảng trắng ở cả ref lẫn hyp | 22.99 % |
| tham chiếu ≤ 8 ký tự (n = 145) | 34.44 % |
| tham chiếu 9–15 ký tự (n = 190) | 18.83 % |
| tham chiếu 16–30 ký tự (n = 165) | 19.87 % |

Sai khoảng cách từ chỉ đóng góp ~0,7 điểm, không phải nguồn lỗi chính. Nhưng clip ngắn thì đắt gần
gấp đôi: T1 phạt nặng các clip 3–8 ký tự, đó là một khắt khe **thật** của bộ test (DeepCW tự công
bố 0 % CER ở 0…−4 dB trên bản benchmark riêng của họ với bản ghi dài, AWGN thuần, không QSB, không
QRM, tiếng Anh, và tốc độ/độ dài khác).

### 2.7 DeepCW trên các lát dễ — gate 2 % có đạt được không?

Cột "sàn từ vựng" là tỉ lệ ký tự tham chiếu mà 41 lớp của DeepCW không biểu diễn được trên đúng
lát đó (xem 1.4); trừ đi để ước lượng phần lỗi "thật" của model.

| Lát cắt | n | CER | sàn từ vựng | ước lượng sau khi trừ sàn |
|---|---|---|---|---|
| `clean`, SNR ≥ 10 dB, **profile `en`** | 14 | **1.02 %** | 0.00 % | **1.0 %** |
| `clean`, SNR ≥ 10 dB, mọi profile | 40 | 2.74 % | 1.33 % | ~1,4 % |
| `clean`, mọi SNR | 100 | 7.06 % | 2.91 % | ~4,2 % |
| `clean` + `mp3` + `qrn`, SNR ≥ 3 dB | 240 | 8.64 % | 3.81 % | ~4,8 % |
| toàn bộ T1 | 500 | 23.70 % | 3.24 % | ~20,5 % |

Đọc bảng này: **gate 2 % đạt được trên T1, nhưng chỉ ở lát `clean` + SNR cao + Latin.** Mở rộng
sang mọi SNR (gồm 0 dB) hoặc thêm `mp3`/`qrn` là đã lên ~8,6 %, và thêm `qsb` là lên 23,7 %. Gate
2 % tính trung bình trên **toàn** ma trận T1 hiện tại nằm ngoài tầm của cả model pretrain 15 MB.

## 3. MorseCodeToolkit (NeMo QuartzNet 10x5)

Chạy được, và kết quả là **85.84 % CER** — vô dụng trên T1.

| Mục | Giá trị |
|---|---|
| Repo | https://github.com/1-800-BAD-CODE/MorseCodeToolkit commit `b47fa0b1631c1eefa017ce715fa5274c2d9ec769` (2022-08-05) |
| Model | `pretrained/english/quartznet10x5.nemo`, `pretrained/russian/quartznet10x5.nemo` (Apache-2.0, kèm repo, không cần HF) |
| Môi trường | WSL Ubuntu 26.04, venv riêng `/root/mct/venv-mct`, `OMP_NUM_THREADS=8` |

Cài được sau 5 lần ghim phiên bản (NeMo 1.23 đụng hệ sinh thái mới):

| Vấn đề | Cách xử lý |
|---|---|
| `youtokentome==1.0.6` không build (thiếu Cython trong build deps) | cài `Cython<3` + `--no-build-isolation` |
| `pkg_resources` bị bỏ ở setuptools ≥ 81 | ghim `setuptools<81` |
| `HfFolder`/`ModelFilter` bị bỏ ở huggingface_hub ≥ 0.24 | ghim `huggingface_hub==0.20.3` |
| `transformers` 5.x cần hub mới | ghim `transformers==4.36.2`, `tokenizers<0.16` |
| `datasets` mới cần `huggingface_hub.errors` | ghim `datasets==2.16.1` |
| `np.sctypes` bị bỏ ở NumPy 2 | ghim `numpy<2` |

Phiên bản cuối: Python 3.10.21, `nemo_toolkit` 1.23.0, torch 2.14.0+cpu, pytorch-lightning 2.0.7,
numpy 1.26.4. **Bản cài đã được kiểm chứng đúng** bằng chính ví dụ trong README của họ:
`Wikipedia-Morse.ogg` → `WELCOME TO WIKIPEDIA, THE FREE ENCYCLOPEDIA THAT ANYONE CAN EDIT.`
(khớp từng ký tự). Nên 85,84 % là số thật, không phải lỗi cài.

Kết quả (model `english` cho profile `en`, model `russian` cho `ru` và `kk-cyrl-ru` vì `text` của
kk đã render sang Cyrillic nằm trọn trong bảng chữ Nga; 0,015 s/clip):

| Lát cắt | CER |
|---|---|
| tổng (n = 500) | 85.84 % (WER 99.23 %) |
| en / ru / kk-cyrl-ru | 81.66 % / 89.02 % / 86.84 % |
| clean / mp3 / qrn / qrm / qsb | 80.77 % / 80.51 % / 81.31 % / 91.13 % / 95.46 % |
| SNR 0 / 3 / 6 / 10 / 20 dB | 96.38 % / 90.41 % / 88.52 % / 86.57 % / 67.30 % |
| WPM 12 / 18 / 25 / 35 | 80.94 % / 80.21 % / 86.58 % / 95.62 % |

Nguyên nhân, đọc thẳng từ `model_config.yaml` của họ:

1. **Bảng nhãn không có chữ số**: `A`–`Z` `.` `?` `,` + khoảng trắng (30 lớp) cho tiếng Anh,
   `А`–`Я` `.` `?` `,` + khoảng trắng (36 lớp) cho tiếng Nga. T1 đầy số (`73`, `88`, `579`, hô
   hiệu) → 5,4–7,4 % ký tự tham chiếu nằm ngoài tầm ngay từ đầu.
2. **SNR huấn luyện 10–50 dB**. T1 chạy 0–20 dB; ô 0 dB cho 96,4 % CER.
3. **Dit 50–130 ms ⇒ 9–24 WPM**. T1 có 25 và 35 WPM nằm ngoài; đúng là 35 WPM cho 95,6 %.
4. Một kiểu gõ máy duy nhất, không bug/drift/jitter/farnsworth; không QSB, không QRM.

Kết luận: MorseCodeToolkit **không dùng được làm mốc cho T1**. Nó là bằng chứng phụ rằng model
Morse huấn luyện trên phân bố hẹp sụp hoàn toàn khi ra khỏi phân bố đó — đúng rủi ro mà E3 đang gặp
ở ô QSB.

## 4. Kết luận

**Khoảng cách của E3 chủ yếu do dữ liệu/huấn luyện, không phải do T1 quá khó.** Ba số quyết định:

1. Ở ô **clean** — không fading, không nhiễu xung, không nén — DeepCW đạt **7,06 %** còn E3
   **17,87 %**. Một bộ test "quá khắt khe" không thể làm một model kém 2,5× ở ô mà chính nó không
   hề khắt khe.
2. Trên `clean` + SNR ≥ 10 dB, profile `en`, DeepCW đạt **1,02 %** với sàn từ vựng 0 % — **gate
   2 % là đạt được trên T1**, chỉ là chưa đạt trên toàn ma trận. Gate không vô lý về nguyên tắc;
   vấn đề là E3 còn cách rất xa ngay cả ở lát dễ này.
3. Hai ô mà E3 kêu khó nhất đều **học được**: 0 dB (DeepCW 28,3 % vs E3 40,8 %) và QSB (47,0 % vs
   62,3 %).

Nhưng T1 **có** ba chỗ khắt khe thật, cần ghi nhận khi đọc con số gate:

- **QSB 20 dB / 4 s** làm cả model 15 MB pretrain tụt xuống 47 %. Gate 2 % tính trung bình trên
  toàn ma trận, trong đó 1/5 clip là QSB, gần như chắc chắn không ai đạt được.
- **Clip ngắn** (trung bình 13,1 ký tự): tham chiếu ≤ 8 ký tự cho CER gần gấp đôi tham chiếu dài.
- **QRM** không so sánh được với DeepCW vì bản CLI của họ không chọn băng.

### Khuyến nghị cho tuần 5–6

Theo thứ tự lợi ích/chi phí:

1. **Tăng cường QSB đúng bằng độ khó của T1, có trọng số.** Ô QSB là ~1/5 clip nhưng ~1/2 tổng
   lỗi của E3. Sinh fading depth tới 20 dB, chu kỳ 2–8 s (hiện tăng cường nhẹ hơn ô T1) và tăng tỉ
   lệ lấy mẫu QSB trong batch. Đây là thay đổi duy nhất có bằng chứng trực tiếp rằng 15 điểm đang
   nằm trên bàn.
2. **AGC / chuẩn hóa hai tầng ở frontend.** `morsedesk/constants.py` cho `FEAT_DIM = 11` với 1 kênh
   envelope AGC; với chu kỳ fade 4 s bằng đúng độ dài cửa sổ 4 s thì chuẩn hóa theo cửa sổ không
   cứu được. Cần tau 0,3–0,5 s, hoặc chuẩn hóa theo từng bin (CMVN theo mẫu như nhánh narrow của
   DeepCW) thay vì theo cửa sổ.
3. **Nhiễu thật thay AWGN tổng hợp**: https://github.com/e04/HamNoise (cùng tác giả DeepCW) cho
   nền nhiễu băng sóng ngắn thật. Kiểm giấy phép trước khi dùng dữ liệu đó để huấn luyện — nếu
   không tương thích, chỉ dùng để **đánh giá**, như DeepCW ở đây.
4. **Năng lực model.** ~200k tham số / 11 chiều đặc trưng thủ công so với ~3,7 M tham số / phổ 2-D
   65 bin. Khoảng cách ở ô `clean` (10,8 điểm) là khoảng cách năng lực + huấn luyện thuần túy, và
   E3 đã bão hòa ở TER 22 % sau bước 21500. Thử hidden 192 hoặc thêm một khối Conv 2-D trên phổ
   trước BiGRU; đây là bước tốn nhất nên làm sau (1) và (2).
5. **Giữ lợi thế QRM.** Tone-lock của MorseDesk hơn DeepCW 23 điểm ở ô QRM. Đừng đổi sang phổ toàn
   băng mà bỏ khóa tone.
6. **Định nghĩa lại gate theo tầng, đừng bỏ gate.** Số ở 2.7 cho thấy một ngưỡng 2 % duy nhất trên
   toàn ma trận T1 nằm ngoài tầm của cả model pretrain 15 MB, nên nó không phân biệt được tiến bộ.
   Đề xuất ba tầng, mỗi tầng kèm mốc DeepCW đo được ở đây làm chuẩn tham chiếu:

   | Tầng | Lát cắt | Ngưỡng đề xuất | DeepCW đo được |
   |---|---|---|---|
   | A (gate ra mắt) | `clean`, SNR ≥ 10 dB | ≤ 3 % | 2.74 % |
   | B (chất lượng) | `clean` + `mp3` + `qrn`, SNR ≥ 3 dB | ≤ 10 % | 8.64 % |
   | C (bền vững) | `qsb`, mọi SNR | ≤ 45 % | 47.00 % |

   Giữ `qrm` là chỉ số riêng (E3 đã 18,4 %, hơn DeepCW 23 điểm — báo cáo như điểm mạnh, không gộp
   vào gate). Ghi rõ CER của T1 bị khuếch đại bởi clip ngắn (2.6); cân nhắc thêm một lớp clip
   15–20 s cho tầng A để số so được với benchmark ngoài.

## 5. DeepCW làm engine của MorseDesk (tuần 5)

Từ tuần 5 DeepCW không còn chỉ là thước đo: lõi tiền xử lý nằm ở `morsedesk/model/deepcw.py` và
`Decoder(profile="en", engine="deepcw")` dùng nó cho profile `en` (bảng chữ của nó chỉ có Latin).

Tuần 5 nối thêm **beam ký tự CTC + LM ký tự `en` của dự án** lên hậu nghiệm DeepCW
(`morsedesk/model/deepcw_beam.py`). Bảng chữ của DeepCW là Latin nên LM áp thẳng, không phải đi
qua tầng mẫu chấm gạch như `morsedesk/lm/beam.py`.

| Cấu hình | n | CER T1 (chỉ profile `en`) | WER | s/clip | Realtime |
|---|---|---|---|---|---|
| greedy (mốc 2026-09-21) | 167 | 22,80 % | 47,70 % | 0,057 | x135,8 |
| beam ký tự + LM `en` (alpha 0,3, beta 0,5, beam 64) | 167 | **19,39 %** | **38,61 %** | 0,222 | x35,2 |

Theo kênh, chênh lệch dồn vào nơi tín hiệu còn đọc được:

| Kênh | greedy | beam + LM | Chênh |
|---|---|---|---|
| clean | 5,95 % | **2,76 %** | −3,19 |
| mp3 | 7,57 % | 6,09 % | −1,48 |
| qrn | 11,35 % | 9,65 % | −1,70 |
| qrm | 42,95 % | 35,42 % | −7,53 |
| qsb | 47,06 % | 43,85 % | −3,21 |

Quyết định: **giữ** beam+LM cho engine `deepcw` (`api.DEEPCW_LM = True`). Lấy 3,41 điểm CER và
9,09 điểm WER với giá gấp bốn thời gian, nhưng vẫn nhanh hơn thời gian thực 35 lần nên không ảnh
hưởng trải nghiệm. Đáng chú ý nhất là kênh `clean` xuống **2,76 %**, tức ngưỡng gate 2 % lần đầu
nằm trong tầm với ở một ô của ma trận. Lệnh tái lập ở
`docs/superpowers/plans/2026-09-22-week5-quality.md` Task 3.

## Giấy phép và phạm vi sử dụng

- **DeepCW / deepcw-engine — AGPL-3.0-only.** Dùng ở đây **chỉ để đo**. Không sao chép model,
  trọng số hay mã của họ vào repo; không phân phối; không tham chiếu trong sản phẩm.
  `tools/bench_pretrained.py` là mã viết mới theo *mô tả* tiền xử lý trong `model.onnx.json` và
  README của họ, nhận đường dẫn model từ tham số dòng lệnh.
- **MorseCodeToolkit — Apache-2.0.** Tương thích hơn, nhưng kết quả cho thấy không đáng dùng cho
  T1; cũng chỉ đo, không nhúng.
- **HamNoise** (gợi ý ở mục 4.3): phải kiểm giấy phép trước khi dùng dữ liệu để huấn luyện.
