# Backlog — việc còn phải sửa / đo

Sổ này để KHÔNG quên giữa các phiên. Ghi ngay khi phát hiện; khi xong thì chuyển xuống "Đã xong" kèm
commit. Mỗi dòng: vấn đề — bằng chứng (số đo) — hướng làm. Đọc cùng CLAUDE.md.

## Đang mở — ưu tiên cao

1. **Chế độ nghe có thể dính cùng lỗi cửa sổ rỗng** như bản tin dài ở chế độ file (đã sửa 24/09,
   xem "Đã xong"): bộ đệm live cắt giữa tín hiệu dày. Đo lại T3 và một phiên nghe dài vài phút.
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

## Đang mở — trung bình

5. **Huấn luyện model âm học không dùng corpus thật.** tools/train.py không truyền `corpus` cho
   SynthGenerator -> 60 % văn bản là chuỗi từ ghép từ danh sách dựng sẵn 51/40/40 từ. corpus/*.txt có
   sẵn 1,2 triệu dòng. Thử huấn luyện lại với corpus (GPU ~3 h), đo T1/dev/T2 ghép cặp.
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

- Thử nghiệm / chọn tham số / so model: chạy SONG SONG mọi lõi (`--workers`), cache khi được.
- Huấn luyện: GPU trong WSL (scripts/wsl_train.sh).
- Nghiệm thu app thật: CPU, tuần tự, đúng đường sản phẩm (`bench --workers 1`, test_windows_exe.ps1,
  test_appimage.sh); chỉ số thời gian (giây/clip) chỉ tin ở chế độ này.
- Tốc độ đạt được: T1 500 clip 284 s -> 16 s (kết quả giống hệt 500/500); long_random_eval
  119 phút âm thanh x 4 cách giải mã ~4 phút. Beam + LM chiếm ~93 % thời gian và là thuật toán CPU
  tuần tự; GPU chỉ có ích nếu viết lại beam search dạng tensor (kiểu NGPU-LM của NeMo) — việc lớn,
  cần research trước.

## Đã xong (phiên 24/09)

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
