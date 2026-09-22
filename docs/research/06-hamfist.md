# HamFist: đánh giá và những gì lấy được

Ngày 2026-09-22. Nguồn: https://github.com/dawsonjon/HamFist (Jonathan P Dawson), giấy phép **MIT**.
Bản clone dùng để đo nằm ở thư mục nháp của phiên làm việc, không đưa vào repo.

## 1. Cơ chế

Bộ giải mã CW cho Raspberry Pi Pico, viết bằng C++, kèm **mô hình tham chiếu bằng Python**
(`python_model/cw_decode.py`, 256 dòng) nên đọc được thuật toán mà không cần đọc mã nhúng.

**Tầng tín hiệu** (`cw_decoder/cw_dsp.cpp`): FFT 64 điểm ở 15 kHz, 6 kênh × 5 bin. Mỗi bin giữ một
ước lượng nền nhiễu và cập nhật **có cổng**:

```cpp
if (magnitude < 2.0 * noise_estimate || magnitude < 5) {
    noise_estimate = 0.99*noise + 0.01*magnitude;   // im lặng: cập nhật chậm
    gate_count = 0;
} else if (gate_count > 50) {
    noise_estimate = 0.9*noise + 0.1*magnitude;     // mức cao kéo dài: cả băng to lên thật
} else {
    gate_count++;                                    // đang có dấu: KHÔNG cập nhật
}
threshold = noise_estimate * thresh_mult;
```

Kèm trễ Schmitt: bật khi vượt ngưỡng, chỉ tắt khi rơi dưới `0.7 × ngưỡng`. Sau 500 khung im lặng
thì giải mã những gì đang có rồi **học lại** thống kê timing. Và có một cổng quan trọng: chỉ giải
mã khi `get_snr(channel) > 12.0f`, tức **từ chối tín hiệu yếu thay vì cố đoán**.

**Tầng phân loại**: k-means, 2 cụm trên độ dài các dấu (chấm/gạch), 3 cụm trên độ dài các khoảng
lặng (trong chữ / giữa chữ / giữa từ). Không giả định tốc độ trước.

**Tầng giải mã**: beam search Bayes. Mỗi quan sát chấm bằng log-Gaussian theo từng giả thuyết;
beam giữ `(văn bản, mẫu đang dở, log xác suất)`; mẫu bị ràng buộc phải là tiền tố hợp lệ của bảng
Morse. Ở mỗi khoảng giữa từ cộng thưởng ngôn ngữ: `log(6)` nếu là viết tắt nghiệp dư, `log(4)` nếu
nằm trong từ điển 9787 từ. Một chi tiết đúng mà mình nên nhớ: khoảng giữa từ **dài hơn** kỳ vọng
không bị phạt (`log_gaussian(...) if x < long_mu else 0`), vì người gõ có quyền nghỉ lâu.

## 2. Bốn lỗi trong mô hình Python, lộ ra khi chạy trên dữ liệu của mình

Mô hình Python là bản phác, không phải bản chạy thật (bản thật là C++ `cw_classifier.cpp`). Ai
định port thì port từ C++.

| # | Lỗi | Vì sao bản gốc không gặp |
|---|---|---|
| 1 | `np.array(clusters)` trên các cụm khác độ dài → `ValueError` với numpy ≥ 1.24 | numpy cũ chấp nhận mảng răng cưa |
| 2 | `sigma = np.std(dits)` bằng 0 → chia cho 0 → mọi log xác suất thành `nan` | tín hiệu thật luôn có rung; clip gõ bằng máy của mình có timing hoàn toàn đều |
| 3 | k-means không xử lý cụm rỗng; một cụm trống làm `nan` lan ra toàn bộ và dồn hết điểm vào một cụm | khởi tạo xen kẽ thường may mắn trên dữ liệu thật |
| 4 | Bước kết thúc chỉ nhận giả thuyết kết thúc bằng mẫu **hoàn chỉnh**, nên clip kết thúc bằng khoảng lặng trả về rỗng | máy thu của họ cắt ở chỗ có tín hiệu |

Sau khi vá cả bốn, phân cụm chạy rất chuẩn trên clip sạch 12 WPM: dit 19,45 và dah 59,38 (đúng tỉ
lệ 1:3), khoảng lặng 20,4 / 66,9 / 140,5 (đúng 1:3:7), và giải mã ra **"BUT GET ARE" chính xác
tuyệt đối**.

## 3. Số đo trên 167 clip profile `en` của T1

| Cách tách mark/space | CER |
|---|---|
| Ngưỡng cố định 0,45 (như baseline hiện tại của mình) | 823,35 % |
| Trễ Schmitt 0,45/0,30 + làm mượt + xóa run ngắn hơn 0,4 dit | **87,31 %** |

Theo kênh với cách thứ hai: clean 94,61 %, mp3 75,23 %, qrm 79,74 %, qrn 91,69 %, qsb 94,92 %.

Đối chiếu trên cùng bộ: model CTC của mình 23,85 % (beam+LM, toàn T1), DeepCW 22,80 % (trên `en`),
bộ giải mã DSP hiện tại của mình 296 %.

## 4. Kết luận

**Bộ giải mã Bayes rất tốt khi khâu phân đoạn đúng, và sụp hoàn toàn khi phân đoạn sai.** Nó sinh
một ký tự cho **mọi** run, nên vài chục run nhiễu đủ đẩy CER vượt 100 % vì chèn thừa. Bản gốc tránh
điều này bằng cổng SNR 12 dB, tức từ chối làm việc ở mức tín hiệu mà bộ test của mình coi là bình
thường. Đây đúng là điểm yếu cố hữu của bộ giải mã cổ điển và là lý do đường CTC không phân đoạn
vẫn là đường chính.

**Không phải lối tắt tới ngưỡng 2 %.** Nhưng có hai thứ lấy được ngay:

1. **Thay bộ giải mã DSP dự phòng.** Bản hiện tại 296 % là gánh nặng: giao diện hiện nó ra cho
   người dùng dưới nhãn "kết quả bộ giải mã DSP" khi độ tin cậy thấp. Chỉ riêng trễ Schmitt cộng
   xóa run ngắn đã đưa xuống 87 %, tốt hơn 3,4 lần, và chưa tinh chỉnh gì. Thuật toán không phụ
   thuộc bảng chữ nên thay bảng của mình vào là dùng được cho cả Nga và Kazakh.
2. **Ước lượng nền có cổng** cho khâu đặc trưng của model. Đóng băng ước lượng nền khi đang có dấu
   là cách xử lý đúng bản chất hơn so với việc chỉ rút ngắn hằng thời gian AGC như thí nghiệm E7
   đang định làm: vấn đề không nằm ở hằng thời gian dài hay ngắn, mà ở chỗ chính các dấu Morse kéo
   nền lên.

**Không lấy**: mã RP2040, driver màn hình, FFT, vỏ in 3D, bàn phím cảm ứng.

**Một chi tiết nhỏ đáng lấy**: danh sách viết tắt nghiệp dư (`CQ DE K AR BT SK BK AS KN TNX FER UR
OM ES AGN PSE HW ...`) để làm giàu phần thưởng từ vựng cho profile `en`.

## 5. Đã áp dụng: trễ Schmitt + xóa run ngắn cho bộ giải mã DSP (2026-09-22)

Điểm 1 ở mục 4 đã làm xong, nhưng **không** bằng cách port bộ giải mã Bayes của HamFist: chỉ lấy
đúng hai cơ chế tách mark/space của nó và đặt vào bộ giải mã DSP sẵn có
(`morsedesk/dsp/baseline.py`), vì bộ quét (ngưỡng × độ dài dit) theo chi phí timing của mình vốn
đã tốt hơn khâu k-means của họ khi phân đoạn sạch.

| Cách dựng mask | CER trên 152 clip `en` của T1 |
|---|---|
| Ngưỡng cứng (bản cũ) | 306,84 % |
| + trễ Schmitt (tắt ở 0,67 × ngưỡng) | 72,20 % |
| + xóa run ngắn hơn 0,6 dit | **26,44 %** |

Tốt hơn **11,6 lần**. Theo kênh: clean 281,91 → 18,44 %; mp3 287,30 → 20,52; qrm 203,96 → 17,44;
qrn 286,17 → 19,44; qsb 556,86 → 70,65.

### Ba chi tiết chỉ lộ ra khi đo

1. **Ngưỡng xóa run phải suy từ chính ứng viên dit đang xét**, không từ thống kê chung của clip.
   Lấy trung vị độ dài các dấu thì bản tin nhiều gạch có trung vị bằng 3 dit, và 0,4 × 3 = 1,2 dit
   nuốt luôn khoảng lặng 1 dit trong chữ — "CQ CQ DE R1ABC K" đọc thành "FFE EDII". Lấy tâm cụm
   thấp của 2-means thì bản tin toàn gạch vẫn hỏng ("TTT" thành "S"), vì khi chỉ có một cụm thì
   tâm đó chính là dah. Suy từ ứng viên đang xét thì giả thuyết sai tự lộ ra ở chi phí timing và
   vòng quét loại nó.
2. **Xóa gai bật trước, lấp khe tắt sau — hai bước tuần tự.** Lật mọi run ngắn cùng một lúc làm
   hai run ngắn kề nhau đổi chỗ cho nhau mỗi vòng và không bao giờ ổn định.
3. **Quét song song cả mask cứng lẫn mask Schmitt rồi để chi phí timing tự chọn thì xấu hơn**
   (33,62 % so với 26,44 %): trên clip nhiễu, mask cứng sinh những giả thuyết có chi phí thấp giả
   tạo. Đây là hướng nghe rất hợp lý mà số đo bác bỏ.

Hệ quả phụ đáng nói: bốn ca "giới hạn đã biết" của bộ DSP (SI ở 40 WPM, HI ở 48 và 60 WPM, SI ở
60 WPM) nay giải đúng, vì chúng hỏng do nhiễu lượng tử ở ranh giới run chứ không do mơ hồ thật.
Đổi lại, "TTT" ở 35 WPM chuyển thành ca mơ hồ: nó khớp timing hệt "S" ở 12 WPM tới bốn chữ số,
nên chỉ còn prior tốc độ phá thế hòa và prior lại ưu ái giả thuyết chậm. Bản cũ đúng ca này nhờ
nhiễu lượng tử chứ không nhờ nguyên lý, nên giữ nó làm mốc chặn sẽ là chuẩn giả.

Điểm 2 ở mục 4 (ước lượng nền có cổng cho đặc trưng của model) **đã bị bác bỏ** bằng phép đo d'
trong `docs/research/02-baseline-numbers.md`: 2,56 so với 4,50 của AGC hiện tại.
