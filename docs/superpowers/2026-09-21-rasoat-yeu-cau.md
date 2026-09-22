# Rà soát yêu cầu MorseDesk — chốt kiểm sau tuần 4

Ngày: 2026-09-21. Trạng thái mã: `main` sau khi merge tuần 4.
Nguồn yêu cầu: `docs/superpowers/specs/2026-09-18-morsedesk-design.md` (spec gốc, mục 1–12),
`2026-09-19-morsedesk-week3-design.md`, `2026-09-21-morsedesk-week4-gui-design.md`.

Mục đích: đối chiếu **từng điều khoản** của spec với mã đang có, nêu bằng chứng cho mỗi mục đạt,
và chuyển mọi mục chưa đạt thành chốt kiểm (checkpoint) có tiêu chí nghiệm thu đo được.

## Quy ước trạng thái

| Ký hiệu | Nghĩa |
|---|---|
| **ĐẠT** | Có bằng chứng kiểm chứng được: test tự động, số đo, hoặc commit cụ thể. |
| **LỆCH** | Làm khác spec một cách có chủ ý, đã ghi lý do trong mục "lệch" của spec tương ứng. |
| **CHƯA ĐẠT** | Spec yêu cầu, chưa có hoặc có nhưng không đạt ngưỡng. Sinh ra một checkpoint. |
| **HOÃN** | Thuộc tuần 5 hoặc 6 theo lộ trình spec mục 10. Không tính là nợ của tuần 4. |

Mỗi dòng "bằng chứng" phải trỏ tới thứ kiểm lại được: đường dẫn kèm số dòng, tên test, hoặc lệnh.

---

## A. Tiêu chí nghiệm thu v1 (spec mục 1)

| # | Điều khoản | Trạng thái | Bằng chứng / khoảng cách |
|---|---|---|---|
| A1 | CER < 2 % ở ô SNR ≥ 0 dB và 10–35 WPM trên ma trận tổng hợp T1 | **CHƯA ĐẠT** | `uv run pytest -m gate` → `test_t1_gate_onnx` FAIL. Đo: 26,45 % greedy, 25,27 % beam+LM (`docs/research/02-baseline-numbers.md`). Mốc ngoài: DeepCW 23,70 % trên cùng bộ (`docs/research/04-pretrained-baselines.md`). → **CP-01** |
| A2 | CER < 2 % trên ARRL W1AW 18–40 WPM (bộ T2) | **CHƯA ĐẠT** | Không có dữ liệu T2 trong repo: `testdata/` chỉ có `generated/`. Chưa từng đo. → **CP-02** |
| A3 | Nhận diện ngôn ngữ bản tin tự động | **CHƯA ĐẠT** | `language_acc` = 0,584 trên T1, mục tiêu 0,95 (`test_t1_lm_not_worse_than_greedy_and_language_acc` FAIL). Nguyên nhân đã phân tích: radiogram ham chuyển tự trung lập ngôn ngữ. → **CP-03** |
| A4 | Chỉ giải mã và sửa lỗi, không dịch chéo ngôn ngữ | **ĐẠT** | Không có đường dẫn dịch máy nào trong `morsedesk/`. |
| A5 | Profile `kk-cyrl-ru`: khôi phục 9 chữ Kazakh bằng LM từ bảng Nga | **ĐẠT** | `morsedesk/profiles/kk-cyrl-ru.yaml`; roundtrip "СӘЛЕМ" qua GUI trả đúng (kiểm chứng Task 7, mục 5 spec tuần 4). |
| A6 | Giao diện đổi ngay giữa Kazakh, Nga, Anh | **ĐẠT** | `tests/app/test_i18n.py`; ảnh chụp 05, 06. |
| A7 | Chỉ nhúng Apache-2.0 / MIT / BSD / LGPL, không AGPL, không GPL | **ĐẠT** (phần phụ thuộc) | `PySide6-Essentials` + `shiboken6` LGPLv3, `pyqtgraph` MIT, `numpy`/`scipy`/`soundfile`/`PyYAML` BSD/MIT. Đã kiểm cài mới: 22 module Qt, không còn QtCharts/QtDataVisualization/QtGraphs (chỉ-GPL). |
| A8 | Hồ sơ giấy phép kèm sản phẩm (văn bản LGPL, cam kết relink) | **CHƯA ĐẠT** | Repo không có `LICENSE`, `NOTICE` hay `THIRD_PARTY`; chỉ có `models/lm/LICENSES.md` cho corpus. Nghĩa vụ LGPL chưa chuẩn bị. → **CP-04** |
| A9 | Môi trường đích Ubuntu/Debian x86_64, không mạng | **MỘT PHẦN** | Đã kiểm trên Ubuntu 26.04 LTS (WSL, 2026-09-21): toàn bộ test xanh, ruff sạch, `build_i18n --check` sạch, GUI khởi động trả mã 2 khi thiếu model, CLI giải mã một clip tiếng Nga ra đúng "ТНЬ ФЕР ЦАЛЛ", cửa sổ Qt dựng được bằng plugin **wayland**, ảnh chụp hiện đủ Ә Ғ Қ Ң Ө Ұ Ү Һ І (máy có 89 font, gồm DejaVu). Còn thiếu: chưa kiểm trên **22.04/24.04 LTS** là bản spec nhắm, và plugin **xcb** không khởi tạo được. → **CP-05**, **CP-16** |

## B. Lõi và tạo mã (spec mục 2, 3)

| # | Điều khoản | Trạng thái | Bằng chứng / khoảng cách |
|---|---|---|---|
| B1 | Stack LM runtime: `pyctcdecode` + `kenlm` | **LỆCH** | Beam search và n-gram tự viết thuần numpy; KenLM chỉ là công cụ dev để dựng `.bin`. Lý do ghi ở spec tuần 3 mục 6.1 dòng 17. Phụ thuộc runtime thực tế: numpy, scipy, soundfile, PyYAML. |
| B2 | Bố cục repo: `app/` và `profiles/` ở gốc | **LỆCH** | Thực tế `morsedesk/app/` và `morsedesk/profiles/` để đóng gói được bằng wheel/PyInstaller. `app/` đã ghi ở spec gốc mục 4; `profiles/` **chưa ghi** → bổ sung trong đợt này. |
| B3 | `encode.text` chuẩn hóa theo profile, `strict=False` bỏ qua ký tự lạ | **ĐẠT** | `morsedesk/encode/text.py`; `unsupported_chars` ở GUI cảnh báo danh sách ký tự bỏ qua (ảnh 09). |
| B4 | `encode.timing` chuẩn PARIS, Farnsworth ARRL, `weight` | **ĐẠT** | `morsedesk/encode/timing.py`; `tests/unit` T0 timing. |
| B5 | `encode.synth` sine, sườn raised-cosine 5 ms, 8/16/44,1 kHz, nhiễu theo SNR | **ĐẠT** | `morsedesk/encode/synth.py`. |
| B6 | Xuất WAV, FLAC, OGG qua soundfile | **ĐẠT** | Sửa ở `morsedesk/audio/io.py:60-62` (trước đó ép `PCM_16` nên OGG luôn lỗi); test ghi-đọc cả ba định dạng ở `tests/unit/test_audio_io.py`. |
| B7 | Xuất MP3: libsndfile có lame → ghi thẳng; không thì gọi `ffmpeg` ngoài; không có thì báo không hỗ trợ. Kiểm khả năng lúc khởi động và hiện trong Cài đặt | **CHƯA ĐẠT** | `FORMATS` chỉ có WAV/FLAC/OGG; không có dò `ffmpeg`, không có thông báo khả năng. → **CP-06** |
| B8 | Ghi được mọi đuôi trong `SUPPORTED_EXT` | **CHƯA ĐẠT** | `.aif` và `.oga` đọc được nhưng `save_audio` ném `TypeError`. Chưa với tới từ GUI (hộp thoại chỉ 3 định dạng) nhưng CLI `encode --out x.oga` sẽ hỏng. → **CP-07** |
| B9 | Chuỗi chấm gạch: cách chữ một khoảng trắng, cách từ ` / ` | **ĐẠT** | `Encoder('en').to_morse_string('CQ DE K')` → `-.-. --.- / -.. . / -.-`. |

## C. GUI (spec mục 4)

| # | Điều khoản | Trạng thái | Bằng chứng / khoảng cách |
|---|---|---|---|
| C1 | `QMainWindow` với ba trang (Giải mã, Tạo mã, Cài đặt) | **LỆCH / HOÃN** | `QTabWidget` hai tab; trang Cài đặt thuộc tuần 5. Ghi ở spec gốc mục 4 và spec tuần 4 mục 5. |
| C2 | Nguồn file: hộp thoại và kéo thả | **ĐẠT** | `decode_page.py`; kiểm chứng Task 7 mục 3–4; test `test_on_busy_blocks_drops_and_open_button`. |
| C3 | Nguồn thiết bị thu (combo liệt kê từ sounddevice) | **HOÃN** | Tuần 5 (chế độ live). |
| C4 | Waterfall phổ 0–2 kHz bằng pyqtgraph, vạch tone đang bám | **ĐẠT phần tĩnh / HOÃN phần live** | `SpectrogramView`; ảnh 02. Waterfall cuộn theo thời gian thực thuộc tuần 5. |
| C5 | Từ tô màu theo tin cậy, tooltip tin cậy và thời điểm | **ĐẠT** | `word_view.py`; ngưỡng 0,8 / 0,5 và ba mã màu đúng spec tuần 4. Sửa 75dd557: ghim màu chữ `#1a1a1a` vì ở giao diện tối chữ trắng trên nền nhạt chỉ đạt tương phản 1,25:1 (đo trên ảnh chụp thật), nay 13,89:1. |
| C6 | Combo ngôn ngữ bản tin (Tự động/Anh/Nga/Kazakh) kèm ba điểm nhận diện | **ĐẠT** | `PROFILE_CHOICES`; tooltip `StatsBar.language_widget` hiện ba điểm (kiểm chứng Task 7 mục 2). |
| C7 | Chỉ số WPM, tone Hz, SNR dB | **ĐẠT** | `StatsBar`; đơn vị Hz/dB nay đi qua `tr()` (sửa 75dd557). |
| C8 | Chỉ số tiến trình file | **CHƯA ĐẠT** | Chỉ có thanh tiến trình vô định (`stats_bar.py:21` `setRange(0, 0)`). File 19,5 phút chạy ~3,7 phút không biết còn bao lâu. → **CP-08** |
| C9 | Nút hủy khi đang giải mã | **CHƯA ĐẠT** | Không có. Đóng cửa sổ giữa chừng nay an toàn nhưng vẫn phải chờ xong. → **CP-09** |
| C10 | Nút xuất TXT và JSON | **ĐẠT** | `export_txt` / `export_json`; kiểm chứng Task 7 mục 5; lỗi ghi file nay có banner (nhóm 4.4 đợt sửa). |
| C11 | Live: callback sounddevice, `DecoderWorker(QThread)`, signal `words_ready`/`stats`/`warning` | **HOÃN** | Tuần 5. Lưu ý kiến trúc: `DecoderWorker` hiện là QThread có vòng `queue.get()` chặn, **không có event loop**, nên không nhận được queued slot call. Tuần 5 phải chọn `moveToThread` + `QEventLoop` hoặc thread thứ hai. → ghi vào kế hoạch tuần 5 |
| C12 | Tạo mã: ô nhập, bảng ký tự Cyrillic và 9 chữ Kazakh, tham số, nghe thử, lưu, hiện chuỗi chấm gạch | **ĐẠT** | `encode_page.py`; ảnh 07; roundtrip "СӘЛЕМ" đúng. |
| C13 | Cài đặt: ngôn ngữ giao diện, profile mặc định, thiết bị mặc định, thư mục xuất, bật/tắt fallback DSP, lưu bằng `QSettings` | **MỘT PHẦN / HOÃN** | Ngôn ngữ giao diện và thư mục gần nhất đã lưu bằng `QSettings` (`settings.py`). Bốn mục còn lại thuộc trang Cài đặt tuần 5. |
| C14 | Mọi chuỗi hiển thị qua `self.tr()` | **CHƯA ĐẠT (còn sót)** | Chuỗi lỗi của `DecoderWorker` đã qua bảng mã + `tr()`, nhưng `DecodeResult.warnings` do lõi sinh (tiếng Việt) và thông điệp của `Player.play` (tiếng Anh) vẫn đổ thẳng vào banner. → **CP-10** |
| C15 | Nguồn `.ts` cho cả en, ru, kk | **LỆCH** | Chỉ sinh `ru` và `kk`; tiếng Anh là ngôn ngữ nguồn nên không cần `.qm`. Ghi ở spec tuần 4 mục 5. |
| C16 | Ngôn ngữ mặc định theo locale hệ thống, không khớp thì Anh | **ĐẠT** | `settings.default_language`; test `test_startup_settings.py`. |
| C17 | Đóng gói font DejaVu Sans và Noto Sans, đặt làm font ứng dụng | **CHƯA ĐẠT** | Chưa có font trong repo, chưa đặt font ứng dụng. Bằng chứng cần thiết: Qt chạy headless không tìm thấy font nào, mọi ký tự vẽ thành ô vuông. Trên máy Linux tối giản (air-gap) rủi ro tương tự với Ә Ғ Қ Ң Ө Ұ Ү Һ І. → **CP-11** |
| C18 | Bản dịch Kazakh do người bản ngữ soát; đến khi đó gắn nhãn "bản nháp" | **MỘT PHẦN** | Nhãn "Қазақша (nháp)" có ở combo (spec nói đặt trong Cài đặt). Chưa có người bản ngữ soát. → **CP-12** |

## D. Bộ test (spec mục 6)

| # | Tầng | Ngưỡng spec | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| D1 | T0 unit: timing chính xác từng mẫu | — | **ĐẠT** | `tests/unit/` timing. |
| D2 | T0: encode → decode audio sạch 10–40 WPM, ba profile, **CER = 0** | CER = 0 | **CHƯA ĐẠT** | `test_trained_model_roundtrip` (gate) FAIL: `ПРИВЕТ МИР` → `ПРИВЕТ МЕРН`, CER 0,2. Lưu ý thêm: chính test này đặt ngưỡng **0,1** chứ không phải 0 như spec, tức là kể cả khi test xanh vẫn chưa thỏa spec. → gộp vào **CP-01** |
| D3 | T1 ma trận tổng hợp, gate trong pytest | CER < 2 % | **CHƯA ĐẠT** | Xem A1. Bộ T1 có đủ 500 clip đúng ma trận. |
| D4 | T2 bản ghi thật (ARRL, Wikimedia, SRAA, QSO Ý, Nga/Kazakh tự thu) | ARRL < 2 %, QSO tay < 10 % | **CHƯA LÀM** | Không có `testdata/private`. → **CP-02** |
| D5 | T3 live qua loopback | lệch CER < 1 điểm | **HOÃN** | Tuần 5. |
| D6 | Baseline công cụ sẵn có trên T2 | ghi số đối chứng | **MỘT PHẦN** | DeepCW và MorseCodeToolkit đã đo **trên T1** (`docs/research/04-pretrained-baselines.md`). ggmorse, pycw, multimon-ng chưa đo; chưa có T2 để đo. → **CP-13** |
| D7 | Bộ test mặc định xanh, ruff sạch | — | **ĐẠT** | 319 test pass trên Windows **và** trên Ubuntu 26.04, `ruff check morsedesk tests tools` sạch ở cả hai. |
| D8 | Bộ test chạy được trên máy đích | — | **ĐẠT sau khi sửa** | Ba test (`test_player_wraps_sounddevice`, `test_play_and_stop_use_player`, `test_farnsworth_above_wpm_errors_for_both_play_and_save`) xanh trên Windows nhưng **đỏ trên Ubuntu** vì `import sounddevice` ném `OSError: PortAudio library not found` khi máy không có `libportaudio2`. Đã thay bằng fixture `fake_sounddevice` bơm module giả vào `sys.modules`, cộng test mới `test_player_reports_when_sounddevice_is_missing` cho đúng tình huống máy đích thiếu PortAudio. |

## E. Xử lý lỗi (spec mục 7)

| # | Tình huống | Hành vi spec | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| E1 | File không đọc được / định dạng lạ | thông báo kèm danh sách định dạng | **ĐẠT** | `audio/io.py:44`; banner đỏ (ảnh 04); QA đối kháng thử 17 input độc hại đều trả dưới 0,5 giây. |
| E2 | Sample rate / số kênh bất kỳ | resample và trộn mono | **ĐẠT** | `load_audio`; QA thử file 8 kênh. |
| E3 | Không dò được tone | kết quả rỗng, cảnh báo, không bịa chữ | **ĐẠT** | `api.py:264`. |
| E4 | Tone thứ hai đáng kể | cảnh báo nêu tần số đang bám | **ĐẠT** | `api.py:277`. |
| E5 | Model/LM thiếu hoặc hỏng | fail ngay lúc khởi động, hộp thoại nêu đường dẫn | **ĐẠT** | `startup.check_models` + `main()` trả 2 (ảnh 10); test `test_main_exits_2_when_models_missing`. |
| E6 | Thiết bị thu bận hoặc mất | liệt kê lại, nút thử lại | **HOÃN** | Tuần 5. |
| E7 | Tràn buffer live | bỏ khối, tăng bộ đếm | **HOÃN** | Tuần 5. |
| E8 | Tin cậy thấp | tô đỏ, hiện fallback DSP nếu bật | **ĐẠT phần hiển thị** | Màu đỏ `#f7c6c6` dưới 0,5; `fallback_label`. Công tắc bật/tắt fallback nằm ở trang Cài đặt (tuần 5); CLI đã có `--no-fallback`. |
| E9 | File dài hơn 1 giờ | xử lý streaming, thanh tiến trình, nút hủy | **CHƯA ĐẠT** | Thay bằng từ chối file dài hơn 20 phút. Khác hẳn spec. → **CP-08**, **CP-09**, **CP-14** |
| E10 | Mọi ngoại lệ ghi log xoay vòng tại `~/.local/share/morsedesk/logs/` | | **LỆCH** | Có log xoay vòng 1 MB × 3, nhưng đường dẫn là `<AppDataLocation>/MorseDesk/MorseDesk/logs/` do `QStandardPaths` lồng tên tổ chức và tên ứng dụng. Cần chốt: theo spec hay theo Qt. → **CP-15** |

## F. CLI (spec mục 8)

| # | Điều khoản | Trạng thái | Bằng chứng |
|---|---|---|---|
| F1 | `morsedesk decode FILE [--profile] [--json] [--no-fallback]` | **ĐẠT** | `morsedesk decode --help` có đủ, thêm `--engine`, `--no-lm`, `--beam`, `--lm-dir`. |
| F2 | `morsedesk encode "TEXT" --profile --wpm [--farnsworth] [--tone] [--snr] --out` | **ĐẠT** | `morsedesk encode --help`. |
| F3 | `morsedesk devices` | **ĐẠT** | Có trong danh sách lệnh con. |
| F4 | `morsedesk bench --set t1\|t2` | **LỆCH** | Dùng `--manifest <đường dẫn>` thay cho `--set`; linh hoạt hơn nhưng khác spec. Ghi lại, không sửa. |

## G. Đóng gói (spec mục 9)

Toàn bộ **HOÃN** sang tuần 6: container Ubuntu 22.04, PyInstaller onedir, AppImage, `QT_QPA_PLATFORM_PLUGIN_PATH`,
gói kèm model/profile/`.qm`/font, mục tiêu dưới 400 MB, kiểm không có lời gọi mạng bằng `strace`, `SHA256SUMS`.
Hai việc của tuần 6 đã có đầu vào từ tuần 4: **CP-04** (hồ sơ giấy phép) và **CP-11** (font).

---

## H. Chốt kiểm (checkpoint) cho các yêu cầu chưa đạt

Cập nhật 22/09: thêm **CP-17** (dấu câu tiếng Nga) phát hiện khi đối chiếu với nghiên cứu ngoài.

Mỗi chốt kiểm có tiêu chí nghiệm thu đo được. "Chặn" nghĩa là không thể tuyên bố v1 nếu chưa đạt.

| ID | Nội dung | Mức | Tiêu chí nghiệm thu | Tuần |
|---|---|---|---|---|
| **CP-01** | Chất lượng giải mã chưa đạt gate | **Chặn v1** | `uv run pytest -m gate` xanh, hoặc gate được định nghĩa lại và người dùng duyệt. Đề xuất ba tầng dựa trên mốc DeepCW: A `clean` + SNR ≥ 10 ≤ 3 %, B `clean`+`mp3`+`qrn` + SNR ≥ 3 ≤ 10 %, C `qsb` ≤ 45 %, `qrm` báo riêng. Kèm T0 roundtrip ba profile CER = 0. | 5–6 |
| **CP-02** | Không có bộ T2 bản ghi thật | **Phần lớn đã xong** | `testdata/private/` có ARRL W1AW 11 tốc độ kèm text, tối thiểu 20 clip QSO tay; `morsedesk bench` chạy được trên T2; số đo ghi vào `docs/research/02-baseline-numbers.md`.  **Tiến triển 22/09:** `tools/fetch_t2.py` đã tải 10 bản ghi thật của ARRL W1AW (5-40 WPM, 124 phút, kèm đáp án) vào `testdata/private/t2/`; `bench` chạy được trên T2 với `source_gate` theo từng nguồn; số đo đã ghi vào `docs/research/02-baseline-numbers.md`. Bộ T2 lập tức lộ ra lỗi lệch phân bố SNR mà 500 clip T1 không thể lộ, và sau khi sửa thì engine `onnx` đạt **4,0 %** trên bản ghi thật (bốn bản dưới 2 %). Còn thiếu: tối thiểu 20 clip QSO gõ tay, và phần tiếng Nga/Kazakh. | 5 |
| **CP-03** | Nhận diện ngôn ngữ 58,4 % so với mục tiêu 95 % | **Đạt có điều kiện** | Hoặc đạt 95 % trên một bộ đo có nội dung phân biệt được ngôn ngữ, hoặc người dùng duyệt hạ mục tiêu kèm lý do (radiogram ham trung lập ngôn ngữ).  **ĐO LẠI 22/09 — mục tiêu ĐẠT khi bản tin đủ dài:** nhận diện đúng 100 % từ 50 ký tự trở lên (8 clip mỗi ô, SNR 15 dB, 20 WPM, cả ba profile); ở 20 ký tự chỉ còn 71 % và chỗ hỏng duy nhất là `ru` bị đọc thành `kk-cyrl-ru`, vì bảng Kazakh là bảng Nga cộng 9 chữ nên bản tin Nga ngắn không có gì loại trừ Kazakh. Con số 58,4 % cũ là hệ quả của T1 (bản tin trung bình 13 ký tự), không phải của thuật toán. Đề nghị nghiệm thu: giữ mục tiêu 95 % kèm điều kiện độ dài tối thiểu 50 ký tự, và giao diện nói rõ 'chưa đủ dữ liệu' với bản tin ngắn hơn. | 5 |
| **CP-04** | Chưa có hồ sơ giấy phép bên thứ ba | **ĐÓNG 22/09: người dùng chốt bỏ qua** | Người dùng chốt ngày 22/09: phần mềm nội bộ 100 %, chạy offline, không thương mại hóa, nên không cần hồ sơ giấy phép bên thứ ba, `THIRD_PARTY.md` hay mô tả relink Qt theo LGPL. Vẫn ghi lại ở đây: nếu về sau phân phối ra ngoài tổ chức thì đây là việc phải làm trước, và `docs/research/04-pretrained-baselines.md` mục "Giấy phép và phạm vi sử dụng" đã liệt kê sẵn giấy phép của các model mượn. | — |
| **CP-05** | Chạy trên Linux mới kiểm được một phần | **Chặn v1** | Đã xong trên Ubuntu 26.04 (test, ruff, i18n, CLI, cửa sổ Wayland, font Kazakh). Còn lại: bộ test đầy đủ xanh trên **Ubuntu 22.04 và 24.04** x86_64; `morsedesk-gui` mở thật và giải mã một file trên máy Linux không phải WSL. | 5 |
| **CP-06** | Chưa xuất được MP3 | **ĐÓNG 22/09** | `Encoder` xuất MP3 qua libsndfile nếu có lame, nếu không thì gọi `ffmpeg` ngoài, nếu không thì báo rõ; khả năng này hiện trong trang Cài đặt; test bao cả ba nhánh.  **Đã đóng 22/09:** libsndfile 1.2.2 đã có LAME nên là đường chính; thêm nhánh ffmpeg ngoài và nhánh báo lỗi nêu rõ cách khắc phục. `mp3_capability()` cho trang Cài đặt biết trạng thái. Test phủ cả ba nhánh (`tests/unit/test_mp3_export.py`). Phần hiển thị trong trang Cài đặt nằm ở nhánh giao diện tuần 5. | — |
| **CP-07** | `save_audio` không ghi được `.aif`, `.oga` | **ĐÓNG 22/09** | Ghi và đọc lại được mọi đuôi trong `SUPPORTED_EXT`, hoặc thu hẹp `SUPPORTED_EXT` cho đúng khả năng thật; test bao mọi đuôi.  **Đã đóng 22/09:** Nguyên nhân: libsndfile gọi định dạng theo TÊN chứ không theo đuôi file, `.aif` thuộc `AIFF` và `.oga` thuộc `OGG`. Thêm bảng ánh xạ `EXT_TO_FORMAT` và truyền `format=` tường minh; test roundtrip mọi đuôi trong `SUPPORTED_EXT` (`tests/unit/test_audio_ext.py`). | — |
| **CP-08** | Không có tiến trình phần trăm khi giải mã | **ĐÓNG 22/09** | Thanh tiến trình hiện phần trăm theo số cửa sổ đã xử lý cho file dài hơn 30 giây; test kiểm tín hiệu tiến trình tăng đơn điệu.  **Đã đóng 22/09:** Thanh tiến trình chuyển từ vô định sang phần trăm theo số cửa sổ đã chạy qua mô hình; `DecoderWorker.progress(done, total)`; test kiểm tiến trình tăng đơn điệu và tổng không đổi giữa chừng (`tests/unit/test_progress_cancel.py`, `tests/app/test_progress_ui.py`). | — |
| **CP-09** | Không hủy được lần giải mã đang chạy | **ĐÓNG 22/09** | Nút Hủy dừng trong vòng 1 giây với file 20 phút; worker trở lại trạng thái rảnh; test kiểm không rò thread.  **Đã đóng 22/09:** Nút Hủy hiện khi đang giải mã, đặt `threading.Event` mà lõi kiểm ở mỗi cửa sổ; worker phát `cancelled(path)`, hạ cờ bận và nhận yêu cầu tiếp theo. Test kiểm thẳng `_handle` và `run()` thay vì qua signal để không đua (`tests/app/test_worker_progress.py`). | — |
| **CP-10** | Cảnh báo của lõi và của trình phát chưa qua `tr()` | **ĐÓNG 22/09** | Mọi chuỗi tới banner đều có bảng mã và bản dịch ru/kk; `tools/build_i18n.py --check` vẫn xanh; test kiểm banner tiếng Nga không chứa ký tự Latin của thông điệp gốc.  **Đã đóng 22/09:** `morsedesk/warnings.py` giữ năm mã cảnh báo kèm tham số; `DecodeResult.warning_codes` chạy song song với `warnings`; giao diện dịch bằng literal `tr()` để lupdate trích được; bản dịch ru/kk đầy đủ, `tools/build_i18n.py --check` xanh (`tests/unit/test_warning_codes.py`). | — |
| **CP-11** | Chưa đóng gói font cho chữ Kazakh | **Chặn phát hành** | AppImage kèm DejaVu Sans và Noto Sans, đặt làm font ứng dụng; ảnh chụp trên VM Ubuntu sạch hiện đủ Ә Ғ Қ Ң Ө Ұ Ү Һ І. | 6 |
| **CP-12** | Bản dịch Kazakh chưa được người bản ngữ soát | Nên có | Người bản ngữ soát `translations.json`, gỡ nhãn "nháp" khỏi combo; ghi ngày soát vào spec. | 6 |
| **CP-13** | Chưa đo baseline ggmorse, pycw, multimon-ng | Nên có | Ba công cụ chạy trên cùng bộ T1 (và T2 khi có), số đo thêm vào `docs/research/04-pretrained-baselines.md`. | 5 |
| **CP-14** | Trần 20 phút thay vì xử lý file dài hơn 1 giờ | **ĐÓNG 22/09** | Hoặc giải mã theo luồng cho file tới 1 giờ với tiến trình và nút hủy, hoặc người dùng duyệt trần 20 phút và spec mục 7 được sửa cho khớp.  **Tiến triển 22/09:** hai thứ chặn việc nâng trần đã xong — tiến trình phần trăm (CP-08) và nút Hủy (CP-09) đã có, và beam search nay tuyến tính theo độ dài thay vì bậc hai (0,09 ms mỗi ký tự, không đổi từ 100 tới 1600 ký tự). Bản ghi thật dài nhất trong T2 là 37 phút và đã giải mã được. Còn lại: đo thật một file 60 phút để chốt `MAX_SECONDS`.  **ĐÓNG 22/09:** `MAX_SECONDS` nay là 1 giờ đúng spec mục 7. Ba thứ từng chặn đã gỡ: tiến trình theo cửa sổ (CP-08), nút Hủy (CP-09), beam search tuyến tính thay vì bậc hai, và bộ nhớ hằng số ở khâu ước lượng tone cùng envelope. Đo thật trên file 60 phút: **162 giây** (nhanh hơn thời gian thực 22 lần) và **583 MB** đỉnh bộ nhớ, so với 5 414 MB trước khi sửa. | — |
| **CP-17** | Dấu câu tiếng Nga va chạm với ITU | **ĐÓNG 22/09: người dùng chốt giữ quy ước ITU** | Đối chiếu ngày 22/09: quy ước Nga `.` = `......` **không có trong bảng của mình**; `,` = `.-.-.-` bị giải thành `.`; `!` = `--..--` bị giải thành `,`. Ba lỗi này **không bao giờ lộ ra trong bộ test** vì T1 do chính bảng của mình sinh ra. Sửa cần: (a) cho phép một mẫu giải ra nhiều chữ ở chiều giải mã trong khi chiều mã hóa vẫn duy nhất (hiện `Profile.__post_init__` ném lỗi nếu một chữ thuộc hai mẫu), và (b) **bản ghi tiếng Nga thật để đo**, vì thêm nhập nhằng có thể làm xấu chính T1. **Người dùng đã chốt ngày 22/09: giữ nguyên quy ước ITU cho cả ba profile.** Không sửa. Ghi lại ở đây để người đọc sau không tưởng là bỏ sót: nếu về sau có bản tin dùng quy ước Nga thì đây là chỗ cần đụng tới. | — |
| **CP-16** | Plugin nền tảng `xcb` không khởi tạo được trên Ubuntu tối giản | **Chặn phát hành** | Thiếu 8 thư viện hệ thống: `libxcb-cursor.so.0`, `libxcb-icccm.so.4`, `libxcb-image.so.0`, `libxcb-keysyms.so.1`, `libxcb-render-util.so.0`, `libxcb-util.so.1`, `libxcb-xkb.so.1`, `libxkbcommon-x11.so.0`. AppImage phải đóng gói đủ (spec mục 9 đã yêu cầu kèm plugin xcb), hoặc tuyên bố chỉ hỗ trợ Wayland. Nghiệm thu: AppImage mở được cửa sổ trên VM Ubuntu 22.04 sạch ở cả phiên X11 lẫn Wayland. | 6 |
| **CP-15** | Đường dẫn log khác spec | **ĐÓNG 22/09** | Chốt một trong hai: theo Qt (`<AppDataLocation>/MorseDesk/MorseDesk/logs/`) và sửa spec, hoặc ép đúng `~/.local/share/morsedesk/logs/` và sửa mã.  **Đã đóng 22/09:** Log về đúng `~/.local/share/morsedesk/logs/` như spec mục 7: trên Linux theo chuẩn XDG thay vì `QStandardPaths.AppDataLocation` (Qt ghép cả tên tổ chức lẫn tên ứng dụng nên cho ra `.../MorseDesk/MorseDesk/logs`); nền tảng khác vẫn theo Qt để test chạy được trên máy dev (`tests/app/test_log_path.py`). | — |

### Thứ tự đề nghị cho tuần 5

1. **CP-05** trước tiên: chạy trên Linux có thể lộ lỗi làm thay đổi mọi ước lượng còn lại.
2. **CP-02** rồi **CP-01**: có bản ghi thật mới biết cải thiện nào có tác dụng; nếu không, việc chỉnh
   model chỉ là tối ưu trên dữ liệu tổng hợp của chính mình.
3. **CP-03** cùng đợt với CP-02 vì dùng chung dữ liệu.
4. Nhóm giao diện **CP-08, CP-09, CP-10, CP-14** làm chung với chế độ live, vì đều đụng
   `DecoderWorker` và đằng nào cũng phải đổi kiến trúc thread (xem C11).
5. **CP-06, CP-07, CP-13, CP-15** là việc nhỏ, chèn vào chỗ trống.
6. **CP-04, CP-11, CP-12** dồn vào tuần 6 cùng đóng gói.

---

## Phụ lục: những gì đã được kiểm chứng bằng cách chạy thật

Để tránh nhầm "có test" với "chạy được", các mục sau đã chạy với model ONNX thật và ba LM thật:

| Phép kiểm | Kết quả |
|---|---|
| Kịch bản đầu-cuối 29 mục (mở file, đổi profile, kéo thả, lỗi, xuất, đổi ngôn ngữ, tạo mã, đóng) | 29/29 đạt |
| Giải mã lần đầu (gồm nạp ONNX và LM) | 0,57 giây |
| Giải mã các lần sau | 0,41 giây |
| Roundtrip Tạo mã → WAV → Giải mã, profile Kazakh | "СӘЛЕМ" đúng nguyên văn |
| Đóng cửa sổ khi đang giải mã file 2 phút | Hoãn đóng 0,51 giây, thoát mã 0 |
| Dán 100 000 ký tự vào tab Tạo mã | 1,03 giây, 43 MB |
| QA đối kháng | 99 phép thử, 13 kịch bản |
| Tương phản chữ trên chip tin cậy (đo trên ảnh chụp) | 13,89:1 (chuẩn AA cần 4,5:1) |
| Cài mới từ `uv.lock` vào venv sạch | 22 module Qt, không có module chỉ-GPL, 52 test GUI xanh |
| Toàn bộ bộ test trên Ubuntu 26.04 LTS (WSL, Python 3.11) | exit 0; ruff sạch; `build_i18n --check` sạch |
| CLI giải mã trên Linux với model thật | `ТНЬ ФЕР ЦАЛЛ`, đúng nguyên văn tham chiếu của clip |
| Cửa sổ Qt trên Linux | dựng được bằng plugin `wayland`; `xcb` thiếu 8 thư viện hệ thống |
| Chữ Kazakh trên Ubuntu | hiện đủ Ә Ғ Қ Ң Ө Ұ Ү Һ І với 89 font hệ thống (có DejaVu) |
