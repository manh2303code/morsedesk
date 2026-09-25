"""Cửa sổ chính: thanh công cụ (ngôn ngữ giao diện), các tab chức năng + Giới thiệu, đổi QTranslator."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QSize, QTranslator
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from morsedesk.app.about_page import AboutPage
from morsedesk.app.branding import app_icon
from morsedesk.app.decode_page import DecodePage
from morsedesk.app.doc_window import TechDocWindow
from morsedesk.app.encode_page import EncodePage
from morsedesk.app.live_page import LivePage
from morsedesk.app.settings import UI_LANGUAGES, AppSettings
from morsedesk.app.settings_page import SettingsPage
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.flags import LanguageBar
from morsedesk.app.worker import DecoderWorker, Player

# Tên hiển thị ngôn ngữ giao diện, viết bằng chính ngôn ngữ đó. KHÔNG gắn nhãn "bản nháp" cho bản
# nào: tác giả là người Kazakh, và một ghi chú quy trình nội bộ (soát bản dịch, CP-12) không phải
# việc của người dùng cuối — nó chỉ làm họ mất tin vào đúng ngôn ngữ của mình.
LANGUAGE_NAMES = {"en": "English", "ru": "Русский", "kk": "Қазақша"}


class MainWindow(QMainWindow):
    """Cửa sổ chính: chọn ngôn ngữ giao diện trên toolbar, tab Giải mã (Task 4) và Tạo mã (Task 5)."""

    def __init__(
        self, worker: DecoderWorker, player: Player, settings: AppSettings, i18n_dir: Path,
        parent=None, live=None
    ) -> None:
        super().__init__(parent)
        self.worker = worker
        self.player = player
        self.settings = settings
        self.i18n_dir = Path(i18n_dir)
        self.current_language = "en"
        self._translator: QTranslator | None = None
        self._closing = False   # đã hoãn một lần đóng để chờ worker chạy xong chưa
        self.doc_window: TechDocWindow | None = None
        self.resize(1000, 700)
        self.setWindowIcon(app_icon())

        bar = QToolBar(self)
        bar.setMovable(False)
        self.addToolBar(bar)
        # Nhận diện ngay trong cửa sổ: logo + tên bên trái, ngôn ngữ giao diện bên phải.
        self.brand_logo = QLabel(self)
        self.brand_logo.setPixmap(app_icon().pixmap(QSize(24, 24)))
        self.brand_name = QLabel("MorseDesk", self)
        self.brand_name.setStyleSheet("font-size: 12pt; font-weight: 700; padding-left: 4px;")
        bar.addWidget(self.brand_logo)
        bar.addWidget(self.brand_name)
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)
        self.language_label = QLabel(self)
        self.language_label.setProperty("role", "caption")
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
        # Tab Nghe chỉ có khi bên gọi cấp một LiveWorker: test dựng cửa sổ trần không phải trả
        # giá mở thêm một luồng và một Decoder nữa.
        self.live = live
        self.live_page = LivePage(live, self) if live is not None else None
        self.tabs.addTab(self.decode_page, "")
        if self.live_page is not None:
            self.tabs.addTab(self.live_page, "")
        self.tabs.addTab(self.encode_page, "")
        self.tabs.addTab(self.settings_page, "")
        self.about_page = AboutPage(self)
        self.about_page.open_docs_requested.connect(self.open_docs)
        self.tabs.addTab(self.about_page, "")
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
        app.setProperty("ui_language", code)     # số trong tooltip theo ngôn ngữ (word_view.fmt_number)
        self.settings.ui_language = code
        self.language_bar.set_current(code)
        self.about_page.set_language(code)
        self.decode_page.load_sample(code)       # "Xin chào" bằng chính ngôn ngữ vừa chọn
        if self.doc_window is not None:
            self.doc_window.set_language(code)
        self.retranslate()
        return ok

    def open_docs(self) -> TechDocWindow:
        """Tài liệu kỹ thuật đúng ngôn ngữ giao diện hiện tại; mở lại thì đưa cửa sổ cũ lên trước."""
        if self.doc_window is None:
            self.doc_window = TechDocWindow(self.current_language, self)
        elif self.doc_window.language != self.current_language:
            self.doc_window.set_language(self.current_language)
        self.doc_window.show()
        self.doc_window.raise_()
        self.doc_window.activateWindow()
        return self.doc_window

    def retranslate(self) -> None:
        self.setWindowTitle(self.tr("MorseDesk"))
        self.language_label.setText(self.tr("UI language:"))
        self.language_bar.set_names(LANGUAGE_NAMES)
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            if page is self.decode_page:
                self.tabs.setTabText(i, self.tr("Decode"))
            elif page is self.live_page:
                self.tabs.setTabText(i, self.tr("Listen"))
            elif page is self.encode_page:
                self.tabs.setTabText(i, self.tr("Encode"))
            elif page is self.about_page:
                self.tabs.setTabText(i, self.tr("About"))
            else:
                self.tabs.setTabText(i, self.tr("Settings"))
        self.decode_page.retranslate()
        self.encode_page.retranslate()
        self.settings_page.retranslate()
        self.about_page.retranslate()
        if self.doc_window is not None:
            self.doc_window.retranslate()
        if self.live_page is not None:
            self.live_page.retranslate()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        """Đóng cửa sổ mà không bao giờ hủy QThread đang chạy.

        Có HAI luồng phải lo: worker giải mã file và worker nghe trực tiếp. Luồng nghe dừng
        được ngay (nó chỉ đang chờ khối audio tiếp theo, tối đa 200 ms), nên xử lý gọn ở đây;
        luồng giải mã có thể đang giữa một file dài nên mới cần cơ chế hoãn đóng bên dưới.

        Worker còn chạy -> xin dừng không chờ rồi chờ ngắn 500 ms. Nếu yêu cầu hiện tại vẫn
        chưa xong (file dài có thể mất vài phút) thì **hoãn đóng**: `event.ignore()`, khóa
        giao diện, hiện banner, và nối `worker.finished` vào `close()` đúng một lần. Khi worker
        kết thúc, `close()` chạy lại, `isRunning()` là False và cửa sổ đóng bình thường.
        """
        if self.live is not None and self.live.isRunning():
            self.live.shutdown()
            self.live.wait(1500)
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
