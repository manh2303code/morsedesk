#!/usr/bin/env bash
# Dựng AppImage trong container Ubuntu 22.04. Gọi từ gốc repo:
#
#   docker build -f packaging/Dockerfile.build -t morsedesk-build .
#   docker run --rm -v "$PWD":/src morsedesk-build bash scripts/build_appimage.sh
#
# Kết quả: dist/MorseDesk-x86_64.AppImage và dist/SHA256SUMS.
set -euo pipefail
cd /src

# Môi trường ảo phải nằm NGOÀI cây mount: repo được mount từ máy Windows, và một .venv kiểu
# Linux tạo ở đó sẽ đè lên .venv của máy dev (đã gặp: `uv sync` trên Windows sau đó báo
# "failed to remove file .venv/lib64: Access is denied").
export UV_PROJECT_ENVIRONMENT=/opt/venv

echo "== cài phụ thuộc =="
uv sync --extra runtime --extra gui --extra dev
uv pip install "pyinstaller>=6.6,<7"

echo "== dựng bản onedir =="
rm -rf build dist/morsedesk
uv run pyinstaller --noconfirm --workpath build --distpath dist packaging/morsedesk.spec

echo "== dựng cây AppDir =="
APPDIR=build/MorseDesk.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r dist/morsedesk "$APPDIR/usr/lib/morsedesk"
install -m 755 packaging/appimage/AppRun "$APPDIR/AppRun"
install -m 644 packaging/appimage/morsedesk.desktop "$APPDIR/morsedesk.desktop"
cp "$APPDIR/morsedesk.desktop" "$APPDIR/usr/share/applications/"
# appimagetool đòi có icon ở gốc AppDir; sinh một icon đặc nếu repo chưa có file thật.
if [ -f packaging/appimage/morsedesk.png ]; then
    cp packaging/appimage/morsedesk.png "$APPDIR/morsedesk.png"
else
    uv run python packaging/make_icon.py "$APPDIR/morsedesk.png"
fi
cp "$APPDIR/morsedesk.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"

echo "== gói AppImage =="
mkdir -p dist
ARCH=x86_64 appimagetool --appimage-extract-and-run "$APPDIR" dist/MorseDesk-x86_64.AppImage

echo "== tổng kiểm =="
( cd dist && sha256sum MorseDesk-x86_64.AppImage > SHA256SUMS )
ls -lh dist/MorseDesk-x86_64.AppImage
