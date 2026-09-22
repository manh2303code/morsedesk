#!/usr/bin/env bash
# Kiểm AppImage trên Ubuntu 22.04 "sạch" — không cài 8 thư viện xcb mà CP-16 liệt kê (CP-16, CP-05, CP-11).
#
#   docker build -f packaging/Dockerfile.test -t morsedesk-test .
#   docker run --rm -v "$PWD":/work morsedesk-test bash /work/scripts/test_appimage.sh
set -uo pipefail
APP=${1:-/work/dist/MorseDesk-x86_64.AppImage}
OUT=${2:-/work/dist}
RC=0

echo "== bung AppImage (container không có FUSE) =="
cd /tmp && rm -rf squashfs-root
"$APP" --appimage-extract >/dev/null || { echo "KHÔNG bung được"; exit 2; }
APPDIR=/tmp/squashfs-root
INTERNAL="$APPDIR/usr/lib/morsedesk/_internal"

echo "== plugin nền tảng đi kèm =="
ls "$INTERNAL/PySide6/Qt/plugins/platforms/" || RC=1

echo "== thư viện còn thiếu của plugin xcb =="
# Phải dùng đúng LD_LIBRARY_PATH mà AppRun đặt: chạy ldd trần sẽ báo thiếu những thư viện vốn
# nằm ngay trong gói, và đó là báo động giả.
MISSING=$(LD_LIBRARY_PATH="$INTERNAL" ldd "$INTERNAL/PySide6/Qt/plugins/platforms/libqxcb.so" 2>/dev/null \
          | awk '/not found/ {print $1}' | sort -u)
if [ -n "$MISSING" ]; then
    echo "THIẾU:"; echo "$MISSING"; RC=1
else
    echo "không thiếu thư viện nào"
fi

echo "== tám thư viện của CP-16 có trong gói chưa =="
for lib in libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-image.so.0 libxcb-keysyms.so.1 \
           libxcb-render-util.so.0 libxcb-util.so.1 libxcb-xkb.so.1 libxkbcommon-x11.so.0; do
    if [ -e "$INTERNAL/$lib" ]; then echo "  có   $lib"; else echo "  THIẾU $lib"; RC=1; fi
done

echo "== mở cửa sổ thật dưới Xvfb rồi chụp màn hình =="
export HOME=/tmp
Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 &
XVFB=$!
sleep 3
DISPLAY=:99 "$APPDIR/AppRun" --engine baseline >/tmp/gui.out 2>/tmp/gui.err &
GUI=$!
sleep 25
if kill -0 $GUI 2>/dev/null; then
    echo "cửa sổ CHẠY (còn sống sau 25 giây)"
    DISPLAY=:99 import -window root "$OUT/appimage-ubuntu2204-en.png" 2>/tmp/shot.err \
        && echo "ảnh: $OUT/appimage-ubuntu2204-en.png" || { echo "không chụp được"; cat /tmp/shot.err; RC=1; }
    kill $GUI 2>/dev/null; wait $GUI 2>/dev/null

    # Lan hai bang tieng Kazakh: anh nay la bang chung cho CP-11.
    DISPLAY=:99 "$APPDIR/AppRun" --engine baseline --lang kk >/tmp/gui_kk.out 2>/tmp/gui_kk.err &
    GUI_KK=$!
    sleep 20
    if kill -0 $GUI_KK 2>/dev/null; then
        DISPLAY=:99 import -window root "$OUT/appimage-ubuntu2204-kk.png" 2>/dev/null \
            && echo "anh: $OUT/appimage-ubuntu2204-kk.png"
        kill $GUI_KK 2>/dev/null; wait $GUI_KK 2>/dev/null
    else
        echo "ban Kazakh CHET"; tail -10 /tmp/gui_kk.err; RC=1
    fi
else
    echo "cửa sổ CHẾT — stderr:"; tail -20 /tmp/gui.err; RC=1
fi
kill $XVFB 2>/dev/null

echo "== không có lời gọi mạng nào lúc khởi động (spec mục 9) =="
if grep -qiE "socket|connect" /tmp/gui.err 2>/dev/null; then echo "  có dấu hiệu, xem /tmp/gui.err"; else echo "  stderr sạch"; fi
exit $RC
