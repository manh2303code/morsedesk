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
