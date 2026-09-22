# Thí nghiệm model tuần 3 (tuyến B)

Mốc E0 = v1b (resume v1, tổng 24.000 bước, hidden 96, đặc trưng clip, LR 1e-3 hằng, không MP3): TER validation 30,56%.
T1 dùng để đo: 500 clip vùng gate, sinh lại ngày 2026-09-20 (T1 v2: 100 ô MP3 thật qua ffmpeg 9.0.1, cột `text_original`). Mọi run đo bằng
`uv run python tools/eval_run.py --run runs/<name> --name <name>`; dòng bảng dán nguyên văn từ stdout.

Tốc độ tham chiếu: v1 (clip, workers 0, Windows) ≈ 0,95 s/bước ở batch 16 → 8.000 bước ≈ 2,1 h, 30.000 bước ≈ 8 h.

## Bảng tổng hợp

| Mã | Thay đổi so với mốc | hidden | feature_mode | bước (ckpt best) | giờ máy | TER val | CER T1 greedy | CER T1 beam+LM | en / ru / kk (greedy) |
|---|---|---|---|---|---|---|---|---|---|
| v1 | tuần 2, 8.000 bước | 96 | clip | 7500 | 2,1 | 38.00% | 33.52% | – | 35.15% / 34.18% / 31.20% |
| E0 = v1b | v1 + 16.000 bước resume | 96 | clip | 14000 | ~6,3 | 30.56% | 31.47% | 36.10% (alpha 0,6 cũ) | 33.50% / 32.46% / 28.42% |
| E1 | đặc trưng theo cửa sổ | 96 | window | 8000 | 2,39 | 31.15% | 38.37% | – | 37.78% / 40.34% / 36.98% |
| E2 | E1 + hidden 128 | 128 | window | 6500 | 2,74 | 27.64% | 29.14% | 28.40% | 29.49% / 29.86% / 28.08% |
| E3 | E2 + cosine, warmup 500, 30.000 bước | 128 | window | 21500 | 9,40 | 22.29% | 26.45% | 25.27% | 27.89% / 27.49% / 23.97% |
| E4 | E3 + MP3 (ffmpeg), chạy trong WSL 8 worker | 128 | window | 21000 | 4,38 | 23.15% | 28.53% | 27.68% | 29.57% / 29.78% / 26.23% |
| E5 | E4 trong WSL, `--workers 8` (đo tốc độ) | 128 | window | 1000 | 0,145 | 100% (@1000, chưa hội tụ) | – | – | – |

## Chi tiết từng thí nghiệm

Mỗi mục: lệnh chạy nguyên văn, ngày/giờ bắt đầu–kết thúc, `s/bước` đọc từ log, đường cong TER (bước → TER), bảng
SNR × WPM của greedy và beam+LM (dán từ `t1_summary.json` hoặc stdout), CER theo kênh / kiểu gõ / profile, nhận xét
một đoạn (thay đổi nào có tác dụng, ô nào còn kém).

### v1 và E0 trên T1 mới

Greedy trên T1 v2 (eval_run, v1): gate CER 33.52%, 0.05 s/clip.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   53.64   56.63   53.36   60.88
    3.0   39.63   41.82   35.39   36.56
    6.0   32.56   29.55   25.91   24.08
   10.0   29.06   23.12   20.64   30.25
   20.0   26.69   16.22   19.65   14.68
```

Theo kênh: clean=24.31%, mp3=24.49%, qrm=24.43%, qrn=26.12%, qsb=68.23%. Theo kiểu gõ: bug=33.72%, drift=31.25%, farnsworth=37.16%, jitter=34.37%, machine=31.09%. Theo WPM: 12.0=36.32%, 18.0=33.47%, 25.0=30.99%, 35.0=33.29%.

v1 (checkpoint bước 7500, TER 38,00%) đo lại trên T1 v2: 33,52% so 33,6% trên T1 v1 (khác biệt = 100 ô MP3 thật thay clean). MP3 64 kbps hầu như không hại (mp3 24,5% ≈ clean 24,3%).

Greedy trên T1 v2 (eval_run, v1b): gate CER 31.47%, 0.04 s/clip.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   50.16   48.94   48.18   50.70
    3.0   39.53   37.73   33.37   32.84
    6.0   30.24   29.89   24.96   21.49
   10.0   28.27   23.67   20.00   30.00
   20.0   25.97   17.81   18.75   16.85
```

Theo kênh: clean=23.51%, mp3=21.03%, qrm=23.66%, qrn=23.44%, qsb=65.69%. Theo kiểu gõ: bug=32.72%, drift=29.42%, farnsworth=34.92%, jitter=33.23%, machine=27.05%. Theo WPM: 12.0=34.83%, 18.0=31.61%, 25.0=29.05%, 35.0=30.37%.

E0 = v1b (TER 30,56%) đạt 31,47% greedy; QSB vẫn là kênh kém nhất (65,7%), các kênh khác 21–24%. Beam+LM đo riêng ở mục LM (docs/research/02-baseline-numbers.md, tuần 3).

### E1

Greedy trên T1 v2 (eval_run, E1): gate CER 38.37%, 0.05 s/clip.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   65.94   61.09   52.46   52.00
    3.0   51.52   50.60   35.98   32.85
    6.0   43.08   36.33   33.87   18.66
   10.0   45.59   39.55   30.05   14.32
   20.0   39.83   25.83   28.75    9.12
```

Theo kênh: clean=29.51%, mp3=30.69%, qrm=28.90%, qrn=31.42%, qsb=71.33%. Theo kiểu gõ: bug=40.06%, drift=37.33%, farnsworth=40.63%, jitter=38.51%, machine=35.33%. Theo WPM: 12.0=49.19%, 18.0=42.68%, 25.0=36.22%, 35.0=25.39%.

Lệnh: `-m tools.train --name E1 --steps 8000 --batch 16 --lr 1e-3 --seed 11 --val-clips 200 --val-every 500 --hidden 96 --feature-mode window --lr-schedule constant --no-mp3`; 2026-09-20 09:xx→11:40, 1,06–1,14 s/bước, 2,39 h. TER val: 100% tới bước 500, 31,15% ở bước 8000 (best).

Nhận xét: E1 tốt hơn v1 rõ trên validation (31,15% so 38,00% cùng 8.000 bước) nhưng KÉM hơn trên T1 (38,37% so 33,52%). Chẩn đoán: E1 với metadata `feature_mode=clip` cũng cho 38,8% nên đường suy luận theo cửa sổ không phải nguyên nhân; E1 thắng ở 35 WPM (25,4% so 33,3%) nhưng thua nặng ở 12 WPM (49,2% so 36,3%) và QSB không cải thiện (71,3%). Validation (kênh ngẫu nhiên nhẹ) không dự báo T1 (ô cố định khắt khe). Quyết định: vẫn chạy E2 theo spec; trước E3 so E2 với v1b trên T1, nếu window vẫn kém clip thì E3 dùng `--feature-mode clip` (ghi là lệch spec).

### E2

Lệnh: `-m tools.train --name E2 --steps 8000 --batch 16 --lr 1e-3 --seed 12 --val-clips 200 --val-every 500 --hidden 128 --feature-mode window --lr-schedule constant --no-mp3`; 2026-09-20 11:43→14:27, ~1,2 s/bước (CPU chia sẻ với bench/test), 2,74 h; 198k tham số. TER val: 100% tới bước 1000, 47,8% @2000, 34,9% @2500, 28,5% @5000, 27,64% @6500 (best), 27,9% @8000.

Greedy trên T1 v2 (eval_run, sau cổng tone theo cửa sổ 9744b07; trước đó 29,41%): gate CER 29.14%, 0.09 s/clip.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   43.61   44.81   44.25   53.69
    3.0   32.11   32.71   27.55   33.22
    6.0   23.96   27.32   26.60   20.45
   10.0   26.77   24.03   22.23   29.66
   20.0   22.04   14.57   22.33   16.39
```

Theo kênh: clean=23.20%, mp3=16.74%, qrm=18.71%, qrn=22.14%, qsb=66.29%. Theo kiểu gõ: bug=31.11%, drift=27.40%, farnsworth=30.51%, jitter=31.10%, machine=26.96%. Theo WPM: 12.0=29.70%, 18.0=28.69%, 25.0=28.59%, 35.0=30.68%.

Nhận xét: hidden 128 sửa điểm yếu tốc độ thấp của E1 (12 WPM 29,7% so 49,2%) và cho kết quả T1 tốt nhất tới nay (29,41% so v1b 31,47% với 3× số bước ít hơn). MP3 thật (16,7%) không khó hơn clean; QSB vẫn 66%. Beam+LM với alpha 0,2/beta 1,0 (mặc định mới) cho 28.74% (alpha 0,6 cũ: 34,89%); chi tiết ở mục LM trong 02-baseline-numbers.md. Quyết định: E3 giữ window + hidden 128 (khởi động 14:35, seed 13, cosine + warmup 500, 30.000 bước).

### E3

Lệnh: `-m tools.train --name E3 --steps 30000 --batch 16 --lr 1e-3 --seed 13 --val-clips 200 --val-every 500 --hidden 128 --feature-mode window --lr-schedule cosine --warmup 500 --no-mp3`; 2026-09-20 14:35 → 2026-09-21 00:00, ~1,1–1,5 s/bước (CPU chia sẻ với bench/test/review), 9,40 h. TER val: 500–1000: 100%, 1500: 99,3%, 2000: 74,8%, 2500: 42,5%, 3000: 34,9%, 5000: 30,8%, 9500: 25,2%, 14000: 24,7%, 17000: 24,5%, 20000: 23,5%, 21500: 22,29% (best), 25000: 23,8%, 30000: ~23,2%. Warmup làm khởi đầu chậm hơn E2 (74,8% @2000 so 47,8%) nhưng vượt từ bước ~9000; cosine không cho cải thiện thêm sau bước 21500 (dao động 22,3–23,8%).

Greedy trên T1 v2 (eval_run): gate CER 26.45%, 0.08 s/clip.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   41.56   43.01   40.34   38.34
    3.0   30.90   30.78   25.76   22.77
    6.0   27.87   26.05   23.06   19.95
   10.0   28.52   22.35   22.12   21.62
   20.0   18.39   13.07   21.51   11.10
```

Theo kênh: clean=17.87%, mp3=15.22%, qrm=18.41%, qrn=18.43%, qsb=62.34%. Theo kiểu gõ: bug=28.11%, drift=24.37%, farnsworth=29.40%, jitter=26.70%, machine=23.69%. Theo WPM: 12.0=29.45%, 18.0=27.05%, 25.0=26.56%, 35.0=22.76%. Theo SNR: 0.0=40.81%, 3.0=27.55%, 6.0=24.23%, 10.0=23.65%, 20.0=16.02%.

Beam + LM (alpha 0,2, beta 1,0): gate CER 25.27% (en 23.67%, ru 26.45%, kk theo text_original 25.69%); theo kênh: clean=17.42%, mp3=14.90%, qrm=16.40%, qrn=17.07%, qsb=60.55%.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   42.44   39.67   39.20   36.56
    3.0   29.38   32.43   23.95   21.77
    6.0   27.97   23.37   21.31   18.21
   10.0   31.37   16.89   19.52   19.14
   20.0   19.62   15.76   16.88    9.88
```

Nhận xét: E3 là run tốt nhất (greedy 26,45% so E2 29,14%, LM 25,27% so 28,40%); cải thiện đều ở mọi kênh trừ QSB (62% → vẫn 60%), tức QSB giờ chiếm phần lớn khoảng cách tới gate: bỏ QSB thì CER các kênh khác ~15–18%. Ô tốt nhất 20 dB / 35 WPM còn 9,9%, nên ngay điều kiện dễ cũng chưa tới 2%: model còn thiếu năng lực (deletion/gộp từ) chứ không chỉ nhiễu. Bước tiếp theo trong tuần 3 theo spec: E4 (MP3) — nhưng MP3 thật đã dễ hơn clean trên T1, nên E4 khó cải thiện CER; giá trị của E4 là độ bền với MP3 khi train.

### E4

Lệnh (WSL, `OMP_NUM_THREADS=8`, `--workers 8`, ffmpeg 8.0.1): `-m tools.train --name E4 --steps 30000 --batch 16 --lr 1e-3 --seed 14 --val-clips 200 --val-every 500 --hidden 128 --feature-mode window --lr-schedule cosine --warmup 500 --workers 8` (MP3 bật); 2026-09-21 02:48 → 07:11, 0,52 s/bước, 4,38 h (so E3 9,40 h trên Windows). TER val: 37,2% @3000, 29,2% @5000, 26,7% @10000, 24,3% @15000, 23,8% @20000, 23,15% @21000 (best), 23,6% @27500.

Greedy trên T1 v2 (eval_run): gate CER 28.53%. Theo kênh: clean=20.70%, mp3=18.86%, qrm=19.42%, qrn=21.17%, qsb=62.51%. Theo WPM: 12.0=29.99%, 18.0=29.76%, 25.0=28.20%, 35.0=26.18%. Theo SNR: 0.0=42.91%, 3.0=31.58%, 6.0=24.07%, 10.0=25.29%, 20.0=18.81%.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   45.27   47.16   40.98   38.22
    3.0   36.36   31.85   31.52   26.59
    6.0   24.61   27.57   24.62   19.47
   10.0   23.46   25.69   24.45   27.58
   20.0   20.24   16.55   19.43   19.03
```

Beam + LM: gate CER 27.68% (en 26.37%, ru 28.70%, kk theo text_original 27.96%).

Nhận xét: E4 kém E3 khoảng 2 điểm ở cả validation và T1 (greedy 28,5% so 26,5%; LM 27,7% so 25,3%). Tăng cường MP3 khi huấn luyện không giúp T1 vì ô MP3 thật (64 kbps) vốn dễ hơn clean với model này (18,9% so 20,7%), trong khi seed khác (14 so 13) và dữ liệu MP3 chiếm chỗ dữ liệu sạch. Không tách được ảnh hưởng seed vì mỗi cấu hình chỉ chạy một lần. Kết luận: giữ E3.

### E5

Lệnh (WSL Ubuntu 26.04, uv riêng `~/.venv-morsedesk`, khởi động qua `Start-Process wsl.exe -- bash wsl_train_fg.sh` để wsl.exe giữ tiến trình sống; `nohup` trong WSL bị tắt cùng distro): `-m tools.train --name E5 --steps 1000 --batch 16 --lr 1e-3 --seed 15 --val-clips 50 --val-every 500 --hidden 128 --feature-mode window --lr-schedule cosine --warmup 100 --workers 8` (MP3 bật, ffmpeg 8.0.1 trong WSL).

Tốc độ: lần 1 với torch 16 thread mặc định: **~44 s/bước** — main process 1578% CPU, 8 worker rảnh; micro-benchmark (batch 16 × 1600 khung, hidden 128) trên WSL2: 16 thread 27,6 s/bước, 8 thread 0,26 s, 4 thread 0,27 s, 2 thread 0,28 s → thrash thread torch/OMP khi dùng đủ 16 hyperthread. Với `OMP_NUM_THREADS=8`: **0,52 s/bước** (1000 bước = 0,145 h) so Windows `--workers 0` 1,1–1,3 s/bước (không MP3) → nhanh ~2,3×; E4 chạy trong WSL. TER 100% ở bước 1000 giống E2/E3 cùng mốc (chỉ đo tốc độ).

## Kết luận và điều kiện ra

Run được chọn: **E3** (`runs/E3/best.pt`, bước 21500, hidden 128, đặc trưng theo cửa sổ, cosine + warmup 500, không MP3) — xuất thành `models/acoustic.onnx` v0.2.0 (metadata `models/acoustic.json` đã commit). Lý do: CER T1 v2 thấp nhất ở cả greedy (26.45%) và beam+LM (25.27%); E4 (thêm MP3) kém ~2 điểm; E2 kém ~3 điểm.

Gate CER < 2% (SNR ≥ 0 dB, 10–35 WPM): **KHÔNG ĐẠT**. Tiến bộ trong tuần: ONNX v1 33,6% (T1 v1) → v1b 31,5% → E3 26,5% greedy / 25,3% beam+LM (T1 v2). Khoảng cách còn lại theo ô (beam+LM, E3):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   42.44   39.67   39.20   36.56
    3.0   29.38   32.43   23.95   21.77
    6.0   27.97   23.37   21.31   18.21
   10.0   31.37   16.89   19.52   19.14
   20.0   19.62   15.76   16.88    9.88
```

Theo kênh (beam+LM): clean=17.42%, mp3=14.90%, qrm=16.40%, qrn=17.07%, qsb=60.55%. Theo kiểu gõ: bug=26.38%, drift=23.13%, farnsworth=28.36%, jitter=25.73%, machine=22.74%.

Nguyên nhân nghi ngờ, theo thứ tự ảnh hưởng:
1. **QSB** (fading 20 dB, chu kỳ 4 s): 60–62% ở mọi run, gần như không đổi từ v1; chiếm ~1/5 clip nhưng ~1/2 tổng lỗi. Chuẩn hóa theo cửa sổ 4 s không đủ vì chu kỳ fade bằng độ dài cửa sổ; cần AGC nhanh hơn (tau 0,3–0,5 s) hoặc chuẩn hóa theo từng phần tử, hoặc tăng cường QSB mạnh hơn khi train (hiện depth/period được lấy ngẫu nhiên nhẹ hơn ô T1).
2. **SNR 0 dB**: 40–45% ở mọi tốc độ; validation ngẫu nhiên ít mẫu 0 dB nên model không được tối ưu cho ô này. Cần validation dạng T1 (ô cố định) thay validation ngẫu nhiên — đã thấy validation không dự báo T1 ở E1.
3. **Năng lực model**: ngay ô dễ nhất (20 dB, 35 WPM, clean) còn ~10%; lỗi phổ biến là mất ký tự và gộp từ (`CANGE` cho `CAN GET`), LM ký tự không bù được. Cần model lớn hơn hoặc dài hơn (E3 hội tụ ~22% TER và không giảm thêm sau bước 21500) và/hoặc dữ liệu khó hơn.
4. Tốc độ thấp (12 WPM) kém hơn 35 WPM ở mọi run (~30% so ~21%): cửa sổ 4 s chứa ít ký tự, ít ngữ cảnh cho BiGRU.

Bước tiếp (tuần 4+, không làm trong tuần này): validation dạng T1; tăng cường QSB/0 dB có trọng số; AGC tau ngắn hơn hoặc chuẩn hóa hai tầng; thử hidden 192 hoặc thêm một lớp Conv; chạy trong WSL (0,52 s/bước) để mỗi thí nghiệm 30k bước còn ~4,5 h; đánh giá language_acc trên tập câu tự nhiên thay T1.

Kết quả `uv run pytest -m gate` với E3: xem `docs/research/02-baseline-numbers.md` mục "Model tuần 3".

## E6 (2026-09-22): tăng cường QSB mạnh hơn — KẾT QUẢ ÂM

Giả thuyết: ô QSB chiếm ~1/5 số clip nhưng ~1/2 tổng lỗi, nên huấn luyện với QSB đúng độ khó của
T1 (sâu tới 20 dB, chu kỳ 2–8 s, tăng tỉ lệ lấy mẫu) sẽ thu hẹp khoảng cách.

Cấu hình: đúng E3 cộng đúng một biến `--qsb-hard`, cùng seed 13, 30000 bước, hidden 128, window,
cosine + warmup 500. Chạy trên GPU RTX 5090: **45 phút** thay vì 4,7 giờ trên CPU.

| | val TER | CER greedy | CER beam+LM |
|---|---|---|---|
| E3 (mốc) | 22,29 % | 24,99 % | 23,85 % |
| E6 (`--qsb-hard`) | 27,30 %* | **37,62 %** | **35,67 %** |

\* tập validation của E6 cũng khó hơn nên số này không so trực tiếp được; chỉ T1 cố định mới so được.

**Bị loại.** Xấu hơn 12,6 điểm. Model 200k tham số không đủ sức gánh cả điều kiện khó lẫn dễ; ép
nó học QSB nặng làm hỏng mọi kênh còn lại. Kết quả này khớp với ghi chép âm của dự án `cwxss`
(`models/README.md`): huấn luyện trên tay gõ thô hơn cũng làm kết quả xấu đi.

**Bài học cho các thí nghiệm sau:** trước khi đổ thêm dữ liệu khó, hãy phân tích *loại* lỗi. Làm
đúng việc đó ngay sau E6 cho thấy 74 % lỗi là **xóa** ký tự chứ không phải nhận sai, và bản vá
đúng chỗ (thưởng ký tự trong beam, `docs/research/02-baseline-numbers.md`) lấy lại 2,27 điểm
trong vài phút mà không cần huấn luyện gì.

## Lexicon rộng hơn: kết quả âm (2026-09-22)

HamFist thưởng mọi từ nằm trong từ điển 9787 từ, còn `en.yaml` của mình chỉ liệt kê 21 viết tắt
nghiệp vụ, nên có vẻ như đang bỏ sót một nguồn thông tin rẻ. Quét trên 167 clip `en` của T1,
thêm top-N từ của `corpus/en.txt` (chỉ giữ từ toàn chữ cái trong bảng của profile) vào
`lexicon_bonus`:

| Số từ thêm | Tổng từ trong lexicon | CER |
|---|---|---|
| 0 | 21 | 18,19 % |
| 1 000 | 1 021 | 18,13 % |
| 5 000 | 5 021 | 18,23 % |

**Không lấy.** 1 000 từ chỉ được 0,06 điểm — dưới mức nhiễu đo — và 5 000 từ đã xấu đi. Lý do
hợp lý: LM ký tự 4-gram huấn luyện trên chính corpus đó đã mang gần hết thông tin từ vựng, nên
phần thưởng lexicon chỉ cộng thêm một hằng số cho những giả thuyết mà LM vốn đã xếp hạng cao;
càng nhiều từ thì phần thưởng càng ít phân biệt, và bắt đầu nâng cả những từ sai nhưng quen.

Danh sách 21 viết tắt hiện tại thì khác: chúng là những chuỗi mà LM ký tự **không** thấy nhiều
trong văn bản thường (CQ, QTH, QRZ, 73), nên phần thưởng của chúng mang thông tin thật.

## E9: model lớn hơn (hidden 128 → 256) — kết quả ÂM (2026-09-22)

Giả thuyết: chênh lệch với DeepCW trên kênh sạch (13,88 % so với 7,06 % lúc đặt giả thuyết) là
do năng lực mô hình, nên tăng `hidden` sẽ thu hẹp. Cấu hình y hệt E3 trừ `hidden` 128 → 256
(198 337 → 560 577 tham số), 40 000 bước thay vì 30 000, seed 19, chạy trên GPU trong 1,98 giờ.

| | E3 (hidden 128) | E9 (hidden 256) |
|---|---|---|
| TER validation | 22,29 % | **19,67 %** |
| **CER trên T1, 500 clip** | **20,21 %** | 28,44 % |
| clean | 12,73 % | 23,45 % |
| mp3 | 11,15 % | 22,78 % |
| qrm | 12,69 % | 22,94 % |
| qrn | 12,80 % | 23,24 % |
| qsb | 51,68 % | **49,78 %** |

**Bị loại.** Xấu hơn 8,2 điểm trên T1 dù thắng ở mọi mốc validation trong suốt lượt huấn luyện
(bước 6000: 26,48 so với 29,28; bước 14000: 23,39 so với 24,72).

### Bài học về phương pháp, quan trọng hơn chính thí nghiệm

TER validation và CER trên T1 **đi ngược nhau**. Lý do: tập validation được sinh ngẫu nhiên từ
`channel.py` theo seed của lượt huấn luyện, nên E3 (seed 13) và E9 (seed 19) chấm trên hai tập
khác nhau; còn T1 là một **ma trận cố định** với các giá trị rời rạc (SNR 0/3/6/10/20 dB, WPM
12/18/25/35, 5 kênh, 3 profile). Model lớn hơn học sát phân bố liên tục của bộ sinh và tổng
quát hóa kém hơn sang các điểm rời rạc đó.

Hệ quả cho các thí nghiệm sau: **TER validation không so sánh được giữa hai lượt khác seed**.
Chỉ CER trên T1 (và nay cả T2) mới là thước đo để quyết định.

Điểm dương duy nhất: E9 tốt hơn ở kênh `qsb` (49,78 so với 51,68), đúng ô khó nhất. Nếu sau này
cần một model riêng cho vùng fading sâu thì đây là manh mối, nhưng không đủ để đổi model chính.
