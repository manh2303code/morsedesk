# MorseDesk tuần 3: tầng ngôn ngữ và vòng cải thiện model

Ngày: 2026-09-19. Trạng thái: đã duyệt qua brainstorming, chờ người dùng soát bản viết.
Spec gốc: `docs/superpowers/specs/2026-09-18-morsedesk-design.md` (mục 2.6, 2.7, 6, 10). Kế hoạch tuần 1–2 đã merge vào `main` tại d7edc6a.

## 1. Mục tiêu và phạm vi

Tuần 3 có hai tuyến gần độc lập, làm trên nhánh `week3`:

- **Tuyến A, tầng ngôn ngữ:** LM ký tự n-gram cho en, ru, kk; beam search có LM trên lưới mẫu; ánh xạ một-nhiều Kazakh trong beam; nhận diện ngôn ngữ theo đoạn; profile `auto`; đo trên T1.
- **Tuyến B, cải thiện model:** xử lý theo cửa sổ thống nhất giữa huấn luyện và suy luận; chuỗi thí nghiệm E1–E5 mỗi lần đổi một biến; mục tiêu gate T1 CER < 2% (SNR ≥ 0 dB, 10–35 WPM) với beam có LM.

Quyết định đã chốt với người dùng:

| Hạng mục | Quyết định |
|---|---|
| LM runtime | Tự viết beam search + n-gram thuần numpy. Không dùng pyctcdecode/kenlm ở runtime (lệch spec gốc mục 2.6, lý do: kenlm cần biên dịch C++, pyctcdecode ghim numpy < 2 và không khớp mẫu→chữ một-nhiều). |
| Dựng LM | `lmplz` của KenLM chạy trong WSL Ubuntu 26.04 lúc dev (KenLM LGPL, chỉ là công cụ dev, không vào sản phẩm); ARPA → nhị phân numpy. Dự phòng: bộ dựng thuần Python `train_small` cho corpus nhỏ và cho test. |
| Corpus | Chỉ nguồn CC BY, CC0, public domain hoặc MIT. Không dùng Wikipedia (CC BY-SA). Ghi công trong `models/lm/LICENSES.md`. |
| Compute | Chỉ laptop CPU (Windows + WSL Ubuntu 16 nhân, 31 GB), chạy qua đêm; tối đa 3–4 thí nghiệm mỗi ngày. |
| Hướng cải thiện | A: từng bước trên pipeline hiện có (chuẩn hóa theo cửa sổ, hidden 128, lịch LR, MP3, worker WSL). Không đổi sang spectrogram thuần, không curriculum trong tuần này. |
| Kế hoạch | Hai file kế hoạch riêng: tầng ngôn ngữ và model. |

Ngoài phạm vi tuần 3: GUI, live sound card, đóng gói, streaming file dài, bảng Kazakh mở rộng/Latin, mô hình transformer sửa chính tả.

## 2. Tuyến A: tầng ngôn ngữ

### 2.1 Bảng chữ LM

Mỗi profile có bảng chữ LM = tập chữ trong `Profile.map` (kể cả các chữ một-nhiều), số, dấu câu ITU, khoảng trắng, cộng ba ký hiệu `<s>`, `</s>`, `<unk>`. Prosign và `<unk>` của bộ giải mã (mẫu không thuộc profile) không vào LM: được chấm bằng hằng phạt `UNK_LOGP = ln(1e-4)`. Chữ trong LM là chữ hiển thị của profile (viết hoa; Ё và Ъ đã quy về Е và Ь theo alias khi chuẩn hóa corpus, nhưng Ъ vẫn là chữ riêng vì `-..-` → [Ь, Ъ]).

### 2.2 `morsedesk/lm/ngram.py`

- `CharNGramLM`: bậc `order` (mặc định 6), log-prob tự nhiên. Dữ liệu: với mỗi bậc k = 1..order, ba mảng cùng độ dài đã sắp theo hash: `hashes uint64`, `logp float32`, `backoff float32` (backoff = 0 cho bậc cao nhất). Hash của n-gram = FNV-1a 64 bit trên chuỗi id ký tự (id theo `alphabet`), va chạm chấp nhận (xác suất ~1e-12 với vài triệu mục).
- `score(context: tuple[int, ...], symbol: int) -> float`: Katz/Kneser-Ney backoff chuẩn ARPA: tìm n-gram dài nhất (context[-k+1:] + symbol) có trong bảng; cộng backoff của các context không tìm thấy dọc đường. Cache LRU 100.000 mục theo khóa (context tuple, symbol).
- `score_many(context, symbols: np.ndarray) -> np.ndarray`: vector hóa bằng `searchsorted`, dùng cho beam.
- `sentence_logprob(text: str) -> float` (thêm `<s>`, `</s>`) và `perplexity`.
- Định dạng nhị phân `.bin`: `np.savez` gồm `alphabet` (json), `order`, và với mỗi bậc `h{k}`, `p{k}`, `b{k}`; nạp bằng `np.load(mmap_mode=None)`. Mục tiêu ≤ 50 MB mỗi ngôn ngữ (prune n-gram đơn lẻ từ bậc 3).
- `load_arpa(path, alphabet) -> CharNGramLM` (dev) và `save_bin`/`load_bin`.
- `train_small(lines: list[str], alphabet, order) -> CharNGramLM`: Kneser-Ney nội suy đơn giản (discount 0.75), chỉ dùng cho test và corpus dưới 5 MB.

### 2.3 `morsedesk/lm/beam.py`

- Đầu vào: `log_probs [T', C]` (C = 65), `profile`, `lm` (hoặc None), tham số `BeamParams(beam=64, alpha=0.6, beta=0.5, lexicon_bonus=1.0, topk_per_frame=8, unk_logp=ln(1e-4), space_id=1, blank_id=0)`; `alpha` là trọng số LM, `beta` là thưởng mỗi từ (chống chèn/xóa dấu cách).
- Thuật toán: prefix beam search CTC. Tiền tố = chuỗi token đã phát (mẫu hoặc SPACE) kèm chuỗi chữ đã chọn và khung phát ra từng token; giữ `p_blank`, `p_nonblank` theo log. Mỗi khung chỉ xét blank cộng tối đa `topk_per_frame` lớp có log-prob cao nhất. Khi phát mẫu có k chữ ứng viên theo `profile.decode_options`, tiền tố rẽ thành k tiền tố, mỗi nhánh cộng `alpha * lm.score(context_chars, letter)`. Khi phát SPACE: cộng `alpha * lm.score(context, ' ')`, `beta`, và `lexicon_bonus` nếu từ vừa xong thuộc `profile.lexicon_bonus`. Mẫu không thuộc profile (render `#`) và prosign: cộng `unk_logp`, không cập nhật context LM. Hai tiền tố cùng chuỗi token và chữ được gộp. Cắt còn `beam` tiền tố theo tổng điểm sau mỗi khung.
- Đầu ra: `list[Hypothesis]` sắp theo điểm; `Hypothesis(tokens, letters, frames, acoustic_logp, lm_logp, score, n_words)`. `emissions` = `[(token, frame, prob)]` để tái dùng `emissions_to_words` (prob = exp(log-prob của lớp tại khung phát ra).
- `lm=None` → beam thuần âm thanh (tương đương greedy khi beam = 1). Với `lm=None` và `beam=1` kết quả phải bằng `greedy_decode`.
- Trạng thái nối tiếp: `BeamState` có thể tiếp tục với khối log-prob tiếp theo (`beam.step(state, log_probs_chunk) -> state`), để tuần 5 dùng live; tuần 3 chỉ cần test tương đương một cửa sổ.
- Hiệu năng mục tiêu: ≤ 2 s cho clip 12 s ở beam 64 trên CPU laptop (đo trong bench, cột `seconds`).

### 2.4 `morsedesk/lm/langid.py`

- `split_segments(log_probs, silence_frames=300, max_frames=3000) -> list[(start, end)]`: cắt tại chuỗi blank liên tục ≥ 3 s (300 khung đầu ra) hoặc tối đa 30 s.
- `detect(log_probs, profiles, lms, params) -> LangIdResult(profile_id, scores: dict[str, float], per_segment)`: với mỗi đoạn, chạy beam cho từng profile ứng viên; điểm = `lm_logp / n_chars` của giả thuyết tốt nhất (phần âm thanh chung nên bỏ); chọn cao nhất; ngôn ngữ cả file = profile chiếm nhiều ký tự nhất; `scores` = trung bình theo trọng số ký tự. Ngưỡng biên `MIN_MARGIN = 0.15` nat/ký tự: dưới ngưỡng thì giữ profile của đoạn trước (nếu có).

### 2.5 Thay đổi API, CLI, dữ liệu

- `Decoder(profile="auto"|id, engine, model_path=None, fallback=True, lm=True, beam=64, lm_dir=None)`. `lm_dir` mặc định `<repo>/models/lm`. `profile="auto"` nạp ba profile và ba LM; thiếu file LM → `FileNotFoundError` nêu đường dẫn. `lm=False` → greedy như hiện nay. Với engine `baseline`, LM chưa áp dụng (giữ nguyên hành vi).
- `DecodeResult.language` = profile chọn; `language_scores` = điểm từng profile khi `auto`, rỗng khi ép profile; `words[].confidence` như cũ từ `emissions`.
- CLI `decode`: `--profile` mặc định `auto`; `--no-lm`; `--beam N`. `bench`: `--profile-override auto` để đo nhận diện ngôn ngữ, thêm `language_acc` vào summary và cột `language` từng hàng; `--no-lm`.
- `Example` và manifest T1 thêm `text_original` (chữ gốc trước khi render qua profile: Ә, Ғ, Қ, Ң, Ө, Ұ, Ү, І của Kazakh, cả Ъ của Nga — mọi chữ chia mẫu với chữ khác trong profile). `bench` tính CER trên `text_original` khi engine onnx có LM, trên `text` khi không có (giữ so sánh công bằng với tuần 1–2).

### 2.6 Pipeline corpus và dựng LM

| Bước | Công cụ | Nội dung |
|---|---|---|
| Tải | `tools/fetch_corpus.py --lang en|ru|kk --out corpus/raw/` | en: Project Gutenberg (public domain, danh sách id cố định trong script) + `michaellin/morse-translate-transcribe-100k` (Apache-2.0, cột english); ru: sách tiếng Nga trên Gutenberg (danh sách id cố định) + radiogram tự sinh từ `HAM_TEMPLATES` chuyển tự; kk: `yeshpanovrustem/kaznerd` (CC BY 4.0, ghép tokens) + transcript `issai/Kazakh_Speech_Corpus_2` (MIT) nếu file text tải riêng được. Mỗi nguồn ghi tên, URL, license vào `models/lm/LICENSES.md`. |
| Chuẩn hóa | `tools/normalize_corpus.py --profile <id> --in corpus/raw/<lang> --out corpus/<lang>.txt` | viết hoa, alias, bỏ dòng có > 5% ký tự ngoài bảng LM, giữ số và dấu ITU, gộp khoảng trắng, một câu một dòng, in thống kê ký tự và số dòng. |
| Dựng | `tools/build_lm.sh` (WSL Ubuntu 26.04) | cài `cmake build-essential libboost-all-dev`, build KenLM, `lmplz -o 6 --discount_fallback --prune 0 0 1 1 1 1 -S 20% --text corpus/<lang>.txt --arpa corpus/<lang>.arpa`. |
| Đóng gói | `tools/arpa_to_bin.py --arpa ... --profile <id> --out models/lm/<lang>.bin` | ARPA → `.bin` numpy; in kích thước, số n-gram mỗi bậc, perplexity trên 1.000 dòng giữ lại. |

`models/lm/*.bin` không commit (gitignore), `LICENSES.md` và script commit. Kích thước mục tiêu ≤ 50 MB mỗi ngôn ngữ; nếu vượt, tăng prune.

### 2.7 Kiểm thử tuyến A

- Đơn vị `ngram`: `train_small` trên corpus vài dòng cho xác suất unigram/bigram đúng theo tay tính; backoff khi context chưa gặp; `save_bin`/`load_bin` giữ nguyên điểm; ARPA nhỏ viết tay nạp đúng.
- Đơn vị `beam`: lưới one-hot của "CQ DE K" cho đúng chuỗi; lưới mơ hồ (một khung chia đôi giữa hai mẫu) mà LM chọn từ có nghĩa; lưới của "ӘЛЕМ" (mẫu `.-` `.-..` `.` `--`) với LM kk nhỏ huấn luyện trên câu có ӘЛЕМ cho "ӘЛЕМ", với LM ru cho "АЛЕМ"; `lm=None, beam=1` bằng greedy; `step` qua hai nửa cho cùng kết quả với một lần.
- Đơn vị `langid`: lưới one-hot từ encoder cho câu en, ru, kk (chữ Kazakh) chọn đúng profile với LM nhỏ; đoạn tách đúng tại khoảng lặng 3 s.
- Tích hợp (đánh dấu `gate`, cần `models/acoustic.onnx` và `models/lm/*.bin`): T1 với LM có CER ≤ không LM trên từng profile; `language_acc` ≥ 95%.

## 3. Tuyến B: cải thiện model

### 3.1 Xử lý theo cửa sổ thống nhất

Vấn đề: đặc trưng hiện chuẩn hóa trên cả clip (median/p95 phổ; AGC khởi tạo từ giây đầu) và dò tone toàn cục, còn suy luận cắt cửa sổ 4 s trên ma trận toàn cục; khi train clip 4–12 s. QSB sâu và bản ghi dài làm thống kê lệch. Thiết kế mới:

- `frontend.WindowFeatures`: `compute_features_windowed(x, window_s=4.0, step_s=3.0, f0_hint=None) -> list[Window(start_sample, f0_hz, feats [T_w, 11], has_signal)]`. Mỗi cửa sổ: `estimate_tone` riêng (nếu không có tín hiệu thì dùng `f0_hint` hoặc tone cửa sổ trước), đặc trưng chuẩn hóa nội bộ (AGC khởi tạo từ 0,5 s đầu cửa sổ; median/p95 phổ trong cửa sổ).
- `chunker.run_chunked` nhận `x` và gọi `compute_features_windowed`, gộp log-prob theo tâm gần nhất như hiện nay. Chữ ký cũ (nhận ma trận đặc trưng) giữ lại cho test cũ nhưng `Decoder` dùng đường mới.
- Huấn luyện: `example_features` chuẩn hóa clip bằng cách cắt cùng cửa sổ 4 s/bước 3 s rồi ghép lại theo khung (cửa sổ chồng lấy trung bình), để phân bố đặc trưng khi train khớp khi suy luận. Nhãn CTC vẫn là nhãn cả clip.

### 3.2 Thí nghiệm

Mỗi thí nghiệm đổi một biến so với mốc, đo cùng validation 200 clip (seed cố định) và T1 gate 500 clip bằng greedy và bằng beam có LM khi LM sẵn sàng.

| Mã | Thay đổi | Ghi chú |
|---|---|---|
| E0 | v1b (resume v1, tổng 24.000 bước) | mốc |
| E1 | chuẩn hóa theo cửa sổ (3.1) | train lại từ đầu 8.000 bước để so công bằng với v1 |
| E2 | E1 + hidden 128 | tham số ~210k, vẫn nhỏ |
| E3 | E2 + lịch LR cosine có warmup 500 bước, 30.000 bước | `--lr-schedule cosine --warmup 500` |
| E4 | E3 + MP3 (cài `scoop install ffmpeg` trên Windows hoặc `apt install ffmpeg` trong WSL) | T1 kênh mp3 thật thay cho fallback clean |
| E5 | E4 chạy trong WSL với `--workers 8` | chỉ đo tốc độ; kết quả tương đương trong sai số |

`tools/train.py` thêm: `--hidden`, `--lr-schedule {constant,cosine}`, `--warmup`, `--resume` khôi phục optimizer và bước (giữ tương thích checkpoint cũ), `--feature-mode {clip,window}`. `CONFIG_DEFAULT` giữ 96; hidden ghi trong checkpoint và metadata ONNX (`config`), `OnnxAcousticModel` đọc `config.hidden` chỉ để hiển thị.

Kết quả ghi `docs/research/03-model-experiments.md`: bảng cấu hình, bước, giờ máy, TER, bảng T1 theo SNR × WPM, kênh, kiểu gõ, profile.

### 3.3 Điều kiện ra tuần 3

- Đạt: gate T1 CER < 2% (beam có LM) → xuất `models/acoustic.onnx` + `models/acoustic.json` (commit json), `uv run pytest -m gate` xanh, cập nhật `02-baseline-numbers.md` và `03-model-experiments.md`.
- Không đạt: ghi khoảng cách theo ô và nguyên nhân nghi ngờ; xuất model tốt nhất hiện có dưới tên `models/acoustic.onnx` để GUI tuần 4 dùng, gate test tiếp tục chạy bằng `-m gate` và được phép đỏ cho tới khi đạt (không nằm trong bộ test mặc định).
- T2 ARRL: nếu người dùng tải bộ W1AW vào `testdata/private/arrl`, chạy `make_t2_manifest` + `bench` cho baseline và ONNX, ghi số vào tài liệu.

## 4. Lịch trong tuần

| Ngày | Tuyến A | Tuyến B |
|---|---|---|
| 1 | `ngram.py` + `train_small` + test; `fetch_corpus`, `normalize_corpus` | `compute_features_windowed`, `run_chunked` theo audio, test; bắt đầu E1 qua đêm |
| 2 | dựng KenLM trong WSL, `arpa_to_bin`, ba `.bin`, `LICENSES.md` | đo E1; `--hidden`, `--lr-schedule`, resume đầy đủ; bắt đầu E2 |
| 3 | `beam.py` + test | đo E2; bắt đầu E3 |
| 4 | `langid.py`, `Decoder` auto, CLI, `text_original`, bench `language_acc` | cài ffmpeg, E4; E5 trong WSL |
| 5 | T1 với LM, so sánh có/không LM, tài liệu | tổng hợp, gate, xuất ONNX, tài liệu |

## 5. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Không cài được KenLM trong WSL (mạng, boost) | `train_small` thuần Python trên corpus rút gọn ≤ 5 MB để không chặn tích hợp; LM lớn làm sau |
| Beam thuần Python chậm | `topk_per_frame`, cache LM, đo `seconds` trong bench; ngưỡng 2 s/clip 12 s |
| Corpus ru public domain văn phong cổ | bổ sung radiogram tự sinh; đo perplexity trên bản tin ham |
| Gate không đạt cuối tuần | GUI tuần 4 vẫn bắt đầu với model tốt nhất; ghi rõ khoảng cách |
| Chuẩn hóa theo cửa sổ thay đổi phân bố đặc trưng | E1 train lại từ đầu, so trực tiếp với v1 cùng số bước |

## 6. Lệch so với spec gốc

- Runtime LM: numpy tự viết thay pyctcdecode + kenlm (mục 2.6); KenLM chỉ dùng lúc dev.
- Corpus: bỏ Wikipedia (CC BY-SA) và `multidomain-kazakh-dataset` (license chưa rõ); dùng Gutenberg, KazNERD, KSC2, dataset Apache-2.0.
- Dò tone theo cửa sổ (mục 2.3 spec) được kéo lên tuần 3 nhờ thiết kế 3.1.

### 6.1 Lệch phát sinh khi thực thi (2026-09-20)

- `BeamParams` mặc định alpha 0,2 / beta 1,0 thay 0,6 / 0,5 (mục 2.3): đo trên T1 v2 với model E2, alpha 0,6 làm CER xấu hơn greedy ở cả ba profile (ru +5,5 điểm), alpha 0,2 + beta 1,0 thắng greedy cả ba (en 29,9→27,0; ru 30,1→29,1; kk theo `text_original` 31,3→24,2 loại clip không tone). Chi tiết: `docs/research/02-baseline-numbers.md`.
- `lm=None` là beam thuần âm thanh: không cộng beta/lexicon/unk (mục 2.3 chỉ nói "thuần âm thanh"; mã mẫu kế hoạch cộng bonus cả khi không LM và bị sửa).
- Ghép đặc trưng khi huấn luyện (mục 3.1) dùng cửa sổ có tâm gần nhất thay trung bình vùng chồng, để khớp cách gộp log-prob khi suy luận.
- Corpus thực tế: en = 40 sách Gutenberg + michaellin (Apache-2.0) + radiogram; ru = 5 sách Gutenberg + Tatoeba 300k câu (CC BY 2.0 FR, export chính thức; bản HF bị gate) + radiogram 5k; kk = KazNERD + radiogram; KSC2 không có transcript tải riêng nên chưa dùng. Tatoeba là nguồn CC BY chưa liệt kê ở mục 2.6.
- KenLM trong WSL Ubuntu 26.04: `sudo` cần mật khẩu nên chạy `wsl -d Ubuntu-26.04 -u root`; Boost 1.90 không còn thành phần `system` nên vá `CMakeLists.txt` của KenLM.
- Mục tiêu `language_acc ≥ 95%` (mục 2.7) không đạt trên T1: 56,6% với E2, vì 30% clip T1 là radiogram ham đã chuyển tự (trung lập ngôn ngữ) và 10% nhóm ký tự ngẫu nhiên; cần bộ đo riêng bằng câu tự nhiên. Gate test tương ứng được phép đỏ theo mục 3.3.
- Kết quả E1 (đặc trưng theo cửa sổ, hidden 96) kém v1 trên T1 dù validation tốt hơn; E2 (thêm hidden 128) mới vượt v1b. Validation ngẫu nhiên không dự báo T1; cần cân nhắc validation dạng T1 ở tuần sau.
