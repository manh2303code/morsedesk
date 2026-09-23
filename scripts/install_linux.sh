#!/usr/bin/env bash
# Cài MorseDesk cho người dùng cuối trên Linux. Không cần quyền quản trị, không cần mạng.
#
#   bash install_linux.sh                       # tìm AppImage cạnh script này
#   bash install_linux.sh /duong/dan/tới.AppImage
#
# Vì sao cần script này thay vì "chép file rồi bấm đúp": file chép từ USB, từ email hay từ
# Windows KHÔNG có bit thực thi, và trình quản lý file (Nautilus, Dolphin, Thunar) khi bấm đúp
# một file như vậy thì **không làm gì cả và cũng không báo lỗi** — người dùng tưởng ứng dụng hỏng.
# Script này chmod +x, chép vào ~/Applications, rồi ghi desktop entry để MorseDesk hiện trong
# menu ứng dụng như mọi phần mềm khác.

set -euo pipefail

APP_NAME="MorseDesk"
DEST_DIR="${HOME}/Applications"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="${1:-}"
if [ -z "$src" ]; then
    for cand in "$here"/*.AppImage "$here"/../dist/*.AppImage; do
        [ -f "$cand" ] && { src="$cand"; break; }
    done
fi
if [ -z "$src" ] || [ ! -f "$src" ]; then
    echo "Không tìm thấy file .AppImage." >&2
    echo "Dùng: bash $(basename "$0") /đường/dẫn/tới/MorseDesk-x86_64.AppImage" >&2
    exit 1
fi
src="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"

# FAT32 mount `showexec` nên chỉ .EXE/.COM/.BAT mới chạy được: chmod +x ở đó không có tác dụng
# và cũng không báo lỗi. Chạy thẳng từ USB FAT32 là hỏng im lặng, nên phải chép đi nơi khác —
# việc script này vẫn làm — và chỉ cảnh báo để người dùng hiểu vì sao.
fstype="$(df --output=fstype "$src" 2>/dev/null | tail -1 || echo "")"
case "$fstype" in
    vfat|msdos|fat|exfat)
        echo "Lưu ý: nguồn nằm trên phân vùng $fstype, không giữ được quyền thực thi."
        echo "       Script sẽ chép sang $DEST_DIR nên vẫn chạy được."
        ;;
esac

mkdir -p "$DEST_DIR" "$DESKTOP_DIR" "$ICON_DIR"
dest="${DEST_DIR}/${APP_NAME}.AppImage"
if [ "$src" != "$dest" ]; then
    cp -f "$src" "$dest"
fi
chmod +x "$dest"

# Biểu tượng: lấy từ trong AppImage nếu bung được, không thì bỏ qua (menu vẫn chạy, chỉ thiếu icon).
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
if (cd "$tmp" && "$dest" --appimage-extract 'morsedesk.png' >/dev/null 2>&1); then
    found="$(find "$tmp/squashfs-root" -name 'morsedesk.png' -print -quit 2>/dev/null || true)"
    [ -n "$found" ] && cp -f "$found" "${ICON_DIR}/morsedesk.png"
fi

cat > "${DESKTOP_DIR}/morsedesk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MorseDesk
Comment=Decode and send Morse code offline (English, Russian, Kazakh)
Comment[ru]=Декодирование и передача азбуки Морзе без интернета (английский, русский, казахский)
Comment[kk]=Морзе әліпбиін интернетсіз декодтау және жіберу (ағылшын, орыс, қазақ)
Exec=${dest}
Icon=morsedesk
Terminal=false
StartupWMClass=MorseDesk
Categories=AudioVideo;Audio;Utility;
EOF
chmod +x "${DESKTOP_DIR}/morsedesk.desktop"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

# AppImage type 2 cần FUSE để tự mount. Ubuntu 22.04 và 24.04 đều KHÔNG cài libfuse2 sẵn, nhưng
# runtime nhúng của bản dựng này liên kết tĩnh và tìm `fusermount` kèm chữ số, nên bắt được
# `fusermount3` mà cả hai bản đều có. Chỉ khi không có cái nào mới phải dùng --appimage-extract.
if ! command -v fusermount3 >/dev/null 2>&1 && ! command -v fusermount >/dev/null 2>&1; then
    echo
    echo "Máy này không có fusermount. Nếu bấm chạy không lên, dùng cách bung sẵn:"
    echo "    cd ${DEST_DIR} && ./${APP_NAME}.AppImage --appimage-extract && ./squashfs-root/AppRun"
fi

echo
echo "Xong. MorseDesk đã cài vào ${dest}"
echo "Mở bằng: menu ứng dụng (gõ \"MorseDesk\"), hoặc chạy thẳng ${dest}"
