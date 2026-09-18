# Nghiên cứu thị trường: phần mềm giải mã / tạo mã Morse từ âm thanh (Anh, Nga, Kazakh) cho Linux air-gap

Ngày lập: 2026-09-18. Phạm vi: sản phẩm thương mại, mã nguồn mở, mô hình học máy có sẵn, thư viện tạo mã, chuẩn bảng chữ Nga/Kazakh, dữ liệu huấn luyện, và khuyến nghị kiến trúc.

Yêu cầu đích của dự án:

| # | Yêu cầu | Ghi chú |
|---|---------|---------|
| R1 | Input là file âm thanh (WAV, MP3, ...) | không chỉ mic/sound-card thời gian thực |
| R2 | Ngôn ngữ: tiếng Anh, tiếng Nga, tiếng Kazakh | bảng Latin + bảng Cyrillic Nga + 9 chữ Kazakh |
| R3 | Output là văn bản "có nghĩa" | cần sửa lỗi / khôi phục theo ngữ cảnh, không chỉ tra bảng |
| R4 | Linux, air-gap, offline hoàn toàn | không tải model, không gọi API |
| R5 | Cả hai chiều: giải mã (audio → text) và tạo mã (text → Morse/audio) | |

---

## 1. Kết luận điều hành

1. **Không có sản phẩm nào trên thị trường đáp ứng đồng thời R1–R4.** Mọi bộ giải mã tìm được đều chỉ hỗ trợ bảng Latin, trừ CwGet (Windows) có bảng tiếng Nga tích hợp và MorseCodeToolkit (mã nguồn mở) có model tiếng Nga.
2. **Không tồn tại chuẩn Morse công khai cho 9 chữ riêng của tiếng Kazakh** (Ә Ғ Қ Ң Ө Ұ Ү Һ І). Đã tra Wikipedia tiếng Anh, Nga, Kazakh và tìm kiếm bằng ba ngôn ngữ. Giới radio nghiệp dư Kazakhstan dùng bảng Nga. Dự án phải tự định nghĩa hồ sơ bảng chữ Kazakh (xem mục 5) và coi đây là quyết định thiết kế cần chốt với bên yêu cầu.
3. **Có 3 mô hình nhẹ mã nguồn mở đáng tái dụng**, tất cả chỉ tiếng Anh trừ một:
   - `pycw` / `cw-train` (Apache-2.0, 2026): CNN×3 + BiGRU, ~95 nghìn tham số, 374 KB, chạy numpy thuần, train lại 4 phút trên CPU. Ứng viên số 1 để làm nền train lại đa ngôn ngữ.
   - `MorseCodeToolkit` (Apache-2.0, 2022): NeMo QuartzNet 10x5, có sẵn model **tiếng Anh và tiếng Nga**, bảng chữ khai báo bằng YAML nên thêm Kazakh dễ. Nhược điểm: phụ thuộc NeMo cũ.
   - `DeepCW` / `deepcw-engine` (AGPL-3.0, 2026): ONNX 15 MB, độ chính xác tốt nhất hiện có (0% CER tới -4 dB SNR, dưới 1.5% ở -8 dB). Chỉ Latin, không có mã huấn luyện, license AGPL cần cân nhắc nếu phần mềm đóng.
4. **Yêu cầu "có nghĩa" (R3) chưa có giải pháp sẵn cho tiếng Nga/Kazakh.** Cách làm chuẩn ngành là CTC beam search kết hợp mô hình ngôn ngữ n-gram (KenLM) chạy CPU, cộng thêm mô hình sửa chính tả nhỏ. Có sẵn mô hình cho tiếng Nga (sage-fredt5-distilled-95m, rubert-tiny2) và tiếng Kazakh (kaz-roberta-conversational) cùng corpus để tự dựng n-gram.
5. **Khuyến nghị:** tự phát triển, tái dụng thành phần mở (Apache/MIT), theo kiến trúc 4 tầng: DSP front-end → mô hình CTC nhỏ đa bảng chữ huấn luyện bằng dữ liệu tổng hợp → giải mã theo hồ sơ ngôn ngữ → hậu xử lý bằng LM. Chi tiết mục 8.

---

## 2. Bộ giải mã có trên thị trường (audio → text)

### 2.1 Thương mại / đóng

| Sản phẩm | Nền tảng | Input file? | Thuật toán | Bảng chữ | Giá / license | Đánh giá cho dự án |
|---|---|---|---|---|---|---|
| CW Skimmer (VE3NEA, dxatlas.com) | Windows (chạy được qua Wine/Docker) | Có, qua sound card ảo | Bayesian, đa kênh | Latin | Shareware, trả phí | Chuẩn tham chiếu về độ nhạy; không Linux native, không Cyrillic |
| MRP40 (polar-electric.com) | Windows | Sound card | DSP | Latin | Trả phí | Không phù hợp |
| CwGet (DXsoft, Nga) | Windows, Android | Sound card | DSP, đa kênh | **Anh, Nga, Thụy Điển, tự định nghĩa** | Shareware | Sản phẩm duy nhất có sẵn bảng tiếng Nga; không Linux, không Kazakh |
| Morse Expert (VE3NEA) | Android | Mic / cáp audio | Thuật toán của CW Skimmer | Latin | Miễn phí | Tham khảo thôi |
| GGMorse app (G. Gerganov) | iOS, Android, web | Mic | DSP (ggmorse) | Latin | Miễn phí | Thư viện nền là mã nguồn mở, xem 2.2 |

### 2.2 Mã nguồn mở chạy Linux, thuật toán DSP cổ điển

| Dự án | Ngôn ngữ / license | Input file? | Cách hoạt động | Bảng chữ | Cập nhật | Đánh giá |
|---|---|---|---|---|---|---|
| **ggmorse** (github.com/ggerganov/ggmorse) | C++, MIT, 309 sao | Thiết kế cho mic thời gian thực; API nhận buffer nên nạp file được | STFT dò tần số 0.2–1.2 kHz, lọc Goertzel, tối ưu cặp (tốc độ, ngưỡng) 5–55 WPM | 53 ký tự Latin, số, dấu câu; **không Cyrillic** | 08/2026 | Baseline DSP tốt nhất, nhẹ, dễ nhúng; bảng chữ hard-code trong `ggmorse.cpp` nên thêm Cyrillic phải sửa nguồn |
| fldigi | C++, GPL | Có (playback file audio) | Giải điều chế biên độ + ngưỡng tự động, SOM fuzzy | Latin | Đang bảo trì | GUI ham radio, giải mã CW được đánh giá yếu; không Cyrillic |
| multimon-ng | C, GPL | Có: `multimon-ng -a MORSE_CW -t wav file.wav` | DSP đơn giản | Latin | Đang bảo trì | Tiện để so sánh, chất lượng thấp |
| SDRangel plugin Morse decoder | C++, GPL | Từ luồng SDR | Dùng ggmorse | Latin | Đang bảo trì | Không cần |
| csdr-skimmer (luarvique) | C++, GPL-3 | I/Q, audio | CW + RTTY skimmer | Latin | Đang phát triển | Hướng SDR, không cần |
| RSCW (PA3FWM) | C, Linux | Sound card | Tối ưu cho tín hiệu yếu nhưng **chỉ timing máy hoàn hảo** | Latin | Cũ | Không phù hợp tín hiệu tay |
| xdemorse, morse2txt | C/GTK | Sound card | DSP | Latin | Cũ | Không phù hợp |
| unixcw (`cw`, `xcwcp`, `cwgen`) | C, GPL | Tạo mã + luyện tập | | ASCII | Debian package | Chỉ dùng cho tạo mã / kiểm thử |
| morse-audio-decoder (PyPI, mkouhia) | Python, MIT | WAV | RMS envelope + ngưỡng + KMeans tách dot/dash | Latin | 2022 | Mẫu tham khảo cách làm DSP trong Python |
| cwt (gagregrog) | TypeScript, MIT | WAV, MP3, M4A, FLAC, OGG | Quadrature demod + boxcar filter, tự dò tần số/WPM | Latin | Đang phát triển | Trình duyệt, offline được, chỉ Latin |

### 2.3 Mã nguồn mở dùng học máy / học sâu

| Dự án | Mô hình | Kích thước | Runtime | Dữ liệu train | Kết quả công bố | Bảng chữ | License | Cập nhật |
|---|---|---|---|---|---|---|---|---|
| **DeepCW** web (e04/web-deep-cw-decoder) + **deepcw-engine** | Mạng nơ-ron trên spectrogram log1p, CTC 42 lớp | ONNX **15.1 MB** | ONNX Runtime; ví dụ Python và Node.js; audio 3200 Hz mono, FFT 256, hop 48, băng 400–1200 Hz | Tổng hợp, tham số không công bố; không có mã train | CER 0% từ 0 đến -4 dB, <1.5% ở -8 dB, <8% ở -10 dB (chế độ high); vượt CW Skimmer, fldigi, ggmorse trên bản ghi thật | A–Z, 0–9, `, . / ?`, space; **không Cyrillic** | engine: **AGPL-3.0-only**; web app: không ghi | 08/2026 |
| **pycw** (PyPI 1.1.0) + **cw-train** + **gocw** (bigsk05) | CNN×3 + BiGRU + head, **~95k tham số**; đặc trưng: down-conversion phức, I/Q envelope, AGC log, 200 frame/s | **374 KB** (`model.bin`) | numpy thuần; Go runtime riêng; PyTorch chỉ để train | Tổng hợp: 12–30 WPM, SNR -12…+22 dB, tone 500–1100 Hz, QSB, jitter tay 3–18%, QRM, xung nhiễu; train ~4 phút CPU | CER 0.02–0.05 ở -8…+12 dB | Latin, số, prosign | **Apache-2.0** | 09/2026 |
| **MorseCodeToolkit** (1-800-BAD-CODE) + HF `morsecode_en_quartznet_10x5` | NeMo QuartzNet 10x5, CTC | `.nemo` **4.5 MB** | NeMo (PyTorch) | Bộ sinh tổng hợp riêng: dit 75 ms ± 5 ms, tone tùy chọn, SNR tùy chọn, trộn nhiễu nền (LibriSpeech), 8/16 kHz | ~1% WER trên dữ liệu tổng hợp | **international.yaml và russian.yaml**; có sẵn `pretrained/english` và `pretrained/russian`; thêm bảng mới bằng YAML | **Apache-2.0** | 08/2022 (NeMo cũ) |
| whisper-small-morse (HF michaellin) | Whisper-small fine-tune 15 epoch | **967 MB** | transformers | 100k mẫu tổng hợp từ dataset text `morse-translate-transcribe-100k` (Claude sinh), tone/nhiễu/WPM ngẫu nhiên | Không công bố số | Latin; có task "translation" (diễn giải ý nghĩa bản tin ham radio) | Apache-2.0 | 05/2026 |
| MorseAngel (f4exb) | 2 LSTM + Dense, phân loại phần tử | Nhỏ | PyTorch + PyQt5, Linux | Tự sinh | "có dấu hiệu hoạt động, còn cải thiện" | Latin ≤ 5 phần tử | MIT | 02/2021, ngừng |
| deepmorse-decoder, LSTM_morse (AG1LE) | CNN-LSTM-CTC trên khung spectrogram 128×32 | Nhỏ | TensorFlow | 27.8 h audio ARRL | CER 1.5%, word acc 97.2% | Latin | GPL-3 | 12/2022 |
| MorseNet (netom) | LSTM + CTC trên raw audio | | TensorFlow | Tổng hợp | Nghiên cứu | Latin | | Cũ |
| Kaggle Morse Learning Machine v1/v2 | Cuộc thi | | | WAV 8 kHz float32, SNR -14…+20 dB, 12–80 WPM, A–Z 0–9 `. ? /` | | Latin | | 2014–2015 |
| Bài báo: MorseNet (phát hiện + CRNN trên spectrogram), YFDM (YOLO), 3DCNN-BiConvLSTM-CTC, Noise Adaption Network (arXiv 2410.19180) | | | | | | | | 2018–2024 |
| LLM fine-tune trên HF: Gemma-3-1b morse (GGUF), Mistral-7B morse, Qwen3-32B morse (04/2026), Morsent-128 GPT-2 (en, ru) | Text ↔ Morse bằng LLM | 1–32B | | | Thí nghiệm | | | |

Nhận xét:

- Toàn bộ mô hình học sâu có sẵn chỉ nhận **tiếng Anh**, trừ QuartzNet tiếng Nga của MorseCodeToolkit.
- Không có bất kỳ dataset audio Morse tiếng Nga hay Kazakh công khai. Mọi dự án đều huấn luyện bằng dữ liệu tổng hợp, và các bộ sinh dữ liệu (cw-train, MorseCodeToolkit, ebook2cw) đều mở nguồn nên tái dụng được.
- Kích thước mô hình hiệu quả nằm trong khoảng 0.4–15 MB; CPU là đủ. Whisper-size là quá mức cho bài toán.

---

## 3. Công cụ tạo mã (text → Morse / audio)

| Công cụ | Nền tảng / license | Bảng chữ | Output | Tham số đáng chú ý |
|---|---|---|---|---|
| **ebook2cw** 0.8.5 (fkurz.net, DJ1YFK) | Linux/FreeBSD/Win, GPLv2, có gói Debian | UTF-8: **Latin, Cyrillic, Greek, Hebrew, Arabic** (`-u`) | MP3, OGG | WPM `-w`, Farnsworth `-e`, tone `-f`, dạng sóng `-T`, QRQ `-Q`, **mô phỏng nhiễu** `-N` (SNR -10…10), băng thông `-B`, prosign `<AR>` |
| unixcw `cw`, `cwgen` | Linux, GPL | ASCII | Loa / file | WPM, tone, weight |
| pycw encode | Python, Apache-2.0 | Latin | WAV | WPM, Hz, sample rate |
| MorseCodeToolkit generator | Python, Apache-2.0 | YAML bất kỳ (có Nga) | WAV | dit ± sigma, tone, SNR, nhiễu nền |
| cw-train generator | Python, Apache-2.0 | Latin | Tensor / WAV | QSB, jitter, QRM, impulse |
| morsify (JS/Rust/Ruby) | MIT | Latin, Latin mở rộng, Cyrillic, Hy Lạp, Do Thái, Ả Rập, Ba Tư, Nhật, Hàn, Thái; **không Kazakh** | Web Audio | oscillator, tần số, tốc độ |
| MorseCodePy 4.2.1 (PyPI) | Python ≥ 3.11, MIT | en, ru, uk, es, fr; không Kazakh | Chỉ text | |
| morse-talk (PyPI) | Python | Latin | Text | |

Kết luận: tạo mã tiếng Anh và Nga có sẵn công cụ; tiếng Kazakh phải tự viết bảng. Phần tạo mã đơn giản, nên tự triển khai trong cùng codebase để dùng chung bảng chữ với bộ giải mã và bộ sinh dữ liệu huấn luyện.

---

## 4. Bảng chữ tiếng Nga (đã chuẩn hóa)

- Bảng Nga được thông qua năm 1856, nguyên tắc: chữ Cyrillic lấy mã của chữ Latin đồng âm (Л→L, В→W, Ж→V, Щ→Q, Ь→X, Ы→Y). Quan hệ này sau thành cơ sở của КОИ-7/КОИ-8 và МТК-2.
- Bảng hiện hành: 31 chữ + 10 số. **Ё** dùng mã của Е. **Ъ** dùng mã của Ь (`-..-`); mã cũ của Ъ là `--.--` (trùng Ñ), nay bỏ.
- Chuẩn quốc tế tham chiếu: ITU-R M.1677-1 (10/2009), 27 chữ Latin (có Ę), 10 số, 20 dấu/ký hiệu dịch vụ. Chữ có dấu khác và mọi bảng phi Latin **không nằm trong ITU**.

| Chữ | Mã | Chữ | Mã | Chữ | Mã |
|---|---|---|---|---|---|
| А | `.-` | Л | `.-..` | Ц | `-.-.` |
| Б | `-...` | М | `--` | Ч | `---.` |
| В | `.--` | Н | `-.` | Ш | `----` |
| Г | `--.` | О | `---` | Щ | `--.-` |
| Д | `-..` | П | `.--.` | Ъ | `-..-` (= Ь; cũ `--.--`) |
| Е / Ё | `.` | Р | `.-.` | Ы | `-.--` |
| Ж | `...-` | С | `...` | Ь | `-..-` |
| З | `--..` | Т | `-` | Э | `..-..` |
| И | `..` | У | `..-` | Ю | `..--` |
| Й | `.---` | Ф | `..-.` | Я | `.-.-` |
| К | `-.-` | Х | `....` | | |

Lưu ý quan trọng cho thiết kế: bảng Nga đã **chiếm hết 16 mã 4 phần tử** và chiếm luôn các mã Latin mở rộng phổ biến: Ä `.-.-` = Я, Ö `---.` = Ч, Ü `..--` = Ю, CH `----` = Ш, É `..-..` = Э, Q `--.-` = Щ. Nghĩa là không thể "mượn" mã Ä/Ö/Ü cho Ә/Ө/Ү khi thông điệp ở chữ Cyrillic.

---

## 5. Tiếng Kazakh: hiện trạng và phương án

### 5.1 Hiện trạng

- Bảng chữ Kazakh Cyrillic có 42 chữ = 33 chữ Nga + 9 chữ riêng: **Ә Ғ Қ Ң Ө Ұ Ү Һ І**.
- Kazakhstan có kế hoạch (công bố 2021) chuyển sang bảng Latin 31 chữ: A Ä B D E F G Ğ H I İ J K L M N Ñ O Ö P Q R S Ş T U Ū Ü V Y Z.
- **Không tìm thấy chuẩn Morse cho 9 chữ riêng** ở: Wikipedia tiếng Anh ("Morse code for non-Latin alphabets" chỉ có Nga, Bulgaria, Ukraina), Wikipedia tiếng Nga, Wikipedia tiếng Kazakh (trang "Морзе әліппесі" chỉ in bảng Nga/Latin), tìm kiếm tiếng Nga và tiếng Kazakh. Thực tế radio nghiệp dư Kazakhstan dùng bảng Nga.
- Hệ quả: một thông điệp Kazakh "thật" ngoài đời nhiều khả năng được gõ bằng bảng Nga với 9 chữ riêng bị **thay bằng chữ Nga gần nhất** (Ә→А, Ғ→Г, Қ→К, Ң→Н, Ө→О, Ұ/Ү→У, Һ→Х, І→И). Khi đó việc khôi phục đúng chữ Kazakh là việc của mô hình ngôn ngữ, không phải của bộ giải mã.

### 5.2 Ba hồ sơ (profile) nên hỗ trợ

| Profile | Mô tả | Khi dùng |
|---|---|---|
| `kk-Cyrl-ru` | Bảng Nga nguyên vẹn; LM tiếng Kazakh khôi phục 9 chữ riêng theo ngữ cảnh | Thông điệp thực tế từ người dùng bảng Nga |
| `kk-Cyrl-ext` | Bảng Nga + 9 mã mở rộng do dự án định nghĩa (nháp bên dưới) | Liên lạc nội bộ hai đầu đều dùng phần mềm này |
| `kk-Latn-2021` | Bảng Latin ITU + mã Latin mở rộng phi chuẩn cho Ä Ö Ü Ñ Ğ Ş Ū İ | Nếu bên yêu cầu dùng chữ Latin mới |

### 5.3 Bảng nháp `kk-Cyrl-ext` (ĐỀ XUẤT, chưa phải chuẩn)

Nguyên tắc chọn: mã 5 phần tử **chưa bị dùng** bởi bảng Nga, 10 số và 18 dấu câu ITU; ưu tiên mã đã có tiền lệ trong các bảng Latin mở rộng để dễ nhớ.

| Chữ | Mã đề xuất | Tiền lệ | Ghi chú |
|---|---|---|---|
| Ә | `..-.-` | (trống) | |
| Ғ | `--.-.` | Ĝ (Esperanto) | |
| Қ | `-.-..` | Ç / Ć | không thể dùng Q `--.-` vì đó là Щ |
| Ң | `--.--` | Ñ, cũng là Ъ cũ | chấp nhận được vì Ъ cũ đã bỏ |
| Ө | `---.-` | (trống) | không dùng Ö `---.` vì đó là Ч |
| Ұ | `..--.` | Ð | |
| Ү | `.-.--` | (trống) | không dùng Ü `..--` vì đó là Ю |
| Һ | `.--..` | Þ | không dùng H `....` vì đó là Х |
| І | `.---.` | Ĵ | không dùng I `..` vì đó là И |

Mã 5 phần tử còn trống khác để dự phòng: `-..--`, `-.-.-`, `-.---`, `.-..-`, `--..-`, `...-.`.

### 5.4 Bảng `kk-Latn-2021` (tái dụng mã Latin mở rộng, ngoài ITU)

Ä `.-.-`, Ö `---.`, Ü `..--`, Ñ `--.--`, Ğ `--.-.` (Ĝ), Ş `----` (theo Š/CH) hoặc `...-.` (Ŝ), Ū `..--.`, İ `..` (= I), Q `--.-`. Hai chữ Ş và Ū không có tiền lệ thống nhất, cần chốt.

---

## 6. Yêu cầu "có nghĩa": mô hình ngôn ngữ hậu xử lý

Không có sản phẩm hay mô hình nào sẵn có làm việc này cho tiếng Nga/Kazakh. Whisper-small-morse cho tiếng Anh là bằng chứng ý tưởng nhưng nặng 967 MB và không mở rộng được sang Cyrillic mà không train lại.

Cách làm chuẩn ngành, chạy CPU và offline:

1. **CTC beam search + n-gram LM** (KenLM) qua `pyctcdecode` hoặc `torchaudio` flashlight-text: bộ giải mã trả về ma trận xác suất ký tự, LM ưu tiên chuỗi hợp lệ. Cần dựng LM riêng cho từng ngôn ngữ từ corpus text; kích thước vài chục MB.
2. **Từ điển miền**: Q-code, viết tắt điện báo (CQ, DE, PSE, K, 73), prosign, tên riêng; điểm thưởng trong beam search.
3. **Sửa chính tả bằng mô hình nhỏ** (tùy chọn, sau bước 1):

| Ngôn ngữ | Mô hình có sẵn | Kích thước | License | Vai trò |
|---|---|---|---|---|
| Nga | `ai-forever/sage-fredt5-distilled-95m` | ~95M tham số | MIT | sửa chính tả + dấu câu |
| Nga | `cointegrated/rubert-tiny2` | 29M, 117 MB | MIT | rescoring / masked LM |
| Kazakh | `kz-transformers/kaz-roberta-conversational` | RoBERTa 6 lớp, 334 MB | Apache-2.0 | rescoring, khôi phục 9 chữ riêng (profile `kk-Cyrl-ru`) |
| Kazakh | `amandyk/KazakhBERTmulti` | base | AFL-3.0 | thay thế |
| Kazakh | `issai/Qwen3.5-4B-Kazakh` (GGUF Q4 ~2.5 GB) | 4B | | chỉ khi cần "diễn giải" ý nghĩa, không nhẹ |

Corpus để dựng KenLM: tiếng Nga (Wikipedia dump), tiếng Kazakh (`kz-transformers/multidomain-kazakh-dataset` ~24.9 triệu văn bản, `kurumikz/Kazakh_news_corpus`, transcript của `issai/Kazakh_Speech_Corpus_2`), tiếng Anh (Wikipedia + corpus ham radio tổng hợp `michaellin/morse-translate-transcribe-100k`).

---

## 7. Dữ liệu huấn luyện

| Nguồn | Ngôn ngữ | Loại | Ghi chú |
|---|---|---|---|
| cw-train generator | Latin | Tổng hợp, có QSB/QRM/jitter/impulse | Tái dụng, đổi bảng chữ |
| MorseCodeToolkit generator | Bất kỳ (YAML) | Tổng hợp, nhiễu nền thật | Có sẵn bảng Nga |
| ebook2cw `-N` | Latin, Cyrillic | MP3/OGG có nhiễu | Tốt để tạo bộ kiểm thử qua codec MP3 |
| Kaggle Morse Learning Machine v2 | Latin | 8 kHz, SNR -14…+20, 12–80 WPM | Bộ kiểm thử chuẩn |
| AG1LE ARRL 27.8 h | Latin | Audio luyện tập ARRL | Tín hiệu máy, sạch |
| "Morse Code Datasets for Machine Learning" (arXiv 1807.04239) | Latin | Bộ sinh 1-D | Tham khảo |
| Bản ghi thật | Không có cho Nga/Kazakh | | Cần tự thu hoặc lấy từ WebSDR (chỉ cho kiểm thử) |

Pipeline sinh dữ liệu đề xuất: corpus text theo ngôn ngữ → hồ sơ bảng chữ → mô hình tay gõ (jitter, weight, Farnsworth) → tone (500–1100 Hz) → kênh (AWGN, QSB, QRM tone lân cận, xung, lọc băng) → codec (WAV, MP3 64–128 kbps, OGG) → cặp (audio, text). Trộn ba ngôn ngữ trong cùng một tập với nhãn profile.

---

## 8. Khuyến nghị kiến trúc và lộ trình

### 8.1 Kiến trúc

```
file (wav/mp3/ogg/flac)
  → ffmpeg / libsndfile ≥ 1.1 (giải mã MP3 offline) → mono 8 kHz
  → DSP front-end: dò tần số (STFT/Goertzel), down-conversion, envelope, AGC
  → mô hình CTC nhỏ (kiến trúc cw-train, ~100k–1M tham số, ONNX, CPU)
      vocab hợp nhất: Latin 26 + số 10 + dấu + Cyrillic 32 + Kazakh 9 + blank ≈ 85 lớp
      hoặc một model / một profile
  → CTC beam search + KenLM theo profile (en / ru / kk-Cyrl-ru / kk-Cyrl-ext / kk-Latn)
  → (tùy chọn) sửa chính tả bằng mô hình nhỏ
  → văn bản + độ tin cậy từng từ + WPM/tần số phát hiện
```

Chiều tạo mã dùng chung bảng chữ: text → Morse → WAV/MP3 với WPM, Farnsworth, tone, tùy chọn nhiễu.

### 8.2 Lộ trình

| Giai đoạn | Việc | Tái dụng |
|---|---|---|
| 0. Baseline (1–2 tuần) | Chạy ggmorse, pycw, DeepCW engine, MorseCodeToolkit (EN/RU) trên bộ kiểm thử tự sinh; đo CER theo SNR/WPM | tất cả mã mở |
| 1. Bảng chữ | Định nghĩa YAML cho en, ru, kk (3 profile); chốt bảng Kazakh với bên yêu cầu | format YAML của MorseCodeToolkit |
| 2. Sinh dữ liệu | Bộ sinh đa ngôn ngữ, có codec MP3 | cw-train + ebook2cw |
| 3. Mô hình | Train lại kiến trúc cw-train với vocab hợp nhất; xuất ONNX; so với QuartzNet 10x5 | cw-train (Apache), MorseCodeToolkit (Apache) |
| 4. LM | Dựng KenLM 3 ngôn ngữ; tích hợp pyctcdecode; thử sage / kaz-roberta | mô hình HF nêu ở mục 6 |
| 5. Đóng gói air-gap | Wheel cache offline, ONNX Runtime CPU, ffmpeg tĩnh, không tải model lúc chạy; hoặc binary Go (gocw) / C++ | |

### 8.3 Lưu ý license

- Ưu tiên Apache-2.0 / MIT: pycw, cw-train, gocw, MorseCodeToolkit, ggmorse, KenLM (LGPL, dùng động), pyctcdecode (Apache).
- **deepcw-engine là AGPL-3.0**: nếu nhúng vào sản phẩm đóng thì phải mở toàn bộ mã; chỉ nên dùng làm thước đo hoặc mua/xin license khác.
- ebook2cw, fldigi, multimon-ng là GPL: dùng như công cụ ngoài (gọi tiến trình) thì không lây license.

---

## 9. Nguồn

Bộ giải mã và thư viện:
- ggmorse: https://github.com/ggerganov/ggmorse
- DeepCW: https://github.com/e04/web-deep-cw-decoder , engine: https://github.com/e04/deepcw-engine , HamNoise: https://github.com/e04/HamNoise
- pycw: https://pypi.org/project/pycw/ , https://github.com/bigsk05/pycw , cw-train: https://github.com/bigsk05/cw-train
- MorseCodeToolkit: https://github.com/1-800-BAD-CODE/MorseCodeToolkit , model HF: https://huggingface.co/1-800-BAD-CODE/morsecode_en_quartznet_10x5
- whisper-small-morse: https://huggingface.co/michaellin/whisper-small-morse , dataset: https://huggingface.co/datasets/michaellin/morse-translate-transcribe-100k
- MorseAngel: https://github.com/f4exb/morseangel
- AG1LE: https://github.com/ag1le/deepmorse-decoder , https://ag1le.blogspot.com/2020/04/new-real-time-deep-learning-morse.html
- MorseNet (netom): https://github.com/netom/MorseNet
- morse-audio-decoder: https://github.com/mkouhia/morse-audio-decoder
- cwt: https://github.com/gagregrog/cwt
- multimon-ng: https://github.com/EliasOenal/multimon-ng
- csdr-skimmer: https://github.com/luarvique/csdr-skimmer
- fldigi CW: https://www.w1hkj.org/FldigiHelp/cw_configuration_page.html
- RSCW: https://www.pa3fwm.nl/software/rscw/
- CW Skimmer: https://en.wikipedia.org/wiki/CW_Skimmer
- CwGet: https://www.dxsoft.com/en/products/cwget/
- Morse Expert: https://ve3nea.github.io/MorseExpert/
- ebook2cw: https://fkurz.net/ham/ebook2cw.html
- morsify: https://github.com/pcodejs/morsify
- MorseCodePy: https://pypi.org/project/MorseCodePy/

Chuẩn và bảng chữ:
- Morse code for non-Latin alphabets: https://en.wikipedia.org/wiki/Morse_code_for_non-Latin_alphabets
- Russian Morse code: https://en.wikipedia.org/wiki/Russian_Morse_code
- Азбука Морзе (ru): https://ru.wikipedia.org/wiki/Азбука_Морзе
- Морзе әліппесі (kk): https://kk.wikipedia.org/wiki/Морзе_әліппесі
- Morse code (diacritics, prosigns, ITU-R M.1677-1): https://en.wikipedia.org/wiki/Morse_code
- Kazakh alphabets: https://en.wikipedia.org/wiki/Kazakh_alphabets

Dữ liệu và nghiên cứu:
- Kaggle Morse Learning Machine v2: https://www.kaggle.com/c/morse-learning-machine-challenge-v2
- Morse Code Datasets for ML: https://arxiv.org/pdf/1807.04239
- MorseNet paper: https://www.researchgate.net/publication/344064119
- YFDM: https://www.nature.com/articles/s41598-023-48030-7
- Noise Adaption Network: https://arxiv.org/pdf/2410.19180

Mô hình ngôn ngữ / corpus:
- sage: https://github.com/ai-forever/sage , https://huggingface.co/ai-forever/sage-fredt5-distilled-95m
- rubert-tiny2: https://huggingface.co/cointegrated/rubert-tiny2
- kaz-roberta-conversational: https://huggingface.co/kz-transformers/kaz-roberta-conversational
- KazakhBERTmulti: https://huggingface.co/amandyk/KazakhBERTmulti
- Kazakh Speech Corpus 2: https://huggingface.co/datasets/issai/Kazakh_Speech_Corpus_2
