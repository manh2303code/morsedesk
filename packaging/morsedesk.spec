# PyInstaller spec cho MorseDesk (onedir, xem spec mục 9).
#
# Gói kèm dữ liệu mà ứng dụng đọc lúc chạy: profile YAML, bản dịch .qm, font, model âm thanh và
# mô hình ngôn ngữ. Model và LM không nằm trong repo nên chỉ đưa vào khi có mặt — bản dựng thiếu
# chúng vẫn chạy được ở engine baseline, và `check_models` sẽ báo đường dẫn còn thiếu.

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

ROOT = Path(SPECPATH).parent

def tree(src: str, dst: str) -> list[tuple[str, str]]:
    base = ROOT / src
    if not base.is_dir():
        return []
    return [(str(p), str(Path(dst) / p.relative_to(base).parent))
            for p in base.rglob("*") if p.is_file()]

datas = (
    tree("morsedesk/profiles", "morsedesk/profiles")
    + [(str(p), "morsedesk/app/i18n") for p in (ROOT / "morsedesk/app/i18n").glob("*.qm")]
    + tree("morsedesk/app/fonts", "morsedesk/app/fonts")
    + [(str(p), "models") for p in (ROOT / "models").glob("acoustic.*")]
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
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="morsedesk-gui",
          console=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="morsedesk")
