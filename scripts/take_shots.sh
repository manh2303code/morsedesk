#!/usr/bin/env bash
# Chụp màn hình GUI trên Ubuntu qua Xvfb, để soi UI/UX bằng mắt chứ không chỉ bằng test.
#
#   docker run --rm -v "$PWD":/src morsedesk-build bash scripts/take_shots.sh
set -uo pipefail
cd /src
export UV_PROJECT_ENVIRONMENT=/opt/venv VIRTUAL_ENV=/opt/venv HOME=/tmp
uv sync --extra runtime --extra gui --quiet

Xvfb :99 -screen 0 1280x900x24 >/tmp/xvfb.log 2>&1 &
XVFB=$!
sleep 3
DISPLAY=:99 uv run python packaging/shots.py /src/dist/shots
RC=$?
kill $XVFB 2>/dev/null
ls -la /src/dist/shots 2>/dev/null | tail -12
exit $RC
