# Nguồn corpus của mô hình ngôn ngữ

File `models/lm/{en,ru,kk}.bin` là bảng thống kê n-gram ký tự dựng từ các nguồn dưới đây. Chi tiết từng file tải về nằm trong `corpus/raw/<lang>/SOURCES.json` (không commit).

| Ngôn ngữ | Nguồn | Giấy phép | Ghi công |
|---|---|---|---|
| en | Project Gutenberg (sách public domain, danh sách top downloads) | Public domain; Project Gutenberg License cho định dạng | "This eBook is for the use of anyone anywhere at no cost" – gutenberg.org |
| en | michaellin/morse-translate-transcribe-100k, cột english | Apache-2.0 | https://huggingface.co/datasets/michaellin/morse-translate-transcribe-100k |
| ru | Project Gutenberg, sách tiếng Nga | Public domain | gutenberg.org/browse/languages/ru |
| en, ru, kk | Radiogram tự sinh từ mẫu ham radio của dự án (`--ham-lines`) | Tự tạo | – |
| kk | KazNERD (yeshpanovrustem/kaznerd) | CC BY 4.0 | Yeshpanov, Khassanov, Varol (LREC 2022) |
| kk | Kazakh Speech Corpus 2 (issai), phần transcript | MIT | ISSAI, Nazarbayev University |

Công cụ dựng: KenLM (LGPL 2.1) chỉ dùng lúc phát triển, không có trong sản phẩm.
