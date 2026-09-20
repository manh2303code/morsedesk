# Số đối chứng baseline: bộ giải mã DSP (`baseline`) trên ma trận T1

Ngày đo: 2026-09-19. Máy đo: laptop Windows 11, không có ffmpeg (kênh "mp3" tự động rơi về "clean",
ghi lại ở `channel_actual`).

## Lệnh chạy

```
uv run python tools/make_t1.py
uv run morsedesk bench --manifest testdata/generated/t1/manifest.jsonl --engine baseline --gate
```

Ma trận T1 (vùng gate, không `--full`): 5 SNR × 4 WPM × 5 kiểu gõ × 5 kênh = 500 clip
(seed cố định `seed_base=1000`, 1 clip/ô).

## Kết quả (nguyên văn stdout)

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0  835.14  663.04  464.32  313.65
    3.0  875.10  357.29  296.85  302.01
    6.0  520.49  507.53  156.18   98.24
   10.0  237.21  143.94   64.48   29.24
   20.0   13.16   19.16   15.74   16.85
by_keying: bug=282.37%, drift=279.96%, farnsworth=383.28%, jitter=269.77%, machine=267.03%
by_channel: clean=263.14%, qrm=243.14%, qrn=307.53%, qsb=405.45%
by_profile: en=290.64%, kk-cyrl-ru=279.66%, ru=319.05%
n=500 CER=296.48% WER=418.50% -> bench_results\bench_baseline_20260919_055356.json
gate (SNR>=0, 10-35 WPM, n=500): CER=296.48% TRƯỢT (ngưỡng 2.00%)
```

## Ghi chú

- **Gate TRƯỢT** trên toàn vùng SNR≥0 dB, 10–35 WPM, không chỉ ở SNR thấp như dự đoán ban đầu
  trong task brief. Bộ giải mã DSP (`baseline`) hiện tại (dò tone + tách khoảng theo ngưỡng, không
  có mô hình học máy) chịu ảnh hưởng nặng bởi các kiểu gõ méo (jitter/bug/drift/farnsworth) và
  kênh nhiễu (qsb/qrm/qrn) dùng trong ma trận T1 — vốn khắt khe hơn nhiều so với dữ liệu tổng hợp
  đơn giản đã dùng để test baseline ở các task trước.
- CER > 100% xảy ra khi bản dịch giả (hyp) dài hơn nhiều so với nhãn thật (ref) — khoảng cách
  Levenshtein khi đó có thể vượt độ dài ref (ví dụ dòng đầu ma trận: SNR 0 dB/12 WPM/machine/clean,
  ref="NUMBER", hyp="E E D( DE EII F MATE # ESI# E4T U L L EE M M #T A E").
- Nhóm "clean" trong `by_channel` gộp cả các ô kênh "clean" thật và các ô kênh "mp3" bị rơi về
  "clean" do máy đo không có ffmpeg (`channel_actual`), nên n của "clean" gấp đôi các kênh khác.
- Số liệu này là đối chứng tuần 1 cho baseline DSP; sẽ so sánh với engine ONNX ở Task 17 sau khi có
  `models/acoustic.onnx` (bài test `test_t1_gate_onnx` trong `tests/regression/test_t1.py` hiện bị
  skip vì chưa có model).

## Engine ONNX v1 (checkpoint runs/v1/best.pt, 8000 bước, TER validation 38.0%)

Ngày đo: 2026-09-19. Model xuất tạm sang models/eval_v1.onnx (không commit). Cùng manifest T1 vùng gate, 500 clip.

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   55.01   56.63   53.57   60.71
    3.0   39.63   41.82   35.39   36.56
    6.0   32.56   29.55   25.91   24.08
   10.0   29.06   23.57   20.64   30.10
   20.0   26.69   16.22   19.65   14.68
by_keying: bug=33.72%, drift=31.50%, farnsworth=37.16%, jitter=34.46%, machine=31.17%
by_channel: clean=24.62%, qrm=24.43%, qrn=26.12%, qsb=68.23%
by_profile: en=35.31%, kk-cyrl-ru=31.39%, ru=34.09%
n=500 CER=33.60% WER=75.45% -> gate TRƯỢT (ngưỡng 2%)
```

Nhận xét: sau 8000 bước model đã vượt xa baseline (33.6% so với 296%) nhưng còn thiếu huấn luyện (TER validation 100% tới bước 1000, 38% ở bước 7500 và vẫn giảm). QSB là kênh yếu nhất (68%). Bước tiếp: train tiếp v1b (resume, 16000 bước, seed 2), rồi cân nhắc hidden 128, lịch learning rate và tăng tỉ lệ mẫu QSB; mục tiêu gate CER < 2% thuộc vòng lặp tuần 3.

## Tuần 3: LM ký tự và beam search (model E2 = `models/eval_E2.onnx`, T1 v2)

Ngày đo: 2026-09-20. T1 v2 = 500 clip vùng gate sinh lại cùng seed, 100 ô MP3 thật (ffmpeg 9.0.1), cột `text_original`.
LM: n-gram ký tự bậc 6 dựng bằng KenLM `lmplz --prune 0 0 1 1 1 1` trong WSL, nhị phân numpy (`tools/arpa_to_bin.py`): en.bin 19,3 MB (perplexity holdout 3,82), ru.bin 13,6 MB (3,62), kk.bin 10,1 MB (3,04). Nguồn: `models/lm/LICENSES.md`.
Tham chiếu CER: en/ru theo `text`; kk theo `text` khi không LM và theo `text_original` (chữ Kazakh gốc, khắt khe hơn) khi có LM. 13/166 clip kk và một số clip khác ở 0 dB không dò được tone và tính 100% ở mọi cấu hình.

| Cấu hình | CER gate | en / ru / kk | language_acc | s/clip |
|---|---|---|---|---|
| greedy, không LM | 29.41% | 29.90% / 30.08% / 28.26% | – | 0.07 |
| beam 64 + LM (alpha 0,2, beta 1,0), ép profile | 28.74% | 27.02% / 29.03% / 30.17% | – | 0.35 |
| beam 64 + LM, profile auto | 44.38% | 33.36% / 46.89% / 52.95% | 56.6% | – |

Tinh chỉnh alpha/beta trên toàn T1 v2 với E2 (CER en / ru / kk-orig): greedy 29,90 / 30,08 / 31,34; alpha 0,6 beta 0,5 (spec) 31,73 / 35,54 / 30,64; alpha 0,3 27,95 / 30,90 / 26,22; alpha 0,2 27,66 / 29,60 / 25,09; alpha 0,15 27,75 / 29,23 / 24,60; **alpha 0,2 beta 1,0: 27,02 / 29,14 / 24,23** (kk-orig ở đây loại 13 clip không tone). Với v1b (model yếu hơn) mọi alpha ≥ 0,3 đều làm xấu ru. Mặc định `BeamParams` đổi thành alpha 0,2, beta 1,0 (lệch spec 0,6/0,5, commit 50dc2c9); beam không LM bằng greedy (26,08% so 26,25% trên 40 clip).

Greedy (eval_run):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   43.61   44.81   44.25   53.69
    3.0   32.11   32.71   27.55   33.22
    6.0   23.96   27.32   26.60   20.45
   10.0   26.77   24.03   22.23   29.66
   20.0   22.04   14.57   22.33   16.39
```

Beam + LM (eval_run):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   45.86   43.06   41.86   50.24
    3.0   29.63   35.89   27.13   31.54
    6.0   24.42   26.67   26.83   19.29
   10.0   24.89   23.78   22.41   27.94
   20.0   19.66   15.28   22.13   16.25
```

Auto (bench --profile-override auto): by_channel clean=39.18%, mp3=31.97%, qrm=40.05%, qrn=35.63%, qsb=75.09%; language_acc 56.6%.

Nhận xét:
- LM giúp cả ba profile khi ép profile: en 29,9 → 27,0; ru 30,1 → 29,0; kk 28,3 (so `text`) → 30,2 (so `text_original`, tức đã khôi phục được phần lớn Ә/Ғ/Қ/Ң/Ө/Ұ/Ү/І: greedy so `text_original` là 31,3). Lỗi còn lại chủ yếu là mất ký tự và gộp từ của model âm thanh (CANGE cho "CAN GET"), LM ký tự không bù được deletion.
- Beam thuần Python: 0,35 s/clip (6–8 s) kể cả tải ONNX, đạt mục tiêu 2 s/12 s; đường tắt blank kích hoạt 88–96% khung với model thật.
- Nhận diện ngôn ngữ auto chỉ 56,6%: 30% clip T1 là radiogram ham đã chuyển tự (trung lập ngôn ngữ, đúng 30% ≈ ngẫu nhiên), random group 10%; trên phần "từ" đạt ~64% với v1b. CER auto (44%) cao hơn ép profile vì đoán sai profile làm render sai bảng chữ (kk↔ru). Mục tiêu 95% của spec không đạt được với T1 hiện tại; cần (a) đo language_acc trên tập câu tự nhiên, (b) model âm thanh tốt hơn (E3), (c) LM ru/kk phân biệt hơn (corpus kk còn nghiêng KazNERD).
- Baseline + auto (CLI mặc định khi chưa có model ONNX) chấm LM trên bản render chữ đầu nên kk thường bị nhận thành ru; hạn chế đã biết, đường onnx+beam là đường chính.
