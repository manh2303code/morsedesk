# MorseDesk

Ứng dụng desktop Linux **air-gap** giải mã và tạo mã Morse cho tiếng Anh, Nga, Kazakh.
Người dùng là người Việt: **trả lời bằng tiếng Việt, giữ đủ dấu**. Chữ trong giao diện, mã nguồn
và tài liệu thì theo ngôn ngữ đã dùng ở đó.

**Việc còn phải sửa/đo nằm ở `docs/backlog.md` — đọc và cập nhật mỗi phiên** (phát hiện gì thì ghi
ngay, xong thì chuyển xuống "Đã xong" kèm commit).

## Quy tắc số một: số đo quyết định, không phải lập luận

Dự án này đã nhiều lần đi ngược trực giác, và lần nào cũng chỉ phát hiện được nhờ đo. Trước khi
áp dụng bất cứ thay đổi nào ảnh hưởng chất lượng:

1. Chạy **toàn bộ T1** (500 clip tổng hợp) — không phải một lát cắt.
2. Chạy **T2** (bản ghi ARRL thật) — dữ liệu duy nhất không do chính mình sinh ra. 30 dòng Nga/Kazakh
   trong T2 (thư mục `ebook2cw*`) thực ra do Encoder của dự án sinh (ebook2cw chưa từng được cài) và
   dùng CHÍNH danh sách từ lúc huấn luyện: không phải phép thử độc lập.
3. Chỉ CER trên T1/T2 mới dùng để quyết định. **Chỉnh tham số thì chỉnh trên bộ dev** (xem mục
   "Nhiễu đo" cuối file), T1 chỉ để xác nhận.
4. **Ngoại lệ (25/09): thay đổi VĂN BẢN huấn luyện** quyết định bằng **dev-OOV + T4 (bản ghi thật) +
   long_random**, không bằng T1/dev: ~50 % từ của T1/dev nằm trong chính danh sách 51 từ mà E16 học
   thuộc, nên model "thuộc bài" luôn trông tốt hơn trên chúng (E17: T4 −0,60, dev-OOV −1,15 nhưng
   dev +1,15). Người dùng đặt thước đo: file thật, dài, từ internet.

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
| Đệm nhiễu 0,5 s hai đầu CẢ FILE (ngoài đệm mép trong cửa sổ) | T1 7,78 → 9,55 %, dev 8,07 → 9,83 % | 12 s | **có** |
| Đệm mép trong CẢ cửa sổ không tone / sóng mang liên tục | nhiễu xung ra `R R TU DE`, sóng mang ra `A` (test §7 đỏ) | 12 s | **có** |
| Chỉ đệm-lại cửa sổ model trả RỖNG hoàn toàn | bản tin 130 s 11,3 % so với 1,2 % khi đệm mọi cửa sổ có nhịp phím | 12 s | **có** |
| Gộp cửa sổ bằng trung bình xác suất có trọng số tam giác (thay "cửa sổ tâm gần nhất") | bản tin dài: model-only −0,26 nhưng app/model+LM không có ý nghĩa; **T2 xấu +0,76** (2 file ru/kk) | 12 s | **có** |
| Luật khóa ngôn ngữ live "3 lần giải mã liền nhau cùng ngôn ngữ" | 26/54 phiên 2 phút khóa NHẦM, CER 15–47 %; thay bằng điểm LM tích lũy cả phiên | 12 s | **có** |
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
PYTHONUTF8=1 uv run pytest -p no:warnings          # ~700 test; -p no:warnings để đọc được kết quả
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" wsl.exe -d Ubuntu-26.04 --   bash /mnt/c/Users/Admin/morsedesk/scripts/test_linux.sh   # cùng bộ test trên LINUX (venv riêng, ~25 phút)
PYTHONUTF8=1 uv run python -m morsedesk.cli bench --manifest <m> --engine onnx --out-dir runs/<tên>
                                                   # song song mọi lõi (mặc định); --workers 1 = nghiệm thu
PYTHONUTF8=1 uv run python tools/long_random_eval.py   # bản tin ~2 phút x 3 ngôn ngữ, ~4 phút
                              # --configs live,live-auto = chế độ NGHE đúng như LiveWorker (~20–45 phút)
PYTHONUTF8=1 uv run python tools/make_t1.py --out testdata/generated/t1oov --seed-base 700000 --holdout-text
                                                   # dev-OOV: văn bản model CHƯA thấy (xem Gotchas)
PYTHONUTF8=1 uv run python tools/make_t4.py        # T4: bản ghi THẬT từ internet (SRR ru, ARRL, SAQ...)
PYTHONUTF8=1 uv run python tools/net_eval.py [--model models/eval_X.onnx]   # T7 điện văn mạng thật (3 file + bản chép)
PYTHONUTF8=1 uv run python tools/net_traffic_bench.py [--model ...]  # điện văn tổng hợp x lối phím đo thật x SNR (~10 phút)
bash scripts/regress_pair.sh <worktree mốc> runs/<ra> 8   # hồi quy GHÉP CẶP hai phiên bản mã: T1/dev/dev-OOV/T2/T4 (~1 giờ)
PYTHONUTF8=1 uv run python tools/calibrate_confidence.py   # % "từ ở mức này đúng khoảng" trong tooltip (~25 phút)
                                                   # CHẠY LẠI sau MỖI lần đổi model âm học/LM
PYTHONUTF8=1 uv run ruff check .
PYTHONUTF8=1 uv run python tools/build_i18n.py     # sau MỖI lần thêm/sửa chuỗi self.tr()
PYTHONUTF8=1 uv run morsedesk-gui
PYTHONUTF8=1 uv run python packaging/shots.py <thư mục>   # chụp mọi trang giao diện
PYTHONUTF8=1 uv run python tools/signal_view_latency.py   # hình/s, CPU, độ trễ của khối Tín hiệu
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
- **MỌI lời gọi PortAudio chạy ở MỘT luồng thiết bị** (`audio/engine.py`, 27/09) — kể cả `import
  sounddevice` (= `Pa_Initialize`), liệt kê thiết bị, mở/dừng/đóng. Luồng giao diện không bao giờ gọi
  PortAudio và không bao giờ chờ luồng đó (chỉ đọc trạng thái Python; vị trí phát tính từ đồng hồ callback
  ghi lại, KHÔNG `stream.time` — trên ALSA nó gọi vào driver). PortAudio cấm gọi từ nhiều luồng; driver âm
  thanh có thể treo vĩnh viễn (máy dev 27/09: mở micro lúc loa phát -> audiodg kẹt tới khi khởi động lại).
  Phát và thu KHÔNG BAO GIỜ mở cùng lúc (engine.claim_input/claim_output). Thoát: `main.finish` đóng có
  hạn giờ, kẹt thì TerminateProcess (atexit của sounddevice gọi `Pa_Terminate` và treo theo driver).
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
| `models/acoustic.onnx` | CTC 65 lớp, BiGRU 1 lớp hai chiều × 384, 4,5 MB, 1 119 425 tham số (E21 v0.7.0 = E18 + điện văn mạng + lối phím đo thật) | 65 lớp là **cả ký tự** (`.-`, `-...`), không phải từng chấm gạch |
| `models/lm/{en,ru,kk}.bin` | n-gram ký tự bậc 6, 41 MB | **bảng đếm thống kê, không phải nơ-ron**; chấm cùng đáp án gốc thì đáng ~3,9 điểm CER (T1 13,57 → 9,70 %), riêng Kazakh ~8,5 điểm |
| `models/deepcw/model.onnx` | model ngoài, 15 MB | chỉ profile `en`, dùng đối chứng |

## Gotchas — mỗi dòng ở đây từng tốn thời gian thật

### Đo đạc và mô hình
- **Mọi bộ đo cũ đều là clip NGẮN (<= 12 s = một cửa sổ) nên che mất lỗi của âm thanh dài.** Đến
  24/09 cửa sổ 12 s nằm giữa bản tin dày tín hiệu làm model trả RỖNG cả cửa sổ (26/60): bản tin 2 phút
  sai 50 %, bản ghi ARRL chỉ "đẹp" vì đi đường cổ điển. Sửa bằng đệm nhiễu nền 0,5 s ở mép TRONG
  cửa sổ (`WINDOW_PAD_FRAMES`, `frontend.repad_window`) — CHỈ cửa sổ có tone đang được đánh phím
  (`key_down_fraction` < 0,9: Morse thật 0,41–0,63, sóng mang 1,00). Kiểm âm thanh dài bằng
  `tools/long_random_eval.py`, không chỉ T1/dev/T2.
- **Model âm học có "LM ngầm" và T1/dev KHÔNG thấy nó.** E16 học 60 % văn bản từ danh sách 51/40/40 từ
  (`data/text.py` BUILTIN_WORDS): trên văn thật nó nuốt dấu cách cạnh từ 1–2 chữ (WHENIGOT) và đọc WILL
  thành WALL; nhóm mã ngẫu nhiên thì gần như không lỗi. T1/dev có ~50 % từ nằm trong chính danh sách đó
  → quyết định mọi thay đổi văn bản huấn luyện bằng **dev-OOV** (t1oov) + long_random, không bằng T1.
- **Lỗi của model phụ thuộc vị trí trong cửa sổ**: cùng âm thanh, các cửa sổ chồng nhau đọc khác nhau.
  Nghi phạm: AGC khởi tạo mức nền từ 0,5 s đầu cửa sổ (`agc_init_s`). Gộp trung bình xác suất bị bác (bảng trên).
- **LM ký tự không có OOV cứng nhưng làm HẠI nhóm mã và hô hiệu** (6,2–7,1 bit/ký tự, tệ hơn mô hình
  đều; T1 nhóm mã −1,75 điểm; CZWCI → CQWCI). Corpus một câu một dòng → dấu chấm giữa bản tin bị phạt
  3–4,6 nat; đã sửa bằng ranh giới câu trong beam (`BeamParams.sentence_breaks`, 25/09).
  Chi tiết: .superpowers/sdd/research-lm-2026-09-24.md.
- **Độ tin cậy thô của từ LẠC QUAN** (calibrate_confidence.py, 28/09 với model 0.7.0, ~9 300 từ): >= 0,97 đúng 94 %
  (chế độ nghe 88 %), 0,80–0,90 chỉ đúng 67 %. Ngưỡng gạch chân 0,97 / 0,8 (word_view); tooltip đọc bảng đo ở
  morsedesk/app/data/confidence_calibration.json, không đặt tay con số. Độ tin cậy = mạng nghe RÕ đến đâu, KHÔNG
  phải người gửi đánh đúng: T7 hai chữ số nhân viên sửa (2094->2093, 3408->3498, hai giám khảo cũng nghe như vậy)
  được 0,97 / 0,999. **Tách/ghép từ phải giữ xác suất TỪNG CHỮ** (`Word.char_probs`, api.char_confs): trước 28/09
  từ mới lấy mức thấp nhất của cả từ gốc — 351 (nhịp phím làm chính dồn cả bản tin thành một từ) mọi nhóm 0,23.
- **Chế độ nghe tự nhận ngôn ngữ: CHƯA khóa thì CHƯA chốt** (model/stream.py `_pending`): mỗi lần giải
  bộ đệm ~9,5 s tự chọn ngôn ngữ riêng, chốt ngay là dòng chữ lẫn Latin/Kirin. Chữ chờ hiện dạng tạm,
  quy về một bảng chữ theo mẫu (`Profile.retarget`); quá PIN_FORCE_LETTERS thì khóa theo ngôn ngữ dẫn đầu.
- **Tiếng CLICK của phím điện báo không phải tone** (dsp/clicks.py): bộ dò tone có thể tưởng có tone
  (cộng hưởng cơ học ~1 kHz) và model bịa chữ. Nhận ra bằng số xung/giây + độ nhọn dải cao + tone chỉ
  ngân ngắn (key_down_fraction < 0,15) -> trả rỗng + KEY_CLICKS. CHƯA giải được loại âm thanh này.
- **Model hay phát ký tự ĐẦU TIÊN ngay khung đầu ra số 0** (BiGRU biết trước), bất kể ký tự nằm ở
  đâu — nên không được đệm rồi cắt ở đầu/cuối file.
- **Mismatch giữa lúc huấn luyện và lúc chạy là mỏ vàng.** Hai thắng lợi lớn nhất đều từ đó:
  SNR (train −6…25 dB, bản ghi thật 49–143 dB → thêm dither, CER 89,8 % → 28,9 %) và độ dài cửa
  sổ (clip train 4–12 s nhưng suy luận cắt 4 s → nới lên 12 s, 17,96 % → 10,87 %). Sửa ở khâu
  **suy luận** rẻ hơn huấn luyện lại hàng chục lần.
- **Số: bộ đo tổng hợp KHÔNG thấy lỗi của điện số thật** (27/09). Số tổng hợp sai 0,2 % chữ số,
  trạm số thật (T5: `tools/real_numbers_eval.py`, testdata/private/t5, bản chép Priyom) sai 25 %. Lỗi
  nằm SAU mô hình: số viết tắt (trạm số đánh 0 bằng một gạch dài = mẫu `T`), Auto cắt lưới mỗi 30 s
  rồi ghép chữ (nay: đoạn chỉ để bỏ phiếu ngôn ngữ, văn bản giải cả lưới một lượt), DSP dính các
  nhóm đánh sát nhau mà timing vẫn khớp lưới (nay `dsp_keeps_words`), chế độ nghe chỉ chốt cả từ nên
  dãy số dài hơn bộ đệm 9 s mất phần đầu. Chi tiết: .superpowers/sdd/research-numbers-2026-09-27.md.
- **Số viết tắt chỉ đổi khi chắc** (`morsedesk/numbers.py`): bản tin phải là điện số; nhóm TOÀN chữ số
  + chữ viết tắt được; ngoài nhóm đúng độ dài cố định chỉ đổi `T`; nhóm có dấu câu giữ nguyên (tọa
  độ `…N/…E`, `T=05`), trừ trong điện nhóm cố định (ở đó dấu câu là rác nghe nhầm). `5NN`, hô hiệu
  `UA9T`, lưới `EB84`, nhóm mã SRR `Д088А` không bị đụng — có test cho từng loại.
- **Dấu cách giữa dãy số gõ tay là nhập nhằng THẬT**: khoảng giữa chữ bị kéo tới 4–6,8 dit trùng
  khoảng giữa từ ngắn nhất (4,6 dit); mọi dấu cách "nhầm" đo 27/09 đều rơi đúng chỗ đó. Độ chắc CTC của
  dấu cách không phân biệt được (0,36–0,996 so với 0,51–1,0). Rút khoảng giữa nhóm trong dữ liệu huấn
  luyện (E18) làm model tách SỚM hơn (từ 4,06 dit thay vì 4,66).
- **Mốc CTC của một chữ phát SỚM hơn chữ** (~0,23 x độ dài chữ trước điểm bắt đầu): chế độ nghe chốt
  theo chữ phải lùi mép 2 khoảng cách chữ (`ripe_edge` trong model/stream.py), nếu không chữ số 0
  (năm gạch) bị chốt khi mới nghe được ba gạch -> `Ш`/`#`.
- **File thật từ internet lộ lỗi mà bộ đo tổng hợp không bao giờ lộ** (27/09, testdata/private/t6):
  libsndfile đọc MP3 VBR không header Xing theo bitrate KHUNG ĐẦU rồi DỪNG — mất 30 % bài tập số (sửa:
  audio/mp3len.py đếm khung, chèn khung Xing); xuất OGG dài làm SẬP app (libsndfile Vorbis; sửa: ghi theo
  khối). Không có bản chép thì dựng đáp án bằng hai giám khảo LLM độc lập đọc ảnh đường bao "mù"
  (tools/envelope_strips.py) + tools/multi_decode.py; 5/5 cặp khớp 100 %.
- **Đối chiếu với nhịp phím (morsedesk/keyed.py) chỉ khi CHẮC tín hiệu sạch** — mỗi cổng có một hồi quy
  T1 đứng sau: SNR >= 15 dB (nhiễu xung 10 dB), biên độ ổn định (fading), độ phủ bên trong bản tin (fading
  giấu ký tự dưới ngưỡng phím), nhịp như MÁY mới được sửa/chèn chữ (gõ tay: nhịp phím gộp hai chữ làm
  một), lặng THẬT phải không thuần tone (đáy fading vẫn là tone). Bản đầu không cổng: T1 8,36 -> 14,56 %.
- **Nhịp phím v2 (keyed.py) CHỈ bật với phím NHẸ** (`_light_fist`: >= 60 chấm, chấm/lặng trong ký tự < 0,7 và hụt
  >= 2,5 khung): cho mọi tín hiệu thì nhiễu xung thành "chấm" giữa hai gạch (T1/dev xấu 5 clip). Phím nhẹ tách
  bạch (`separable`) thì nhịp phím là nguồn CHÍNH của `reconcile` — mô hình chưa học lối phím đó mới là bên sai.
- **Phím nhẹ THẬT (T7, đo 28/09): mọi xung hụt ~0,4 đơn vị, LẶNG SAU GẠCH rút ~0,5** — chấm sau gạch KHÔNG ngắn
  hơn chấm khác (giả thuyết ban đầu sai; E20 học theo giả thuyết đó). Đo khoảng lặng "theo nhịp" bị bác (351:
  3,80 -> 7,28 %). Mô hình lối phím dùng CHUNG ở data/keyer.apply_fist, tools/net_traffic_bench.py và test.
- **Điện văn mạng: ký tự đúng nhưng NHÓM DÍNH LIỀN** (`67A3TD3D6746`): thước đo bỏ dấu cách không thấy — T7 chấm
  thêm "nhóm bản chép đúng như hiện ra" (46/108 trước tầng cấu trúc morsedesk/traffic.py). Tầng này chỉ bật khi
  có mốc RMKS theo MẪU (352 bị tự nhận tiếng Nga: `РМКС`); `TO` giữa các nhóm RMKS là một từ (cả 3 file).
- **Bản chép nhân viên KHÁC âm thanh ở chỗ không phải nhóm số**: hô hiệu (352 phát KK3J — đo nhịp phím — bản chép
  ghi RY2J), bỏ `TO`, bỏ nhóm đánh hỏng. `tools/copy_align.py` chỉ căn vùng nhóm sau RMKS.
- **Khoảng lặng dài ĐỀU giữa các chữ là nhập nhằng thật**: cùng âm thanh với một từ Farnsworth (T1 có
  loại này). Chỉ tách thành chữ rời khi lặng dài LỆCH nhau như bài học thật (30/49, 40/59, 23–59 dit).
- **Mốc CTC với chữ rời lặng dài**: mô hình phát mốc ký tự k+1 ngay ĐẦU khoảng lặng trước nó (ký tự đầu ở
  khung 0) — ghép mô hình với nhịp phím theo THỨ TỰ (quy hoạch động), không theo mốc thời gian.
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
- **Ứng dụng LUÔN TỐI** (người dùng chốt 24/09): không làm giao diện sáng hay "theo hệ thống".
- **Màu chữ đặt cho KHUNG không tới nhãn con**: luật `QWidget { color: TEXT }` của theme khớp
  thẳng vào QLabel nên thắng. Banner từng ra chữ trắng trên nền vàng nhạt (1,05:1). Đặt màu cho
  chính `Khung QLabel`, và sau mọi thay đổi màu chạy `uv run python tools/contrast_audit.py` (đo
  điểm ảnh thật, mọi trang + banner + trạng thái khóa; `tests/app/test_contrast.py` canh lại).
  Stylesheet có nhiều luật `:disabled` — luật viết SAU thắng, sửa đúng luật cũ chứ đừng thêm luật mới.
- **Ảnh chụp bắt lỗi mà test không bắt.** Ba lần trong một phiên: nút phát bị khóa vĩnh viễn, thác
  nước thành mảng vàng đặc, rồi thác nước phẳng lì. Sau mỗi thay đổi giao diện, chạy
  `packaging/shots.py` và **nhìn ảnh**.
- Nút bị `setEnabled(False)` **không phải bất biến** — phải chốt lại trong chính hàm thực thi.
- `QRawFont.supportsCharacter` nhận `str` trả `False` cho mọi ký tự ngoài Latin-1; phải truyền `ord(ch)`.
- `setStretchFactor` chỉ chia phần dư, **không quyết định kích thước ban đầu** — phải đặt cả
  `setSizes` lẫn `setMinimumHeight`.
- Chuyển tab theo **widget** (`tabs.indexOf(page)`), không theo chỉ số cứng: chèn một tab vào giữa
  làm sai mọi chỉ số mà không test nào canh.
- **Widget tự đặt chiều cao tối thiểu theo NỘI DUNG phải nằm trong khung cuộn.** Băng Morse trang Tạo
  mã từng setMinimumHeight(số dòng x 40): bản tin 6 000 ký tự kéo cửa sổ cao 22 624 px, xóa chữ thì
  khung nhập chiếm cả trang (cửa sổ vẫn cao như cũ, phần dưới nằm ngoài màn hình) — 25/09, nay
  `MorseTapeView`. Cập nhật mỗi phím gõ phải rẻ: đừng gọi `load_profile` (đọc YAML) trong đường
  nóng; văn bản > DEBOUNCE_CHARS thì gộp phím (encode_page), khóa Play/Save trong lúc chờ.
- **Hình chạy theo tiếng phải lấy vị trí từ `AudioPlayback.position_s`** (giây đang ra loa, đã trừ độ
  trễ thiết bị), không từ đồng hồ riêng hay `sd.play`. Trang Tạo mã (25/09) dùng cùng cơ chế với
  karaoke trang Giải mã; dòng thời gian dấu ở `encode/timeline.py` dựng từ đúng `tokens_to_elements`.
- Không dùng emoji cờ 🇬🇧 — Linux tối giản thiếu font vùng miền sẽ hiện ra chữ "GB".
- **Khối Tín hiệu hai trang là MỘT khối** (widgets/signal_panel.py, 25/09): 3D hoặc phổ 2D, chung một
  `signal_view.Timeline`. Khung 12 s bám con trỏ với đèn ở GIỮA (chỉ nửa khung đầu/cuối thì đèn đi từ
  mép vào) — người dùng chốt; trang Nghe dùng đúng công thức với "cuối" = bây giờ (đèn ở mép phải).
  Kéo/lăn = lướt và thôi bám; bấm phát / con trỏ nhảy > 0,75 s / bấm biểu đồ = bám lại. Trang Nghe
  KHÔNG phát ra loa khi đang thu (micro thu lại → giải mã trùng); dừng rồi mới nghe lại (10 phút cuối).
- Phổ theo cột (signal_columns): cột j = [j·32 ms, (j+1)·32 ms), file tính lười theo ô 12 s, trực tiếp
  cùng lưới (test so hai đường ra cùng số). Mốc trang Nghe = giây kể từ bấm Nghe, trùng Word.start_s
  của StreamDecoder — nút Xóa giữa phiên KHÔNG đặt lại mốc (`keep_time`).
- **Vẽ 3D tốn theo SỐ ĐỈNH đa giác, không theo diện tích**: một đa giác 377 đỉnh/dải 28 ms/khung, cắt
  mỗi dải thành khối 32 cột còn 11 ms (FILL_CHUNK_COLS). Đường khử răng cưa ~5 ms mỗi đường. Chỉ dựng
  biểu đồ đang hiện, và giữ ngân sách vẽ 25 % một lõi khi con trỏ tự chạy (RENDER_DUTY). Đo bằng
  `tools/signal_view_latency.py` sau mỗi thay đổi đồ họa. Cảnh 3D vẽ vào ảnh đệm: thứ gì đổi hình
  cảnh phải gọi `_invalidate()`, không chỉ `update()`.
- **File sạch (khoảng lặng số 0) có nền -120 dB**: chuẩn hóa hình theo phân vị nền thì đuôi phổ cũng
  thành núi — cảnh 3D kẹp dải động 30 dB (RIDGE_RANGE_DB), ô số đo kẹp "dB trên nền" 0–60.

### Test
- **Test ghim hằng số phải tính theo hằng số đó**, đừng ghim số. Đổi `WINDOW_FRAMES` đã làm đỏ
  test đúng mã hai lần vì clip dựng sẵn ngắn hơn cửa sổ mới.
- **Fixture trùng tên che nhau**: `tests/app/conftest.py` từng có `fake_sounddevice` riêng che mất
  bản đầy đủ ở `tests/conftest.py`, làm test thấy một module giả thiếu `OutputStream`.
- Test GUI chờ `result_ready` rồi kiểm nút ngay sẽ **flaky** — `busy(False)` tới sau; phải chờ nút
  bật lại.
- Vét hàng đợi trong khi luồng còn chạy = vòng lặp vô hạn. `stop()` trước rồi mới vét.
- **Không test nào chạm PortAudio thật** (tests/conftest.py thay `sounddevice` bằng module rỗng cho MỌI
  test; `fake_sounddevice` ghi đè khi cần stream). Trước 27/09 mọi test dựng MainWindow gọi `Pa_Initialize`
  thật: driver máy dev treo là cả bộ test đứng im ở test_contrast. Test luồng thiết bị thật (hạn giờ, driver
  kẹt) tự dựng `AudioEngine()` và giả "treo" bằng stream chờ một Event.
- **Đừng thử âm thanh thật bừa bãi trên máy dev**: mở micro lúc loa đang phát từng làm sập dịch vụ âm thanh
  Windows 3 lần (27/09), audiodg kẹt trong driver tới khi khởi động lại máy. Âm thanh WSLg (PulseAudio qua
  RDP) cũng kẹt theo. Thử PortAudio thật trên Linux mà không phụ thuộc Windows: giải nén libportaudio2
  (22.04 = bản trong AppImage) vào /tmp, `.asoundrc` với `pcm.!default { type null }`, `PULSE_SERVER` giả.

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
- **"Cửa sổ chính 4,7 s" trong test_windows_exe KHÔNG phải chậm đi so với "2,8 s" trước 24/09**: từ
  3e0c225 script đo đúng cửa sổ tiêu đề "MorseDesk" (sau hoạt cảnh chờ 1,64 s), trước đó nó bắt nhầm
  màn hình chờ động. Mã nguồn dựng cửa sổ ~1,2 s, không đổi (đo 24/09). Ảnh chờ tĩnh hiện sau 0,2 s.
- Tiến trình con hiện **màn hình chờ động trước** (tiêu đề "MorseDesk splash"), rồi mới tới cửa
  sổ chính "MorseDesk". Script kiểm tìm cửa sổ theo tiêu đề; đóng màn hình chờ giữa chừng là hủy
  khởi động (Qt không tính cửa sổ kiểu SplashScreen là "cửa sổ cuối", nên phải tự thoát).
- Onefile chạy **hai tiến trình** (cha bung, con chạy app) — `Start-Process -PassThru` trả tiến
  trình cha nên `MainWindowHandle` luôn 0, dễ tưởng app hỏng.
- **`scripts/build_windows.ps1` chạy bằng PowerShell 7 (`pwsh`)**, không `powershell.exe` 5: 27/09 bản 5
  báo `Get-FileHash` không tồn tại ở bước tổng kiểm (exe đã dựng xong, chỉ thiếu SHA256SUMS).
- **KHÔNG dựng exe và AppImage song song**: `build_appimage.sh` chạy `rm -rf build` trên chính repo
  được mount vào container, xóa `build/win` của bản Windows đang dựng (`base_library.zip` not found).
- **27/09 exe khởi động 18 s trên máy dev** (hoạt cảnh chờ 7 s; 25/09 là 4,7 s) trong khi mã nguồn nạp
  1,2 s và AppImage nhanh: Defender đang ở chế độ thụ động, trình diệt virus thật là **Kaspersky** — nghi
  nó quét ~300 MB onefile bung vào %TEMP% mỗi lần mở (CPU của avp không đọc được để xác nhận). Đừng coi
  là hồi quy của mã khi mã nguồn vẫn nhanh; thử loại trừ `%TEMP%\_MEI*` hoặc bản onedir.

## Nơi tra số

| Cần gì | Ở đâu |
|---|---|
| Mọi con số CER/WER và vì sao | `docs/research/02-baseline-numbers.md` |
| Thí nghiệm model E0–E15 | `docs/research/03-model-experiments.md` |
| So với model có sẵn (DeepCW, QuartzNet) | `docs/research/04-pretrained-baselines.md` |
| Research realtime và đóng gói | `.superpowers/sdd/research-*.md` |
| Số / điện số / trạm số thật (T5) | `.superpowers/sdd/research-numbers-2026-09-27.md`, `tools/numeric_eval.py`, `tools/real_numbers_eval.py` |
| Bộ test chuẩn cho số (122 ca, mức must/hard/ambiguous) + file thật T6 có đáp án giám khảo LLM | `docs/research/05-numbers.md`, `tools/numeric_edge_bench.py`, `testdata/private/t6/manifest.jsonl` |
| Điện văn mạng CW (M89/M95) + phím nhẹ: T7 (3 file thật + bản chép nhân viên), lối phím đo thật, tầng cấu trúc | `docs/research/06-net-traffic-light-keying.md`, `tools/net_eval.py`, `tools/net_traffic_bench.py`, `testdata/private/t7` |
| Nhật ký từng task (gitignored) | `.superpowers/sdd/progress.md` |

## Hiện trạng

Model **E21 v0.7.0** (28/09: E18 tinh chỉnh thêm 24 000 bước, 30 % văn bản số là điện văn mạng M89/M95 và 35 %
clip có lối phím ĐO trên 3 file thật T7 — data/keyer.apply_fist; E18 = 0.6.0 ở models/archive, xem
03-model-experiments), cửa sổ 12 s, beam `alpha` 0,3 / `char_bonus` 1,25 + ranh giới câu; điện số đọc thẳng từ
mô hình (không LM); nhịp phím v2 khi phím nhẹ; tầng cấu trúc điện văn mạng (morsedesk/traffic.py, cả chế độ
nghe). Ba bộ tổng hợp cùng ma trận (ghép cặp 28/09):

| | tổng | clean | mp3 | qrm | qrn | qsb |
|---|---|---|---|---|---|---|
| T1 (seed 1000) | **8,72 %** | 1,74 | 1,68 | 1,47 | 1,47 | 37,26 |
| dev (seed 500000) | **9,60 %** | 2,61 | 2,97 | 2,72 | 2,88 | 36,84 |
| dev-OOV (seed 700000, văn bản chưa thấy) | **8,76 %** | 1,71 | 0,98 | 3,50 | 1,68 | 35,91 |

dev xấu hơn E18 (+0,82 có ý nghĩa, dồn ở `qsb` 0–3 dB — E20 cũng vậy: do văn bản/tinh chỉnh, xem
03-model-experiments); dev-OOV tốt hơn (−0,23 ns). **T7 điện văn mạng thật (3 file, bản chép nhân viên): nhóm
bản chép đúng 103/108 ở file, 98/108 ở chế độ nghe** (27/09 trước tầng cấu trúc: 46 và 32). **T4 1,26 %**: đề
thi SRR 0,55 %, ARRL 0,05 %, K7QO/SKCC 0 %, VK6FLAB 0,79 %, **SAQ gõ tay on-air 13,46 %** (khoảng cách lớn
nhất còn lại). **T5 trạm số thật (6 file) sai 16,27 % chữ số, 73,25 % nhóm đúng** (26/09: 25,12 / 42,36;
ggmorse 28,79 / 36,78). **Bộ test biên số must 109/109**. Chế độ nghe: văn bản 3,18 % (18 bản tin; file 3,16),
điện số 120 bản tin 0,2 % / 87,4 % nhóm đúng. Không có bản ghi Kazakh thật nào. T2 **1,41 %** (bản ghi ARRL thật
0,95 %, 18–40 WPM không sai ký tự nào). **Không kênh nào qua cổng 2 % một cách chắc chắn** — trên T1 bốn kênh
chạm dưới 2 % nhưng dev độc lập cho 2,6–3,0 %.

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

**Đóng gói (dựng lại 28/09 tối, model 0.7.0 + điện văn mạng, 6b80068; trước đó 27/09 khuya 452949b = luồng thiết bị âm thanh).** Windows `dist/MorseDesk.exe` một file
139,7 MB (`scripts/build_windows.ps1`); Linux `dist/MorseDesk-x86_64.AppImage` 148 MB. Kiểm: chạy
`scripts/test_windows_exe.ps1` TRƯỚC (nó sinh mẫu `dist/selftest/`), rồi `scripts/test_appimage.sh`
— cả hai đòi `--self-test` ra văn bản giống hệt mã nguồn. Đổi model thì phải dựng lại CẢ HAI.
Docker Desktop có lúc báo "running" mà máy ảo đã chết (lỗi 500): `docker desktop restart` — train
trong WSL vẫn sống qua lần khởi động lại đó (đã thử 23/09).

Chưa làm: T3 live so với file lệch **3,1 điểm** (spec đòi dưới 1); trang Nghe chưa hiện bộ đếm khối
bị bỏ (spec tuần 5–6 §7.6); đo chế độ nghe qua micro thật. CP-12 (soát bản Kazakh) KHÔNG còn là
nhãn cho người dùng: 24/09 người dùng quyết bỏ mọi chữ "bản nháp/жоба" — tác giả là người Kazakh.
