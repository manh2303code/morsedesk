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
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

ROOT = Path(SPECPATH).parent
ICON_DIR = ROOT / "morsedesk" / "app" / "icons"

opts = argparse.ArgumentParser()
opts.add_argument("--onefile", action="store_true")
options = opts.parse_args()


def tree(src: str, dst: str) -> list[tuple[str, str]]:
    base = ROOT / src
    if not base.is_dir():
        return []
    return [(str(p), str(Path(dst) / p.relative_to(base).parent))
            for p in base.rglob("*") if p.is_file()]


def build_ico(ico: Path) -> Path:
    """ICO nhiều cỡ (16…256) từ bộ PNG của `packaging/make_icon.py`, mỗi mục là PNG nguyên vẹn.

    Explorer và thanh tác vụ chọn cỡ gần nhất; một ICO chỉ có bản 256 bị thu nhỏ thành nhòe ở 16 px.
    PyInstaller chỉ tự đổi PNG sang ICO khi có Pillow — không đáng thêm phụ thuộc vì một biểu tượng.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_icon", ROOT / "packaging" / "make_icon.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    pngs = [(s, (ICON_DIR / f"morsedesk-{s}.png").read_bytes())
            for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    ico.parent.mkdir(parents=True, exist_ok=True)
    ico.write_bytes(mk.ico_bytes(pngs))
    return ico


datas = (
    tree("morsedesk/profiles", "morsedesk/profiles")
    + [(str(p), "morsedesk/app/i18n") for p in (ROOT / "morsedesk/app/i18n").glob("*.qm")]
    + tree("morsedesk/app/fonts", "morsedesk/app/fonts")
    + tree("morsedesk/app/icons", "morsedesk/app/icons")      # logo cửa sổ và thanh tác vụ
    + tree("morsedesk/app/docs", "morsedesk/app/docs")        # trang Giới thiệu, tài liệu kỹ thuật
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
ICON_PNG = ICON_DIR / "morsedesk-256.png"

if options.onefile:
    icon = build_ico(Path(workpath) / "morsedesk.ico")
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
