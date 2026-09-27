# Backlog — việc còn phải sửa / đo

Sổ này để KHÔNG quên giữa các phiên. Ghi ngay khi phát hiện; khi xong thì chuyển xuống "Đã xong" kèm
commit. Mỗi dòng: vấn đề — bằng chứng (số đo) — hướng làm. Đọc cùng CLAUDE.md.

## Đang mở — ưu tiên cao

1. **Chế độ nghe: giá realtime 2–4 điểm.** Đo 24/09 (`long_random_eval --configs live,live-auto`, 54 bản
   tin 2 phút, đúng cấu hình LiveWorker): không có cửa sổ rỗng; biết trước ngôn ngữ văn thật 4,4–5,2 %,
   điện văn 3,5–11 % (file 1–2 %). Khóa nhầm ngôn ngữ đã sửa (xem "Đã xong"). Hướng: nhìn trước > 1 s
   hoặc bộ đệm dài hơn — đo, đừng đoán.
2. **Tự nhận ngôn ngữ yếu với tin ngắn / nhóm mã ngẫu nhiên.** T1 chế độ auto chỉ đúng ngôn ngữ
   338/500 clip, CER 24 % so với 7,78 % khi biết ngôn ngữ; tin Kazakh ngắn T2 đúng 8/15 (bị đọc thành
   Nga); nhóm mã Latin ngẫu nhiên có bản bị nhận là tiếng Nga -> 61–63 % CER. long_random_eval (24/09,
   bản tin 2 phút): văn thật 6/6 đúng mọi ngôn ngữ, nhưng nhóm mã sai 1–2/6 -> auto 12,6 % (en),
   25,3 % (kk) so với 1,4 % / 16,4 % khi biết ngôn ngữ. Hướng: đo theo độ dài, thêm "không chắc" ->
   hỏi người dùng / để mặc định ngôn ngữ giao diện, dùng xác suất từng bảng chữ.
3. **Chưa có bản ghi THẬT tiếng Nga/Kazakh.** Mọi số ru/kk là dữ liệu tự sinh; 30 dòng ru/kk trong
   T2 do Encoder của dự án sinh (thư mục tên `ebook2cw*` nhưng ebook2cw chưa từng được cài). Cần vài
   chục tin người gõ thật + đáp án (tác giả là người Kazakh).
4. **Nhóm mã Kazakh ngẫu nhiên: 16 % theo chữ nhưng 1,1 % theo mẫu Morse.** Bảng mã Kazakh dùng
   CHUNG mẫu với chữ Nga cho ӘҒҚҢӨҰҮҺІ (quy ước của dự án), nên với nhóm chữ ngẫu nhiên không có gì
   để phân biệt Қ với К — model nghe đúng, chỉ không thể biết chữ nào. Văn thật thì LM gỡ được (1,1 %).
   Không phải lỗi giải mã; cần ghi rõ trong tài liệu / cân nhắc hiển thị "Қ/К" khi LM không chắc.

14. **Giải Morse dạng TIẾNG CLICK của phím/sounder** (người dùng thử bản ghi "key typing 1930s", 25/09).
    Nay chỉ nhận ra và báo KEY_CLICKS. Khả thi: khoảng cách click tụ thành cụm rõ (~45/75/140 ms ở
    25–30 WPM). Việc khó: phân biệt click nhấn/nhả, tiếng nảy, vang phòng. Cần research (sounder
    decoding) + bộ đo có đáp án (tự sinh bằng tests/unit/test_clicks.key_click_audio, cộng bản ghi thật).
15. **Hiệu chuẩn độ tin cậy lại sau mỗi lần đổi model** (tools/calibrate_confidence.py). Chế độ nghe
    có ít từ dưới 0,9 (gộp thành một khoảng, đúng 61 %) — thêm dữ liệu live nếu muốn chia nhỏ.

16. **Khối Tín hiệu trực tiếp trôi theo bước 100 ms** (mỗi khối thu một lần vẽ): mượt hơn cần nội suy
    theo đồng hồ + vẽ ~25 hình/s = ~2x CPU cho 3D. Để nguyên vì người dùng đặt "hạn chế tài nguyên";
    làm nếu người dùng thấy giật. Cũng chưa có bản đồ thu nhỏ cả file để nhảy xa (hiện dùng thanh phát).

17. **Số: cần thêm bản ghi THẬT có bản chép đáng tin** (27/09). T5 chỉ có 6 file trạm số (M01 x2, M12 x3,
    M14 x1, bản chép Priyom). M14: lỗi dồn ở đoạn 70–90 % bản chép (78 nhóm liền không khớp) trong khi
    bản giải không có khoảng trống -> nghi bản chép lệch âm thanh; M01-713: bản chép đáng ngờ (27 % nhóm
    đúng với mọi bộ giải mã, kể cả ggmorse). Cần thêm điện số thật: điện thi đấu (serial, 5NN), điện
    thời tiết/hàng hải, trạm số khác (E11, S06…).
18. **Dấu cách trong dãy số gõ tay là nhập nhằng thật** (tools/numeric_eval.py, 27/09): mọi dấu cách
    "nhầm" rơi đúng vào khoảng giữa chữ bị kéo tới 4–6,8 dit, trùng khoảng giữa từ ngắn nhất (4,6 dit).
    Chỉ sửa được bằng BIẾT độ dài nhóm: tự nhận (numbers.py, cần >= 4 nhóm thuần số và >= 50 % cùng độ
    dài) hoặc cho người dùng đặt "nhóm N chữ số" trong giao diện. Chưa làm tùy chọn giao diện.
19. **Điện số: đoạn rác đầu/cuối đọc thành số** (M12, E18): tiếng dò sóng/tín hiệu gọi trước điện ra
    `58446`, `19159 5` — với E17 ra chữ (`'RM`). Không đụng thân điện nhưng làm bẩn đầu/cuối.
20. **Auto với nhóm chữ-số và số có định dạng**: phần chữ không có từ nào để LM chọn bảng chữ, nên có
    bản tin Latin bị nhận là Kirin (đã biết ở #2). Hướng: hòa điểm thì theo ngôn ngữ giao diện.

## Đang mở — trung bình

5. **Model âm học: hướng tiếp theo (P2–P7 trong .superpowers/sdd/research-acoustic-2026-09-24.md).**
   E17 (v0.5.0) đã gỡ phần lớn "LM ngầm" (xem Đã xong). Còn: frontend băng hẹp (5e), cửa sổ liên tục +
   mẫu nhiễu thuần, fading Rayleigh + tay gõ theo thống kê VE3NEA + nhiễu thu thật (nhắm SAQ 16 %),
   BiGRU 2 lớp (CPU x3). E17 kém E16 ở fading rất sâu 0–3 dB kể cả trên dev-OOV (0 dB 66,5 -> 71,9) —
   theo dõi. Mỗi lượt quyết định bằng dev-OOV + T4 + long_random (CLAUDE.md quy tắc 4).
5c. **LM làm nhóm mã và hô hiệu XẤU đi** (T1 −1,75 điểm có ý nghĩa; bịa CZWCI -> CQWCI, BS5MSB ->
   BU5MSB). Hướng: chế độ "nhóm mã" (alpha thấp / tắt LM) + trạng thái "không chắc" cho auto khi mọi
   LM > ~4,5 bit/ký tự; kiểm hô hiệu SAU khi giải và GẮN CỜ, không tự sửa (research-lm §8).
5d. **Lỗi phụ thuộc vị trí trong cửa sổ**: cùng âm thanh, các cửa sổ chồng nhau đọc khác nhau
   ("INTERESTEDM" / "INTERESTED ME" / "INTERESTEDME"). Gộp trung bình xác suất đã THỬ và BỊ BÁC (T2
   +0,76). Nghi phạm gốc chưa thử: AGC khởi tạo mức nền từ 0,5 s đầu cửa sổ (`agc_init_s`).
5e. **Frontend lọc quá rộng**: E16 cần 0 dB để còn ~2 % ở 12 WPM, DeepCW chỉ cần −4 dB (bin 31 Hz, lọc
   200 Hz so với bin 12,5 Hz). Hướng P2: thêm kênh envelope băng hẹp 15/40/100 Hz, huấn luyện lại.
5f. **Gõ TAY trên sóng thật là khoảng cách lớn nhất còn lại.** T4 (25/09): gõ máy thật en/ru đều < 1 %
   (SRR ru 0,55 %, ARRL 0,05 %, K7QO/SKCC 0 %), nhưng SAQ Grimeton (gõ tay, VLF, QRN) 17–29 %: chèn
   chữ ở xung nhiễu, lẫn chấm/gạch, mất dấu cách. Hướng: P4 (tay gõ VE3NEA, Rayleigh, nhiễu thu thật)
   và mở rộng T4 phần on-air (USCG NMN, thêm bản thu SAQ, WebSDR). Chưa có ru/kk gõ tay thật (#3).
5g. **T2 đọc đáp án ARRL sai**: byte 0x89 (BT `=`) / 0x83 (AS `&`) bị `errors="replace"` xóa trong
   make_t2_manifest -> CER các file 5–15 WPM bị đội (file 5 WPM năm 2013 trong T4: 2,61 % -> 0,00 % khi
   đọc đúng); `parse_wpm("_075WPM")` = 75. make_t4.py đã đọc đúng. Sửa T2 = đổi mốc T2 -> chạy lại mốc.
6. **AppImage cần glibc >= 2.35**: chạy Ubuntu 22.04+/Debian 12+/Fedora 40, KHÔNG chạy Ubuntu 20.04/
   Debian 11 (`GLIBC_2.35 not found`). Nếu máy đích cũ: dựng lại trên nền glibc 2.28.
7. **exe chưa ký số**: Smart App Control (Windows 11) chặn hẳn; SmartScreen cảnh báo khi có
   Mark-of-the-Web. Windows 10 chưa thử.
8. **Bộ nhớ 2 GB cho file 1 giờ** (giữ log-prob mọi cửa sổ chồng). Hướng: xử lý cửa sổ theo dòng.
9. **Chế độ nghe**: T3 live lệch file 3,1 điểm (spec < 1); chưa hiện bộ đếm khối bị bỏ (spec §7.6);
   chưa đo qua micro thật; số trong tài liệu còn là của model 0.3.0.
10. **Profile ru/kk** có `lexicon_bonus` chứa từ radio viết chữ Latin (CQ, DE, PSE…) — bảng Kirin
    không bao giờ sinh ra được nên vô tác dụng.
11. **Bảng số tự nhận ngôn ngữ trong tài liệu** (8/20/50 ký tự) đo với model cũ — đo lại với 0.4.0.
12. **Nhiễu tuần hoàn ra `EEEE`** với độ tin cậy ~0,99 (giới hạn đã biết của §7).
13. **Tai nghe Bluetooth**: độ trễ không được driver báo nên karaoke/3D có thể đi trước tiếng.

## Cơ chế đo (quy ước từ 24/09)

- **Chế độ nghe rất đắt để mô phỏng** (giải lại bộ đệm 9,5 s mỗi 0,5 s; tự nhận ngôn ngữ x3): 54 bản
  tin live + live-auto ~50 phút trên 14 lõi. Kiểm nhanh: CHỈ cấu hình bị đổi (`--configs live-auto`)
  và `--per-cell 1` (18 bản tin); bộ đủ chỉ khi nghiệm thu. Đổi phần không đụng tới cấu hình nào thì
  khỏi đo lại cấu hình đó (25/09 đã đo thừa `live` dù mã của nó không đổi).
- Thử nghiệm / chọn tham số / so model: chạy SONG SONG mọi lõi (`--workers`), cache khi được.
- Huấn luyện: GPU trong WSL (scripts/wsl_train.sh).
- Nghiệm thu app thật: CPU, tuần tự, đúng đường sản phẩm (`bench --workers 1`, test_windows_exe.ps1,
  test_appimage.sh); chỉ số thời gian (giây/clip) chỉ tin ở chế độ này.
- Tốc độ đạt được: T1 500 clip 284 s -> 16 s (kết quả giống hệt 500/500); long_random_eval
  119 phút âm thanh x 4 cách giải mã ~4 phút. Beam + LM chiếm ~93 % thời gian và là thuật toán CPU
  tuần tự; GPU chỉ có ích nếu viết lại beam search dạng tensor (kiểu NGPU-LM của NeMo) — việc lớn,
  cần research trước.

## Đã xong (phiên 24/09)

- **Nhận diện SỐ** (27/09, người dùng 26/09: "giải mã số học cực kỳ kém"). Research + đo:
  .superpowers/sdd/research-numbers-2026-09-27.md. Bộ đo mới: `tools/numeric_eval.py` (số tổng hợp,
  5 loại nội dung) và `tools/real_numbers_eval.py` (T5: trạm số thật M01/M12/M14, so ggmorse).
  - Số viết tắt (0 = T; bộ thi đấu trong nhóm cố định) + ghép/tách nhóm độ dài cố định, CHỈ trong điện
    số (`morsedesk/numbers.py`); tọa độ `N/E`, `T=`, `5NN`, hô hiệu, nhóm mã SRR không bị đụng.
  - Điện số đọc thẳng từ mô hình, không qua LM văn bản (LM kéo `(` về `9`: 21/202 -> 4/202 nhóm).
  - Auto: đoạn 30 s chỉ để bỏ phiếu ngôn ngữ, văn bản giải cả lưới một lượt (nhóm không còn bị cắt).
  - DSP phải giữ cấu trúc từ (`dsp_keeps_words`): M12 đánh nhóm sát nhau -> DSP dính cả bản tin.
  - Chế độ nghe: chốt dần từng chữ của từ dài (dãy số dài hơn bộ đệm), lùi mép 2 khoảng cách chữ vì
    mốc CTC phát sớm; nhận ra chữ đã chốt bằng chữ GẦN mốc nhất (ngưỡng cố định từng nuốt chữ đầu
    từ sau: `HAVE TOLD` -> `HAVEOLD`); bộ đệm đã cắt đầu được đệm nhiễu ở mép đầu như mép trong
    (bộ đệm nằm trọn trong dãy số ra RỖNG 6/8 lần -> mất đuôi bản tin).
  - Model E18 v0.6.0 (E17 + 35 % điện số); E19 (không rút khoảng giữa nhóm) không được chọn.
  - Kết quả: T5 trạm số thật 25,12 % lỗi chữ số / 42,36 % nhóm đúng -> **17,00 / 73,25** (ggmorse
    28,79 / 36,78); chế độ nghe với số 24,8 / 62,7 -> **0,0 / 95,4**; chế độ nghe văn bản 5,55 ->
    **3,21 %** (18 bản tin; ghép cặp E17 5,55 -> 3,29, [−3,79; −0,88]); số tổng hợp nhóm đúng 88,8 ->
    89,7 % (94,9 % theo mẫu), số có định dạng 90,8 -> 94,6 %; T4 1,34 -> 1,25 %; T1/dev/dev-OOV/T2
    không đổi có ý nghĩa.
- **Ba file mẫu "Xin chào" thuần Morse** (25/09, người dùng): bỏ nhiễu SNR 15 dB — sine 700 Hz liên
  tục pha, sườn raised-cosine 5 ms, khoảng lặng là số 0 tuyệt đối. Cả ba vẫn tự nhận đúng nguyên văn
  và ngôn ngữ (đi đường DSP, SNR đo 51 dB). Cảnh 3D: dải động hiển thị tối đa 30 dB (MAX_RANGE_DB) để
  file sạch không nhòe thành đồi; gai nhỏ còn lại ở mép dấu là dải biên thật của sườn 5 ms.
- **Khối Tín hiệu bám con trỏ, lướt được, bấm để nghe** (25/09, người dùng; thay bản "quét điện tim"
  cùng ngày): hai trang cùng SignalPanel (3D hoặc phổ 2D, một khung 12 s). Nghe lại: đèn ghim giữa,
  trừ nửa khung đầu/cuối; kéo/lăn để lướt, nút "Theo con trỏ"; bấm biểu đồ hay từ = nghe từ đó.
  Nghe trực tiếp: đèn ở mép phải ("bây giờ"), xem lại 10 phút, "Về trực tiếp"; dừng rồi bấm để nghe
  lại. Rê chuột: ô số đo (từ, Hz, dB trên nền, thời điểm). Đo (tools/signal_view_latency.py, cửa sổ
  mặc định / toàn màn hình 1080p): nghe lại 3D 20 hình/s, CPU 22–25 % một lõi, trễ hình 9–26 ms sau
  nhịp thanh phát (+~25 ms nửa nhịp); phổ 2D 20 hình/s, 4–9 % CPU, trễ 3 ms; trực tiếp 10 hình/s
  (theo khối thu 100 ms), 3D 13–20 %, 2D 1–5 %. Nhịp thanh phát 33 ms bị bác: 3D không nhanh hơn
  ở màn hình lớn (trễ 39 ms) mà CPU 32 %.
- **Rê chuột trên mọi biểu đồ tín hiệu** (25/09): cảnh 3D chọn điểm theo thứ tự che khuất; cảnh vẽ
  vào ảnh đệm nên rê chuột 3,3 ms/khung thay vì vẽ lại cả cảnh.

- **Trang Tạo mã: hiệu ứng theo tiếng khi Nghe thử** (25/09): chữ đang phát có khung bo tròn, dấu
  đang kêu to và sáng hơn; phím Morse động (vẽ bằng key_art như logo) nhấn đúng lúc tone vang. Thời
  điểm từ encode/timeline.py (cùng tokens_to_elements với âm thanh, lệch < 6 ms), vị trí từ
  AudioPlayback (giây đang ra loa).
- **Trang Tạo mã với văn bản cực dài** (25/09): băng Morse trong khung cuộn (cửa sổ không còn bị kéo
  cao 22 624 px, xóa chữ không làm khung nhập chiếm cả trang), chỉ vẽ phần nhìn thấy, profile nạp một
  lần, gộp phím khi > 1 500 ký tự. Trễ mỗi phím: 200 ký tự 60 -> 7 ms; 6 000 ký tự 298 -> 29 ms (đo
  cả vẽ lại trang), và > 1 500 ký tự chỉ dựng lại một lần khi ngừng gõ.
- **Chế độ nghe không bao giờ trộn bảng chữ** (25/09): chưa khóa ngôn ngữ thì chưa chốt, chữ tạm viết
  một bảng chữ. live-auto 11,94 -> 7,87 % [-6,64; -1,55], bản tin lẫn Latin+Kirin 31/54 -> 0/54.
- **Tiếng click phím điện báo**: nhận ra, trả rỗng + KEY_CLICKS (dsp/clicks.py); T1/dev/dev-OOV/T2/T4
  giống hệt từng clip.
- **Gạch chân + tooltip độ tin cậy ở cả trang Giải mã và trang Nghe**, % đo bằng
  tools/calibrate_confidence.py; ngưỡng 0,97 / 0,8 theo số đo; en/ru/kk.
- **Model v0.5.0 = E17** (25/09): như E16 nhưng văn bản huấn luyện là câu thật từ corpus (50 %), nhóm
  mã 1–8 chữ (20 %), điện văn (20 %), danh sách cũ (10 %). T4 1,94 -> 1,34 % (SAQ gõ tay on-air 22,9 ->
  16,2), dev-OOV 10,10 -> 8,95, bản tin dài 3,69 -> 3,26 (văn thật chế độ file 0,29 %), chế độ nghe 6,93
  -> 5,56; dev xấu 8,06 -> 9,21 và T1 8,39 (văn bản từ danh sách cũ + fading 0–3 dB). E16 ở
  models/archive/acoustic-0.4.0-E16.onnx.
- **Chế độ nghe khóa nhầm ngôn ngữ** (25/09): luật "3 lần giải mã liền nhau" thay bằng điểm LM tích lũy
  cả phiên -> live-auto văn thật 15–17 % -> 5,0–6,9 %, điện văn 15–46 % -> 7,9–14 %.
- **LM phạt dấu chấm giữa bản tin** (25/09): ranh giới câu trong beam; bản tin dài app 3,87 -> 3,69 %
  [-0,31; -0,08], 11 tốt / 0 xấu; T1 7,78 -> 7,75; dev, dev-OOV, T2 không đổi.
- **Bộ đo mới** (25/09): dev-OOV (t1oov, E16 10,13 %) và T4 bản ghi thật (tools/make_t4.py, 40 file).
- **Bản tin DÀI mất cả cửa sổ** (0bc8dfc). Cửa sổ 12 s nằm giữa bản tin dày tín hiệu từ đầu
  tới cuối -> model trả RỖNG (26/60 cửa sổ); bản tin 2 phút sai 50 %, gõ tay 32–53 %. Sửa: đệm nhiễu
  nền 0,5 s ở mép giáp cửa sổ khác, CHỈ cửa sổ có tone đang được đánh phím (`key_down_fraction` < 0,9),
  cắt phần đầu ra tương ứng. Kết quả: bản tin 130 s 50,2 -> 1,2 %; long_random_eval app 1,1–2,0 % văn
  thật, 1,2–5,3 % mã/điện văn; T1 7,78 / dev 8,07 giống hệt 500/500 clip; T2 1,62 -> 1,51 (Kazakh
  3,50 -> 3,21); test §7 (nhiễu trắng/sóng mang/nhiễu xung không ra chữ) vẫn qua.
- Phép thử chạy song song mọi lõi: `bench --workers`, `tools/long_random_eval.py` (0bc8dfc).
- Một bản tin = một bảng chữ; phiên nghe khóa ngôn ngữ (00c2639).
- Banner đọc được trên nền tối + đo tương phản tự động (628dca2).
- Đồng bộ hình/tiếng khi phát nhanh/chậm (3ce0699).
- Tài liệu: bỏ nhãn "bản nháp", sửa ~30 điểm phi logic, nguồn dữ liệu đúng (3abac81, dd3d6fb).
