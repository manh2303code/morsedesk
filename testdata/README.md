# testdata

- `public/`: file được phép phân phối lại (Wikimedia Commons, tự thu). Commit được.
- `private/`: file có bản quyền hoặc chỉ dùng nội bộ (ARRL W1AW, SRAA CC BY-NC, kho QSO). KHÔNG commit.
- `generated/`: sinh bằng công cụ (T1, WAV thử tay). KHÔNG commit, tạo lại bằng `uv run python tools/make_t1.py`.

## Gom bộ T2 (làm tay, một lần)

1. ARRL W1AW: tải MP3 và file text cùng tên từ trang "N WPM Code Archive" của arrl.org cho các tốc độ
   5, 7.5, 10, 13, 15, 18, 20, 25, 30, 35, 40 (ít nhất 2 ngày mỗi tốc độ) vào `testdata/private/arrl/`.
   Tên file dạng `260303_20WPM.mp3` và `260303_20WPM.txt`.
2. Wikimedia Commons, Category "Audio files of Morse code": tải WAV/OGG vào `testdata/public/commons/`,
   ghi đáp án vào file `.txt` cùng tên (nghe và chép tay).
3. SRAA (shortwavearchive.com, tag CW) và kho QSO Ý: tải khoảng 20 clip vào `testdata/private/real/`,
   cắt đoạn 30–60 s bằng Audacity, chép tay đáp án vào `.txt` cùng tên; ghi WPM và loại khóa vào tên
   file dạng `qso01_25WPM_bug.wav` nếu biết.
4. Tiếng Nga/Kazakh: thu người gõ thật hoặc tạo bằng ebook2cw (gọi ngoài) vào `testdata/private/ru/` và
   `testdata/private/kk/`, kèm `.txt`.
5. Tạo manifest:
   `uv run python tools/make_t2_manifest.py testdata/private/arrl --source arrl --profile en --out testdata/manifests/t2_arrl.jsonl`
   và tương tự cho các thư mục khác (đổi `--profile ru` / `kk-cyrl-ru`).

## Đo công cụ ngoài (Ubuntu 22.04, chỉ để có số đối chứng, không nhúng vào sản phẩm)

```bash
sudo apt install multimon-ng
uv run python tools/bench_external.py --manifest testdata/manifests/t2_arrl.jsonl \
  --cmd "multimon-ng -a MORSE_CW -t wav {path}" --strip-prefix "MORSE_CW:" --name multimon
pipx install pycw
uv run python tools/bench_external.py --manifest testdata/manifests/t2_arrl.jsonl \
  --cmd "pycw -d {path}" --name pycw
git clone https://github.com/e04/deepcw-engine /tmp/deepcw-engine   # AGPL: chỉ đo, không nhúng
# xem /tmp/deepcw-engine/examples/python/README để biết tên script; mẫu:
uv run python tools/bench_external.py --manifest testdata/manifests/t2_arrl.jsonl \
  --cmd "python /tmp/deepcw-engine/examples/python/decode.py /tmp/deepcw-engine/model.onnx /tmp/deepcw-engine/model.onnx.json {path}" --name deepcw
```

Baseline nội bộ đo bằng `uv run morsedesk bench --manifest testdata/manifests/t2_arrl.jsonl --engine baseline` (Task 14).
