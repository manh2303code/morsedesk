# MorseDesk tuần 4: GUI PySide6 giải mã file, tạo mã, i18n

Ngày: 2026-09-21. Trạng thái: kiến trúc đã duyệt qua brainstorming, chờ người dùng soát bản viết.
Spec gốc: `docs/superpowers/specs/2026-09-18-morsedesk-design.md` (§4 GUI, §7 xử lý lỗi, §10 tuần 4). Lõi tuần 3 đã merge vào `main` (3f98956): `Decoder`, `DecodeResult`, `Encoder`, profile `auto`, LM.

## 1. Mục tiêu và phạm vi

Tuần 4 giao ứng dụng desktop chạy được từ mã nguồn: mở file âm thanh, giải mã bằng lõi tuần 3, xem từ tô màu theo tin cậy và spectrogram có vạch tone, tạo mã từ văn bản và nghe thử/lưu WAV, đổi ngay ngôn ngữ giao diện Kazakh/Nga/Anh.

Quyết định đã chốt với người dùng:

| Hạng mục | Quyết định |
|---|---|
| Phạm vi | Đúng lộ trình tuần 4: giải mã file, spectrogram tĩnh (pyqtgraph, vạch tone), tô màu tin cậy, khung i18n, trang tạo mã (nghe thử, lưu). Không live, không trang Cài đặt (chỉ combo ngôn ngữ giao diện trên thanh công cụ). |
| Thiếu model | Theo spec §7: kiểm tra lúc khởi động; thiếu `models/acoustic.onnx` hoặc `models/lm/{en,ru,kk}.bin` → hộp thoại liệt kê đường dẫn thiếu và cách dựng, thoát mã 2. |
| Kiến trúc | Widgets PySide6 + một `DecoderWorker(QThread)` sở hữu `Decoder`; UI không chạm lõi trực tiếp; không giải mã song song. |
| Vị trí mã | Gói `morsedesk/app/` (trong package để wheel/PyInstaller đóng gói; lệch spec §2.2 vốn để `app/` ở gốc). |
| Trang | `QTabWidget` hai tab Giải mã, Tạo mã (tab Cài đặt thêm ở tuần 5) thay `QStackedWidget` ba trang. |

Ngoài phạm vi tuần 4: live sound card, trang Cài đặt đầy đủ, AppImage/PyInstaller, đóng gói font, streaming file dài hơn 20 phút, bản dịch Kazakh do người bản ngữ soát.

## 2. Kiến trúc

### 2.1 Gói và phụ thuộc

```
morsedesk/app/
  __init__.py
  main.py            entry `morsedesk-gui`: parse args, kiểm model, QApplication, QTranslator, MainWindow
  startup.py         check_models(model_path, lm_dir, engine) -> list[str] đường dẫn thiếu; hướng dẫn dựng
  settings.py        AppSettings (QSettings): ui_language, last_dir; default_language() theo QLocale
  worker.py          DecoderWorker(QThread), EncoderWorker(QThread), Spectrogram (dataclass)
  main_window.py     MainWindow: toolbar (combo ngôn ngữ giao diện), QTabWidget, banner lỗi/cảnh báo, changeEvent
  decode_page.py     DecodePage: chọn/kéo thả file, combo ngôn ngữ bản tin, checkbox LM, nút Giải mã, chỉ số, xuất
  encode_page.py     EncodePage: nhập văn bản, bảng ký tự, tham số, chuỗi chấm gạch, Nghe thử, Lưu
  widgets/
    banner.py        Banner(QFrame): thông báo đỏ/vàng có nút đóng
    spectrogram.py   SpectrogramView(pyqtgraph.PlotWidget): ImageItem 0–2 kHz, InfiniteLine tone, vạch đầu từ
    word_view.py     WordView(QWidget): FlowLayout các WordLabel tô màu, tooltip tin cậy + thời điểm
    stats_bar.py     StatsBar(QWidget): WPM, tone, SNR, ngôn ngữ (tooltip điểm ba profile), thời gian
    charmap.py       CharMap(QWidget): nút Cyrillic + 9 chữ Kazakh, signal char_clicked(str)
    flow_layout.py   FlowLayout (theo ví dụ Qt)
  i18n/
    morsedesk_en.ts, morsedesk_ru.ts, morsedesk_kk.ts, *.qm (commit cả .qm để chạy từ nguồn)
tools/build_i18n.py  chạy pyside6-lupdate rồi pyside6-lrelease
```

Phụ thuộc mới, extra `gui` trong `pyproject.toml`: `PySide6>=6.6` (LGPL, dùng động), `pyqtgraph>=0.13` (MIT). Extra `dev` thêm `pytest-qt>=4.2` (MIT). Script `[project.scripts] morsedesk-gui = "morsedesk.app.main:main"`. Lõi (`morsedesk/*` ngoài `app/`) không import Qt.

### 2.2 Khởi động

`main(argv)`: tham số `--model PATH` (mặc định `DEFAULT_MODEL_PATH`), `--lm-dir PATH` (mặc định `models/lm`), `--engine {onnx,baseline}` (mặc định onnx; `baseline` chỉ để dev/test, khi đó không cần ONNX nhưng vẫn cần LM cho `auto`), `--lang {en,ru,kk}` (ghi đè ngôn ngữ giao diện). Thứ tự: `check_models` → nếu thiếu: `QMessageBox.critical` với danh sách đường dẫn và ba dòng hướng dẫn (xuất ONNX bằng `tools/export_onnx.py`; dựng LM theo README), `return 2` → nếu đủ: cài `QTranslator`, tạo `MainWindow`, `DecoderWorker.start()`.

Logging: `logging` gốc ghi `RotatingFileHandler` (1 MB × 3) tại `QStandardPaths.AppDataLocation/logs/morsedesk.log`; `sys.excepthook` ghi log và hiện banner đỏ "Lỗi nội bộ, xem log" thay vì chết im.

### 2.3 Luồng dữ liệu giải mã

```
DecodePage ──request(path, profile_id, use_lm)──▶ DecoderWorker (QThread)
                                                  │ Decoder(profile, engine, model_path, lm, lm_dir, acoustic_model=shared)
                                                  │ x = load_audio(path); result = decode_array(x)
                                                  │ spec = Spectrogram.from_audio(x)
DecodePage ◀──result_ready(DecodeResult, Spectrogram, path)── │
DecodePage ◀──failed(message)───────────────────────────────── │
DecodePage ◀──busy(bool)──────────────────────────────────────── │
```

- `DecoderWorker` chạy vòng lặp trên `queue.Queue(maxsize=1)`; yêu cầu mới thay yêu cầu đang chờ (không xếp hàng nhiều), yêu cầu đang chạy không bị hủy giữa chừng (giải mã ≤ 20 phút audio mất vài giây).
- Worker giữ cache `Decoder` theo khóa `(profile_id, use_lm)`; ONNX session (`OnnxAcousticModel`) nạp một lần và truyền qua `acoustic_model` cho mọi `Decoder`. LM nạp qua `LMStore` dùng chung (một `LMStore` cho worker, truyền `lm_dir`).
- `Spectrogram`: dataclass `(power_db: np.ndarray [n_bins, n_cols] float32, freqs_hz: np.ndarray, times_s: np.ndarray)` tính từ `dsp.stft.stft_power` (8 kHz, N_FFT 256, HOP 40), chỉ giữ bin ≤ 2 kHz (65 bin), log10 chuẩn hóa về dB tương đối [-60, 0], gộp theo thời gian (max-pool) để không quá 4000 cột. Tính trong worker.
- File dài hơn 20 phút (`audio_info`) → `failed("file dài hơn 20 phút, chưa hỗ trợ ở bản này")` trước khi nạp.
- Kết quả: `DecodeResult` giữ nguyên hợp đồng tuần 3 (`text`, `words[]` với `start_s/end_s/confidence`, `wpm`, `tone_hz`, `snr_db`, `language`, `language_scores`, `warnings`, `engine`, `fallback_text`).

### 2.4 Trang Giải mã

Bố cục dọc: (1) hàng điều khiển: nút "Mở file…", nhãn đường dẫn (elide), combo "Ngôn ngữ bản tin" [Tự động, Tiếng Anh, Tiếng Nga, Tiếng Kazakh], checkbox "Dùng mô hình ngôn ngữ" (mặc định bật), nút "Giải mã" (bật khi có file); (2) `Banner` cảnh báo/lỗi; (3) `QSplitter` dọc: `SpectrogramView` trên, `WordView` dưới; (4) `StatsBar`; (5) hàng nút: "Sao chép", "Xuất TXT…", "Xuất JSON…", nhãn "Kết quả DSP dự phòng" mở rộng được khi `fallback_text` khác None.

- Kéo thả: cả trang nhận `dragEnterEvent` với URL file có phần mở rộng trong `SUPPORTED_EXT`.
- Mở file hoặc đổi combo/checkbox khi đã có file → tự gửi yêu cầu mới (nút "Giải mã" để chạy lại thủ công).
- `WordView`: mỗi từ là `WordLabel(QLabel)` nền theo tin cậy: ≥ 0,8 xanh lá nhạt, 0,5–0,8 vàng, < 0,5 đỏ nhạt (ngưỡng trùng `FALLBACK_CONFIDENCE`/`LOW_CONFIDENCE` của `api.py`); tooltip "tin cậy 0,87 · 1,20–1,85 s"; click từ → di chuyển vạch đứng trên spectrogram tới `start_s`.
- `SpectrogramView`: trục x giây, y Hz 0–2000, `ImageItem` với LUT xám hoặc viridis; `InfiniteLine` ngang tại `tone_hz` (ẩn khi None); vạch đứng mờ tại `start_s` mỗi từ; cảnh báo tone thứ hai hiện trong Banner (không vẽ).
- `StatsBar`: "WPM 20,3 · Tone 700 Hz · SNR 12,4 dB · Ngôn ngữ: Tiếng Nga (tự động)" với tooltip điểm ba profile khi auto; `language == ""` hiển thị "Chưa nhận diện"; thời gian giải mã (giây).
- Xuất TXT: `text` (UTF-8, BOM không); xuất JSON: `DecodeResult.to_json()`. Thư mục gợi ý = `last_dir` trong `AppSettings`.
- Trạng thái bận: nút và combo vô hiệu, con trỏ chờ, `QProgressBar` không xác định trong StatsBar.

### 2.5 Trang Tạo mã

- Trái: `QPlainTextEdit` văn bản, dưới là `CharMap` (33 chữ Cyrillic + 9 chữ Kazakh Ә Ғ Қ Ң Ө Ұ Ү Һ І, nhóm Kazakh chỉ hiện khi profile kk; click chèn tại con trỏ); ô "Chuỗi chấm gạch" chỉ đọc, cập nhật khi văn bản/profile đổi (`Encoder.to_morse_string(strict=False)`); ký tự không hỗ trợ được liệt kê trong nhãn cảnh báo vàng ("Bỏ qua: X, Y").
- Phải: profile (Tiếng Anh/Nga/Kazakh), WPM (5–60, mặc định 20), Farnsworth WPM (checkbox + spin 5–60), weight (2,0–4,0, bước 0,1), tone (300–1500 Hz), SNR (checkbox + spin −10…30 dB), định dạng lưu (WAV/FLAC/OGG).
- Nút "Nghe thử"/"Dừng": `EncoderWorker` tạo audio (`Encoder.to_audio`) và phát qua `sounddevice.OutputStream` trong thread; không có thiết bị phát → banner vàng, vẫn lưu được. Nút "Lưu…": `QFileDialog` với phần mở rộng theo định dạng, `save_audio`.
- Văn bản rỗng → nút vô hiệu. Hai lần bấm Nghe thử trong khi đang phát → dừng rồi phát lại.

### 2.6 i18n

- Mọi chuỗi hiển thị qua `self.tr()`; mỗi page/widget có `retranslate()` được gọi từ `changeEvent(QEvent.LanguageChange)`; nội dung động (tên ngôn ngữ trong combo, chỉ số) cũng đặt lại trong `retranslate()`.
- `MainWindow.set_language(code)`: gỡ translator cũ, nạp `morsedesk/app/i18n/morsedesk_<code>.qm` bằng `QTranslator`, `QApplication.installTranslator`, lưu `AppSettings.ui_language`. Tiếng Anh là ngôn ngữ nguồn (không cần file `.qm`, vẫn có `.ts` để làm mốc).
- Mặc định: `--lang` > `AppSettings` > `QLocale.system()` (kk/ru) > en.
- Combo ngôn ngữ giao diện trên thanh công cụ hiển thị tên bản ngữ: "English", "Русский", "Қазақша (nháp)" — nhãn "bản nháp" theo spec §4 cho tới khi có người bản ngữ soát; văn bản dịch do Claude soạn.
- `tools/build_i18n.py`: gọi `pyside6-lupdate morsedesk/app -ts morsedesk/app/i18n/morsedesk_{en,ru,kk}.ts` rồi `pyside6-lrelease` từng file; `.ts` và `.qm` commit (để chạy từ nguồn không cần lrelease); test kiểm số chuỗi chưa dịch của ru = 0, kk = 0 (kk là bản nháp nhưng đầy đủ).
- Font: dùng font hệ thống (Segoe UI / DejaVu Sans đều có Cyrillic mở rộng); đóng gói font để tuần 5–6. Test không kiểm hiển thị glyph.

### 2.7 Xử lý lỗi (bản tuần 4 của spec §7)

| Tình huống | Hành vi |
|---|---|
| File không đọc được / định dạng lạ | banner đỏ với thông điệp `UnsupportedAudio` (đã kèm danh sách định dạng) |
| Không dò được tone | kết quả rỗng, banner vàng "không có tín hiệu Morse" (từ `warnings`) |
| Tone thứ hai | banner vàng từ `warnings` |
| Model/LM thiếu | hộp thoại lúc khởi động, thoát mã 2 |
| Tin cậy thấp | từ tô đỏ; `fallback_text` hiện trong khối mở rộng |
| File > 20 phút | banner đỏ, không nạp |
| `auto` không nhận diện được (`language == ""`) | StatsBar "Chưa nhận diện", văn bản rỗng |
| Ngoại lệ bất kỳ trong worker | `failed(message)`, log; worker vẫn sống |
| Không có thiết bị phát | banner vàng ở trang Tạo mã, lưu vẫn được |

### 2.8 Kiểm thử

- `pytest-qt`, `QT_QPA_PLATFORM=offscreen` đặt trong `tests/app/conftest.py`; test GUI nằm ở `tests/app/` và chạy trong bộ mặc định (không cần model thật: `--engine baseline` + LM tí hon `train_small` như `tests/unit/test_api_lm.py`, hoặc model ONNX chưa train từ fixture xuất tạm khi cần kiểm đường onnx).
- Đơn vị: `startup.check_models` (thiếu/đủ), `Spectrogram.from_audio` (kích thước, dải dB, max-pool khi dài), `WordView` màu theo ngưỡng và tooltip, `CharMap` chèn ký tự, `AppSettings` mặc định theo locale, `build_i18n` không cần chạy trong test (kiểm `.qm` tồn tại và `.ts` không có `type="unfinished"`).
- Tích hợp (qtbot): `DecoderWorker` giải mã WAV "CQ DE K" (baseline, LM tí hon) → `result_ready` với text đúng; `DecodePage` mở file → từ hiển thị, StatsBar có WPM, xuất TXT/JSON ra file; đổi combo ngôn ngữ bản tin → yêu cầu mới; `EncodePage` nhập "SOS" → chuỗi chấm gạch "... --- ...", Lưu tạo WAV đọc lại được; `MainWindow.set_language("ru")` đổi nhãn tab thành "Декодирование"; `main([... "--model", missing])` trả 2 mà không mở cửa sổ (QMessageBox được patch).
- Ruff sạch; `uv run pytest` gồm test app; thời gian test app dưới 60 s.

## 3. Điều kiện ra tuần 4

- `uv run morsedesk-gui` mở được trên Windows dev (và Ubuntu theo lý thuyết, không kiểm tuần này): mở clip T1, giải mã `auto` có LM, từ tô màu, spectrogram có vạch tone, đổi ngôn ngữ giao diện kk/ru/en ngay lập tức, tạo mã "СӘЛЕМ" ra WAV và nghe thử.
- Bộ test mặc định xanh (kể cả `tests/app/`), ruff sạch, không import Qt trong lõi.
- Tài liệu: README mục "GUI" (cách chạy, tham số, i18n, dựng .qm); ghi vào spec gốc §4 các lệch (gói trong package, hai tab, không waterfall live).

## 4. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| PySide6 trên Windows dev và pytest-qt offscreen không ổn định | pin `PySide6-Essentials>=6.6,<7` (xem mục 5); test dùng `qtbot.waitSignal` với timeout; nếu offscreen lỗi, đánh dấu `skipif` theo biến môi trường và chạy tay |
| Spectrogram file 20 phút nặng UI | max-pool xuống ≤ 4000 cột trong worker; ImageItem cập nhật một lần |
| Bản dịch kk/ru sai ngữ | nhãn nháp; mọi chuỗi tập trung trong `.ts` để sửa không cần đụng mã |
| `sounddevice` không có thiết bị (CI/offscreen) | Nghe thử bắt `sounddevice.PortAudioError`/`OSError` → banner; test không gọi phát thật |
| Đổi profile tạo lại Decoder chậm | ONNX session dùng chung qua `acoustic_model`; LM cache trong `LMStore` |

## 5. Lệch khi thực thi

Ghi lại sau khi chạy Task 1–7. Mỗi mục là lệch so với mục 2 ở trên, không phải lỗi còn mở.

**Kiến trúc**

- Nghe thử dùng lớp `Player` bọc `sounddevice.play` (không chặn) thay cho `EncoderWorker(QThread)` như mục 2.5: tạo audio cho một bản tin mất dưới 100 ms nên không cần thread riêng. `Player` nằm cùng `worker.py` với `DecoderWorker` và `Spectrogram`.
- Lõi nhận thêm tham số tương thích ngược `Decoder(lm_store=...)` (mục 2.3 chỉ nói "LMStore dùng chung"): GUI tạo một `LMStore` rồi truyền cho mọi `Decoder`, nên ba profile chia sẻ cùng LM đã nạp.
- Không cài `sys.excepthook` hiện banner đỏ "Lỗi nội bộ" như mục 2.7. `main()` đặt excepthook ghi log rồi gọi hook mặc định; lỗi trong worker vẫn tới banner qua tín hiệu `failed`. Banner cho lỗi bất đồng bộ để tuần 5, khi có chế độ live sinh ra nhiều nguồn lỗi hơn.
- `DecodePage` được gia cố ngoài mục 2.4 sau review: `on_result` bỏ qua kết quả không khớp file đang mở, và `on_busy` khóa cả kéo-thả. Không có việc này thì thả file B trong lúc giải mã file A sẽ vẽ kết quả A dưới tên B (và xuất ra file sai nội dung).
- Tên định dạng lưu ("WAV", "FLAC", "OGG") không qua `self.tr()`: là tên định dạng file, giữ nguyên ở cả ba ngôn ngữ.

**Lệch so với mục 2 (phát hiện khi review toàn nhánh)**

- `startup.check_models` đòi **cả** `acoustic.onnx` lẫn `acoustic.json` (metadata của model), mục 2.2 chỉ nói tới file ONNX. Thư mục trùng tên cũng bị coi là thiếu (`is_file()`, không phải `exists()`).
- Không sinh `morsedesk_en.ts`: tiếng Anh là ngôn ngữ nguồn, `tools/build_i18n.py` chỉ dựng `ru` và `kk` (mục 2.2/2.6 có nhắc `morsedesk_en.ts` "để làm mốc").
- `CharMap` bị **ẩn hoàn toàn** với profile `en` (mục 2.5 chỉ nói nhóm Kazakh ẩn khi không phải `kk`).
- `path_label` **không** elide đường dẫn dài như mục 2.4; `fallback_text` hiện trong một `QLabel` phẳng có word-wrap, không phải "khối mở rộng được"; trạng thái bận **không** đổi con trỏ chuột thành con trỏ chờ.
- `MainWindow` có thêm một `Banner` mức cửa sổ (mục 2.2 đã dự tính) dùng cho thông báo lúc hoãn đóng cửa sổ.
- Extra `gui` khai `PySide6-Essentials>=6.6,<7` thay cho meta `PySide6>=6.6` của mục 2.1 (meta kéo theo `PySide6-Addons`, trong đó QtCharts/QtDataVisualization/QtGraphs chỉ có GPLv3 hoặc thương mại, mà dự án đóng nguồn; QtWebEngine là LGPLv3 nhưng nặng và không dùng tới), và `pyqtgraph>=0.13,<0.15` có trần.
- Tất cả thông điệp lỗi của `DecoderWorker` đi qua `failed(code, detail, path)` với `code` thuộc `FAILURE_CODES`; `DecodePage` dựng câu bằng `tr()`, `detail` chỉ làm tooltip. Mục 2.3 vẽ `failed(message)`.

**Hành vi phát hiện khi chạy**

- Profile `ru` và `kk-cyrl-ru` không chứa chữ Latin, nên gõ văn bản Latin ở tab Tạo mã rồi đổi sang hai profile này sẽ cảnh báo "ký tự không hỗ trợ" cho từng chữ Latin, không phải chuyển tự. Đây là hệ quả đúng của bảng mã, cần nhớ khi viết test.
- Đóng cửa sổ trong lúc đang giải mã: `closeEvent` gọi `DecoderWorker.stop_async()` rồi chờ ngắn 500 ms; nếu yêu cầu hiện tại chưa xong thì **hoãn đóng** (`event.ignore()`), khóa `QTabWidget`, hiện banner "đang hoàn tất giải mã" và nối `worker.finished` vào `close()`. Cửa sổ đóng ngay khi worker kết thúc. Vòng lặp sự kiện cũng có thể kết thúc không qua `closeEvent` (`QCoreApplication.exit`, đăng xuất phiên), nên `create_app` nối thêm `app.aboutToQuit` vào `DecoderWorker.stop`. Hai chốt này cùng bảo đảm QThread không bị hủy khi đang chạy; trước khi sửa, file dài hơn ~1 phút làm tiến trình chết `0xC0000409`.
- Trong lúc giải mã file mới, kết quả cũ vẫn hiển thị dưới tên file mới cho tới khi có kết quả. Các điều khiển bị khóa là: "Mở file…", combo ngôn ngữ bản tin, ô "Dùng mô hình ngôn ngữ", "Giải mã", ba nút "Sao chép"/"Xuất TXT…"/"Xuất JSON…" và cả kéo-thả; StatsBar hiện thanh tiến trình vô định. Chấp nhận ở tuần 4.

- Ngưỡng 20 phút của tab Tạo mã được kiểm ở hai chỗ: trạng thái nút (cập nhật khi đổi văn bản, profile
  hoặc tham số timing) và `audio_or_error()` ngay trước khi dựng audio. Nút bị vô hiệu chỉ là chỉ dẫn giao
  diện, không phải bất biến, nên gọi thẳng `play()`/`save_to()` vẫn bị chặn.

**Giới hạn đã biết, chưa sửa ở tuần 4**

- Cảnh báo trong `DecodeResult.warnings` (lõi sinh, tiếng Việt) và thông điệp lỗi của `Player.play`
  (tiếng Anh) vẫn đổ thẳng vào banner, chưa qua `tr()`. Khác với nhóm lỗi của worker đã có bảng mã.
- `worker.py` gộp mọi `ValueError` phát sinh khi giải mã vào mã `config`, nên một `ValueError` từ numpy
  cũng hiện câu về "thiếu file model/LM"; chi tiết thật nằm ở tooltip.
- `save_audio` chưa ghi được `.aif` và `.oga` dù hai đuôi này nằm trong `SUPPORTED_EXT` (chỉ đọc được).
  Không với tới từ GUI vì hộp thoại Lưu chỉ có WAV/FLAC/OGG.
- Thả nhiều file cùng lúc chỉ nhận file đầu tiên.
- File 19,5 phút mất khoảng 3,7 phút và 2,1 GB, chỉ có thanh tiến trình vô định, chưa có nút Hủy.

**Kiểm chứng Task 7 (2026-09-21, engine ONNX thật + 3 LM thật, offscreen)**

29/29 mục kiểm đạt, gồm: mở file T1 và giải mã 0,55 giây lần đầu (đã gồm nạp ONNX + LM) và 0,41 giây các lần sau; StatsBar đủ WPM/tone/SNR; spectrogram có vạch tone; đổi profile Kazakh cho ra Cyrillic; profile Tự động trả đủ điểm ba ngôn ngữ và tooltip; kéo thả file `.wav` chạy, kéo thả `README.md` bị từ chối ở `dragEnterEvent` và cho banner đỏ khi ép nạp; xuất TXT/JSON đúng; đổi giao diện en → ru → kk → en đổi nhãn ngay và lưu vào `QSettings`; tab Tạo mã gõ "СӘЛЕМ" bằng bảng ký tự, lưu WAV rồi giải mã lại đúng "СӘЛЕМ"; đóng cửa sổ dừng worker dưới 2 giây.

Hai điều chưa kiểm được bằng cách này: chữ hiển thị (Qt headless không có font nên mọi ký tự vẽ thành ô vuông — càng cho thấy phải đóng gói DejaVu/Noto như §4 spec gốc yêu cầu, việc của tuần 6) và âm thanh phát ra loa thật.

**Đợt sửa sau hai vòng review (`.superpowers/sdd/fix-list-week4.md`)**

Đã sửa: đóng cửa sổ giữa lúc giải mã không còn hủy QThread; tab Tạo mã ước lượng thời lượng trước khi dựng audio và dùng chung trần 20 phút với tab Giải mã; `save_audio` chỉ ép `PCM_16` cho container PCM nên lưu OGG chạy được (sửa cả `morsedesk encode --out`); ô "Dùng mô hình ngôn ngữ" bị khóa khi profile là `auto`; thông điệp lỗi dựng bằng `tr()` theo mã; `on_failed` bỏ qua lỗi của file không còn mở; xuất TXT/JSON báo lỗi ghi file; nút xuất/sao chép bị khóa lúc bận; Nghe thử báo lỗi tham số timing như Lưu; không còn cắt tên file có dấu chấm; log ghi vào `AppDataLocation` đúng; `check_models` đòi file thật; `last_dir` hỏng trả về thư mục nhà; phụ thuộc đổi sang `PySide6-Essentials` (tránh module Qt chỉ-GPL) và đặt trần `pyqtgraph<0.15`.

**Giới hạn còn lại sau đợt sửa (để tuần 5–6)**

- Thả nhiều file cùng lúc: chỉ nhận file đầu, không báo gì (`decode_page.dropEvent`).
- Sát trần 20 phút vẫn nặng: file 19,5 phút mất **3,7 phút** và **~2,1 GB** RAM, trong suốt thời gian đó chỉ có thanh tiến trình vô định, chưa có nút Hủy. Chế độ live, nút Hủy và tiến trình theo phần trăm thuộc tuần 5.
- Hồ sơ giấy phép bên thứ ba (văn bản LGPL cho Qt, cam kết relink, đóng gói font DejaVu/Noto) là việc chặn tuần 6, cùng lúc dựng AppImage.
- Bản dịch `ru`/`kk` chưa có người bản ngữ soát (phong cách nút, "SNR" so với "ОСШ").
