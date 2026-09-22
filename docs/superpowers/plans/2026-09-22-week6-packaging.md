# Tuần 6: đóng gói và kiểm trên Linux thật

Viết ngày 2026-09-22, sau khi tuần 5 đóng 12 trong 17 chốt kiểm. Kế hoạch này chỉ gom những
việc **không làm được từ máy dev Windows** cộng hai việc chất lượng còn mở.

## Trạng thái vào cuối tuần 5

| Yêu cầu spec | Trạng thái |
|---|---|
| A1 / D3 — gate 2 % trên T1 | **chưa đạt**, đang 20,21 %; phụ thuộc thí nghiệm model |
| A2 — ARRL 18–40 WPM dưới 2 % | **đạt**, 1,52 % |
| D2 — T0 roundtrip audio sạch CER = 0 | **đạt**, 21/21 ô |
| A3 — nhận diện ngôn ngữ | **đạt có điều kiện**, 100 % từ 50 ký tự |
| C17 — font đóng gói | **đạt phần mã**, còn ảnh chụp trên VM |

Chốt kiểm còn mở: CP-01 (gate), CP-05 (Ubuntu LTS), CP-11 (ảnh font trên VM), CP-12 (người bản
ngữ soát Kazakh), CP-13 (multimon-ng), CP-16 (8 thư viện xcb).

## Task 1 — AppImage

- `linuxdeploy` + plugin Python, dựng trong Docker Ubuntu 22.04 để nhị phân liên kết với glibc
  cũ nhất mà ta hứa hỗ trợ.
- Đóng gói kèm: `morsedesk/app/fonts/*.ttf` (đã khai báo `artifacts` trong `pyproject.toml`),
  plugin nền tảng `xcb` cùng **8 thư viện** mà CP-16 liệt kê, `models/acoustic.onnx` và
  `models/lm/*.bin` nếu người dùng muốn bản chạy ngay.
- Nghiệm thu: AppImage mở được cửa sổ trên VM Ubuntu 22.04 **sạch** ở cả phiên X11 lẫn Wayland,
  và giải mã được một file. Đóng CP-16.

**Chặn hiện tại:** Docker Desktop trên máy dev không chạy (`npipe dockerDesktopLinuxEngine` không
tồn tại). Cần người dùng bật, hoặc dựng trong WSL Ubuntu-26.04 rồi chấp nhận glibc mới hơn.

## Task 2 — kiểm trên Ubuntu 22.04 và 24.04

- Bộ test đầy đủ, `ruff`, `tools/build_i18n.py --check`, CLI giải mã một file.
- Mở `morsedesk-gui` thật (không headless), chụp màn hình cả ba ngôn ngữ giao diện.
- Ảnh phải thấy rõ Ә Ғ Қ Ң Ө Ұ Ү Һ І — đóng nốt CP-11.
- Đóng CP-05.

## Task 3 — multimon-ng (CP-13)

Một lệnh cần quyền: `sudo apt-get install -y multimon-ng` trong WSL. Sau đó
`uv run python tools/bench_external.py` trên T1 và T2. `ggmorse` phải build bằng cmake; làm nếu
còn thời gian. `pycw` đã đo xong (59,52 % trên T1 `en`, xem `docs/research/04-pretrained-baselines.md`).

## Task 4 — chất lượng còn mở (CP-01)

Hai hướng đã có bằng chứng, xếp theo tỉ lệ lợi ích trên công sức:

1. **Đuôi SNR sạch trong dữ liệu huấn luyện** — thí nghiệm E11 đang chạy, dẫn E3 khoảng 1,3
   điểm ở bước 17 000. Nếu giữ được tới cuối thì đây là model mới.
2. **Nội suy ranh giới dưới khung trong `run_lengths`** — giúp ở tốc độ **cao**, nơi một dit chỉ
   dài 6 khung nên sai số nửa khung là 8 %. Ảnh hưởng trực tiếp tới đường DSP, tức tới chính
   những ô mà T2 còn yếu.

Đã loại bằng số đo, đừng thử lại: model lớn hơn (E9, xấu hơn 8,2 điểm), tăng cường QSB mạnh hơn
(E6), lexicon rộng hơn, nới `min_prob`, huấn luyện khớp tone ước lượng.

## Task 5 — bản dịch Kazakh (CP-12)

Cần người bản ngữ soát `morsedesk/app/i18n/translations.json` và gỡ nhãn "nháp" khỏi combo ngôn
ngữ. Không có cách nào thay thế được việc này từ trong phiên làm việc.
