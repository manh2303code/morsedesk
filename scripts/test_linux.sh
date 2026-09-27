#!/usr/bin/env bash
# Bộ test MorseDesk trên Linux (WSL), venv RIÊNG ~/.venv-md-test — không đè .venv Windows của repo.
# Gọi từ Git Bash:
#   MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" wsl.exe -d Ubuntu-26.04 -- \
#     bash /mnt/c/Users/Admin/morsedesk/scripts/test_linux.sh [đối số pytest]
# Qt chạy offscreen; không test nào chạm PortAudio thật (tests/conftest.py). ~25 phút trên /mnt/c
# (test_train_smoke chậm nhất: torch CPU trong WSL).
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"          # uv cài theo người dùng; bash không đăng nhập thì thiếu
export UV_PROJECT_ENVIRONMENT="$HOME/.venv-md-test" VIRTUAL_ENV="$HOME/.venv-md-test" UV_LINK_MODE=copy
uv sync --all-extras --frozen >/dev/null
export PYTHONUTF8=1 QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
exec "$HOME/.venv-md-test/bin/python" -m pytest -p no:warnings -q -p no:cacheprovider "$@"
