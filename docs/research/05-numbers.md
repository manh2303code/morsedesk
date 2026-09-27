# Nhận diện số: thiết kế, bộ test chuẩn, giới hạn (27/09/2026)

Người dùng 27/09: "thiết kế thuật toán tối ưu tuyệt đối, không sai số cho việc dịch số, tạo bộ test
chuẩn để đánh giá mọi edgecase", thử trên các file tự tải từ internet, "dùng LLM as judge để xem bản
plaintext ban đầu là gì".

## 1. "Không sai số" nghĩa là gì — nói thẳng

Không bộ giải mã nào đúng 100 % ở MỌI âm thanh, vì có những chỗ thông tin không còn trong âm thanh:
- fading sâu dưới nền nhiễu (0–3 dB): chữ chìm hẳn;
- rớt tín hiệu làm MẤT hẳn một phần tử (khóa UA3AFO thật: một số 3 chỉ còn `..--`);
- người gõ tay ngừng giữa dãy số lâu bằng khoảng giữa từ: âm thanh nói "dấu cách";
- Farnsworth một từ duy nhất và bài học đánh từng chữ với lặng dài là CÙNG MỘT âm thanh.

Mục tiêu đặt ra và đạt được: **đúng tuyệt đối mọi ca mà âm thanh không nhập nhằng** (mức `must` của bộ
test, 110 ca), không bao giờ bịa chữ số từ âm thanh không phải Morse, và báo số trung thực ở mức `hard`.

## 2. Thiết kế: bốn lớp bằng chứng

1. **Đọc file đúng và đủ** (audio/mp3len.py). libsndfile đoán độ dài MP3 VBR không header Xing theo
   bitrate khung đầu và DỪNG ở đó: hai bài tập số tải về mất 30 % (89,4/130,7 s). Nay đếm khung và
   chèn khung Xing đúng — không cần ffmpeg. Xuất OGG dài từng làm SẬP app (libsndfile Vorbis): nay ghi
   theo khối.
2. **Mô hình âm học + ngôn ngữ** (E18 v0.6.0): điện số đọc thẳng từ mô hình (LM văn bản kéo `(` về `9`),
   số viết tắt / nhóm cố định chỉ trong điện số (numbers.py).
3. **Đối chiếu từng ký tự với nhịp phím** (keyed.py), khi tín hiệu sạch (SNR >= 10 dB):
   - đọc nhịp phím với dit đo từ khoảng lặng GIỮA các phần tử (luôn 1 dit) — đúng cả khi bản tin
     toàn gạch (bài học số 0, nơi bộ DSP cổ điển hỏng); rớt tín hiệu < 0,5 dit trong một phần tử là
     một phần tử;
   - căn chuỗi mô hình với chuỗi nhịp phím bằng quy hoạch động (mẫu + thứ tự, băng theo thời gian) —
     KHÔNG theo mốc thời gian: với khoảng lặng dài, mô hình phát mốc ký tự k+1 ngay đầu khoảng lặng
     trước nó;
   - khớp -> giữ chữ LM chọn (Ә/А); lệch với Morse rõ -> theo nhịp phím; Morse rõ bị bỏ sót -> chèn;
     chữ nằm trên đoạn không thuần tone (giọng nói, nhạc) -> bỏ;
   - dấu cách: lặng dài và sạch (>= 10 dit, >= 0,5 s) là dấu cách, trừ cụm dưới của Farnsworth (hai
     cụm tỉ lệ ~7:3); nhịp gõ máy (hai cụm tách bạch, hoặc một cụm đều >= 5,5 dit) quyết mọi dấu cách;
     gõ tay (khoảng 4–6 dit nhập nhằng) để mô hình quyết.
4. **Không phải Morse**: từ kém chắc và không thuần tone (giọng nói) bị bỏ ở mọi SNR; clip >= 60 s không
   có từ nào >= 0,8 và < 20 % ký tự nhịp phím là Morse rõ -> rỗng + NO_SIGNAL (bài hát).

## 3. Bộ test chuẩn

### 3.1 Tổng hợp, đáp án tuyệt đối: `tools/numeric_edge_bench.py` (122 ca, ~80 phút âm thanh, ~1 phút)

| Nhóm | Nội dung | Mức |
|---|---|---|
| A | từng chữ số đứng một mình; 5 chữ số giống nhau; 0–9; mọi cặp chữ số | must |
| B | nhóm dài 1–10; dãy liền 20/30/50 số (máy và tay); chữ số rời lặng 15–50 dit (bài học); trạm số (mào đầu, nhóm đánh hai lần, VVV/<SK>); khoảng giữa nhóm 5/10 dit | must (5 dit: hard) |
| C | trạm số 0 = T; bộ viết tắt thi đấu đầy đủ | must |
| D | hô hiệu có số, locator, nhóm mã chữ-số, số có chữ đuôi | must |
| E, F | dấu câu giữa số; điện thoại, tọa độ, ngày giờ, tần số, số tiền | must |
| G | nhóm ngăn bằng BT/AR; điện văn có số | must |
| H, I, J | 5–60 WPM; Farnsworth 5/8/12; tone 300–1500 Hz | must (60 WPM: hard) |
| K, L | SNR 30…0 dB; QRM, QRN, QSB, MP3, cắt đỉnh | must >= 12 dB; hard dưới |
| M | gõ tay lệch, bug, nhanh/chậm dần; ngừng giữa dãy bằng khoảng giữa từ | hard / ambiguous |
| N | WAV 44,1 kHz stereo, 11 kHz, MP3 VBR không Xing, OGG, FLAC | must |
| O | Morse giữa im lặng / nhiễu / giọng nói / nhạc (giả và THẬT); chỉ nhiễu/giọng/nhạc (phải rỗng); Morse trên nhạc nền | must (nhạc nền: hard) |
| P, Q | bản tin 5 phút; số trong văn bản Anh/Nga/Kazakh | must |

    uv run python tools/numeric_edge_bench.py [--configs app,auto,live] [--only B3,O]

### 3.2 Bản ghi thật, đáp án do giám khảo LLM: `testdata/private/t6` (8 file, 40 phút)

Không có bản chép. Quy trình (LLM as judge):
1. `tools/multi_decode.py`: 7 bộ giải độc lập (E18/E17, có/không LM, DSP, ggmorse) đọc cùng file.
2. `tools/envelope_strips.py`: ảnh đường bao tone theo hàng 8–12 s, mỗi xung ghi độ dài theo dit, mỗi
   khoảng lặng ghi số dit; bản "mù" (không có chữ của bộ giải mã nào).
3. HAI giám khảo LLM độc lập chép từng ký tự từ ảnh mù (hướng dẫn chung, bảng mã, đánh dấu chỗ không
   chắc); đối chiếu từng cặp. Kết quả: 5/5 cặp khớp 100 %; bài hát: không có Morse (remix có đoạn synth
   lặp theo nhịp giống phím nhưng không đúng tỉ lệ 1:3 và không có lặng 1 dit).

| File | Nội dung (theo giám khảo) |
|---|---|
| digits30_006, digits60_008 | `VVV=` + 10/20 nhóm 5 số + `<SK>`, 30/60 ký tự/phút |
| lesson04_seven, lesson10_zero | 82 số 7 / 61 số 0, từng số đánh riêng, lặng 30–59 dit |
| lesson_kontrolnaya | 80 chữ số ngẫu nhiên, từng số đánh riêng, lặng 23–59 dit |
| ua3afo_razdel1 | khóa học: giọng đọc xen chữ Nga, số, dấu (250 ký tự) |
| piknik_single, piknik_remix | bài hát, không có Morse: không được đọc ra chữ số nào |

    uv run python tools/real_numbers_eval.py --manifest testdata/private/t6/manifest.jsonl

## 4. Kết quả (27/09, model 0.6.0, mã cuối)

| Bộ | Trước (mã 82bb622) | Sau |
|---|---|---|
| Bộ test biên, mức must: đúng trọn | 96/110 | **109/109** (lỗi chữ số 51/3333 -> **0/3341**) |
| T6 file thật (giám khảo LLM): lỗi chữ số | 18,66 % | **0,69 %** (chỉ còn chỗ âm thanh hỏng của UA3AFO) |
| T6: 5 file số (digits30/60, 3 bài học): nhóm đúng trọn | 8,5–85 % | **100 %** cả năm |
| T6: bài hát: chữ số bịa | 4 + 4 | **0** (ra rỗng + NO_SIGNAL) |
| T5 trạm số thật: lỗi chữ số / nhóm đúng | 17,00 / 73,25 % | **16,13 / 73,89 %** (M12: 3–5 % -> 0,5–1 %) |
| Chế độ nghe, số (12 bản tin) | 0,0 / 95,4 % | 0,0 / 95,4 % (không đổi) |

## 5. Hồi quy (so ghép cặp, cùng model E18)

| Bộ | Trước | Sau | |
|---|---|---|---|
| T1 | 8,36 % | 8,37 % | [−0,02; +0,03], 1 tốt / 1 xấu |
| dev | 8,79 % | 8,79 % | 0 clip đổi |
| dev-OOV | 8,99 % | 8,98 % | 1 tốt |
| T2 | 1,84 % | 1,84 % | 0 clip đổi |
| T4 | 1,25 % | 1,30 % | SAQ gõ tay 16,50 -> 15,76; 2 bài Fedyai "xấu đi" vì BẢN CHÉP sai: âm thanh cuối bài là `...-.-` = `<SK>` (xem ảnh đường bao), bản chép ghi `.`; app nay đọc đúng |
| số tổng hợp (180 bản tin) | 89,7 % | 89,7 % | |
| bản tin 2 phút (54) | — | y hệt | |
| chế độ nghe, văn bản (18) | 3,21 % | 3,21 % | y hệt từng bản tin |

Mỗi cổng an toàn của keyed.py có một hồi quy đứng sau (bản đầu không cổng: T1 8,36 -> 14,56 %):
- khoảng lặng dài ĐỀU là nhập nhằng (từ Farnsworth T1 bị tách thành chữ rời);
- chỉ tin nhịp phím khi SNR >= 15 dB, biên độ ổn định (fading), đủ độ phủ trong bản tin (fading giấu ký
  tự dưới ngưỡng phím), mô hình đồng ý >= 0,8 ở ký tự trong nhóm (trạm số M14 thu sóng ngắn: 0,735 —
  nhịp phím đọc nhầm nhiễu);
- sửa chữ lệch >= 2 phần tử chỉ khi ký tự đứng riêng / mở đầu đoạn VÀ mọi phần tử sắc nét;
- nhịp như máy mới được sửa/chèn chữ (gõ tay: nhịp phím gộp hai chữ làm một); gõ tay chỉ lặng >= 20 dit
  mới là dấu cách chắc chắn (SAQ ngừng giữa từ);
- lặng THẬT phải không thuần tone (đáy fading vẫn là tone);
- chế độ nghe TẮT đối chiếu (bộ chốt nhận chữ đã chốt bằng mốc của mô hình; đối chiếu đổi mốc -> chữ số
  nhân đôi `00000` -> `000000`, số ở chế độ nghe 0,0 -> 11,8 %).

## 6. Còn lại (backlog)

- Chế độ nghe với chữ rời lặng rất dài (40–59 dit, bài học phát qua micro): vẫn ra mảnh vỡ; bộ đệm 9 s
  chỉ chứa ~2 chữ và mốc giữa các lần giải xê dịch. Lặng 30/49 dit đã gần đúng (sau khi chỉ chốt dần từ
  nhiều chữ).
- Khoảng lặng đều giữa chữ rời (Farnsworth hay chữ rời?) và dấu cách giữa dãy số gõ tay: nhập nhằng thật
  — cần tùy chọn giao diện ("nhóm N chữ số" / "chữ rời").
- M14 (sóng ngắn nhiễu): 23 % lỗi chữ số, phần lớn do bản chép lệch âm thanh; nhịp phím không dùng được.
- Phím bug (gạch lệch nhiều) vẫn sai ở mức hard.
