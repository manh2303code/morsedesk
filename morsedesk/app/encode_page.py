"""Trang Tạo mã: văn bản -> chuỗi chấm gạch, tham số timing/tone/nhiễu, nghe thử, lưu file."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from morsedesk.api import Encoder
from morsedesk.app.settings import AppSettings
from morsedesk.app.theme import mark_primary
from morsedesk.app.widgets.banner import Banner
from morsedesk.app.widgets.charmap import CharMap
from morsedesk.app.widgets.icons import line_icon
from morsedesk.app.widgets.key_anim import KeyAnimation
from morsedesk.app.widgets.morse_tape import MorseTapeView
from morsedesk.app.widgets.player_bar import media_icon
from morsedesk.app.worker import MAX_SECONDS, Player
from morsedesk.audio.io import SUPPORTED_EXT, save_audio
from morsedesk.audio.playback import AudioPlayback, PlaybackError
from morsedesk.constants import SAMPLE_RATE
from morsedesk.encode.detect import detect_profile
from morsedesk.encode.text import normalize
from morsedesk.encode.timeline import Timeline, mark_timeline
from morsedesk.encode.timing import TimingParams, tokens_to_elements, total_seconds
from morsedesk.lm.profile import Profile, load_profile
from morsedesk.model.vocab import SPACE

FORMATS = (("WAV", ".wav"), ("FLAC", ".flac"), ("OGG", ".ogg"))
PROFILES = ("en", "ru", "kk-cyrl-ru")
PAD_S = 0.3         # `Encoder.to_audio` đệm im lặng PAD_S giây ở mỗi đầu (mặc định của lõi)
# Văn bản dài hơn ngần này thì gộp các phím gõ liên tiếp: dựng lại chuỗi Morse, băng và thời lượng
# MỘT lần khi ngừng gõ REFRESH_DELAY_MS. Mỗi lần dựng tỉ lệ với độ dài văn bản (đo 25/09 sau tối ưu:
# 7 ms ở 200 ký tự, 29 ms ở 6 000); văn bản ngắn vẫn cập nhật ngay từng phím.
DEBOUNCE_CHARS = 1500
REFRESH_DELAY_MS = 150
ANIM_MS = 16            # ~60 hình/giây: chấm 20 WPM dài 60 ms, đủ 3–4 hình mỗi chấm
# Đuôi được coi là "đuôi audio biết trước" khi đổi định dạng lưu; đuôi lạ thì nối thêm.
AUDIO_SUFFIXES = frozenset(SUPPORTED_EXT) | {ext for _, ext in FORMATS}
# Mục "Tự động" của combo bảng mã. Việc chọn là TẤT ĐỊNH, không phải đoán: xem
# `morsedesk/encode/detect.py`. Khi nhiều bảng cùng phủ được văn bản, chúng sinh ra đúng cùng
# một chuỗi Morse, nên tín hiệu phát ra không phụ thuộc lựa chọn.
AUTO_PROFILE = "auto"

MAX_MINUTES = int(MAX_SECONDS // 60)    # dùng chung ngưỡng với phía giải mã (spec mục 7: 1 giờ)


def unsupported_chars(text: str, profile: Profile) -> list[str]:
    """Ký tự (sau `normalize`) không phải khoảng trắng/`<`/`>` và không có trong `profile`.

    Trả về duy nhất mỗi ký tự, theo thứ tự xuất hiện lần đầu trong văn bản.
    """
    seen: list[str] = []
    for ch in normalize(text, profile):
        if ch in " <>" or ch in profile.letter_to_pattern or ch in seen:
            continue
        seen.append(ch)
    return seen


class EncodePage(QWidget):
    """Tab Tạo mã: gõ văn bản, xem chuỗi chấm gạch trực tiếp, chỉnh tham số, nghe thử và lưu file."""

    def __init__(self, player: Player, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.player = player
        self.settings = settings
        self._profiles = {pid: load_profile(pid) for pid in PROFILES}
        self._limit_banner = False      # banner đang hiện có phải cảnh báo quá thời lượng không
        self._unsupported: list[str] = []   # ký tự văn bản hiện tại không mã hóa được

        self.text_label = QLabel(self)
        self.text_label.setProperty("role", "section")
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setStyleSheet("QPlainTextEdit { font-size: 14pt; }")
        self.text_edit.setMinimumHeight(110)
        self.charmap = CharMap(self)
        self.morse_label = QLabel(self)
        self.morse_label.setProperty("role", "section")
        # Băng Morse trực quan: dit/dah như đèn tín hiệu, chữ cái dưới từng nhóm — đọc soát dễ
        # hơn nhiều so với dãy `.` và `-` (chuỗi ASCII vẫn giữ bên dưới để sao chép).
        # Trong KHUNG CUỘN: băng trần tự đòi chiều cao = số dòng x 40 px và từng kéo cửa sổ cao 22 624 px
        # với bản tin 6 000 ký tự (xem widgets/morse_tape.py).
        self.tape = MorseTapeView(self)
        self.morse_view = QPlainTextEdit(self)
        self.morse_view.setReadOnly(True)
        # Chuỗi chấm gạch luôn dài gấp năm sáu lần văn bản gốc, nên ô của nó không thể thấp hơn
        # ô nhập nhiều đến thế; và font tỉ lệ làm dấu chấm với gạch khó phân biệt khi đọc soát.
        # Băng Morse ở trên đã là cách đọc chính; ô ASCII chỉ để sao chép nên không cần cao quá 150.
        self.morse_view.setMinimumHeight(80)
        self.morse_view.setMaximumHeight(150)
        morse_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        morse_font.setPointSize(max(12, morse_font.pointSize() + 2))
        # `systemFont` trả đúng họ font nhưng không đặt styleHint, nên nếu họ đó thiếu trên máy
        # đích Qt sẽ thay bằng một font tỉ lệ bất kỳ. Nói rõ ý định để bản thay thế cũng đều nét.
        morse_font.setStyleHint(QFont.StyleHint.Monospace)
        morse_font.setFixedPitch(True)
        self.morse_view.setFont(morse_font)
        self.auto_label = QLabel(self)
        self.auto_label.setProperty("role", "hint")
        self.auto_label.hide()
        self.warn_label = QLabel(self)
        self.warn_label.setStyleSheet(
            "color:#FFD2CC; background:#4E2323; border:1px solid #7A3530; border-radius:6px; padding:5px 8px;")
        self.warn_label.hide()
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.text_label)
        left.addWidget(self.text_edit, 2)
        left.addWidget(self.charmap)
        left.addSpacing(6)
        left.addWidget(self.morse_label)
        left.addWidget(self.tape, 3)
        left.addWidget(self.morse_view)
        left.addWidget(self.auto_label)
        left.addWidget(self.warn_label)

        self.profile_combo = QComboBox(self)
        # Tên ngôn ngữ dịch ra dài hơn tiếng Anh ('Английский' cần 65px so với
        # 'English' 40px): để mặc định combo giữ nguyên bề rộng và cắt mất chữ.
        self.profile_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.profile_combo.addItem(AUTO_PROFILE, AUTO_PROFILE)
        for pid in PROFILES:
            self.profile_combo.addItem(pid, pid)
        self.wpm_spin = QSpinBox(self)
        self.wpm_spin.setRange(5, 60)
        self.wpm_spin.setValue(20)
        self.farnsworth_check = QCheckBox(self)
        self.farnsworth_spin = QSpinBox(self)
        self.farnsworth_spin.setRange(5, 60)
        self.farnsworth_spin.setValue(10)
        self.farnsworth_spin.setEnabled(False)
        self.weight_spin = QDoubleSpinBox(self)
        self.weight_spin.setRange(2.0, 4.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(3.0)
        self.tone_spin = QSpinBox(self)
        self.tone_spin.setRange(300, 1500)
        self.tone_spin.setValue(700)
        self.snr_check = QCheckBox(self)
        self.snr_spin = QSpinBox(self)
        self.snr_spin.setRange(-10, 30)
        self.snr_spin.setValue(10)
        self.snr_spin.setEnabled(False)
        self.format_combo = QComboBox(self)
        for name, ext in FORMATS:
            self.format_combo.addItem(name, ext)
        self.form_labels = [QLabel(self) for _ in range(7)]
        rows = (
            self.profile_combo,
            self.wpm_spin,
            self._pair(self.farnsworth_check, self.farnsworth_spin),
            self.weight_spin,
            self.tone_spin,
            self._pair(self.snr_check, self.snr_spin),
            self.format_combo,
        )
        # Bốn nhóm thông số, mỗi nhóm một tiêu đề nhỏ: Bảng mã | Nhịp | Âm thanh | File.
        self.section_labels = [QLabel(self) for _ in range(4)]
        groups = ((0,), (1, 2, 3), (4, 5), (6,))
        panel = QFrame(self)
        panel.setProperty("panel", True)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 14, 16, 16)
        pl.setSpacing(6)
        self.forms: list[QFormLayout] = []
        for caption, idx in zip(self.section_labels, groups, strict=True):
            caption.setProperty("role", "caption")
            form = QFormLayout()
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(8)
            for i in idx:
                form.addRow(self.form_labels[i], rows[i])
            if self.forms:
                pl.addSpacing(8)
            pl.addWidget(caption)
            pl.addLayout(form)
            self.forms.append(form)
        self.form = self.forms[1]
        self.length_label = QLabel(self)
        self.length_label.setProperty("role", "hint")
        self.play_button = QPushButton(self)
        mark_primary(self.play_button)
        self.play_button.setIcon(media_icon("play", 14))     # cùng biểu tượng ▶ với thanh phát
        self.stop_button = QPushButton(self)
        self.stop_button.setIcon(line_icon("stop", 16))
        self.save_button = QPushButton(self)
        self.save_button.setIcon(line_icon("export", 16))
        buttons = QHBoxLayout()
        buttons.addWidget(self.play_button, 2)
        buttons.addWidget(self.stop_button, 1)
        buttons.addWidget(self.save_button, 1)
        pl.addSpacing(10)
        pl.addWidget(self.length_label)
        pl.addLayout(buttons)
        # Phím Morse động (giống logo) ở chỗ trống dưới cụm nút, nhấn theo tiếng khi Nghe thử.
        self.key_anim = KeyAnimation(self)
        right = QVBoxLayout()
        right.addWidget(panel)
        right.addSpacing(12)
        right.addWidget(self.key_anim, 1)

        self.banner = Banner(self)
        body = QHBoxLayout()
        body.setSpacing(18)
        body.addLayout(left, 3)
        body.addLayout(right, 2)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.addWidget(self.banner)
        lay.addLayout(body, 1)

        # Nghe thử có theo dõi vị trí ĐANG RA LOA (audio.playback): chữ trên băng và phím động chạy
        # đúng theo tiếng. `Player` cũ (sd.play) không biết đang phát tới đâu.
        self.playback = AudioPlayback()
        self._timeline: Timeline | None = None
        self._letters: list[tuple[str, str]] = []       # (chữ, mẫu) theo thứ tự ô trên băng
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(ANIM_MS)
        self._anim_timer.timeout.connect(self._tick_playback)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(REFRESH_DELAY_MS)
        self._refresh_timer.timeout.connect(self.refresh_morse)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.profile_combo.currentIndexChanged.connect(self._on_profile)
        self.charmap.char_clicked.connect(self._insert_char)
        self.farnsworth_check.toggled.connect(self.farnsworth_spin.setEnabled)
        # Ngưỡng 20 phút phụ thuộc cả tham số timing, không chỉ văn bản: nâng WPM theo đúng lời
        # khuyên trong banner phải bật lại nút ngay, không đợi gõ thêm ký tự.
        for w in (self.wpm_spin, self.farnsworth_spin, self.weight_spin):
            w.valueChanged.connect(self.refresh_morse)
        self.farnsworth_check.toggled.connect(self.refresh_morse)
        self.snr_check.toggled.connect(self.snr_spin.setEnabled)
        self.play_button.clicked.connect(self.play)
        self.stop_button.clicked.connect(self.stop)
        self.save_button.clicked.connect(self._save_dialog)
        self._on_profile()
        self.retranslate()

    @staticmethod
    def _pair(check: QCheckBox, spin: QSpinBox) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(check)
        lay.addWidget(spin, 1)
        return w

    # ---- trạng thái ----
    def current_profile_id(self) -> str:
        """Lựa chọn trong combo, có thể là `AUTO_PROFILE`."""
        return str(self.profile_combo.currentData())

    def effective_profile_id(self) -> str:
        """Bảng mã thật sự dùng: chọn tay nếu có, ngược lại suy từ văn bản đang gõ.

        Văn bản rỗng hoặc trộn hệ chữ thì `detect_profile` trả None; khi đó giữ `en` để giao
        diện vẫn dựng được chuỗi Morse cho phần hợp lệ, còn phần không hợp lệ đã có cảnh báo
        ký tự riêng lo.
        """
        chosen = self.current_profile_id()
        if chosen != AUTO_PROFILE:
            return chosen
        return detect_profile(self.current_text()) or "en"

    def current_text(self) -> str:
        return self.text_edit.toPlainText()

    def _encoder(self) -> Encoder:
        return Encoder(self._profiles[self.effective_profile_id()])

    def _on_profile(self) -> None:
        self.refresh_morse()

    def _show_auto_choice(self, pid: str) -> None:
        """Nói rõ bảng nào đang được dùng khi combo để ở Tự động.

        Im lặng tự đổi bảng là kiểu tự động tệ nhất: người vận hành không biết bản tin sắp phát
        đi được mã theo bảng nào.
        """
        if self.current_profile_id() != AUTO_PROFILE or not self.current_text().strip():
            self.auto_label.setText("")
            self.auto_label.hide()
            return
        names = {"en": self.tr("English"), "ru": self.tr("Russian"), "kk-cyrl-ru": self.tr("Kazakh")}
        self.auto_label.setText(
            self.tr("Detected alphabet: {name}").format(name=names.get(pid, pid))
        )
        self.auto_label.show()

    def _insert_char(self, ch: str) -> None:
        self.text_edit.insertPlainText(ch)
        self.text_edit.setFocus()

    def _on_text_changed(self) -> None:
        """Văn bản ngắn: cập nhật ngay. Dài: khóa Nghe thử/Lưu NGAY (chuỗi Morse đang hiện đã cũ —
        không được phát bản tin chưa cập nhật) rồi gộp các phím gõ, dựng lại khi ngừng gõ."""
        if len(self.text_edit.document().toRawText()) <= DEBOUNCE_CHARS:
            self._refresh_timer.stop()
            self.refresh_morse()
            return
        self.play_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self._refresh_timer.start()

    def flush_refresh(self) -> None:
        """Dựng lại NGAY nếu còn lần cập nhật đang chờ (trước khi phát hoặc lưu)."""
        if self._refresh_timer.isActive():
            self._refresh_timer.stop()
            self.refresh_morse()

    def refresh_morse(self) -> None:
        """Cập nhật chuỗi chấm gạch và cảnh báo ký tự không hỗ trợ mỗi khi văn bản đổi.

        Tính MỘT lượt: nhận bảng chữ, dựng token, ước lượng thời lượng — trước 25/09 mỗi phím gõ làm
        việc đó 3–4 lần (effective_profile_id -> detect_profile trên cả văn bản ở mỗi lần gọi
        `_encoder()`/`estimate_seconds()`), cộng vẽ lại toàn bộ băng: 60–300 ms mỗi phím.
        """
        pid = self.effective_profile_id()
        profile = self._profiles[pid]
        text = self.current_text()
        if self._timeline is not None:
            self._end_animation()       # văn bản đổi giữa lúc phát: băng không còn khớp tiếng
        self.charmap.set_profile(pid)
        self._show_auto_choice(pid)
        tokens = Encoder(profile).to_tokens(text, strict=False) if text.strip() else []
        morse = " ".join("/" if t == SPACE else t for t in tokens)
        if self.morse_view.toPlainText() != morse:
            self.morse_view.setPlainText(morse)
        cursor = self.text_edit.textCursor()
        self.tape.set_words(self._tape_words(text, profile) if morse else [],
                            follow_end=cursor.atEnd())
        seconds = self._seconds_for(tokens)
        self._show_length_seconds(seconds if morse else None)
        bad = unsupported_chars(text, profile)
        self._unsupported = list(bad)
        if bad:
            # Đỏ chứ không vàng, và chặn hẳn Nghe thử/Lưu: phát đi một bản tin đã bị cắt mất chữ
            # nguy hiểm hơn nhiều so với việc phải sửa văn bản trước.
            self.warn_label.setText(
                self.tr("Cannot encode {chars} — fix the text or switch alphabet before sending.").format(chars=", ".join(bad))
            )
            self.warn_label.show()
        else:
            self.warn_label.setText("")
            self.warn_label.hide()
        has = bool(morse)
        over = has and self._over_limit(seconds or 0.0) is not None
        ready = has and not over and not bad
        self.play_button.setEnabled(ready)
        self.save_button.setEnabled(ready)

    @staticmethod
    def _tape_words(text: str, profile: Profile) -> list[list[tuple[str, str]]]:
        """Từng từ của văn bản thành cặp (chữ, mẫu) cho băng Morse; prosign `<AR>` là một nhóm."""
        words = []
        for w in normalize(text, profile).split():
            pairs, i = [], 0
            while i < len(w):
                j = w.find(">", i) if w[i] == "<" else -1
                if j > i and w[i:j + 1] in profile.prosign_to_pattern:
                    pairs.append((w[i:j + 1], profile.prosign_to_pattern[w[i:j + 1]]))
                    i = j + 1
                    continue
                pairs.append((w[i], profile.letter_to_pattern.get(w[i], "")))
                i += 1
            words.append(pairs)
        return words

    def _seconds_for(self, tokens: list[str]) -> float | None:
        """Thời lượng audio (giây) của `tokens` với timing hiện tại; None nếu timing không hợp lệ."""
        if not tokens:
            return 0.0
        try:
            return total_seconds(tokens_to_elements(tokens, self.timing_params())) + 2 * PAD_S
        except ValueError:
            return None

    def _show_length_seconds(self, seconds: float | None) -> None:
        if not seconds:
            self.length_label.setText("")
            return
        m, sec = divmod(int(round(seconds)), 60)
        self.length_label.setText(self.tr("Length ≈ {t}").format(t=f"{m}:{sec:02d}"))

    def _show_length(self, has_text: bool) -> None:
        """Như trước (bên gọi ngoài): tự tính thời lượng từ văn bản hiện tại."""
        try:
            seconds = self.estimate_seconds() if has_text else None
        except ValueError:
            seconds = None
        self._show_length_seconds(seconds)

    def _over_limit_seconds(self) -> float | None:
        """Thời lượng ước tính nếu vượt `MAX_SECONDS` (và hiện banner), ngược lại `None`.

        Tham số timing không hợp lệ (vd. Farnsworth > WPM) thì không ước lượng được: coi như
        không vượt ngưỡng và để lỗi nổi lên khi bấm Nghe thử/Lưu (`_audio_or_error`).
        """
        try:
            seconds = self.estimate_seconds()
        except ValueError:
            seconds = 0.0
        return self._over_limit(seconds)

    def _over_limit(self, seconds: float) -> float | None:
        """Banner + trả `seconds` nếu vượt `MAX_SECONDS`, ngược lại xóa banner cũ và trả None."""
        if seconds > MAX_SECONDS:
            # Chuỗi tr() phải nằm trọn một dòng: tools/build_i18n.py trích bằng regex một dòng.
            self.banner.show_warning(
                self.tr("Estimated audio is {minutes} min long; the limit is {limit} min. Shorten the text or raise the speed.").format(minutes=f"{seconds / 60:.1f}", limit=MAX_MINUTES)
            )
            self._limit_banner = True
            return seconds
        if self._limit_banner:
            self.banner.clear()
            self._limit_banner = False
        return None

    # ---- âm thanh ----
    def timing_params(self) -> TimingParams:
        """Tham số timing hiện tại; ném `ValueError` nếu tổ hợp không hợp lệ (Farnsworth > WPM)."""
        return TimingParams(
            float(self.wpm_spin.value()),
            float(self.farnsworth_spin.value()) if self.farnsworth_check.isChecked() else None,
            float(self.weight_spin.value()),
        )

    def estimate_seconds(self) -> float:
        """Thời lượng audio ước tính (giây) mà KHÔNG dựng audio.

        Dùng đúng `tokens_to_elements`/`total_seconds` của lõi nên khớp `build_audio()`, cộng
        `2 * PAD_S` cho phần đệm im lặng hai đầu. Nhờ vậy văn bản 100 000 ký tự được chặn
        trước khi cấp phát mảng nhiều GB.
        """
        text = self.current_text()
        if not text.strip():
            return 0.0
        tokens = self._encoder().to_tokens(text, strict=False)
        if not tokens:
            return 0.0
        return total_seconds(tokens_to_elements(tokens, self.timing_params())) + 2 * PAD_S

    def build_audio(self) -> np.ndarray:
        return self._encoder().to_audio(
            self.current_text(),
            wpm=float(self.wpm_spin.value()),
            farnsworth_wpm=(
                float(self.farnsworth_spin.value()) if self.farnsworth_check.isChecked() else None
            ),
            weight=float(self.weight_spin.value()),
            tone_hz=float(self.tone_spin.value()),
            sample_rate=SAMPLE_RATE,
            snr_db=float(self.snr_spin.value()) if self.snr_check.isChecked() else None,
            seed=0,
            strict=False,
        )

    def audio_or_error(self) -> np.ndarray | None:
        """Chỗ dựng audio dùng chung cho Nghe thử và Lưu: lỗi -> banner đỏ qua tr(), trả `None`.

        Trước đây Lưu hiện banner còn Nghe thử nuốt ngoại lệ nên bấm không thấy gì xảy ra.

        Ngưỡng 20 phút được kiểm lại ngay tại đây chứ không chỉ dựa vào việc nút bị vô hiệu:
        nút tắt chỉ là chỉ dẫn giao diện, còn `play()`/`save_to()` là API công khai của trang
        (test và mã tương lai gọi thẳng). Thiếu chốt này, một lần gọi trực tiếp vẫn cấp phát
        mảng nhiều GB.
        """
        if self._over_limit_seconds() is not None:
            return None          # banner cảnh báo đã do _over_limit_seconds hiện
        # Chốt thứ hai cho ký tự ngoài bảng, cùng lý do như ngưỡng thời lượng: `play()` và
        # `save_to()` là API công khai, nút bị vô hiệu chỉ là chỉ dẫn giao diện.
        if self._unsupported:
            self.banner.show_error(
                self.tr("Cannot encode {chars} — fix the text or switch alphabet before sending.").format(chars=", ".join(self._unsupported))
            )
            return None
        try:
            return self.build_audio()
        except ValueError as e:          # TimingParams: Farnsworth > WPM, weight/wpm ngoài miền
            self.banner.show_error(self.tr("Invalid timing settings: the Farnsworth speed must not exceed the speed in WPM."))
            self.banner.setToolTip(str(e))
        except Exception as e:           # lỗi lạ khi dựng audio (vd. hết bộ nhớ)
            self.banner.show_error(self.tr("Could not build the audio."))
            self.banner.setToolTip(str(e))
        return None

    def play(self) -> None:
        self.flush_refresh()
        self.banner.clear()
        self._limit_banner = False
        x = self.audio_or_error()
        if x is None:
            return
        timeline = self._build_timeline()
        try:
            self.playback.load(x, SAMPLE_RATE)
            self.playback.play()
        except PlaybackError as e:
            self._end_animation()
            self.banner.show_warning(f"cannot play audio: {e}")
            return
        self._timeline = timeline
        self._anim_timer.start()
        self._tick_playback()

    def stop(self) -> None:
        self.playback.stop()
        self._end_animation()

    # ---- hiệu ứng theo tiếng ----
    def _build_timeline(self) -> Timeline | None:
        """Dòng thời gian khớp âm thanh vừa dựng; None nếu không ghép được với các ô trên băng."""
        text = self.current_text()
        profile = self._profiles[self.effective_profile_id()]
        tokens = Encoder(profile).to_tokens(text, strict=False)
        self._letters = [pair for word in self.tape.words() for pair in word]
        # Băng và âm thanh phải cùng một dãy mẫu (thứ tự ô = thứ tự chữ phát): khác thì thà không tô.
        if [t for t in tokens if t != SPACE] != [pat for _ch, pat in self._letters]:
            return None
        try:
            return Timeline(mark_timeline(tokens, self.timing_params(), offset_s=PAD_S))
        except ValueError:
            return None

    def _tick_playback(self) -> None:
        if not self.playback.playing:
            self._end_animation()
            return
        if self._timeline is None:
            self.key_anim.set_state(True)
            return
        m = self._timeline.at(self.playback.position_s)
        if m.letter is None:
            self.tape.set_active(None)
            self.key_anim.set_state(True)
            return
        self.tape.set_active(m.letter, m.element, m.on)
        ch, pat = self._letters[m.letter]
        self.key_anim.set_state(True, m.on, m.symbol, ch, pat, m.element)

    def _end_animation(self) -> None:
        self._anim_timer.stop()
        self._timeline = None
        self.tape.set_active(None)
        self.key_anim.set_state(False)

    def _save_dialog(self) -> None:
        ext = str(self.format_combo.currentData())
        suggested = str(Path(self.settings.last_dir) / f"morse{ext}")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Save audio"), suggested, self.tr("Audio ({ext})").format(ext=f"*{ext}")
        )
        if path:
            self.save_to(Path(path))

    def format_path(self, path: Path) -> Path:
        """Đặt đuôi theo định dạng đang chọn.

        Chỉ **thay** đuôi khi đuôi hiện tại nằm trong `AUDIO_SUFFIXES`; ngược lại **nối thêm**.
        `Path.with_suffix` cắt phần sau dấu chấm cuối nên "toc do 1.5 wpm" từng thành
        "toc do 1.wav" — đè một file khác mà hộp thoại chưa hề hỏi.
        """
        path = Path(path)
        ext = str(self.format_combo.currentData())
        if path.suffix.lower() == ext:
            return path
        return path.with_suffix(ext) if path.suffix.lower() in AUDIO_SUFFIXES else path.with_name(path.name + ext)

    def save_to(self, path: Path) -> None:
        self.flush_refresh()
        path = self.format_path(path)
        x = self.audio_or_error()
        if x is None:
            return
        try:
            save_audio(path, x, SAMPLE_RATE)
        except Exception as e:  # soundfile báo lỗi định dạng/quyền ghi
            self.banner.show_error(self.tr("Cannot write {path}: {detail}").format(path=path.name, detail=getattr(e, "strerror", None) or e))
            self.banner.setToolTip(str(e))
            return
        self.settings.last_dir = str(path.parent)
        self.banner.clear()
        self._limit_banner = False

    # ---- i18n ----
    def retranslate(self) -> None:
        self.text_label.setText(self.tr("Text to encode"))
        self.morse_label.setText(self.tr("Morse code:"))
        self.tape.placeholder = self.tr("The message appears here as signal-lamp marks.")
        for label, text in zip(self.section_labels, (self.tr("Alphabet"), self.tr("Timing"),
                                                     self.tr("Sound"), self.tr("File")), strict=True):
            label.setText(text)
        self.text_edit.setPlaceholderText(self.tr("Type text to see its Morse code."))
        names = {AUTO_PROFILE: self.tr("Auto"), "en": self.tr("English"),
                 "ru": self.tr("Russian"), "kk-cyrl-ru": self.tr("Kazakh")}
        for i in range(self.profile_combo.count()):
            self.profile_combo.setItemText(i, names[self.profile_combo.itemData(i)])
        self._show_auto_choice(self.effective_profile_id())
        for label, text in zip(
            self.form_labels,
            (
                self.tr("Profile:"),
                self.tr("Speed (WPM):"),
                self.tr("Farnsworth (WPM):"),
                self.tr("Weight:"),
                self.tr("Tone (Hz):"),
                self.tr("Add noise, SNR (dB):"),
                self.tr("Format:"),
            ),
            strict=True,
        ):
            label.setText(text)
        self.play_button.setText(self.tr("Play"))
        tip = self.tr("The key presses in time with the sound when you press Play.")
        self.key_anim.setToolTip(tip)
        self.key_anim.setAccessibleName(tip)
        self.stop_button.setText(self.tr("Stop"))
        self.save_button.setText(self.tr("Save…"))
        self.refresh_morse()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)
