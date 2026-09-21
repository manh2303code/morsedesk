# MorseDesk: thiết kế v1

Ngày: 2026-09-18. Trạng thái: đã duyệt qua brainstorming, chờ người dùng soát bản viết.
Nghiên cứu thị trường làm nền: `docs/research/01-nghien-cuu-thi-truong.md`.

## 1. Mục tiêu và phạm vi

MorseDesk là ứng dụng desktop Linux, chạy hoàn toàn offline trong môi trường air-gap, để:

1. **Giải mã** Morse từ file âm thanh (WAV, FLAC, OGG, MP3) và từ sound card thời gian thực thành văn bản tiếng Anh, tiếng Nga hoặc tiếng Kazakh, có sửa lỗi bằng mô hình ngôn ngữ và tự nhận diện ngôn ngữ bản tin.
2. **Tạo mã** từ văn bản ba ngôn ngữ thành chuỗi chấm gạch và file âm thanh.

Quyết định đã chốt:

| Hạng mục | Quyết định |
|---|---|
| "Dịch" | Chỉ giải mã và sửa lỗi trong ngôn ngữ gốc. Không dịch chéo ngôn ngữ, không diễn giải nội dung. |
| Hình thái | Ứng dụng desktop có GUI. |
| Stack | Python 3.11, PySide6, numpy, onnxruntime CPU, soundfile, sounddevice, pyqtgraph, pyctcdecode + kenlm. Huấn luyện bằng PyTorch chỉ trên máy dev. |
| Môi trường đích | Ubuntu/Debian LTS x86_64, CPU thường, không GPU, không mạng. |
| Đầu vào v1 | File âm thanh từng file một, và nghe trực tiếp từ sound card. |
| Tiếng Kazakh | Profile `kk-cyrl-ru`: người gõ dùng bảng Nga, phần mềm khôi phục 9 chữ riêng bằng LM. Không hỗ trợ bảng mở rộng hay bảng Latin trong v1. |
| Frontend | Giao diện đổi ngay lúc chạy giữa Kazakh, Nga, Anh. Ngôn ngữ bản tin tự nhận diện, người dùng có thể ép chọn. |
| License | Sản phẩm đóng nguồn. Chỉ nhúng thành phần Apache-2.0, MIT, BSD, LGPL (liên kết động). GPL chỉ gọi như tiến trình ngoài. Không dùng AGPL (loại DeepCW engine). |
| Tiêu chí v1 | CER < 2% với SNR ≥ 0 dB và 10 đến 35 WPM trên ma trận tổng hợp; CER < 2% trên ARRL W1AW 18 đến 40 WPM. |
| Nguồn lực | Một người + Claude, demo sau 6 tuần. |
| Tín hiệu | Một tín hiệu Morse chính mỗi file, có nhiễu nền. Nhiều tín hiệu cùng lúc chỉ cảnh báo, không tách. |
| Lõi giải mã | Hướng A: mạng CTC nhỏ theo kiến trúc cw-train, đầu ra là mẫu chấm gạch; hướng B (DSP thích nghi kiểu ggmorse) làm baseline và fallback. |

Ngoài phạm vi v1: xử lý hàng loạt thư mục, skimmer đa kênh, dịch máy, mô hình transformer sửa chính tả, bảng Kazakh mở rộng và bảng Latin, Windows/macOS, ARM.

## 2. Kiến trúc tổng thể

### 2.1 Dự án con và thứ tự

| # | Dự án con | Sản phẩm | Phụ thuộc |
|---|---|---|---|
| 1 | `core` | thư viện `morsedesk` (audio, dsp, model, lm, encode, api) và CLI | không |
| 2 | `data` | bộ sinh dữ liệu tổng hợp, bộ test thật, harness đo CER | 1 |
| 3 | `train` | script huấn luyện, xuất ONNX, kiểm tra parity | 2 |
| 4 | `lm` | 3 profile YAML, 3 LM n-gram, nhận diện ngôn ngữ | 1 |
| 5 | `app` | GUI PySide6 ba ngôn ngữ | 1, 4 |
| 6 | `dist` | AppImage, kiểm thử VM sạch | tất cả |

### 2.2 Repo

Một repo `morsedesk` tại `C:\Users\Admin\morsedesk`. Phát triển trên Windows (PySide6 và toàn bộ lõi chạy đa nền tảng), build và kiểm thử đóng gói trong Ubuntu 22.04 (WSL hoặc VM).

```
morsedesk/
  morsedesk/
    audio/        io.py (đọc file, resample), capture.py (sound card), playback.py
    dsp/          tone.py (dò và bám tone), frontend.py (đặc trưng), baseline.py (decoder DSP)
    model/        onnx_runner.py, chunker.py (cửa sổ trượt, gộp log-prob), vocab.py
    lm/           profile.py, ngram.py (bọc kenlm), beam.py (bọc pyctcdecode), langid.py
    encode/       timing.py, synth.py, text.py
    api.py        Decoder, Encoder, DecodeResult
    cli.py
  app/            main.py, windows/, widgets/, i18n/ (morsedesk_en.ts, _ru.ts, _kk.ts)
  profiles/       en.yaml, ru.yaml, kk-cyrl-ru.yaml
  models/         acoustic.onnx, acoustic.json, lm/en.bin, lm/ru.bin, lm/kk.bin
  tools/          gen_synth.py, build_lm.py, train.py, export_onnx.py, bench.py, make_t1.py
  tests/          unit/, regression/
  testdata/       public/ (được phép commit), private/ (gitignore)
  packaging/      pyinstaller.spec, appimage/, Dockerfile.build
  docs/           research/, superpowers/specs/
```

### 2.3 Luồng giải mã

```
nguồn: file (soundfile) hoặc sound card (sounddevice, khối 100 ms)
  → mono float32, resample 8 kHz, bỏ DC, chuẩn hóa mức
  → dsp.tone: STFT 256 điểm, hop 40 mẫu (200 khung/s); chọn đỉnh 300–1500 Hz;
    bám tone theo thời gian, cho phép trôi ≤ 2 Hz/s; báo "không có tín hiệu" khi
    tỉ số đỉnh/nền < 6 dB liên tục 3 s; cảnh báo nếu tồn tại đỉnh thứ hai ≥ nửa công suất đỉnh chính
  → dsp.frontend: trộn xuống băng gốc phức tại f0, lọc thấp 200 Hz, envelope |I+jQ|,
    AGC log (hằng số 1 s), đạo hàm envelope, 9 bin log-phổ quanh f0 (bước 31 Hz, ±125 Hz)
    → vector 11 chiều mỗi khung 5 ms
  → model.chunker: cửa sổ 4 s, bước 3 s (chồng 1 s); live: cửa sổ 2 s, bước 1 s, ngữ cảnh phải 0.5 s
  → model.onnx_runner: CNN×3 + BiGRU + linear → log-prob [T, 65]
  → lm.beam: pyctcdecode beam search (beam 64) trên lưới, ánh xạ mẫu→chữ theo profile,
    LM ký tự bậc 6 KenLM, từ điển miền có điểm thưởng
  → lm.langid: nếu profile = auto, chạy beam cho en, ru, kk trên cùng lưới,
    chọn điểm LM chuẩn hóa cao nhất theo từng đoạn
  → DecodeResult: text, words[{text, start_s, end_s, confidence}], wpm, tone_hz, snr_db,
    language, language_scores, warnings[]
```

### 2.4 Từ vựng đầu ra (65 lớp)

Mỗi mẫu chấm gạch là một lớp; mô hình không biết ngôn ngữ.

- 31 mẫu chữ: 26 mẫu Latin ITU cộng 5 mẫu chỉ có trong bảng Nga: `----` (Ш), `---.` (Ч), `..--` (Ю), `.-.-` (Я), `..-..` (Э).
- 10 mẫu số.
- 18 mẫu dấu câu ITU: `.` `,` `?` `'` `!` `/` `(` `)` `&` `:` `;` `=` `+` `-` `_` `"` `$` `@`.
- 3 prosign có mẫu riêng: SK `...-.-`, SOS `...---...`, lỗi `........`. AR, BT, KN, AS trùng mẫu với `+`, `=`, `(`, `&` nên hiển thị theo profile.
- `<space>` (cách từ), `<unk>` (mẫu không hợp lệ), `<blank>` CTC.

### 2.5 Profile ngôn ngữ

File YAML: `id`, `script`, `display_name`, `lm`, `map` (mẫu → danh sách chữ), `prosigns`, `lexicon_bonus`.

- `en`: mỗi mẫu → một chữ Latin; 5 mẫu Nga-riêng → `<unk>`.
- `ru`: 31 mẫu → 31 chữ Nga; Ё hiển thị là Е, Ъ hiển thị là Ь (LM quyết định Ь/Ъ qua ánh xạ một-nhiều `-..-` → [Ь, Ъ]).
- `kk-cyrl-ru`: như `ru` cộng ánh xạ một-nhiều: `.-` → [А, Ә], `--.` → [Г, Ғ], `-.-` → [К, Қ], `-.` → [Н, Ң], `---` → [О, Ө], `..-` → [У, Ұ, Ү], `....` → [Х, Һ], `..` → [И, І]. LM ký tự Kazakh chọn nhánh trong beam search.

### 2.6 Mô hình ngôn ngữ

- Loại: n-gram ký tự bậc 6, Kneser-Ney, xây bằng `lmplz` của KenLM lúc build, lưu nhị phân (`build_binary -q 8`), kích thước mục tiêu ≤ 50 MB mỗi ngôn ngữ.
- Corpus: en = Wikipedia tiếng Anh mẫu 200 MB + `michaellin/morse-translate-transcribe-100k`; ru = Wikipedia tiếng Nga mẫu 200 MB; kk = `kz-transformers/multidomain-kazakh-dataset` mẫu 200 MB + `kurumikz/Kazakh_news_corpus`. Văn bản chuẩn hóa: viết hoa, bỏ ký tự ngoài bảng mẫu, giữ số và dấu câu ITU.
- Từ điển miền: Q-code, viết tắt điện báo (CQ, DE, PSE, K, KN, 73, TU, RST, QTH...), điểm thưởng cố định trong beam search.
- Nhận diện ngôn ngữ: theo đoạn; đoạn tách bởi khoảng lặng ≥ 3 s hoặc tối đa 30 s. Điểm = log-prob LM chia số ký tự. Người dùng ép chọn thì áp cho cả file. Hiển thị ba điểm.

### 2.7 Mô hình âm thanh

- Kiến trúc: Conv1d(11→32, k5) → Conv1d(32→64, k5, stride 2) → Conv1d(64→64, k5) → BiGRU(64→96×2) → Linear(192→65). Khoảng 300 nghìn tham số. Sau stride 2 còn 100 khung/s.
- Xuất ONNX opset 17, input `features [1, T, 11]`, output `log_probs [1, T/2, 65]`. Metadata JSON kèm: sample_rate, hop, vocab, phiên bản.
- Parity: file golden gồm 20 đặc trưng đầu vào và log-prob PyTorch; onnxruntime phải khớp sai số tuyệt đối ≤ 1e-4.
- Fallback: nếu tin cậy trung bình cả đoạn < 0.5, chạy `dsp.baseline` (port thuật toán ggmorse: tối ưu cặp tốc độ và ngưỡng trên các khoảng bật tắt rồi tra bảng) và hiển thị kết quả cạnh nhau kèm cảnh báo.

### 2.8 Độ tin cậy

Tin cậy từng ký tự = xác suất hậu nghiệm lớn nhất tại các khung mà beam gán cho ký tự đó. Tin cậy từng từ = trung bình hình học của ký tự trong từ. Ngưỡng hiển thị: ≥ 0.8 bình thường, 0.6 đến 0.8 vàng, < 0.6 đỏ.

## 3. Tạo mã

- `encode.text`: chuẩn hóa theo profile; ký tự ngoài bảng gây lỗi `UnsupportedCharacter` liệt kê vị trí; tùy chọn `strict=False` để bỏ qua.
- `encode.timing`: chuẩn PARIS, dit = 1200/WPM ms; dash 3 dit; khoảng trong chữ 1, giữa chữ 3, giữa từ 7. Farnsworth theo phương pháp ARRL: tốc độ ký tự `char_wpm`, kéo dài khoảng giữa chữ và từ để đạt `effective_wpm`. Tham số `weight` (tỉ lệ dash/dot, mặc định 3.0). Tham số chỉ dùng cho sinh dữ liệu: `jitter`, `swing`, `drift`.
- `encode.synth`: sine tại `tone_hz` (mặc định 700), sườn raised-cosine 5 ms, sample rate 8000/16000/44100, tùy chọn nhiễu trắng theo SNR và QSB.
- Xuất: WAV, FLAC, OGG qua soundfile. MP3: nếu libsndfile đóng gói có lame thì ghi trực tiếp, nếu không và có `ffmpeg` trong PATH thì gọi tiến trình ngoài, nếu không thì báo "không hỗ trợ MP3 trên máy này". Kiểm tra khả năng này lúc khởi động và hiển thị trong Cài đặt.
- Xuất chữ: chấm gạch, cách chữ một khoảng trắng, cách từ ` / `.

## 4. GUI

PySide6, một `QMainWindow` với `QStackedWidget` ba trang.

**Giải mã**
- Nguồn: file (hộp thoại, kéo thả) hoặc thiết bị thu (combo liệt kê từ sounddevice).
- Waterfall phổ 0 đến 2 kHz bằng pyqtgraph, vạch tone đang bám.
- Ô văn bản kết quả, từ tô màu theo tin cậy, tooltip hiện tin cậy và thời điểm.
- Combo ngôn ngữ bản tin: Tự động, Anh, Nga, Kazakh. Nhãn hiển thị ba điểm nhận diện.
- Chỉ số: WPM, tone Hz, SNR dB, tiến trình file, đếm khối bị bỏ khi live.
- Nút xuất TXT và JSON (DecodeResult).
- Live: callback sounddevice đẩy khối 100 ms vào `queue.Queue`; `DecoderWorker(QThread)` gọi `Decoder.stream()`; signal `words_ready`, `stats`, `warning`.

**Tạo mã**
- Ô nhập văn bản; bảng bấm ký tự Cyrillic và 9 chữ Kazakh.
- Profile, WPM, Farnsworth WPM, weight, tone, SNR nhiễu (tùy chọn), định dạng.
- Nghe thử qua sounddevice OutputStream, lưu file, hiển thị chuỗi chấm gạch.

**Cài đặt**
- Ngôn ngữ giao diện: Kazakh, Nga, Anh; đổi ngay bằng cách gỡ và cài `QTranslator` mới rồi phát `LanguageChange`, mọi cửa sổ cài đặt lại chuỗi trong `changeEvent`.
- Profile mặc định, thiết bị thu và phát mặc định, thư mục xuất, bật/tắt fallback DSP.
- Lưu bằng `QSettings` vào thư mục người dùng.

**i18n**
- Mọi chuỗi qua `self.tr()`. Nguồn `app/i18n/morsedesk_{en,ru,kk}.ts`, biên dịch `.qm` bằng `pyside6-lrelease` lúc build. Ngôn ngữ mặc định lấy theo locale hệ thống, nếu không khớp thì Anh.
- Font: đóng gói DejaVu Sans và Noto Sans, đặt làm font ứng dụng để chắc chắn hiện Ә Ғ Қ Ң Ө Ұ Ү Һ І.
- Bản dịch Kazakh do người bản ngữ soát trước khi phát hành; đến khi đó gắn nhãn "bản nháp" trong Cài đặt.

**Ghi chú tuần 4 (2026-09-21):** GUI nằm trong gói `morsedesk/app/` (không phải `app/` ở gốc) để wheel/PyInstaller đóng gói; hai tab Giải mã | Tạo mã bằng `QTabWidget` (tab Cài đặt thêm ở tuần 5, hiện chỉ có combo ngôn ngữ giao diện trên thanh công cụ); spectrogram tĩnh của file (waterfall live để tuần 5); nghe thử dùng `sounddevice.play` không chặn qua lớp `Player` thay `EncoderWorker(QThread)`; thiếu model/LM → hộp thoại rồi thoát mã 2 (đúng §7). Chi tiết và danh sách lệch: `docs/superpowers/specs/2026-09-21-morsedesk-week4-gui-design.md` mục 5.

## 5. Dữ liệu và huấn luyện

### 5.1 Bộ sinh tổng hợp (`tools/gen_synth.py`)

Sinh on-the-fly theo seed, mỗi mẫu là clip 4 đến 12 s.

| Thành phần | Phân bố |
|---|---|
| Văn bản | trộn đều en/ru/kk từ corpus LM, cộng bản tin ham radio và radiogram giả lập; 10% chuỗi ngẫu nhiên chữ số dấu câu |
| WPM | log-đều 5 đến 60 |
| Farnsworth | 50% mẫu dưới 18 WPM, effective 5 đến 13 |
| Weight | đều 2.0 đến 4.5 |
| Jitter phần tử | Gaussian, độ lệch 3 đến 20% độ dài phần tử |
| Kiểu bug | 20% mẫu: dit đều, dah lệch 10 đến 30% |
| Trôi tốc độ | tuyến tính hoặc ngẫu nhiên tới ±15% trong clip |
| Lỗi khoảng cách | 5% khoảng giữa chữ rút còn 1.5 dit hoặc kéo tới 5 dit |
| Tone | 400 đến 1200 Hz, trôi ≤ 2 Hz/s |
| Nhiễu | AWGN, SNR đều -6 đến +25 dB (đo trong băng 500 Hz quanh tone) |
| QSB | 40% mẫu, chu kỳ 2 đến 20 s, sâu tới 30 dB |
| QRM | 25% mẫu: tone thứ hai cách 150 đến 600 Hz, là Morse khác hoặc sóng mang, mức thấp hơn 3 đến 20 dB |
| QRN | 20% mẫu: xung ngẫu nhiên 5 đến 50 mỗi giây |
| Băng thông | lọc 300 đến 3000 Hz |
| Mức | ngẫu nhiên, 5% clipping nhẹ, 20% DC offset |
| Codec | 30% mẫu qua MP3 48 đến 128 kbps bằng ffmpeg gọi ngoài lúc sinh |
| Nhãn | chuỗi lớp từ vựng 2.4 kèm dấu cách từ |

### 5.2 Huấn luyện (`tools/train.py`)

PyTorch CPU hoặc GPU nếu có trên máy dev; CTC loss; AdamW lr 1e-3, 50 epoch × 20 nghìn clip sinh mới; chọn checkpoint theo CER trên tập validation cố định seed. Xuất ONNX và chạy kiểm tra parity.

### 5.3 Đánh giá

CER và WER theo ô SNR × WPM × kiểu gõ × kênh, in bảng và lưu JSON để so giữa các phiên bản.

## 6. Bộ test

| Tầng | Nội dung | Ngưỡng |
|---|---|---|
| T0 unit | timing encoder chính xác từng mẫu; encode→decode trên audio sạch 10 đến 40 WPM cho cả ba profile | CER = 0 |
| T1 ma trận tổng hợp, seed cố định, 5 clip mỗi ô | SNR {-6, -3, 0, 3, 6, 10, 20} × WPM {5, 8, 12, 18, 25, 35, 45, 60} × gõ {máy, Farnsworth, jitter, bug, trôi} × kênh {sạch, QSB, QRM, QRN, MP3} | ô SNR ≥ 0 và WPM 10 đến 35: CER < 2%, là regression gate trong pytest |
| T2 bản ghi thật | ARRL W1AW MP3 + text 11 tốc độ (bản quyền ARRL, chỉ dùng nội bộ, để trong `testdata/private`); Wikimedia Commons; SRAA tag CW (CC BY-NC, tự chép đáp án 5 file); kho QSO Ý có WPM và loại khóa, tự chép 20 clip; tiếng Nga và Kazakh: tự thu người gõ thật và tạo bằng ebook2cw gọi ngoài | ARRL 18 đến 40 WPM: CER < 2%; QSO tay: CER < 10%, chỉ theo dõi |
| T3 live | phát file qua thiết bị loopback (PulseAudio/PipeWire null sink), so kết quả live với kết quả file | lệch CER < 1 điểm |
| Baseline | tuần 1 đo ggmorse, pycw, multimon-ng, DeepCW engine (chỉ đo, không nhúng) trên T2 | ghi số đối chứng |

## 7. Xử lý lỗi

| Tình huống | Hành vi |
|---|---|
| File không đọc được hoặc định dạng lạ | thông báo kèm danh sách định dạng hỗ trợ |
| Sample rate hoặc số kênh bất kỳ | resample và trộn mono tự động |
| Không dò được tone | kết quả rỗng, cảnh báo "không có tín hiệu", không bịa chữ |
| Tone thứ hai đáng kể | cảnh báo "đang bám tone mạnh nhất tại X Hz" |
| Model hoặc LM thiếu, hỏng, sai phiên bản | fail ngay lúc khởi động, hộp thoại nêu đường dẫn |
| Thiết bị thu bận hoặc mất | liệt kê lại thiết bị, nút thử lại |
| Tràn buffer live | bỏ khối, tăng bộ đếm hiển thị |
| Tin cậy thấp | tô đỏ, hiển thị fallback DSP nếu bật |
| File dài hơn 1 giờ | xử lý streaming, thanh tiến trình, nút hủy |
| Mọi ngoại lệ | ghi log xoay vòng tại `~/.local/share/morsedesk/logs/` |

## 8. CLI

```
morsedesk decode FILE [--profile auto|en|ru|kk-cyrl-ru] [--json] [--no-fallback]
morsedesk encode "TEXT" --profile ru --wpm 20 [--farnsworth 10] [--tone 700] [--snr 10] --out x.wav
morsedesk devices
morsedesk bench --set t1|t2 [--model models/acoustic.onnx]
```

## 9. Đóng gói

- Build trong container Ubuntu 22.04 (`packaging/Dockerfile.build`, glibc 2.35) để chạy trên 22.04 và 24.04.
- PyInstaller 6 onedir → AppImage bằng appimagetool. AppRun đặt `QT_QPA_PLATFORM_PLUGIN_PATH` và `QT_PLUGIN_PATH`.
- Gói kèm: Python 3.11, PySide6 với plugin xcb và platformthemes, numpy, onnxruntime, soundfile với libsndfile 1.2.2, sounddevice cộng `libportaudio2.so` copy từ hệ thống build, pyctcdecode, kenlm biên dịch trên máy build, pyqtgraph, `models/`, `profiles/`, `.qm`, font.
- Kích thước mục tiêu < 400 MB. Không có lời gọi mạng; kiểm bằng `strace -f -e trace=network` trên VM sạch.
- Kèm `SHA256SUMS` và hướng dẫn cài bằng USB.
- `.deb` là tùy chọn nếu còn thời gian tuần 6.

## 10. Lộ trình 6 tuần

| Tuần | Mốc | Bằng chứng hoàn thành |
|---|---|---|
| 1 | Khung repo, 3 profile, encoder + T0, đọc audio, DSP front-end và tone, baseline DSP, CLI decode/encode; gom T2; đo baseline các công cụ sẵn có | `morsedesk encode` và `decode` chạy trên file sạch; bảng số baseline |
| 2 | Bộ sinh đầy đủ, T1, train, model đầu tiên, ONNX + parity, bench | CER trên T1 in ra được |
| 3 | 3 LM, pyctcdecode, ánh xạ một-nhiều Kazakh, langid, lặp cải thiện | T1 đạt ngưỡng, T2 ARRL đo được |
| 4 | GUI giải mã file, waterfall, tin cậy, khung i18n, trang tạo mã | demo GUI với file |
| 5 | Live, cài đặt, bản dịch đầy đủ, xử lý lỗi, AppImage đầu tiên | T3 chạy; AppImage khởi động trên VM |
| 6 | Tinh chỉnh bản ghi thật, chốt gate, VM offline, tài liệu, demo; dự phòng | tất cả gate xanh; demo |

## 11. Rủi ro và cách giảm

| Rủi ro | Giảm thiểu |
|---|---|
| Tay gõ thật lệch hơn mô phỏng, CER vượt ngưỡng | mở rộng tăng cường; thu thêm clip thật; nới mô hình tới 1 triệu tham số |
| Bản dịch Kazakh không có người soát | gắn nhãn nháp; giao diện vẫn đầy đủ tiếng Nga và Anh |
| kenlm không biên dịch được trên máy build | dự phòng: viết bộ chấm ARPA n-gram thuần Python cho LM ≤ 50 MB |
| MP3 ghi không có lame | fallback ffmpeg ngoài, thông báo rõ |
| PortAudio trên máy đích | đóng gói `.so` kèm; kiểm trên VM sạch |
| ARRL có bản quyền | chỉ trong `testdata/private`, không phát hành |
| Live mode ăn thời gian tuần 6 | live là mục cuối tuần 5; nếu trượt, demo bằng file và loopback |

## 12. Nguồn tái dụng và license

| Thành phần | Dùng thế nào | License |
|---|---|---|
| cw-train / pycw (bigsk05) | học kiến trúc, bộ tăng cường, quy trình parity; viết lại trong repo | Apache-2.0 |
| ggmorse (ggerganov) | port thuật toán baseline sang Python | MIT |
| MorseCodeToolkit | định dạng YAML bảng chữ, ý tưởng sinh dữ liệu | Apache-2.0 |
| pyctcdecode, kenlm | beam search + LM | Apache-2.0, LGPL (liên kết động) |
| onnxruntime, numpy, soundfile, sounddevice, pyqtgraph, PySide6 | runtime | MIT, BSD, BSD, MIT, MIT, LGPL |
| ebook2cw, ffmpeg, multimon-ng, DeepCW engine | chỉ gọi ngoài hoặc chỉ đo, không nhúng | GPL, LGPL/GPL, GPL, AGPL |
