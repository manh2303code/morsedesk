#!/usr/bin/env bash
# Chạy một run huấn luyện trong WSL ở foreground. Gọi từ PowerShell:
#   Start-Process wsl.exe -ArgumentList '-d','Ubuntu-26.04','--','bash',
#     '/mnt/c/Users/Admin/morsedesk/scripts/wsl_train.sh','<tên run>','<cờ>...' -WindowStyle Hidden
#
# Vì sao foreground: `nohup` trong WSL bị giết cùng distro khi wsl.exe thoát (đã gặp ở E5);
# Start-Process giữ wsl.exe sống nên tiến trình huấn luyện sống theo.
#
# Thiết bị: máy dev có RTX 5090 Laptop (24 GB, sm_120). Venv $HOME/.venv-md-cuda cài torch cu128;
# có thì dùng, không thì rơi về venv CPU cũ. Đo trên cấu hình E6 (batch 16, feature_mode window):
#   CPU 8 luồng             0,56  s/bước  -> 30000 bước ~ 4,7 giờ
#   GPU + 8 worker dữ liệu  0,090 s/bước
#   GPU + 14 worker dữ liệu 0,065 s/bước  -> 30000 bước ~ 33 phút
# Giới hạn luồng là BẮT BUỘC: torch lấy cả 16 hyperthread trên WSL2 gây thrash, 27,6 s/bước so
# với 0,26 s/bước khi giới hạn (đo ở E5). Với GPU thì nút cổ chai chuyển sang khâu sinh dữ liệu
# trên CPU, nên để NHIỀU worker và ÍT luồng OMP mỗi worker (4), vì 14 worker x 8 luồng sẽ tranh
# nhau 16 CPU.
set -euo pipefail
NAME="$1"; shift
cd /mnt/c/Users/Admin/morsedesk
if [ -x "$HOME/.venv-md-cuda/bin/python" ]; then
    PY="$HOME/.venv-md-cuda/bin/python"
    export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
else
    PY="$HOME/.venv-morsedesk/bin/python"
    export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8
fi
export PYTHONUTF8=1
mkdir -p "runs/$NAME"
exec "$PY" -m tools.train --name "$NAME" "$@"     >"runs/$NAME/train.log" 2>"runs/$NAME/train.err"
