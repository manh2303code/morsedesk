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
