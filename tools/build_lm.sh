#!/usr/bin/env bash
# Dựng LM ký tự bằng KenLM trong WSL Ubuntu. Chạy từ thư mục repo:
#   cd /mnt/c/Users/Admin/morsedesk && bash tools/build_lm.sh 6
# KenLM (LGPL) chỉ là công cụ dev; sản phẩm chỉ chứa .bin numpy.
set -euo pipefail
ORDER=${1:-6}
PRUNE=${PRUNE:-"0 0 1 1 1 1"}   # ngưỡng count theo bậc; tăng (vd "0 0 1 2 3 3") nếu .bin > 50 MB
ROOT=$(cd "$(dirname "$0")/.." && pwd)
KENLM_DIR=${KENLM_DIR:-$HOME/kenlm}
LMPLZ="$KENLM_DIR/build/bin/lmplz"
if [ ! -x "$LMPLZ" ]; then
  sudo apt-get update
  sudo apt-get install -y build-essential cmake git libboost-all-dev libeigen3-dev zlib1g-dev libbz2-dev liblzma-dev
  [ -d "$KENLM_DIR" ] || git clone https://github.com/kpu/kenlm.git "$KENLM_DIR"
  mkdir -p "$KENLM_DIR/build"
  (cd "$KENLM_DIR/build" && cmake .. && make -j"$(nproc)")
fi
mkdir -p /tmp/kenlm
for lang in en ru kk; do
  IN="$ROOT/corpus/$lang.chars.txt"
  if [ ! -f "$IN" ]; then echo "thiếu $IN, bỏ qua $lang"; continue; fi
  echo "== lmplz $lang (order $ORDER)"
  # shellcheck disable=SC2086
  "$LMPLZ" -o "$ORDER" --discount_fallback --prune $PRUNE -S 20% -T /tmp/kenlm \
    --text "$IN" --arpa "$ROOT/corpus/$lang.arpa"
  ls -la "$ROOT/corpus/$lang.arpa"
done
echo "xong; tiếp: uv run python tools/arpa_to_bin.py --arpa corpus/<lang>.arpa --profile <id> --out models/lm/<lang>.bin --holdout corpus/<lang>.holdout.txt"
