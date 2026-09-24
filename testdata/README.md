# testdata

Mọi file dữ liệu ở đây đều KHÔNG commit (gitignored); chỉ README này nằm trong git.

## Hiện có gì (24/09/2026)

```
testdata/
├── generated/                 tự sinh bằng công cụ của dự án, tạo lại được bất cứ lúc nào
│   ├── t1/                    T1: 500 clip, seed 1000–1499  (tools/make_t1.py)
│   └── t1dev/                 dev: cùng ma trận, seed 500000–500499 (--seed-base 500000)
└── private/t2/                T2 (tools/fetch_t2.py) — manifest.jsonl gom cả ba nguồn, 40 dòng
    ├── arrl/                  10 bản ghi THẬT của ARRL W1AW, 5–40 WPM, 124,6 phút + đáp án
    │                          (dùng nội bộ, không phân phối) — dữ liệu độc lập DUY NHẤT
    ├── ebook2cw/              15 tin tiếng Nga — do Encoder của MorseDesk sinh, KHÔNG phải ebook2cw
    └── ebook2cw_kk/           15 tin tiếng Kazakh — như trên
```

Tên thư mục `ebook2cw*` là lịch sử: `fetch_t2.py synth` dùng ebook2cw nếu có trên PATH, không thì
dùng Encoder của dự án. ebook2cw chưa từng được cài (Windows lẫn WSL) và cả 30 file đều là WAV
(ebook2cw xuất MP3/OGG), nên đây là tín hiệu sạch do chính MorseDesk tạo, văn bản lấy từ danh sách
từ dựng sẵn — cũng là danh sách dùng khi huấn luyện. Chưa có bản ghi THẬT tiếng Nga/Kazakh nào.

## Kế hoạch ban đầu chưa làm

README cũ mô tả `public/` (Wikimedia Commons), `private/real/` (SRAA, QSO thu tay) và
`testdata/manifests/`. Chưa bước nào trong số đó được làm; các lệnh vẫn có trong `tools/fetch_t2.py`:

```bash
uv run python tools/fetch_t2.py commons --source commons --profile en --category "Morse code sound files" --limit 30
uv run python tools/fetch_t2.py local --source sraa --profile en --dir <thư mục đã cắt + chép đáp án>
uv run python tools/fetch_t2.py build          # gộp mọi thư mục con thành manifest.jsonl
```

Việc có giá trị nhất còn thiếu: bản ghi thật tiếng Nga và tiếng Kazakh (người gõ thật, có đáp án).

## Đo

```bash
PYTHONUTF8=1 uv run python -m morsedesk.cli bench --manifest testdata/generated/t1/manifest.jsonl --engine onnx --out-dir runs/<tên>
PYTHONUTF8=1 uv run python -m morsedesk.cli bench --manifest testdata/private/t2/manifest.jsonl --engine onnx --out-dir runs/<tên>
# thêm --profile-override auto để đo cả khâu tự nhận ngôn ngữ
```

Công cụ ngoài (multimon-ng, pycw, DeepCW) chỉ để có số đối chứng, không nhúng vào sản phẩm:
`tools/bench_external.py`, `tools/bench_pretrained.py` — xem docs/research/04-pretrained-baselines.md.
