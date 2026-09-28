#!/usr/bin/env bash
# So hồi quy GHÉP CẶP hai phiên bản mã (worktree mốc vs repo hiện tại) trên T1, dev, dev-OOV, T2, T4.
#   bash scripts/regress_pair.sh <thư mục worktree mốc> <thư mục ra> [workers]
# Mỗi bộ chạy mốc rồi mới; kết quả từng clip ở <ra>/<bộ>_{base,new}.json, so ở <ra>/<bộ>.cmp.txt.
set -uo pipefail
BASE="$1"; OUT="$2"; W="${3:-8}"
NEW="$(cd "$(dirname "$0")/.." && pwd)"
PY="$NEW/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$NEW/.venv/bin/python"
mkdir -p "$OUT"
export PYTHONUTF8=1
for set in t1:testdata/generated/t1 dev:testdata/generated/t1dev oov:testdata/generated/t1oov t2:testdata/private/t2 t4:testdata/private/t4; do
  name="${set%%:*}"; dir="${set#*:}"
  (cd "$BASE" && PYTHONPATH="$BASE" "$PY" tools/paired_bench.py run "$dir/manifest.jsonl" "$OUT/${name}_base.json" --workers "$W")
  (cd "$NEW" && PYTHONPATH="$NEW" "$PY" tools/paired_bench.py run "$dir/manifest.jsonl" "$OUT/${name}_new.json" --workers "$W")
  "$PY" "$NEW/tools/paired_bench.py" cmp "$OUT/${name}_base.json" "$OUT/${name}_new.json" | tee "$OUT/$name.cmp.txt"
done
