"""Đo độ tương phản chữ/nền THẬT của mọi widget có chữ, trên ảnh chụp đã ghép lớp.

Stylesheet nhiều tầng làm màu chữ thực tế khác với màu ghi trong mã: banner cảnh báo từng đặt
`color` cho khung nhưng nhãn con lại ăn luật `QWidget {{ color: TEXT }}` của theme -> chữ sáng
trên nền vàng nhạt, gần như vô hình (ảnh chụp người dùng 24/09). Đọc mã không bắt được loại lỗi
này; đo điểm ảnh thì bắt được.

Cách đo: với mỗi widget đang hiện có chữ, cắt đúng vùng của nó trên ảnh chụp cả cửa sổ; nền là
màu xuất hiện nhiều nhất; chữ là điểm ảnh tương phản mạnh nhất so với nền (bách phân vị 99, để
một điểm viền lẻ không che mất chữ chìm). Ngưỡng WCAG: 4,5:1 cho chữ thường, 3:1 cho chữ lớn.

    uv run python tools/contrast_audit.py            # in bảng, mã thoát 1 nếu có chữ chìm
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

FAIL = 3.0          # dưới mức này là lỗi (kể cả chữ lớn)
WARN = 4.5          # dưới mức này là đáng xem với chữ thường


def _linear(c: np.ndarray) -> np.ndarray:
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb: np.ndarray) -> np.ndarray:
    lin = _linear(rgb.astype(np.float64))
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def image_array(img) -> np.ndarray:
    from PySide6.QtGui import QImage

    img = img.convertToFormat(QImage.Format.Format_RGB32)
    h, bpl = img.height(), img.bytesPerLine()
    arr = np.frombuffer(img.constBits(), np.uint8, count=h * bpl).reshape(h, bpl // 4, 4)
    return arr[:, : img.width(), 2::-1].copy()          # BGRA -> RGB


def measure(crop: np.ndarray) -> tuple[float, tuple[int, int, int], tuple[int, int, int]] | None:
    """(độ tương phản, màu nền, màu chữ) của một vùng; None nếu vùng rỗng."""
    if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
        return None
    flat = crop.reshape(-1, 3)
    q = (flat // 8).astype(np.int32)
    keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    bg_key = vals[np.argmax(counts)]
    bg = flat[keys == bg_key].mean(axis=0)
    lum = luminance(flat)
    lb = float(luminance(bg[None, :])[0])
    ratio = (np.maximum(lum, lb) + 0.05) / (np.minimum(lum, lb) + 0.05)
    # Điểm tương phản cao thứ 12: chữ ngắn trong khung rộng chỉ chiếm vài phần nghìn diện tích nên
    # bách phân vị bỏ sót, còn lấy đúng điểm cao nhất thì một điểm nhiễu lẻ cũng qua.
    k = min(12, ratio.size)
    p = float(np.partition(ratio, -k)[-k])
    fg = flat[int(np.argmin(np.abs(ratio - p)))]
    return p, tuple(int(v) for v in bg), tuple(int(v) for v in fg)


def text_of(w) -> str:
    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
    )

    if isinstance(w, QLabel):
        pm = w.pixmap()
        return "" if (pm is not None and not pm.isNull()) else w.text()
    if isinstance(w, QAbstractButton):
        return w.text()
    if isinstance(w, QComboBox):
        return w.currentText()
    if isinstance(w, QLineEdit):
        return w.text() or w.placeholderText()
    if isinstance(w, (QPlainTextEdit, QTextEdit)):
        return w.toPlainText()[:60]
    # Widget tự vẽ chữ bằng QPainter: không có text() chuẩn, nhưng chữ vẫn phải đọc được.
    name = type(w).__name__
    if name == "_Canvas":
        return " ".join(w.view.texts())[:60] or w.view.placeholder()
    if name == "MorseTape":
        return "<băng Morse>"
    if name == "ProgressRing":
        return "<vòng tiến trình>"
    return ""


def _dimmed(w) -> bool:
    """Widget cố ý bị làm mờ: có hiệu ứng mờ ở nó hay tổ tiên, hoặc nằm dưới lớp phủ tiến trình
    đang hiện (lớp phủ che kết quả cũ lúc đang giải mã — đó là thiết kế, không phải lỗi)."""
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    from morsedesk.app.widgets.busy_overlay import BusyOverlay

    for ov in w.window().findChildren(BusyOverlay):
        if ov.isVisible() and not ov.isAncestorOf(w) and ov is not w:
            centre = w.mapToGlobal(w.rect().center())
            if ov.rect().contains(ov.mapFromGlobal(centre)):
                return True
    while w is not None:
        eff = w.graphicsEffect()
        if isinstance(eff, QGraphicsOpacityEffect) and eff.opacity() < 1.0:
            return True
        w = w.parentWidget()
    return False


def audit_window(win, state: str) -> list[dict]:
    from PySide6.QtCore import QCoreApplication, QRect
    from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

    for _ in range(6):
        QCoreApplication.processEvents()
    img = win.grab().toImage()
    dpr = img.devicePixelRatio() or 1.0
    arr = image_array(img)
    rows = []
    for w in win.findChildren(QWidget):
        if not w.isVisible() or w.window() is not win:
            continue
        if _dimmed(w):          # cố ý làm mờ (kết quả cũ lúc đang giải mã): không tính là lỗi
            continue
        text = text_of(w).strip()
        if not text:
            continue
        target = w.viewport() if isinstance(w, (QPlainTextEdit, QTextEdit)) else w
        r = target.contentsRect().adjusted(2, 2, -2, -2)
        tl = target.mapTo(win, r.topLeft())
        box = QRect(int(tl.x() * dpr), int(tl.y() * dpr), int(r.width() * dpr), int(r.height() * dpr))
        m = measure(arr[max(0, box.top()): box.bottom(), max(0, box.left()): box.right()])
        if m is None:
            continue
        ratio, bg, fg = m
        rows.append({"state": state, "widget": type(w).__name__, "name": w.objectName(),
                     "text": text.replace("\n", " ")[:48], "ratio": ratio, "bg": bg, "fg": fg,
                     "enabled": w.isEnabled()})
    return rows


def run() -> list[dict]:
    from PySide6.QtCore import QCoreApplication

    from morsedesk.app.main import build_parser, create_app

    app, win = create_app(build_parser().parse_args(["--lang", "en", "--engine", "onnx"]))
    win.resize(1400, 900)
    win.show()
    page = win.decode_page
    rows: list[dict] = []
    for _ in range(300):                               # chờ file mẫu giải xong
        QCoreApplication.processEvents()
        if page.result is not None and not page._busy:
            break
        import time
        time.sleep(0.05)
    tabs = win.tabs
    rows += audit_window(win, "decode: kết quả mẫu")
    page.banner.show_warning("Tone not detected clearly; guessing from the spectral peak, "
                             "so the result may be wrong.")
    rows += audit_window(win, "decode: banner cảnh báo")
    page.banner.show_error("Cannot read this file: the format is not supported.")
    rows += audit_window(win, "decode: banner lỗi")
    page.banner.clear()
    page.on_busy(True)
    page.overlay.set_progress(420, 1000)
    rows += audit_window(win, "decode: đang giải mã")
    page.on_busy(False)
    page.details_button.click()
    rows += audit_window(win, "decode: ẩn văn bản thuần")
    page.details_button.click()
    for pg, label in ((win.live_page, "nghe"), (win.encode_page, "tạo mã"),
                      (win.settings_page, "cài đặt"), (win.about_page, "giới thiệu")):
        if pg is None:
            continue
        tabs.setCurrentIndex(tabs.indexOf(pg))
        rows += audit_window(win, label)
        if hasattr(pg, "banner"):
            pg.banner.show_warning("Warning text for the audit.")
            rows += audit_window(win, f"{label}: banner cảnh báo")
            pg.banner.show_error("Error text for the audit.")
            rows += audit_window(win, f"{label}: banner lỗi")
            pg.banner.clear()
    enc = win.encode_page
    tabs.setCurrentIndex(tabs.indexOf(enc))
    enc.text_edit.setPlainText("ЖЖЖ")                     # chữ ngoài bảng mã tiếng Anh -> cảnh báo
    rows += audit_window(win, "tạo mã: chữ không hợp lệ")
    # cửa sổ tài liệu kỹ thuật
    from morsedesk.app.doc_window import TechDocWindow

    doc = TechDocWindow("en")
    doc.resize(1100, 800)
    doc.show()
    rows += audit_window(doc, "tài liệu kỹ thuật")
    doc.close()
    win.close()
    return rows


def main() -> int:
    rows = run()
    bad = [r for r in rows if r["ratio"] < FAIL and r["enabled"]]
    weak = [r for r in rows if FAIL <= r["ratio"] < WARN and r["enabled"]]
    disabled = [r for r in rows if not r["enabled"] and r["ratio"] < FAIL]
    print(f"đã đo {len(rows)} lượt widget có chữ")
    for title, group in (("CHÌM (< 3:1)", bad), ("YẾU (3–4,5:1)", weak), ("bị khóa, < 3:1", disabled)):
        print(f"\n== {title}: {len(group)}")
        for r in sorted(group, key=lambda r: r["ratio"]):
            print(f"  {r['ratio']:5.2f}  {r['state']:26s} {r['widget']:14s} {r['text']!r}  nền {r['bg']} chữ {r['fg']}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
