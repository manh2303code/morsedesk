# Thí nghiệm model tuần 3 (tuyến B)

Mốc E0 = v1b (resume v1, tổng 24.000 bước, hidden 96, đặc trưng clip, LR 1e-3 hằng, không MP3): TER validation 30,56%.
T1 dùng để đo: 500 clip vùng gate, sinh lại ngày <điền> (có MP3 thật, `text_original`). Mọi run đo bằng
`uv run python tools/eval_run.py --run runs/<name> --name <name>`; dòng bảng dán nguyên văn từ stdout.

Tốc độ tham chiếu: v1 (clip, workers 0, Windows) ≈ 0,95 s/bước ở batch 16 → 8.000 bước ≈ 2,1 h, 30.000 bước ≈ 8 h.

## Bảng tổng hợp

| Mã | Thay đổi so với mốc | hidden | feature_mode | bước | giờ máy | TER val | CER T1 greedy | CER T1 beam+LM | en / ru / kk (greedy) |
|---|---|---|---|---|---|---|---|---|---|
| v1 | tuần 2, 8.000 bước | 96 | clip | 8000 | 2,1 | 38,00% | <điền> | <điền> | <điền> |
| E0 = v1b | v1 + 16.000 bước resume | 96 | clip | 24000 | ~6,3 | 30,56% | <điền> | <điền> | <điền> |
| E1 | đặc trưng theo cửa sổ | 96 | window | 8000 | | | | | |
| E2 | E1 + hidden 128 | 128 | window | 8000 | | | | | |
| E3 | E2 + cosine, warmup 500, 30.000 bước | 128 | window | 30000 | | | | | |
| E4 | E3 + MP3 (ffmpeg) | 128 | window | 30000 | | | | | |
| E5 | E4 trong WSL, `--workers 8` (đo tốc độ) | 128 | window | 1000 | | | – | – | – |

## Chi tiết từng thí nghiệm

Mỗi mục: lệnh chạy nguyên văn, ngày/giờ bắt đầu–kết thúc, `s/bước` đọc từ log, đường cong TER (bước → TER), bảng
SNR × WPM của greedy và beam+LM (dán từ `t1_summary.json` hoặc stdout), CER theo kênh / kiểu gõ / profile, nhận xét
một đoạn (thay đổi nào có tác dụng, ô nào còn kém).

### v1 và E0 trên T1 mới

<điền sau khi chạy eval_run cho runs/v1 và runs/v1b>

### E1

### E2

### E3

### E4

### E5

## Kết luận và điều kiện ra

<điền ở Task 5: run tốt nhất, có đạt gate CER < 2% không, khoảng cách theo ô nếu chưa đạt, nguyên nhân nghi ngờ, bước tiếp>
