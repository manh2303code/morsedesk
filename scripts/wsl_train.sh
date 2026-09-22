#!/usr/bin/env bash
# Chạy một run huấn luyện trong WSL ở foreground. Gọi từ PowerShell:
#   Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash',
#     '/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','<tên run>','<cờ>...' -WindowStyle Hidden
#
# Vì sao foreground: `nohup` trong WSL bị giết cùng distro khi wsl.exe thoát (đã gặp ở E5);
# Start-Process giữ wsl.exe sống nên tiến trình huấn luyện sống theo.
# Vì sao OMP_NUM_THREADS=8: torch dùng đủ 16 hyperthread trên WSL2 gây thrash — micro-benchmark
# cho 27,6 s/bước với 16 thread so với 0,26 s/bước với 8 thread (E5). BẮT BUỘC, đừng bỏ.
set -euo pipefail
NAME="$1"; shift
cd /mnt/c/Users/Admin/morsedesk
export UV_PROJECT_ENVIRONMENT="$HOME/.venv-morsedesk"
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export PYTHONUTF8=1
mkdir -p "runs/$NAME"
exec "$HOME/.local/bin/uv" run python -m tools.train --name "$NAME" "$@" \
    >"runs/$NAME/train.log" 2>"runs/$NAME/train.err"
