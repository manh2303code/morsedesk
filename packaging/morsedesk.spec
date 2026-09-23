# PyInstaller spec cho MorseDesk.
#
#   pyinstaller packaging/morsedesk.spec               -> onedir dist/morsedesk/ (AppImage dùng)
#   pyinstaller packaging/morsedesk.spec -- --onefile  -> một file dist/MorseDesk.exe (Windows)
#
# Gói kèm dữ liệu mà ứng dụng đọc lúc chạy: profile YAML, bản dịch .qm, font, model âm thanh và
# mô hình ngôn ngữ. Model và LM không nằm trong repo nên chỉ đưa vào khi có mặt — bản dựng thiếu
# chúng vẫn chạy được ở engine baseline, và `check_models` sẽ báo đường dẫn còn thiếu.
#
# Vì sao một file cho Windows dù research (.superpowers/sdd/research-distribution.md §3.1) khuyên
# onedir: người dùng muốn MỘT file để chép và bấm. Đo thật 23/09: khởi động onefile 2,6-2,7 s so
# với onedir 1,0-1,2 s — chênh 1,6 s chứ không phải 3 lần như tài liệu PyInstaller. Cái giá thật
# là lần chạy ĐẦU (55 s, Defender quét từng file bung ra) nên bản một file có màn hình chờ.

import argparse
import struct
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

ROOT = Path(SPECPATH).parent

opts = argparse.ArgumentParser()
opts.add_argument("--onefile", action="store_true")
options = opts.parse_args()


def tree(src: str, dst: str) -> list[tuple[str, str]]:
    base = ROOT / src
    if not base.is_dir():
        return []
    return [(str(p), str(Path(dst) / p.relative_to(base).parent))
            for p in base.rglob("*") if p.is_file()]


def png_to_ico(png: Path, ico: Path) -> Path:
    """Bọc nguyên file PNG vào một ICO một ảnh (Windows Vista trở đi đọc được PNG trong ICO).

    PyInstaller chỉ tự đổi PNG sang ICO khi có Pillow; không đáng thêm phụ thuộc vì một biểu tượng.
    Kích thước 256 ghi là 0 trong ICONDIRENTRY — đó là quy ước của định dạng, không phải lỗi.
    """
    data = png.read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    entry = struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0, 1, 32, len(data), 6 + 16)
    ico.parent.mkdir(parents=True, exist_ok=True)
    ico.write_bytes(struct.pack("<HHH", 0, 1, 1) + entry + data)
    return ico


datas = (
    tree("morsedesk/profiles", "morsedesk/profiles")
    + [(str(p), "morsedesk/app/i18n") for p in (ROOT / "morsedesk/app/i18n").glob("*.qm")]
    + tree("morsedesk/app/fonts", "morsedesk/app/fonts")
    # Chỉ hai file này: glob `acoustic.*` còn bắt cả `acoustic.golden.npz` (2,6 MB fixture so
    # sánh bit-exact của bộ kiểm thử), thứ người dùng cuối không bao giờ đọc tới.
    + [(str(ROOT / "models" / n), "models") for n in ("acoustic.onnx", "acoustic.json")
       if (ROOT / "models" / n).exists()]
    + [(str(p), "models/lm") for p in (ROOT / "models/lm").glob("*.bin")]
    + [(str(p), "models/lm") for p in (ROOT / "models/lm").glob("*.md")]
)

# soundfile và sounddevice nạp thư viện C qua ctypes nên PyInstaller không tự thấy.
binaries = collect_dynamic_libs("soundfile") + collect_dynamic_libs("sounddevice")

a = Analysis(
    [str(ROOT / "packaging" / "entry_gui.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["morsedesk.model.onnx_runner", "sounddevice", "soundfile"],
    excludes=["torch", "onnx", "pyarrow", "matplotlib", "tkinter", "pytest",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
ICON_PNG = ROOT / "packaging" / "appimage" / "morsedesk.png"

if options.onefile:
    icon = png_to_ico(ICON_PNG, Path(workpath) / "morsedesk.ico")
    # Bootloader vẽ ảnh chờ bằng Tcl/Tk riêng của nó (không cần module tkinter trong gói) và cập
    # nhật dòng chữ theo tên file đang bung — đó là dấu hiệu "đang chạy" trong lúc chờ Defender.
    splash = Splash(str(ICON_PNG), binaries=a.binaries, datas=a.datas,
                    text_pos=(12, 244), text_size=9, text_color="#9aa0a6",
                    minify_script=True, always_on_top=True)
    exe = EXE(pyz, a.scripts, splash, splash.binaries, a.binaries, a.datas, name="MorseDesk",
              icon=str(icon), console=False, strip=False, upx=False)
else:
    exe = EXE(pyz, a.scripts, exclude_binaries=True, name="morsedesk-gui",
              console=False, strip=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="morsedesk")
