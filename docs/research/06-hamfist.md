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
