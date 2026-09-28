# Điện văn mạng CW + phím "nhẹ": vì sao app sai 23 %, hướng sửa (28/09/2026)

Người dùng 28/09: dựa trên file thật `testdata/private/t6/net_msg_cut_numbers.wav` (5:51, 16 WPM, 1002 Hz,
SNR 32 dB) — "tối ưu lại thuật toán hoặc thêm model nhỏ ở layer giữa chuyên xử lý các trường hợp này… có
giống MoE không? Goal: chính xác tuyệt đối trên điện văn gọi đài Latin + nhiều nhóm số dài".

## 1. Đáp án (hai giám khảo LLM độc lập, khớp 311/316)

Định dạng: mạng CW quân sự Trung Quốc **M89/M95** (UDXF, numbersoddities.nl/Chinese-military-nets.pdf),
gốc quy trình điện báo Liên Xô (ЖЖЖ = VVV, hô hiệu x2–3, ДЕ):
`VV CYHM CYHM DE NJWY NJWY HR MSG GA NR 015/CK 31 16 0914 1900 RMKS … = <31 nhóm 4 ký tự> AR HR`, rồi đài
khác `QSL? HR WKNR 28T`. `CK` = SỐ NHÓM (khớp 31); số viết tắt A1 U2 V3 D8 N9 T0; 8 chấm = xóa, `?` sau nhóm
hỏng = đánh lại. `HR 7GGA` = `HR MSG GA` với khoảng M|S bị bỏ (`--` + `...` = `--...` = 7).

## 2. Số đo

| | app hiện tại (auto+LM) |
|---|---|
| toàn bài, theo mẫu chấm-gạch | 23,4 % |
| thân điện 31 nhóm | 25/31 nhóm đúng (81 %), 5/124 chữ số sai |
| gọi đài / mào đầu / đài trả lời | 48 / 25 / 37 % |

Mọi bộ giải (model có/không LM, DSP cổ điển, E17) sai CÙNG kiểu -> không phải LM.

**Nguyên nhân: phím "nhẹ"** — chấm ~0,6 đơn vị (khoảng lặng ~1,0–1,4), chấm NGAY SAU gạch 0,1–0,5: `C`→`G`,
`Y`→`O`, `K`→`M`, số 5 phần tử bị tách đôi, `VV` đánh liền, 8 chấm -> `S/E`. Dữ liệu huấn luyện
(data/keyer.py) chỉ có jitter + tỉ lệ gạch/chấm 2–4,5, không có bất đối xứng bật/tắt hay rút chấm sau gạch.
Bước khung 5 ms: chấm 7–22 ms vẫn thấy được (không phải giới hạn đặc trưng). keyed.py hỏng với phím nhẹ vì:
đơn vị lấy từ khoảng lặng ngắn nhất (phồng), vứt xung < 0,4 đơn vị, cửa sổ chấm 0,5–1,8 / gạch 2,2–4,6 cố
định -> 75/340 ký tự "mẫu không rõ", đúng những ký tự app sai.

**E1 — bộ đọc nhịp phím tự thích nghi** (phân cụm log-độ dài xung 2 cụm; khoảng lặng 2 tầng; ~40 dòng, không
luật tay): 5,7 % trên file thật (10/18 lỗi còn lại là `VV` đánh liền -> mẫu 8 phần tử, sửa được bằng luật tách).

**E2 — điện văn tổng hợp cùng kiểu**, 6 điện x 2 lối phím x 5 SNR, CER theo nghĩa (Kirin->Latin, số viết tắt->số):

| lối phím | SNR | app hiện tại | nhịp phím tự thích nghi |
|---|---|---|---|
| chuẩn | 30…8 dB | 0,00 % | 0 % (>= 12 dB), 60 % ở 8 dB |
| chuẩn | 4 dB | 0,5 % | hỏng |
| nhẹ | 30 / 20 / 12 dB | 53 / 52 / 37 % | 6 / 8 / 7 % |
| nhẹ | 8 / 4 dB | 36 / 41 % | 37 % / hỏng |

=> lỗi do LỐI PHÍM (cùng nội dung, phím chuẩn: đúng tuyệt đối tới 8 dB); chuyên gia nhịp phím cứu tín hiệu
sạch nhưng sụp khi nhiễu -> mô hình phải học phím nhẹ.

## 3. Tra cứu (3 agent)

- **MoE trong mạng 1,1 M tham số: không nên.** Mọi thành công MoE giọng nói ở 70 M+ tham số, hàng nghìn giờ,
  miền tách bạch; router sụp/lệch tải với ít dữ liệu. Chứng cứ về dịch phân bố: đa dạng DỮ LIỆU mới giúp,
  không phải thêm năng lực. MorseDesk ĐÃ là "MoE mức hệ thống" kiểu Jacobs 1991: chuyên gia = CTC+LM, DSP,
  nhịp phím; router = luật bằng chứng (SNR, độ tách cụm, độ khớp); cổng = chọn cứng/bỏ phiếu. Nên làm mạnh
  kiến trúc này, không nhét MoE vào mạng.
- **Bộ giải khác:** fldigi SOM so mẫu TƯƠNG ĐỐI (chia cho phần tử dài nhất của ký tự — `C` 2,5 0,3 2,1 0,5 vẫn
  gần `-.-.`); ggmorse ước lượng chấm/gạch riêng rồi co giãn quanh tâm (bù weight); không ai mô hình hóa
  "chấm sau gạch bị rút". morseformer: nới dải méo chỉ giúp một phần; bước lớn nhất là trộn 30 % âm thanh gõ
  tay THẬT có căn chỉnh.
- **Cấu trúc điện văn** dùng để tự sửa: hô hiệu lặp (bỏ phiếu), nhóm đúng 4 ký tự, CK = số nhóm (lệch thì
  cảnh báo, không tự thêm/bớt), 8 chấm/`?` = xóa + đánh lại (căn đoạn đánh lại với đoạn trước), cụm thủ tục
  `HR MSG GA / QSL? / MSG AGN / PSE CY` so theo chuỗi phần tử bỏ qua khoảng giữa chữ (chỉ ở vùng mào đầu).
  Rủi ro: số viết tắt trong hô hiệu (MW3D), 6 chấm = dấu chấm Nga, `?` cũng là dấu hỏi thật -> luôn giữ bản
  thô, ghi mọi sửa.

## 4. Kế hoạch (mỗi bước đo trước/sau; hồi quy T1/dev/dev-OOV/T2/T4/T5/T6, bộ test số, long_random)

1. **Chuyên gia nhịp phím v2 (keyed.py):** phân loại xung/khoảng lặng tự thích nghi theo tín hiệu; bỏ cổng
   0,4 đơn vị (thay bằng >= 2 khung + thuần tone); so mẫu tương đối; ước lượng + bù weight; tách mẫu không có
   trong bảng thành hai ký tự hợp lệ (`VV`); >= 6–8 chấm liền = xóa. Đích: file thật ~2–3 %, tổng hợp phím
   nhẹ >= 12 dB ~5 %, không hồi quy.
2. **Tinh chỉnh mô hình với "lối phím" (GPU, E20):** mỗi clip một lối: weight -0,4…+0,3 giữ nhịp, tỉ lệ
   gạch/chấm 2,5–6, xác suất rút chấm sau gạch x0,2–1,0, bug, cặp chữ đánh liền, 6–10 chấm xóa; văn bản điện
   mạng (gọi đài/NR/CK/nhóm số viết tắt). Đích: phím nhẹ ở 8/4 dB, phím chuẩn không đổi. Bản ghi thật này là
   tập GIỮ RIÊNG, không huấn luyện.
3. **Trọng tài theo đoạn:** chọn/kết hợp mô hình và nhịp phím theo từng đoạn ký tự (độ tách cụm, SNR cục bộ,
   xác suất hậu nghiệm đã hiệu chuẩn) thay cổng toàn bài.
4. **Lớp cấu trúc điện văn:** vùng (gọi đài/mào đầu/thân/kết), bỏ phiếu hô hiệu, nhóm 4 ký tự, kiểm CK,
   xử lý xóa/`?`, cụm thủ tục; hiện bản thô + sửa có đánh dấu.
5. Về sau: nhãn giả từ bản ghi sạch thật (chuyên gia nhịp phím) để tinh chỉnh tiếp mô hình.

Công cụ tạm (scratchpad, sẽ đưa vào tools/ ở bước 1): score theo mẫu, semscore theo nghĩa, exp_keyed_adaptive
(E1), exp_synth (E2 — bộ tổng hợp điện mạng + lối phím nhẹ).

## 5. Làm theo kế hoạch (28/09 chiều) — T7, số đo trên 3 file thật + bản chép nhân viên

**Bộ đo T7** (`testdata/private/t7`, gitignored): net1_351 (file trên), net2_347, net3_352 — người dùng gửi thêm
2 file cùng kiểu và BẢN CHÉP của nhân viên cho cả ba. Đáp án = 2 giám khảo LLM (351: 311/316 khớp; 352: 93 %;
347: 80 %, fading sâu 0:57–1:13) + bản chép căn vào vùng nhóm số (`tools/copy_align.py`: chỉ đổi chữ số khi
bản chép lệch <= 1 phần tử so với cách đọc của một giám khảo — lỗi phím nhẹ `V`/`U`, `D`/`N`, `6`/`5`; lệch xa
thì sửa nhưng giữ "không chắc"). Hô hiệu KHÔNG sửa theo bản chép: 352 bản chép ghi RY2J nhưng nhịp phím đo được
`-.- -.- ...-- .---` = KK3J cả 3 lần. `tools/net_eval.py` chấm: mẫu (số viết tắt = chữ số), nghĩa, nhóm theo
mẫu, và **nhóm bản chép đúng NHƯ HIỆN RA** (thước đo gần người dùng nhất: nhóm dính liền = sai).

**Lối phím THẬT (đo, đơn vị nhịp)** — bác bỏ giả thuyết "chấm sau gạch bị rút" của §2:

| | chấm | gạch | lặng sau chấm | lặng sau gạch (trong ký tự) | giữa chữ | giữa từ |
|---|---|---|---|---|---|---|
| 351 | 0,60 | 2,65 | 1,27 | **0,87** | 4,3 | nén vào ~5–6 |
| 352 | 0,75 | 2,8 | 1,14 | 0,8–1,0 | 3,5–4,5 | 7–14 |
| 347 | 0,77 | 2,9 | 1,23 | 0,9–1,0 | ~4 | 6–8 |

Chấm NGAY SAU gạch dài y như chấm khác (351: 0,60 và 0,60); cái bị rút là LẶNG giữa gạch và phần tử sau (phần tử
tới sớm ~0,5 đơn vị). Mọi xung hụt ~0,4 đơn vị, phần hụt dồn sang lặng sau (chấm -> chấm vẫn 1,93). Mô hình lối
phím của data/keyer.py (E21), tools/net_traffic_bench.py và test sửa theo bảng này; E20 đã học mô hình đoán sai.

**Các bước và số đo** (app = auto + LM; nhóm bản chép: 35 + 36 + 37 = 108):

| bước | 351 mẫu / nghĩa | nhóm bản chép 351 / 347 / 352 |
|---|---|---|
| trước (E18, 27/09) | 23,73 / 30,70 % | 9 / 10 / 27 |
| + nhịp phím v2, chỉ bật khi phím nhẹ (cổng) | 3,80 / 8,86 % | 9 / 10 / 27 |
| + tầng cấu trúc (chia nhóm sau RMKS, số viết tắt -> số) | 3,80 / 5,06 % | 31 / 34 / 32 |
| + nhịp phím làm nguồn CHÍNH khi phím nhẹ tách bạch | 2,85 / 3,48 % | 31 / 34 / 32 |
| + giữ chấm ngắn sát xung khác ở MỘT phía | 2,53 / 3,16 % | 31 / 34 / 32 |
| + `TO` là từ, dãy số đủ nhóm tách khỏi chữ lạ | (như trên) | **34 / 36 / 34** |

- **Cổng phím nhẹ** (keyed.py `_light_fist`): >= 60 chấm, chấm/lặng trong ký tự < 0,7 VÀ hụt >= 2,5 khung (ngưỡng
  cắt tự làm hụt ~1 khung: ebook2cw 35 WPM có tỉ lệ 0,75). Quét T1/dev/oov/T2/T4/T5/T6/T7 (1 588 clip): chỉ
  net1_351 qua cổng. Không cổng: T1 +0,04, dev +0,06 (5 clip xấu: nhiễu xung thành "chấm" giữa hai gạch). Có
  cổng: T1/dev/dev-OOV/T2 **giống hệt từng clip** (ghép cặp, scripts/regress_pair.sh).
- **Nhịp phím làm nguồn chính** (`reconcile`, khi `separable`): mô hình chưa học phím nhẹ khớp nhịp phím < 80 %
  nên cổng mức đồng ý (lập 27/09 cho trạm số M14 thu sóng ngắn) từ chối đúng lúc nhịp phím đúng còn mô hình sai.
- **Tầng cấu trúc** (`morsedesk/traffic.py`): chỉ khi có mốc RMKS (theo MẪU — 352 bị tự nhận là tiếng Nga,
  `РМКС`) và vùng sau nó >= 80 % ký tự số. Không đụng mào đầu/hô hiệu.

**Đã thử và BỊ SỐ ĐO BÁC BỎ:** đo khoảng lặng "theo nhịp" (từ đầu xung trừ độ dài danh nghĩa, giả định phần hụt
của chấm dồn sang lặng sau): 351 xấu 3,80 -> 7,28 %. Người gửi thật không dồn như thế (bảng trên).

**Bộ tổng hợp với lối phím ĐO THẬT** (tools/net_traffic_bench.py, 6 điện x 5 SNR, CER theo NGHĨA — chấm theo bản
chữ số do bộ sinh ra: nhóm toàn chữ viết tắt `TVVV` = 0333; trước đó thước đo tính nhầm cả chỗ app ĐÚNG là lỗi):

| mã hiện tại + | chuẩn | t7mid (~352) | t7light (~351) |
|---|---|---|---|
| E18 | 0,00 % | 0,28 % | 2,21 % (0 % ở 30/20 dB — nhịp phím làm chính; 2,8–4,6 % ở 12–4 dB) |
| E20 | 0,00 % | 0,13 % | 0,08 % |

Trước khi sửa luật giữ chấm ngắn (đòi sát xung khác ở CẢ HAI phía -> chấm CUỐI ký tự 0,38 đơn vị bị bỏ: `5` ->
`H`, `6` -> `B`) t7light ở 30/20 dB sai 7,8–8,3 % với cả hai mô hình.

**T7 thật, mã cuối (nhóm bản chép 351 / 347 / 352):** E18 34 / 36 / 34 = **104/108**, 351 theo mẫu 2,53 %;
E20 34 / 35 / 30 = 99/108 (tổng hợp tốt hơn nhưng file thật 352 KÉM: `1360` -> `Е36Т`, `5390` -> `5399`)
-> không dùng E20. 4 nhóm còn sai đều do đọc sai ký tự: `2094` -> `2093` (351), `Л` thay `D`/`9` và
`3408` -> `3498` (352).
