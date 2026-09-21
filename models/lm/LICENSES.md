# Nguồn corpus của mô hình ngôn ngữ

File `models/lm/{en,ru,kk}.bin` là bảng thống kê n-gram ký tự (bậc 6, KenLM `lmplz --prune 0 0 1 1 1 1`, dựng ngày 2026-09-20) từ các nguồn dưới đây. Sản phẩm **chỉ chứa thống kê n-gram** (hash n-gram, log-prob, backoff); không có câu, đoạn hay văn bản nguồn nào được đóng gói hay phân phối lại. "Public domain" dưới đây hiểu theo luật Mỹ, nơi Project Gutenberg xuất bản; tình trạng bản quyền ở nước khác có thể khác. Chi tiết từng file tải về nằm trong `corpus/raw/<lang>/SOURCES.json` (không commit). Cột "dòng" là số dòng thô trước chuẩn hóa.

| Ngôn ngữ | Nguồn | Giấy phép | URL / ghi công | Dòng |
|---|---|---|---|---|
| en | Project Gutenberg, 40 sách (id 2701, 1342, 1727, 2641, 2554, 65238, 3268, 1513, 2465, 2868, 1661, 67979, 1260, 34413, 59828, 62215, 1695, 345, 11, 5197, 21839, 601, 43, 6133, 831, 42, 2680, 3011, 468, 51252, 76639, 564, 47530, 72, 22541, 75201, 45839, 3296, 7326, 42671) | Public domain tại Mỹ (nơi Project Gutenberg xuất bản); Project Gutenberg License cho định dạng | gutenberg.org | 527,942 |
| en | michaellin/morse-translate-transcribe-100k (english) | Apache-2.0 | https://huggingface.co/datasets/michaellin/morse-translate-transcribe-100k | 100,000 |
| en | Radiogram tự sinh từ HAM_TEMPLATES của dự án | Tự tạo | – | 20,000 |
| ru | Project Gutenberg, 5 sách (id 30774, 14741, 5316, 16527, 37196) | Public domain tại Mỹ (nơi Project Gutenberg xuất bản); Project Gutenberg License cho định dạng | gutenberg.org | 21,128 |
| ru | Tatoeba, câu tiếng Nga (export per_language/rus) | CC BY 2.0 FR (tatoeba.org) | https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2 | 300,000 |
| ru | Radiogram tự sinh từ HAM_TEMPLATES của dự án | Tự tạo | – | 5,000 |
| kk | KazNERD (yeshpanovrustem/kaznerd) | CC BY 4.0 | https://huggingface.co/datasets/yeshpanovrustem/kaznerd | 88,540 |
| kk | Radiogram tự sinh từ HAM_TEMPLATES của dự án | Tự tạo | – | 20,000 |

Ghi công: KazNERD — Yeshpanov, Khassanov, Varol, "KazNERD: Kazakh Named Entity Recognition Dataset", LREC 2022 (CC BY 4.0). Tatoeba — câu tiếng Nga từ cộng đồng tatoeba.org, CC BY 2.0 FR (export `per_language/rus`, lấy tối đa 300.000 câu đầu). Kazakh Speech Corpus 2 (ISSAI, MIT) không có file transcript tải riêng được nên chưa dùng. Không dùng Wikipedia (CC BY-SA).

Sau chuẩn hóa (viết hoa, alias, bỏ dòng > 5% ký tự ngoài bảng): en 648k dòng thô; ru 323.884 dòng / 11,1 M ký tự; kk 108.403 dòng / 6,9 M ký tự. Kích thước `.bin` và perplexity trên holdout (mỗi dòng thứ 500, không vào train): en.bin 19,3 MB / 3,82; ru.bin 13,6 MB / 3,62; kk.bin 10,1 MB / 3,04.

Công cụ dựng: KenLM (LGPL 2.1) chỉ dùng lúc phát triển trong WSL Ubuntu 26.04 (vá `CMakeLists.txt` bỏ thành phần Boost `system` vì Boost 1.90 không còn cung cấp), không có trong sản phẩm; runtime chỉ đọc `.bin` numpy.
