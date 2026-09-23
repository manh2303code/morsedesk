"""Cửa sổ chính: thanh công cụ (ngôn ngữ giao diện), hai tab Giải mã | Tạo mã, đổi QTranslator."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.decode_page import DecodePage
from morsedesk.app.encode_page import EncodePage
from morsedesk.app.settings import UI_LANGUAGES, AppSettings
from morsedesk.app.settings_page import SettingsPage
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.flags import LanguageBar
from morsedesk.app.worker import DecoderWorker, Player

# Tên hiển thị ngôn ngữ giao diện. Bản dịch Kazakh chưa được người bản ngữ soát (CP-12) nên có
# nhãn "жоба" — đúng nghĩa "bản nháp" trong chính tiếng Kazakh. Trước đây nhãn này là chữ "nháp"
# tiếng Việt, một ghi chú nội bộ lọt thẳng ra giao diện người dùng cuối; ảnh chụp AppImage trên
# Ubuntu sạch mới làm nó lộ ra.
LANGUAGE_NAMES = {"en": "English", "ru": "Русский", "kk": "Қазақша (жоба)"}


class MainWindow(QMainWindow):
    """Cửa sổ chính: chọn ngôn ngữ giao diện trên toolbar, tab Giải mã (Task 4) và Tạo mã (Task 5)."""

    def __init__(
        self, worker: DecoderWorker, player: Player, settings: AppSettings, i18n_dir: Path, parent=None
    ) -> None:
        super().__init__(parent)
        self.worker = worker
        self.player = player
        self.settings = settings
        self.i18n_dir = Path(i18n_dir)
        self.current_language = "en"
        self._translator: QTranslator | None = None
        self._closing = False   # đã hoãn một lần đóng để chờ worker chạy xong chưa
        self.resize(1000, 700)

        bar = QToolBar(self)
        bar.setMovable(False)
        self.addToolBar(bar)
        self.language_label = QLabel(self)
        bar.addWidget(self.language_label)
        # Ba lá cờ thay hộp chọn: nhận ra ngôn ngữ mình cần mà không phải đọc, kể cả khi giao
        # diện đang ở thứ tiếng mình không biết — đúng tình huống người dùng mở app lần đầu và
        # nó đang hiện tiếng Kazakh.
        self.language_bar = LanguageBar(UI_LANGUAGES, LANGUAGE_NAMES, self)
        bar.addWidget(self.language_bar)
        for code, btn in self.language_bar.buttons.items():
            btn.clicked.connect(lambda _checked=False, c=code: self.set_language(c))

        self.banner = Banner(self)      # thông báo mức cửa sổ (vd. đang chờ worker để đóng)
        self.tabs = QTabWidget(self)
        self.decode_page = DecodePage(worker, settings, self)
        self.encode_page = EncodePage(player, settings, self)
        # Engine lấy từ worker: trang Cài đặt chỉ báo cáo, không phải nguồn sự thật thứ hai.
        self.settings_page = SettingsPage(engine=worker.engine, parent=self)
        self.tabs.addTab(self.decode_page, "")
        self.tabs.addTab(self.encode_page, "")
        self.tabs.addTab(self.settings_page, "")
        central = QWidget(self)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.banner)
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.retranslate()

    # ---- i18n ----
    def set_language(self, code: str) -> bool:
        """Nạp `morsedesk_<code>.qm` (nếu khác "en"), lưu cài đặt, phát LanguageChange qua retranslate().

        Trả `False` nếu `code` không thuộc `UI_LANGUAGES`, hoặc nếu file .qm không tải được
        (chưa có ở Task 4/5; ngôn ngữ hiện tại vẫn được đặt và tiếng Anh vẫn hiển thị đúng).
        """
        if code not in UI_LANGUAGES:
            return False
        app = QCoreApplication.instance()
        if self._translator is not None:
            app.removeTranslator(self._translator)
            self._translator = None
        ok = True
        if code != "en":
            tr = QTranslator(self)
            ok = tr.load(str(self.i18n_dir / f"morsedesk_{code}.qm"))
            if ok:
                app.installTranslator(tr)
                self._translator = tr
        self.current_language = code
        self.settings.ui_language = code
        self.language_bar.set_current(code)
        self.retranslate()
        return ok

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr("MorseDesk"))
        self.language_label.setText(self.tr("UI language:"))
        self.language_bar.set_names(LANGUAGE_NAMES)
        self.tabs.setTabText(0, self.tr("Decode"))
        self.tabs.setTabText(1, self.tr("Encode"))
        self.tabs.setTabText(2, self.tr("Settings"))
        self.decode_page.retranslate()
        self.encode_page.retranslate()
        self.settings_page.retranslate()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        """Đóng cửa sổ mà không bao giờ hủy QThread đang chạy.

        Worker còn chạy -> xin dừng không chờ rồi chờ ngắn 500 ms. Nếu yêu cầu hiện tại vẫn
        chưa xong (file dài có thể mất vài phút) thì **hoãn đóng**: `event.ignore()`, khóa
        giao diện, hiện banner, và nối `worker.finished` vào `close()` đúng một lần. Khi worker
        kết thúc, `close()` chạy lại, `isRunning()` là False và cửa sổ đóng bình thường.
        """
        if self.worker.isRunning() and not self._closing:
            self.worker.stop_async()
            self.worker.wait(500)   # chỉ chờ ở lần đóng đầu tiên, khỏi treo thêm mỗi lần bấm X
        if self.worker.isRunning():
            if not self._closing:
                self._closing = True
                self.worker.finished.connect(self.close)
                self.tabs.setEnabled(False)
                self.banner.show_warning(
                    self.tr("Finishing the current decode; the window will close right after.")
                )
                if self.worker.isFinished():
                    # Worker kết thúc ngay giữa kiểm tra và connect: `finished` đã phát xong nên
                    # không còn ai gọi close() nữa -> đóng luôn thay vì để cửa sổ khóa một nhịp.
                    return super().closeEvent(event)
            event.ignore()
            return
        super().closeEvent(event)
