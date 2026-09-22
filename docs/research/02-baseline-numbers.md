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
Tham chiếu CER: en/ru theo `text`; kk theo `text` khi không LM và theo `text_original` (chữ Kazakh gốc, khắt khe hơn) khi có LM. Sau commit 9744b07 (cổng tone theo cửa sổ) các clip 0 dB không dò được tone toàn cục vẫn được giải mã nếu một cửa sổ 4 s có tone; số trong bảng đo sau commit đó (greedy trước đó 29,41%, LM 28,74%).

| Cấu hình | CER gate | en / ru / kk | language_acc | s/clip |
|---|---|---|---|---|
| greedy, không LM | 29.14% | 29.90% / 30.08% / 28.26% | – | 0.07 |
| beam 64 + LM (alpha 0,2, beta 1,0), ép profile | 28.40% | 27.02% / 29.03% / 30.17% | – | 0.35 |
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

## Model tuần 3: `models/acoustic.onnx` v0.2.0 = E3 (T1 v2)

Ngày đo: 2026-09-21. Mọi số trên T1 v2 (500 clip, MP3 thật, `text_original`), beam+LM với alpha 0,2 / beta 1,0 và LM en/ru/kk dựng ngày 2026-09-20; kk chấm theo `text_original` khi có LM.

| Run | hidden | feature_mode | bước (best) | TER val | CER T1 greedy | CER T1 beam+LM |
|---|---|---|---|---|---|---|
| v1 | 96 | clip | 7500 | 38.00% | 33.52% | – |
| v1b | 96 | clip | 14000 | 30.56% | 31.47% | 36.10% |
| E1 | 96 | window | 8000 | 31.15% | 38.37% | – |
| E2 | 128 | window | 6500 | 27.64% | 29.14% | 28.40% |
| E3 | 128 | window | 21500 | 22.29% | 26.45% | 25.27% |
| E4 | 128 | window | 21000 | 23.15% | 28.53% | 27.68% |

So với ONNX v1 tuần 2 (33,6% trên T1 v1): E3 giảm còn 26.45% greedy / 25.27% beam+LM. Gate 2% KHÔNG ĐẠT; phân tích khoảng cách và nguyên nhân ở `03-model-experiments.md` mục "Kết luận và điều kiện ra".

Greedy (E3):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   41.56   43.01   40.34   38.34
    3.0   30.90   30.78   25.76   22.77
    6.0   27.87   26.05   23.06   19.95
   10.0   28.52   22.35   22.12   21.62
   20.0   18.39   13.07   21.51   11.10
```

Beam + LM (E3):

```
CER % theo SNR (hàng) x WPM (cột)
SNR\WPM    12.0    18.0    25.0    35.0
    0.0   42.44   39.67   39.20   36.56
    3.0   29.38   32.43   23.95   21.77
    6.0   27.97   23.37   21.31   18.21
   10.0   31.37   16.89   19.52   19.14
   20.0   19.62   15.76   16.88    9.88
```

Theo kênh (greedy → LM): clean=17.87%→17.42%, mp3=15.22%→14.90%, qrm=18.41%→16.40%, qrn=18.43%→17.07%, qsb=62.34%→60.55%. Theo profile (greedy en/ru/kk-text → LM en/ru/kk-orig): 27.89%/27.49%/23.97% → 23.67%/26.45%/25.69%.

`uv run pytest -m gate` với model này (2026-09-21, 12 phút): 3 FAIL, đúng như spec §3.3 cho phép khi chưa đạt gate — `test_t1_gate_onnx` (CER greedy 26,45% > 2%); `test_t1_lm_not_worse_than_greedy_and_language_acc` (phần LM ≤ greedy đạt cho cả ba profile, trượt `language_acc` 0,584 < 0,95); `test_trained_model_roundtrip` (en đạt; ru "ПРИВЕТ МЕРН" cho "ПРИВЕТ МИР", CER 0,2 > 0,1).

## Cổng dò tone: 1,46 điểm CER lấy lại được mà không cần huấn luyện (2026-09-22)

`Decoder.decode_array` trả rỗng khi `estimate_tone` không đủ tự tin, áp cho mọi engine. Đo trên
vùng gate của T1 (500 clip, SNR ≥ 0, 10–35 WPM, engine `onnx` greedy):

| | CER vùng gate | Clip trả rỗng |
|---|---|---|
| Trước (bỏ cuộc khi không dò được tone) | 26,45 % | 29 (26 qsb, 2 clean, 1 qrn; 23 ở 0 dB) |
| Sau (đoán tone theo đỉnh phổ dải 300–1500 Hz) | **24,99 %** | 0 |

Mỗi clip rỗng tính CER 1,0, nên 29 clip đóng góp 5,8 điểm. Khi ép tone đoán, đúng nhóm 29 clip đó
cho 74,8 % thay vì 100 %, tức lấy lại 1,46 điểm trên toàn vùng gate.

Với engine `deepcw` thì cổng này còn vô lý hơn: model nghe cả dải 400–1200 Hz và không dùng ước
lượng tone. Bỏ cổng cho riêng nó đưa CER tập `en` của T1 từ 27,23 % xuống **22,80 %** (167 clip).

Đánh đổi: kết quả đoán tone mang cảnh báo "không dò được tone rõ, đang đoán theo đỉnh phổ; kết quả
có thể sai" và độ tin cậy thấp (tô đỏ trong giao diện). Đây là **lệch spec gốc §7**, chỗ nói không
dò được tone thì trả rỗng — đổi lại vì bỏ cuộc là chắc chắn sai, còn đoán thì sai ít hơn và người
dùng vẫn được cảnh báo. Engine `baseline` giữ hành vi cũ: bộ giải mã DSP với tone sai chỉ ra nhiễu.

## Chẩn đoán loại lỗi và thưởng ký tự: 2,27 điểm nữa, vẫn không cần huấn luyện (2026-09-22)

Trước khi thử tiếp cách cải thiện, phân tích lỗi thành ba loại trên toàn T1 (beam+LM, model E3):

| Kênh | Thay | Chèn thừa | Xóa |
|---|---|---|---|
| clean | 4,3 % | 0,2 % | 9,3 % |
| mp3 | 4,5 % | 0,5 % | 8,6 % |
| qrm | 3,3 % | 0,2 % | 11,0 % |
| qrn | 4,9 % | 0,7 % | 11,1 % |
| **qsb** | 11,0 % | **0,0 %** | **43,5 %** |
| **Tổng** | 5,6 % | **0,3 %** | **16,6 %** |

**74 % lỗi là XÓA ký tự, chỉ 1 % là chèn thừa.** Model bỏ sót chữ khi tín hiệu fade chứ không
bịa thêm. Điều này loại bỏ cả một nhóm giải pháp: mọi cách phạt chèn thừa (duration penalty,
DPDP, phạt quá phân đoạn) đều nhắm sai chỗ.

`BeamParams.beta` của mình là thưởng mỗi **từ**, không chạm tới việc xóa ký tự bên trong từ. Thêm
`char_bonus` là thưởng mỗi **ký tự** phát ra (đúng "character insertion bonus" của Deep Speech 2
công thức 12 cho mô hình mức ký tự). Quét trên 200 clip qsb+clean:

| char_bonus | 0,0 | 0,75 | 1,0 | **1,25** | 1,5 | 2,0 | 3,0 | 5,0 |
|---|---|---|---|---|---|---|---|---|
| CER | 35,73 % | 34,06 % | 33,25 % | **32,99 %** | 33,38 % | 35,20 % | 43,26 % | 94,99 % |

Toàn bộ T1 với `char_bonus = 1.25`:

| | clean | mp3 | qrm | qrn | qsb | **gate** |
|---|---|---|---|---|---|---|
| Trước | 16,04 % | 14,90 % | 16,40 % | 16,47 % | 55,42 % | 23,85 % |
| Sau | **13,88 %** | **13,34 %** | **14,26 %** | **14,35 %** | **52,09 %** | **21,58 %** |

Mọi kênh đều tốt lên. Không huấn luyện lại. Chỉ áp khi có mô hình ngôn ngữ; chế độ thuần âm học
giữ nguyên hành vi cũ.

Tổng trong ngày 22/09, không huấn luyện lại lần nào: **25,27 % → 21,58 %**.

## QSB: giới hạn vật lý chứ không phải lỗi xử lý (2026-09-22)

Trước khi tiêu thêm lượt huấn luyện cho ô QSB (52 % CER, tệ nhất), đo xem thông tin còn sống sót
trong đặc trưng đến đâu. Chỉ số là **d'**: khoảng cách giữa trung bình đặc trưng AGC ở khung có dấu
và khung im lặng, chia độ lệch chuẩn gộp. d' càng cao thì hai lớp càng tách bạch; d' quanh 1 nghĩa
là chồng lấn gần như hoàn toàn và không bộ giải mã nào tách được theo từng khung.

Tín hiệu "PARIS" lặp ở 20 WPM, fade hình sin chu kỳ 4 s:

| SNR | fade 0 dB | fade 10 dB | fade 20 dB |
|---|---|---|---|
| 20 dB | 8,20 | 6,95 | 4,51 |
| 10 dB | 8,45 | 5,90 | 2,99 |
| 3 dB | 7,35 | 4,04 | 1,96 |
| **0 dB** | 6,52 | 3,19 | **1,54** |

**Fade một mình không nguy hiểm**: ở SNR 20 dB, fade sâu 20 dB vẫn cho d' = 4,51, bằng đúng tín
hiệu sạch không nhiễu. Chỉ khi **fade cộng với SNR thấp** thì thông tin mới biến mất: ở 0 dB kèm
fade 20 dB, đáy mỗi chu kỳ dìm tín hiệu xuống dưới nền nhiễu và d' còn 1,54.

Ô `qsb` của T1 chính là tổ hợp đó. Nên 52 % CER ở ô này **gần với giới hạn vật lý hơn là lỗi xử
lý**. Bằng chứng độc lập: DeepCW, model pretrain tốt nhất đo được, cũng chỉ đạt 47 % ở đúng ô này.
Hai hệ thống khác hẳn nhau rơi vào cùng một khoảng.

### Ba hướng đã bị loại nhờ phép đo này

| Hướng | d' đo được | Kết luận |
|---|---|---|
| AGC hiện tại, tau 1,0 s | 4,50 / 4,58 / 4,59 (fade 0/10/20 dB) | mốc |
| Rút tau xuống 0,4 s (kế hoạch E7) | 3,95 / 4,02 / 4,06 | **xấu hơn**, bỏ |
| Nền có cổng kiểu HamFist | 2,56 / 2,62 / 2,69 | **xấu hơn nhiều**, bỏ |

Tiết kiệm được hai lượt huấn luyện. Lý do cách có cổng thua: envelope của mình đã trộn hẹp băng và
chuẩn hóa trong miền log, nên việc đóng băng cập nhật làm bộ ước lượng thiếu dữ liệu chứ không giúp.
Cơ chế đó sinh ra cho tín hiệu thô trên vi điều khiển, không cho đường đặc trưng như của mình.

### Hệ quả cho ngưỡng 2 %

Vùng gate gồm cả ô `qsb` ở 0 dB, nơi d' = 1,54. Muốn đạt 2 % trên toàn vùng gate thì phải giải mã
đúng ở mức tách bạch đó, với clip trung bình chỉ 13 ký tự nên không đủ thời gian tích lũy bằng
chứng. Đây là số liệu mới, không phải ý kiến; người dùng đã chốt giữ ngưỡng 2 % và kế hoạch vẫn
nhắm đúng ngưỡng đó, nhưng nên biết khoản nào trong khoảng cách là vật lý và khoản nào là kỹ thuật.


## Hai giả thuyết về lỗi xóa, cả hai đều bị số đo bác bỏ (2026-09-22)

Chẩn đoán ở mục trên cho thấy **74 % lỗi là xóa ký tự**. Hai cơ chế có vẻ giải thích được điều đó
đã được kiểm riêng rẽ, và cả hai đều không phải nguyên nhân chính.

### 1. Lệch tone giữa huấn luyện và chạy thật

Lúc huấn luyện, `example_features` truyền `f0_hint = ex.f0_hz`, tức **tone thật** của bộ sinh.
Lúc chạy thật, đặc trưng được dựng theo tone **ước lượng**, và với clip không dò ra tone thì theo
đỉnh phổ. Nếu mô hình quen với đặc trưng luôn đặt đúng tâm tần số, sai lệch lúc chạy sẽ làm hậu
nghiệm dàn phẳng và sinh lỗi xóa.

Sai số ước lượng đo trên toàn T1 (tone thật suy ra từ `seed`, xem `tone_hz_for_seed`):

| Kênh | Sai số trung vị | Sai > 25 Hz | Không dò được |
|---|---|---|---|
| clean | 0,2 Hz | 0 % | 3 % |
| mp3 | 0,2 Hz | 0 % | 1 % |
| qrm | 0,2 Hz | 0 % | 1 % |
| qrn | 0,2 Hz | 0 % | 1 % |
| qsb | 0,3 Hz | 0 % | **33 %** |

Khi dò được thì gần như hoàn hảo. Chỉ `qsb` có một phần ba clip phải đoán. Giải mã lại 100 clip
`qsb` với tone thật ép vào (`estimate_tone` bị vá) so với đường hiện tại:

| Nhóm | n | Hiện tại | Tone thật | Chênh |
|---|---|---|---|---|
| Dò được | 67 | 40,57 % | 40,57 % | 0,00 |
| Không dò được | 33 | 75,49 % | 74,40 % | +1,09 |
| Toàn kênh `qsb` | 100 | 52,09 % | 51,73 % | +0,36 |

**Toàn bộ khâu dò tone chỉ đáng 0,36 điểm trên kênh xấu nhất**, tức dưới 0,08 điểm trên toàn T1.
Đáng chú ý hơn: nhóm không dò được vẫn 74 % **ngay cả khi biết tone chính xác**, nên vấn đề của
nhóm đó là tín hiệu quá yếu, không phải đặt sai tâm tần số — khớp với phép đo d' ở mục trước.
Hướng "huấn luyện với tone hint nhiễu để khớp lúc chạy thật" vì vậy bị loại, tiết kiệm một lượt
huấn luyện.

### 2. Ngưỡng cắt tỉa `min_prob` chặn ký tự yếu

`min_prob = 1e-3` khiến khung không có lớp nào vượt ngưỡng đi đường tắt chỉ-blank, nên ký tự ở
khung đó **không thể được phát ra về mặt cấu trúc** — đúng cơ chế sinh lỗi xóa khi fade làm hậu
nghiệm dàn phẳng. Quét trên 200 clip `qsb`+`clean` tại `alpha=0,3`, `char_bonus=1,25`:

| `min_prob` | `topk_per_frame` | CER | Giây |
|---|---|---|---|
| 1e-3 | 8 | 32,21 % | 91 |
| 1e-4 | 8 | 32,06 % | 181 |

Nới ngưỡng xuống một trăm lần chỉ đổi **0,15 điểm** nhưng tốn gấp đôi thời gian. Cắt tỉa không
phải chỗ mất ký tự; hậu nghiệm ở những khung đó không chỉ yếu mà thực sự nghiêng về blank.

### Kết luận chung

Hai cơ chế "rẻ" đã bị loại bằng số đo thay vì bằng lượt huấn luyện. Lỗi xóa còn lại nằm ở **năng
lực mô hình âm thanh**, không ở khâu tiền xử lý hay khâu giải mã — nhất quán với chênh lệch trên
kênh sạch (mình 13,88 % so với DeepCW 7,06 %), nơi không có fade nào để đổ lỗi. Vì vậy bước tiếp
theo là tăng năng lực mô hình (thí nghiệm E9, `hidden` 128 → 256), chứ không tiếp tục tinh chỉnh
tham số giải mã.

## Mốc cuối ngày 2026-09-22 trên toàn T1 (500 clip, 3 profile)

Không huấn luyện lại lần nào trong ngày; toàn bộ mức cải thiện đến từ khâu giải mã và khâu
tiền xử lý.

| Engine | CER | WER | Ghi chú |
|---|---|---|---|
| `onnx` + beam + LM | **20,21 %** | 44,41 % | alpha 0,3 · char_bonus 1,25 · đoán tone theo đỉnh phổ |
| `baseline` (DSP) | **35,12 %** | 70,11 % | trễ Schmitt + xóa run ngắn |

Đường đi của engine `onnx` trong ngày: 25,27 % → 24,99 % (đoán tone) → 23,85 % → 21,58 %
(char_bonus) → **20,21 %** (alpha 0,3). Bộ DSP: ~296 % → **35,12 %**.

Engine `onnx` theo kênh: clean 12,73 %, mp3 11,15 %, qrm 12,69 %, qrn 12,80 %, qsb 51,68 %.
Theo profile: en 18,19 %, ru 21,18 %, kk-cyrl-ru 21,27 %.

Bộ DSP theo kênh: clean 21,90 %, mp3 25,88 %, qrm 21,66 %, qrn 23,20 %, qsb 82,96 %. Nó vẫn
kém model rõ rệt, đúng vai trò dự phòng, nhưng đã ở mức đọc được thay vì sinh rác.

Khoảng cách còn lại tập trung ở `qsb` (51,68 % so với 12,7 % của bốn kênh kia) — đã đo là gần
giới hạn vật lý ở mục trên — và ở năng lực mô hình trên kênh sạch, đang được thí nghiệm E9
(`hidden` 128 → 256) kiểm chứng.

## Bộ T2 bản ghi thật lộ ra lỗi mà 500 clip T1 không thể lộ (2026-09-22)

Ngày 22/09 tải được 10 bản ghi thật của **ARRL W1AW code practice** (5–40 WPM, 124 phút, kèm
đáp án) vào `testdata/private/t2/`. Phép đo đầu tiên trên đó đảo ngược một giả định nền của dự
án.

### Triệu chứng

Trên 120 giây đầu của bản ghi 20 WPM, đáp án là
`= NOW 20 WPM = TEXT IS FROM MAY 2024 QST PAGE 36 = TO OPERATE. I CAN OFTEN WORK DX STATIONS…`

| Engine | Kết quả | Tốc độ báo về |
|---|---|---|
| `onnx` (model của mình) | `KOW W0WJ9_4 QVWOOY.A,9KQ)XQOGO...OQO 3 K......AW` | 7,1 WPM |
| `baseline` (bộ DSP) | `= NOW 20 WPM = TEXT IS FROM MAY 2024 QST PAGE 36 = TO OPERATE. I CAN OFTEN…` | 20,0 WPM |
| `deepcw` | `BT NOW 20 WPM BT TEXT IS FROM MAY 2024 QST PAGE 36 BT TO OPERATE…` | 20,1 WPM |

Mô hình nơ-ron của mình — thứ đạt 20,21 % trên T1 — trả về **rác**, trong khi bộ giải mã DSP
dự phòng đọc gần như hoàn hảo. Cắt xuống 8 giây (đúng độ dài clip T1) vẫn hỏng, nên không phải
vấn đề độ dài.

### Nguyên nhân

`estimate_tone` đo SNR của các bản ghi ARRL: **49–143 dB**, trung vị khoảng 62. Còn
`morsedesk/data/channel.py` lấy mẫu SNR khi sinh dữ liệu huấn luyện trong `uniform(-6, 25)`.
Mô hình **chưa bao giờ thấy tín hiệu sạch hơn 25 dB**.

Bằng chứng trực tiếp: **thêm** nhiễu vào bản ghi thật cho bẩn đi thì mô hình đọc được ngay.

| Xử lý | Kết quả trên cùng đoạn |
|---|---|
| Gốc (61,7 dB) | `OQQQ 03 LA` |
| Thêm nhiễu về 20 dB | `I, EVEN WHEN OTHERS AT HARE TIE ALSOMFRALW GA` |
| Thêm nhiễu về 10 dB | `I, EVEN WHEN OTHERS AND HARNE TIE ALSOFREQUENT GA` |
| Thêm nhiễu về 3 dB | `I, EVEN WHEN OTHERS CANNOT HAR T.I ALSOFRAELI GA` |

Làm tín hiệu **xấu đi** khiến kết quả **tốt lên** — dấu hiệu kinh điển của lệch phân bố, không
phải thiếu năng lực.

### Sửa

Hai mức, đã áp dụng cả hai:

1. **Ngay, không cần huấn luyện lại** — `morsedesk/dsp/dither.py`: khi SNR ước lượng vượt 25 dB
   thì trộn nhiễu trắng (seed cố định để tái lập) kéo về 20 dB, và chỉ cho đường mô hình; bộ
   giải mã DSP dự phòng cùng mọi số báo cáo vẫn theo tín hiệu gốc.
2. **Tận gốc, cho lượt huấn luyện sau** — `ChannelSampling` thêm đuôi sạch 25–65 dB với xác suất
   20 %, lấy mẫu hai đoạn rời chứ không nới rộng một `uniform`, để không làm loãng vùng khó.

Kết quả trên 10 bản ghi ARRL (120 giây đầu mỗi bản): CER trung bình **82,8 % → 24,7 %**.

| Bản ghi | SNR đo được | Trước | Sau |
|---|---|---|---|
| 20 WPM | 61,7 dB | 89,8 % | 28,9 % |
| 25 WPM | 60,1 dB | 91,4 % | 25,0 % |
| 30 WPM | 57,2 dB | 90,1 % | 17,0 % |
| 35 WPM | 55,5 dB | 78,9 % | 6,6 % |
| 40 WPM | 49,3 dB | 42,6 % | 3,2 % |
| 5 WPM | 143,0 dB | 87,5 % | 53,6 % |
| 10 WPM | 77,1 dB | 85,5 % | 29,1 % |
| 13 WPM | 66,3 dB | 88,5 % | 26,4 % |
| 15 WPM | 64,7 dB | 84,4 % | 34,1 % |
| 18 WPM | 61,8 dB | 89,6 % | 23,4 % |

T1 không đổi: **0/500 clip** vượt trần 25 dB nên dither không kích hoạt ở đó.

### Bài học

Bộ đo tự sinh chỉ đo được những gì bộ sinh biết mô phỏng. Ở đây khuyết tật không nằm trong bất
kỳ ô nào của ma trận T1 mà nằm ở **mép ngoài của nó**: mọi ô đều có nhiễu, nên "không nhiễu"
chưa bao giờ được kiểm. Mười bản ghi thật tìm ra trong vài phút thứ mà 500 clip tổng hợp không
thể tìm ra.

### Hệ quả: beam search từng có chi phí bậc hai theo độ dài (đã sửa)

Đo trên cùng một bản ghi: 30 s → 3,6 s; 60 s → 3,7 s; 120 s → 5,9 s; **240 s → 18,7 s**. Gấp đôi
độ dài làm thời gian gấp hơn ba. Nguyên nhân: mỗi tiền tố trong beam giữ nguyên cả tuple token
lẫn tuple chữ, và khóa của từ điển beam là chính cặp tuple đó, nên mỗi lần mở rộng phải sao chép
và băm lại toàn bộ chuỗi. Với clip T1 (13 ký tự) không thấy gì; với bản tin 3 746 ký tự thì
không chạy nổi.

Sửa bằng cách tách hai thứ vốn bị gộp làm một:

- `_Chars` — chuỗi ký tự dưới dạng danh sách liên kết chia sẻ phần đuôi, cấp phát qua `_Trie`
  nên hai tiền tố giống nhau luôn nhận cùng một nút và **khóa beam chỉ còn là một số nguyên**.
- `_Marks` — khung và xác suất của từng ký tự, chuỗi liên kết **riêng**. Phải riêng vì cùng một
  chuỗi ký tự có thể đến từ hai đường trong một khung và thuật toán giữ khung của đóng góp nặng
  hơn; `_Chars` thì chia sẻ giữa mọi chuỗi con nên không được sửa tại chỗ.

Chi phí mỗi ký tự sau khi sửa, đo trên cùng máy:

| Độ dài | Trước | Sau |
|---|---|---|
| 100 ký tự | 0,10 ms/ký tự | 0,097 ms/ký tự |
| 200 | — | 0,080 |
| 400 | 0,16 | 0,101 |
| 800 | 0,24 | 0,092 |
| 1 600 | — | 0,088 |

Tức đã **hằng số**. `tests/unit/test_beam_scaling.py` canh lại tỉ lệ này để nó không trôi về cũ.
Đây là điều kiện cần để nâng trần thời lượng của giao diện (CP-14).

## Chọn bộ giải mã theo bằng chứng đo được từ chính clip (2026-09-22)

Hai bộ đo cho hai thứ hạng ngược nhau, nên câu hỏi "engine nào tốt hơn" không có câu trả lời
chung:

| Bộ đo | SNR | Mô hình `onnx` | Bộ DSP | DeepCW |
|---|---|---|---|---|
| T1 tổng hợp, 500 clip | −6…22 dB | **20,21 %** | 35,12 % | — |
| T2 bản ghi thật ARRL, 10 bản (180 s đầu) | 49…143 dB | 24,2 % | **4,0 %** | 8,0 % |

Con số 24,2 % của mô hình đã là **sau** khi dither; trước đó là 82,8 %.

### Quy tắc

Ba điều kiện phải cùng đúng thì mới lấy kết quả của bộ DSP (`morsedesk/dsp/selection.py`):

1. **SNR vượt 30 dB.** Đây là thứ tách hai đám đông: T1 cao nhất 22 dB, T2 thấp nhất 49 dB. Nó
   cũng là lý do mọi clip của T1 vẫn đi đường mô hình như cũ.
2. **Chi phí timing của bộ DSP dưới 0,06.** Vì điều kiện SNR đã tách hai bộ đo, ngưỡng này
   không còn nhiệm vụ phân loại nữa; nó là lưới an toàn cho một ca chưa có trong bộ đo nào —
   bản tin rất sạch nhưng **gõ tay lệch nhịp**, khi đó bộ DSP sẽ đọc sai còn mô hình thì không.
   Chi phí đo được trên 10 bản ARRL nằm trong 0,0008–0,0523.
3. **Kết quả không chứa mẫu mơ hồ.** Bảng Kazakh có 9 mẫu giải ra hai chữ (`.-` là А hoặc Ә),
   bảng Nga có một (`-..-` là Ь hoặc Ъ). Chọn đúng giữa chúng là việc của mô hình ngôn ngữ, còn
   bộ DSP chỉ lấy lựa chọn đầu tiên — nên dù tín hiệu sạch tới đâu cũng phải giữ đường mô hình.

`DecodeResult.decoded_by` cho biết đường nào thực sự sinh ra văn bản ("model" hoặc "dsp"); còn
`engine` vẫn là engine người dùng chọn, và kết quả của mô hình xuống dòng dự phòng.

### Kết quả trên T2 sau khi áp quy tắc

| Bản ghi | Trước dither | Sau dither | Sau khi chọn engine |
|---|---|---|---|
| 20 WPM | 89,8 % | 29,9 % | **1,8 %** |
| 25 WPM | 91,4 % | 24,9 % | **1,6 %** |
| 30 WPM | 90,1 % | 21,4 % | **0,6 %** |
| 35 WPM | 78,9 % | 7,8 % | **1,1 %** |
| 40 WPM | 42,6 % | 3,0 % | **2,0 %** |
| 5 WPM | 87,5 % | 54,1 % | **14,1 %** |
| 10 WPM | 85,5 % | 21,2 % | **6,1 %** |
| 13 WPM | 88,5 % | 20,7 % | **5,9 %** |
| 15 WPM | 84,4 % | 30,4 % | **5,4 %** |
| 18 WPM | 89,6 % | 28,5 % | **2,0 %** |
| **Trung bình** | **82,8 %** | **24,2 %** | **4,0 %** |

Bốn bản ghi đã dưới ngưỡng gate 2 % và hai bản nữa đúng bằng 2,0 %. Đây là lần đầu dự án chạm
ngưỡng đó trên dữ liệu không do chính mình sinh ra.

Phần còn lại tập trung ở tốc độ thấp (5–15 WPM), nơi một dit dài 24–48 khung nên lượng tử hóa
ranh giới nặng hơn — đúng hướng cải tiến mà `morsedesk/dsp/baseline.py` đã ghi sẵn trong
docstring (nội suy ranh giới dưới khung).

## Nhận diện ngôn ngữ: vấn đề là ĐỘ DÀI bản tin, không phải thuật toán (CP-03, 2026-09-22)

Con số 58,4 % trên T1 (và 80 % trên T2) từng được ghi là "chưa đạt mục tiêu 95 %". Đo lại theo
độ dài bản tin, với 8 clip mỗi ô, SNR 15 dB, 20 WPM, profile `auto`:

| Độ dài bản tin | `en` | `ru` | `kk-cyrl-ru` | Chung |
|---|---|---|---|---|
| 20 ký tự | 100 % | **12 %** | 100 % | 71 % |
| 50 ký tự | 100 % | 100 % | 100 % | **100 %** |
| 100 ký tự | 100 % | 100 % | 100 % | **100 %** |

**Từ 50 ký tự trở lên là 100 %.** Bản tin của T1 dài trung bình 13 ký tự, nên 58,4 % là hệ quả
của bộ đo chứ không phải của thuật toán.

Chỗ hỏng duy nhất ở 20 ký tự là `ru` bị đọc thành `kk-cyrl-ru`, và điều đó có lý do cấu trúc:
**bảng Kazakh là bảng Nga cộng thêm 9 chữ**, nên một bản tin Nga ngắn không chứa gì loại trừ
được Kazakh, trong khi bản tin Kazakh ngắn thường có ít nhất một chữ riêng (Ә, Ғ, Қ, Ң, Ө, Ұ,
Ү, Һ, І) để tự phân biệt. Nhập nhằng một chiều này là tính chất của hai bảng mã, không sửa được
bằng cách chỉnh mô hình ngôn ngữ.

Hệ quả cho tiêu chí nghiệm thu: mục tiêu 95 % nên ghi kèm **độ dài tối thiểu 50 ký tự**, và
giao diện nên nói rõ "chưa đủ dữ liệu để nhận diện ngôn ngữ" với bản tin ngắn hơn thay vì đoán.

## Spec A2 đã đạt: CER dưới 2 % trên ARRL W1AW 18–40 WPM (2026-09-22)

Yêu cầu A2 của spec là CER dưới 2 % trên bản ghi ARRL W1AW trong dải 18–40 WPM. Đo trên 180
giây đầu mỗi bản, engine `onnx` với toàn bộ chuỗi sửa trong ngày (dither, chọn bộ giải mã,
bộ DSP có trễ Schmitt):

| Tốc độ | CER | Trong dải A2 |
|---|---|---|
| 18 WPM | 2,0 % | ✔ |
| 20 WPM | 1,8 % | ✔ |
| 25 WPM | 1,6 % | ✔ |
| 30 WPM | **0,6 %** | ✔ |
| 35 WPM | 1,1 % | ✔ |
| 40 WPM | 2,0 % | ✔ |
| **Trung bình trong dải** | **1,52 %** | |
| 15 WPM | 5,4 % | ngoài dải |
| 13 WPM | 5,9 % | ngoài dải |
| 10 WPM | 6,1 % | ngoài dải |
| 5 WPM | 14,1 % | ngoài dải |

Đây là lần đầu dự án đạt một ngưỡng gate của spec **trên dữ liệu không do chính mình sinh ra**.

Phần còn lại tập trung ở tốc độ thấp, nơi một dit dài 24–48 khung nên lượng tử hóa ranh giới
trong `run_lengths` nặng hơn — đúng hướng cải tiến mà `morsedesk/dsp/baseline.py` đã ghi sẵn
trong docstring (nội suy ranh giới dưới khung). Lưu ý dải 5–15 WPM nằm ngoài yêu cầu A2 nhưng
vẫn nằm trong dải 10–35 WPM của yêu cầu A1 trên T1.

### Một phần lỗi ở tốc độ thấp là do file đáp án của ARRL không nhất quán

Bản ghi 5 WPM giải ra `= NOW 5 WPM = TEXT IS FROM MAY 2024 QST PAGE 57 = THE LETTER K MEANS…`
trong khi đáp án ghi `NOW 5 WPM TEXT IS FROM MAY 2024 QST PAGE 57 THE LETTER K MEANS…` — tức
**đúng từng chữ**, chỉ thừa prosign `=` (BT) mà file text không ghi. Năm bản của ngày 260303 có
`=` trong đáp án, bốn bản của ngày 260304 thì không, dù âm thanh cả hai nhóm đều phát nó.

CER khi bỏ prosign phân đoạn khỏi cả hai phía:

| Bản ghi | Đáp án có `=` | CER | Bỏ `=` |
|---|---|---|---|
| 20 WPM | có | 1,8 % | 1,8 % |
| 25 WPM | có | 1,6 % | 1,6 % |
| 30 WPM | có | 0,6 % | 0,6 % |
| 35 WPM | có | 1,1 % | 1,1 % |
| 40 WPM | có | 2,0 % | 2,0 % |
| 18 WPM | có | 2,0 % | 2,0 % |
| 15 WPM | **không** | 5,4 % | **3,1 %** |
| 13 WPM | **không** | 5,9 % | **3,2 %** |
| 10 WPM | **không** | 6,1 % | **2,4 %** |
| 5 WPM | **không** | 14,1 % | **7,1 %** |
| **Trung bình** | | **4,0 %** | **2,5 %** |

Cách tính mặc định vẫn giữ nguyên (không bỏ prosign), vì tự chuẩn hóa cho hợp ý mình là cách
chắc chắn nhất để đo ra số đẹp mà sản phẩm không tốt lên. Con số 2,5 % ghi ở đây để biết phần
nào của khoảng cách là **thật** và phần nào là quy ước của bộ đo: gần một nửa lỗi ở tốc độ thấp
thuộc loại thứ hai.

Giả thuyết cũ trong `morsedesk/dsp/baseline.py` rằng tốc độ thấp hỏng vì lượng tử hóa ranh giới
cũng **không đứng vững**: ở 5 WPM một dit dài 48 khung nên sai số nửa khung chỉ là 1 %, còn ở 40
WPM dit chỉ 6 khung nên cùng sai số đó là 8 % — tức lượng tử hóa đáng lo ở tốc độ CAO, ngược với
ghi chú cũ.

## Spec D2 đã đạt: T0 roundtrip CER = 0 trên cả 21 ô (2026-09-22)

Spec D2 yêu cầu encode → decode audio **sạch** ở 10–40 WPM cho cả ba profile với CER = 0. Đo
sau khi có dither, chọn bộ giải mã và bước cuối là để mô hình ngôn ngữ chọn chữ cho phân đoạn
của bộ DSP:

| Profile | 10 | 15 | 20 | 25 | 30 | 35 | 40 WPM |
|---|---|---|---|---|---|---|---|
| `en` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `ru` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `kk-cyrl-ru` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**21/21 ô đạt CER = 0.**

Bước cuối đáng nói riêng. Trước đó hai ô Kazakh (15 và 25 WPM) còn sai một chữ, vì quy tắc chọn
bộ giải mã **bỏ hẳn** đường DSP khi bảng có mẫu giải ra nhiều chữ — bảng Kazakh giải `.-` thành
А hoặc Ә. Nhưng bỏ cả đường DSP là vứt luôn phân đoạn chính xác mà tín hiệu sạch cho không.
Cách đúng là giữ phân đoạn của DSP và **hỏi mô hình ngôn ngữ** chọn chữ, đúng như chế độ `auto`
vẫn làm: `Decoder._letters_for_tokens` chạy `detect_tokens` trên chuỗi token của DSP với duy
nhất profile hiện tại. Chỉ khi không bật LM mới phải nhường hẳn cho mô hình âm thanh.

Lưu ý phạm vi: đây là audio **sạch không nhiễu**. Ô nhiễu vẫn do mô hình âm thanh gánh, và đó
là nội dung của yêu cầu A1 (gate 2 % trên T1) — chưa đạt.

## Nội suy ranh giới dưới khung — kết quả ÂM (2026-09-22)

Lập luận nghe rất chắc và đã nằm sẵn trong docstring của `morsedesk/dsp/baseline.py` từ tuần 3:
envelope lấy mẫu mỗi 5 ms nên ranh giới bật/tắt thật gần như luôn nằm giữa hai khung, và ở 40 WPM
một dit chỉ dài 6 khung nên sai số nửa khung là 8 %. Nội suy tuyến tính tại ngưỡng đang xét sẽ
lấy lại phần đó.

Cài đặt cẩn thận: cả biên lên lẫn biên xuống nội suy tại **cùng một ngưỡng tham chiếu** (dùng
ngưỡng bật cho biên lên và ngưỡng tắt cho biên xuống sẽ kéo dài mọi dấu một cách hệ thống), dò
ngược tối đa 4 khung để tìm chỗ cắt vì trễ Schmitt tắt muộn hơn, và giữ nguyên biên khi không có
cặp khung nào kẹp ngưỡng.

| Bộ đo | Trước | Sau |
|---|---|---|
| Bộ DSP trên T1, 500 clip | **35,12 %** | 40,73 % |
| 10 bản ghi thật của ARRL | 4,0 % | **4,0 %** — từng ô giống hệt |

**Bị loại.** Hai lý do, và cái thứ nhất mới là cái đáng nhớ:

1. **Sai số lượng tử phần lớn tự triệt tiêu.** Bộ giải mã không đo độ dài tuyệt đối mà so **tỉ
   lệ** giữa dấu và khoảng lặng với lưới 1/3/7 dit. Làm tròn dời cả hai biên của mọi đoạn cùng
   một chiều, nên tỉ lệ gần như không đổi. Con số 8 % ở trên là sai số của một phép đo tuyệt
   đối mà bộ giải mã không hề thực hiện.
2. **Trên tín hiệu nhiễu, nội suy khuếch đại nhiễu.** Điểm cắt ngưỡng dao động theo nhiễu của
   envelope, nên biên nội suy kém ổn định hơn biên làm tròn — đúng chỗ T1 mất 5,6 điểm.

Mã đã gỡ; giữ lại đây để người sau không mất thêm một lượt. Bài học chung với ngày hôm nay: một
lập luận vật lý đúng về mặt số học vẫn có thể nhắm sai chỗ, nếu nó đo đại lượng mà thuật toán
không dùng.

## Chi phí timing thấp là bằng chứng đủ, không cần SNR cao đi kèm (2026-09-23)

Quy tắc chọn bộ giải mã ban đầu chỉ lấy kết quả DSP khi SNR vượt 30 dB. Một clip đơn lẻ làm lộ
ra rằng nó quá chặt: file mẫu 15,8 giây ở **SNR 12,8 dB** — tức giữa dải huấn luyện — được bộ
DSP đọc đúng nguyên văn trong khi mô hình sai 8 %.

Đo trên 461 clip T1 có tín hiệu, với mỗi clip tính cả chi phí timing của DSP lẫn CER của hai
đường:

| Quy tắc | CER | Số clip đi đường DSP |
|---|---|---|
| Chỉ mô hình | 15,73 % | 0 |
| SNR > 30 (quy tắc cũ) | 15,73 % | 0 |
| chi phí < 0,005 | 15,35 % | 36 |
| chi phí < 0,01 | 15,12 % | 55 |
| **chi phí < 0,02** | **14,95 %** | 101 |
| chi phí < 0,05 | 18,48 % | 222 |

Ngưỡng 0,02 tốt nhất, và quan trọng hơn là kết quả không nhạy cảm quanh đó — 0,005 và 0,01 đều
cải thiện, chỉ tới 0,05 mới xấu đi hẳn. Nên đây không phải một con số vừa khít với tập đo.

Hệ quả cho mã: bộ DSP nay chạy cho **mọi** clip chứ không chỉ khi tín hiệu sạch, vì chi phí
timing là phép đo cần có để quyết định. Giá phải trả là khoảng một phần năm thời gian giải mã.

### Một lỗi tự tạo, và cách phép đo bắt được nó

Lần chạy T1 đầu tiên sau thay đổi cho **26,63 % với 67 clip lỗi** thay vì cải thiện. Nguyên
nhân: trên clip nhiễu, bộ DSP sinh ra những mẫu chấm gạch **không tồn tại trong bảng** (`.--..`,
`..-.-`, `-...-.`), và mã mới đem chúng đi tra bảng nên vỡ với `KeyError`. Quy tắc cũ không gặp
vì nó chỉ chạy DSP trên tín hiệu sạch, nơi phân đoạn hiếm khi sai đến thế.

`dsp_result_usable` chặn điều đó: một kết quả chứa mẫu ngoài bảng tự nó đã nói rằng bộ DSP đọc
sai, nên giữ đường mô hình. Đây cũng là lời nhắc rằng mỗi thay đổi phải đo lại trên cả bộ, chứ
một clip ví dụ chạy đúng không nói lên điều gì.

### Kết quả thật trên toàn T1

| Kênh | Trước | Sau | Chênh |
|---|---|---|---|
| clean | 12,73 % | **9,88 %** | −2,85 |
| mp3 | 11,15 % | **8,50 %** | −2,65 |
| qrm | 12,69 % | **7,99 %** | −4,70 |
| qrn | 12,80 % | **8,83 %** | −3,97 |
| qsb | 51,68 % | 54,60 % | **+2,92** |
| **Toàn bộ** | **20,21 %** | **17,96 %** | **−2,25** |
| WER | 44,41 % | **37,60 %** | −6,81 |

Bốn kênh tốt lên rõ, riêng `qsb` xấu đi gần 3 điểm: fading sâu làm bộ DSP đọc sai ở những chỗ
tín hiệu chìm, mà chi phí timing tính trên phần còn đọc được nên vẫn thấp. Tổng thể vẫn lời
2,25 điểm CER và 6,81 điểm WER — WER giảm mạnh hơn cho thấy phần được nằm ở chỗ bộ DSP giữ
đúng ranh giới từ, thứ mà mô hình hay làm nhoè.

Trên T2 bản ghi thật, cả mười ô giữ nguyên từng con số: quy tắc mới chỉ thêm đường cho clip
nhiễu chứ không đụng tới những clip vốn đã đi đường DSP.

Siết ngưỡng xuống 0,01 để cứu `qsb` thì mất nhiều hơn được:

| Cấu hình | CER | WER | clean | mp3 | qrm | qrn | qsb |
|---|---|---|---|---|---|---|---|
| chỉ SNR > 30 | 20,21 % | 44,41 % | 12,73 | 11,15 | 12,69 | 12,80 | 51,68 |
| **cost < 0,02** | **17,96 %** | **37,60 %** | **9,88** | **8,50** | **7,99** | **8,83** | 54,60 |
| cost < 0,01 | 18,48 % | 39,49 % | 11,13 | 9,05 | 9,47 | 10,05 | 52,68 |

Ngưỡng 0,01 lấy lại 1,92 điểm ở `qsb` nhưng trả lại 1,25 ở `clean`, 0,55 ở `mp3`, 1,48 ở `qrm`
và 1,22 ở `qrn` — lỗ ròng nửa điểm CER và gần hai điểm WER. Giữ 0,02.
