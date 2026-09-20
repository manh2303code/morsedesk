# Thí nghiệm model tuần 3 (tuyến B)

Mốc E0 = v1b (resume v1, tổng 24.000 bước, hidden 96, đặc trưng clip, LR 1e-3 hằng, không MP3): TER validation 30,56%.
T1 dùng để đo: 500 clip vùng gate, sinh lại ngày 2026-09-20 (T1 v2: 100 ô MP3 thật qua ffmpeg 9.0.1, cột `text_original`). Mọi run đo bằng
`uv run python tools/eval_run.py --run runs/<name> --name <name>`; dòng bảng dán nguyên văn từ stdout.

Tốc độ tham chiếu: v1 (clip, workers 0, Windows) ≈ 0,95 s/bước ở batch 16 → 8.000 bước ≈ 2,1 h, 30.000 bước ≈ 8 h.

## Bảng tổng hợp

| Mã | Thay đổi so với mốc | hidden | feature_mode | bước (ckpt best) | giờ máy | TER val | CER T1 greedy | CER T1 beam+LM | en / ru / kk (greedy) |
|---|---|---|---|---|---|---|---|---|---|
| v1 | tuần 2, 8.000 bước | 96 | clip | 7500 | 2,1 | 38.00% | 33.52% | – | 35.15% / 34.18% / 31.20% |
| E0 = v1b | v1 + 16.000 bước resume | 96 | clip | 14000 | ~6,3 | 30.56% | 31.47% | 36.10% | 33.50% / 32.46% / 28.42% |
| E1 | đặc trưng theo cửa sổ | 96 | window | 8000 | 2,39 | 31.15% | 38.37% | – | 37.78% / 40.34% / 36.98% |
| E2 | E1 + hidden 128 | 128 | window | 6500 | 2,74 | 27.64% | 29.41% | 34.89% (alpha 0,6) | 29.90% / 30.08% / 28.26% |
| E3 | E2 + cosine, warmup 500, 30.000 bước | 128 | window | 30000 | | | | | |
| E4 | E3 + MP3 (ffmpeg) | 128 | window | 30000 | | | | | |
| E5 | E4 trong WSL, `--workers 8` (đo tốc độ) | 128 | window | 1000 | | | – | – | – |

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

Greedy trên T1 v2 (eval_run): gate CER 29.41%, 0.09 s/clip.

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

Nhận xét: hidden 128 sửa điểm yếu tốc độ thấp của E1 (12 WPM 29,7% so 49,2%) và cho kết quả T1 tốt nhất tới nay (29,41% so v1b 31,47% với 3× số bước ít hơn). MP3 thật (16,7%) không khó hơn clean; QSB vẫn 66%. Beam+LM với alpha 0,6 mặc định vẫn làm xấu (34,89%): xem mục LM trong 02-baseline-numbers.md, alpha đang được tinh chỉnh. Quyết định: E3 giữ window + hidden 128 (khởi động 14:35, seed 13, cosine + warmup 500, 30.000 bước).

### E3

### E4

### E5

## Kết luận và điều kiện ra

<điền ở Task 5: run tốt nhất, có đạt gate CER < 2% không, khoảng cách theo ô nếu chưa đạt, nguyên nhân nghi ngờ, bước tiếp>
