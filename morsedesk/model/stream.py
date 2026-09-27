"""Giải mã theo dòng: đẩy từng khối audio vào, nhận chữ ra ngay, không chờ hết bản tin.

Thiết kế theo số đo trong `.superpowers/sdd/research-realtime-decode.md`, không theo cảm tính:

- **Ngữ cảnh trái 8 giây, nhìn trước 1 giây, khối 0,5 giây.** Đo trên 79,8 phút bản ghi ARRL thật
  cho độ trễ trung bình 1,29 s (chốt ngay) hoặc 1,82 s (LocalAgreement-2), với 0,02 % / 0,00 %
  ký tự phải sửa lại. Nhìn trước dưới 0,5 s mới là chỗ sập (CER 23–59 %).
- **BiGRU hai chiều KHÔNG phải rào cản.** Chạy theo khối với ngữ cảnh trên cho CER 14,9–17,1 % so
  với 20,4 % của đường offline cùng thời điểm — streaming còn *tốt hơn*, không huấn luyện lại gì.
- **Chốt theo ký tự, không theo từ trọn vẹn.** Chốt theo từ hỏng với bản tin ngắn (CER 54–58 %)
  và trên bản ghi dài thì chậm hơn 1,6 s mà không được gì.

**LocalAgreement-2 đã thử và BỊ LOẠI trên dữ liệu của dự án này.** Research đề xuất nó (Liu,
Spanakis, Niehues, Interspeech 2020: *"taking the agreeing prefixes of two consecutive chunks as
stable hypotheses"*), và trên How2 nó chỉ tốn 0,9 điểm WER. Đo trên 40 clip `en` của T1:

| | CER |
|---|---|
| đường file (offline) | 14,21 % |
| **streaming, chốt ngay** | **17,31 %** |
| streaming, LocalAgreement-2 | 38,41 % |

LA-2 làm **mất chữ**, và nới điều kiện khớp không cứu được (300 ms: 36,17 %; bỏ hẳn điều kiện
thời gian, chỉ khớp chữ: 39,48 %) — tức lỗi ở chính ý tưởng, không ở tham số. Nguyên nhân: nó
chờ hai lần giải mã LIÊN TIẾP nói giống nhau, mà bộ giải mã Morse đọc lại toàn bộ cửa sổ mỗi
lần nên ranh giới từ và cả nội dung dao động mạnh hơn hẳn ASR tiếng nói — sự đồng thuận đó
thường không bao giờ tới, và chữ rời khỏi cửa sổ trước khi kịp chốt.

Cờ `local_agreement` giữ lại để ai muốn làm tiếp có điểm bắt đầu, nhưng **mặc định tắt**.

Module thuộc lõi: không import Qt, không động tới thiết bị âm thanh. Bên gọi (GUI, CLI) tự lấy
audio rồi đẩy vào `push()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace as _replace

import numpy as np

from morsedesk.constants import SAMPLE_RATE

LEFT_CONTEXT_S = 8.0        # quá khứ giữ lại cho BiGRU; 8 s là chỗ số đo hết cải thiện
LOOKAHEAD_S = 1.0           # tương lai phải có trước khi tin phần đuôi; dưới 0,5 s thì sập
CHUNK_S = 0.5               # mỗi lần giải mã lại tiến thêm chừng này


_TIME_EPS = 0.05        # 50 ms: hai lần giải mã không bao giờ đặt mốc trùng nhau đến từng mẫu
_MAX_CHAR_JITTER = 0.12  # mốc một chữ xê dịch giữa hai lần giải: đo 27/09 thường 0,01–0,02 s
PIN_MIN_LETTERS = 50    # khóa ngôn ngữ phiên nghe khi đã chốt ngần này chữ (CP-03: 100 % từ 50)
PIN_MARGIN = 0.15       # ... và ngôn ngữ dẫn đầu hơn ngôn ngữ thứ hai ngần này nat/chữ (= langid.MIN_MARGIN)
PIN_FORCE_LETTERS = 150  # quá ngần này chữ mà vẫn chưa đủ chắc (nhóm mã): khóa theo ngôn ngữ dẫn đầu
# "Từ" dài hơn ngần này giây mà chưa kết thúc (dãy số liền, nhóm dính): chốt dần TỪNG CHỮ đã có đủ
# ngữ cảnh phía sau, thay vì chờ cả từ. Bộ đệm chỉ giữ ~9 s, nên chờ cả từ thì phần đầu của một dãy
# 16 chữ số (~19 s ở 20 WPM) rơi khỏi bộ đệm trước khi kịp chốt — đo 26/09: dãy số 8–16 chữ số ở chế
# độ nghe mất 43 % chữ số, chỉ 3 % nhóm đúng.
LONG_WORD_S = 3.0
CONTEXT_WORDS = 60      # số từ gần nhất dùng làm ngữ cảnh "điện số" (morsedesk/numbers.py)


def _agreeing_prefix(prev: list, cur: list) -> list:
    """Dãy từ đầu tiên mà hai lần giải mã liên tiếp nói GIỐNG NHAU (LocalAgreement-2).

    Giống nhau nghĩa là cùng chữ và cùng chỗ trong thời gian; sai lệch mốc dưới `_TIME_EPS` vẫn
    tính là một, vì cửa sổ dịch đi nửa giây thì ranh giới từ cũng nhúc nhích vài chục mili giây.
    """
    out = []
    for a, b in zip(prev, cur, strict=False):
        if a[2] != b[2] or abs(a[0] - b[0]) > _TIME_EPS:
            break
        out.append(b)
    return out


def _with(word, **changes):
    """Bản sao của Word với vài trường đổi (không sửa kết quả của Decoder)."""
    try:
        return _replace(word, **changes)
    except TypeError:                   # bộ giải mã giả trong test trả SimpleNamespace
        from types import SimpleNamespace
        return SimpleNamespace(**{**vars(word), **changes})


def _shift(word, offset: float):
    """Word với mốc thời gian dời thêm `offset` giây (cả mốc từng chữ)."""
    changes = {"start_s": word.start_s + offset, "end_s": word.end_s + offset}
    if getattr(word, "chars", None):
        changes["chars"] = _shift_chars(word, offset)
    return _with(word, **changes)


def _shift_chars(word, offset: float) -> list:
    return [(ch, t + offset) for ch, t in (getattr(word, "chars", None) or [])]


def _part(word, chars: list, end_s: float | None = None):
    """Phần của `word` gồm các chữ `chars` [(chữ, giây)]."""
    return _with(word, text="".join(ch for ch, _ in chars), start_s=chars[0][1],
                 end_s=word.end_s if end_s is None else end_s, chars=list(chars))


def _join(a, b):
    """Nối phần sau `b` vào từ `a` (cùng một từ bị chốt thành nhiều lần)."""
    ca = list(getattr(a, "chars", None) or [])
    cb = list(getattr(b, "chars", None) or [])
    na, nb = max(1, len(ca)), max(1, len(cb))
    conf = float(np.exp((na * np.log(max(a.confidence, 1e-6)) + nb * np.log(max(b.confidence, 1e-6))) / (na + nb)))
    return _with(a, text=a.text + b.text, end_s=b.end_s, confidence=conf, chars=ca + cb)


def _char_spacing(words: list) -> float:
    """Khoảng cách điển hình giữa hai chữ liền nhau trong một từ (giây); 1,0 nếu chưa đo được."""
    gaps = []
    for w in words:
        ts = [t for _, t in (getattr(w, "chars", None) or [])]
        gaps += [b - a for a, b in zip(ts, ts[1:], strict=False) if b > a]
    return float(np.median(gaps)) if gaps else 1.0


def _fresh_cut(words: list, last: float) -> float:
    """Chữ nào của lần giải này là MỚI: mọi chữ có mốc SAU giá trị trả về.

    Chữ cuối đã nhận (mốc `last` ở lần giải trước) là chữ có mốc GẦN `last` nhất, nếu nó lệch không quá
    nửa khoảng cách tới chữ bên cạnh (và không quá `_MAX_CHAR_JITTER`). Không dùng một ngưỡng cố định:
    mốc của chữ dài phát SỚM, nên hai chữ liền nhau có thể chỉ cách nhau 4 dit — `E` cuối từ trước và
    `T` đầu từ sau cách nhau 0,24 s ở 20 WPM, trong khi 40 % khoảng cách chữ trung vị là 0,25 s. Ngưỡng
    đó (trước 27/09) coi `T` là chữ đã nhận: `HAVE TOLD` -> `HAVEOLD`, chế độ nghe văn thật 0,4 -> 6,4 %.
    """
    if not np.isfinite(last):
        return last
    ts = sorted(t for w in words for _, t in (getattr(w, "chars", None) or [(w.text, w.start_s)]))
    if not ts:
        return last
    j = min(range(len(ts)), key=lambda i: abs(ts[i] - last))
    left = ts[j] - ts[j - 1] if j > 0 else np.inf
    right = ts[j + 1] - ts[j] if j + 1 < len(ts) else np.inf
    if abs(ts[j] - last) <= min(_MAX_CHAR_JITTER, 0.5 * min(left, right)):
        return ts[j]
    return last


def longest_common_prefix(a: str, b: str) -> str:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return a[:n]


@dataclass
class StreamUpdate:
    """Kết quả một lần đẩy khối.

    `committed` là phần đã chốt và sẽ KHÔNG bao giờ đổi nữa — giao diện in nó bằng màu thường.
    `tentative` là phần còn có thể bị viết lại — in xám. Người vận hành chép tay theo chữ thường
    thì không bao giờ phải tẩy, đó là lý do hai tầng này tồn tại chứ không phải để cho đẹp.
    `committed_words` / `tentative_words`: cùng nội dung dưới dạng Word (mốc thời gian TUYỆT ĐỐI
    của phiên, độ tin cậy) để giao diện gạch chân từng từ như trang Giải mã.
    """

    committed: str = ""
    tentative: str = ""
    decoded: bool = False       # lần push này có thật sự chạy giải mã không
    audio_s: float = 0.0        # tổng số giây đã nhận
    # Thông số của lần giải mã gần nhất, để trang Nghe hiện đúng những gì trang Giải mã hiện.
    # Không có chúng thì chế độ nghe chỉ là một ô chữ trần, người vận hành không biết máy đang
    # bắt được tone nào, tốc độ bao nhiêu, và có nên tin con chữ trước mắt hay không.
    words: list = field(default_factory=list)   # Word của phần TẠM, kèm độ tin cậy (= tentative_words)
    wpm: float | None = None
    tone_hz: float | None = None
    snr_db: float | None = None
    language: str = ""
    committed_words: list = field(default_factory=list)   # Word của phần ĐÃ CHỐT
    warnings: list = field(default_factory=list)          # mã cảnh báo của lần giải gần nhất (vd key_clicks)

    @property
    def text(self) -> str:
        return self.committed + self.tentative

    @property
    def tentative_words(self) -> list:
        return self.words


@dataclass
class StreamDecoder:
    """Bọc một `Decoder` sẵn có thành bộ giải mã theo dòng.

    Không sao chép logic giải mã: mỗi lần tới hạn thì chạy lại `decoder.decode_array` trên cửa sổ
    trượt. Cách này đắt hơn một bộ giải mã tăng dần thật sự, nhưng research đã đo chi phí là RTF
    0,083 — tức một lõi chạy được mười hai luồng thời gian thực — nên đổi lấy việc *đường live và
    đường file dùng đúng một mã* là lời. Mọi cải thiện chất lượng ở `api.Decoder` tự động có mặt
    ở đây, và không có nguy cơ hai đường trôi khác nhau.
    """

    decoder: object
    sample_rate: int = SAMPLE_RATE
    left_context_s: float = LEFT_CONTEXT_S
    lookahead_s: float = LOOKAHEAD_S
    chunk_s: float = CHUNK_S
    local_agreement: bool = False
    numbers: bool = True        # số viết tắt trong điện số, theo ngữ cảnh CẢ PHIÊN (không chỉ bộ đệm)

    _buf: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32), init=False)
    _total_frames: int = field(default=0, init=False)       # tổng mẫu đã nhận, kể cả đã bỏ
    _dropped_frames: int = field(default=0, init=False)      # số mẫu đã cắt khỏi đầu buffer
    _since_decode: int = field(default=0, init=False)
    _committed_words: list = field(default_factory=list, init=False)
    _committed_until: float = field(default=0.0, init=False)  # giây tuyệt đối đã chốt tới
    _last_char_s: float = field(default=float("-inf"), init=False)  # mốc chữ cuối đã nhận (chốt/chờ)
    _glued: bool = field(default=False, init=False)   # từ tạm đầu tiên nối tiếp từ đã chốt (không cách)
    _prev_fresh: list = field(default_factory=list, init=False)   # phần chưa chốt của lần trước
    # Tự nhận ngôn ngữ, CHƯA khóa: từ đủ "chín" để chốt nhưng còn chờ biết bảng chữ — (Word, ngôn ngữ
    # của lần giải ra nó). Hiện ở dạng tạm, quy về MỘT bảng chữ; khóa xong mới chốt tất cả.
    _pending: list = field(default_factory=list, init=False)
    _tentative_words: list = field(default_factory=list, init=False)
    _wpm: float | None = field(default=None, init=False)
    _tone_hz: float | None = field(default=None, init=False)
    _snr_db: float | None = field(default=None, init=False)
    _language: str = field(default="", init=False)
    _evidence: dict = field(default_factory=dict, init=False)    # pid -> (tổng điểm x chữ, tổng chữ)
    _pinned: str | None = field(default=None, init=False)
    _warnings: list = field(default_factory=list, init=False)

    @property
    def committed(self) -> str:
        return " ".join(w.text for w in self._committed_words)

    @property
    def _committed(self) -> str:
        return self.committed

    @property
    def _tentative(self) -> str:
        text = " ".join(w.text for w in self._tentative_words)
        return (" " + text) if (text and self._committed_words and not self._glued) else text

    @property
    def pinned_language(self) -> str | None:
        """Ngôn ngữ mà phiên nghe đã khóa vào (None khi còn đang tự nhận)."""
        return self._pinned

    @property
    def text(self) -> str:
        return self._committed + self._tentative

    @property
    def audio_s(self) -> float:
        return self._total_frames / self.sample_rate

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        self._total_frames = 0
        self._dropped_frames = 0
        self._since_decode = 0
        self._committed_words = []
        self._committed_until = 0.0
        self._last_char_s = float("-inf")
        self._glued = False
        self._prev_fresh = []
        self._pending = []
        self._tentative_words = []
        self._reset_stats()
        self._evidence = {}
        if self._pinned is not None and hasattr(self.decoder, "pin_language"):
            self.decoder.pin_language(None)
        self._pinned = None

    def push(self, block: np.ndarray) -> StreamUpdate:
        """Nhận một khối audio mono. Chỉ giải mã lại khi đã dồn đủ `chunk_s`."""
        b = np.asarray(block, dtype=np.float32).reshape(-1)
        if len(b):
            self._buf = np.concatenate([self._buf, b])
            self._total_frames += len(b)
            self._since_decode += len(b)
        self._trim()
        if self._since_decode < int(self.chunk_s * self.sample_rate):
            return self._snapshot(False)
        self._since_decode = 0
        return self._decode()

    def _reset_stats(self) -> None:
        self._wpm = self._tone_hz = self._snr_db = None
        self._language = ""

    def flush(self) -> StreamUpdate:
        """Kết thúc phiên: giải mã nốt phần đuôi và chốt tất cả.

        Lúc này không còn tương lai để chờ nên `lookahead` hết ý nghĩa — cái gì đọc được thì chốt.
        """
        self._since_decode = 0
        self._decode(final=True)
        return self._snapshot(True)

    # ---- nội bộ ----
    def _trim(self) -> None:
        """Giữ buffer không dài quá ngữ cảnh trái cộng nhìn trước.

        Phải chặn cứng: một phiên trực kéo dài hàng giờ mà cứ dồn vào mảng thì vừa hết RAM vừa
        chậm dần. Research đo phiên 37 phút với ngữ cảnh trái chặn 8 s vẫn 0,00 % ký tự phải sửa,
        nên cắt bỏ quá khứ xa không làm hỏng gì.
        """
        keep = int((self.left_context_s + self.lookahead_s) * self.sample_rate)
        if len(self._buf) > keep:
            cut = len(self._buf) - keep
            self._buf = self._buf[cut:]
            self._dropped_frames += cut

    def _choosing(self) -> bool:
        """Đang tự nhận ngôn ngữ và CHƯA khóa: chữ chưa được chốt (xem `_pending`)."""
        return (self._pinned is None and hasattr(self.decoder, "pin_language")
                and bool(getattr(self.decoder, "auto", True)))

    def _leader(self) -> str | None:
        ranked = sorted(((tot / n, pid) for pid, (tot, n) in self._evidence.items() if n > 0), reverse=True)
        return ranked[0][1] if ranked else None

    def _profile(self, pid: str):
        profiles = getattr(self.decoder, "_profiles", None) or {}
        if pid in profiles:
            return profiles[pid]
        from morsedesk.lm.profile import load_profile
        try:
            return load_profile(pid)
        except Exception:
            return None

    def _in_alphabet(self, word, src: str, dst: str | None):
        """Word viết lại bằng bảng `dst` (không đổi nếu thiếu thông tin hoặc cùng bảng)."""
        if not dst or not src or src == dst:
            return word
        a, b = self._profile(src), self._profile(dst)
        if a is None or b is None:
            return word
        return _with(word, text=a.retarget(word.text, b))

    def _commit_pending(self, language: str) -> None:
        self._committed_words += [self._in_alphabet(w, src, language) for w, src in self._pending]
        self._pending = []

    def _maybe_pin_language(self, scores: dict, new_letters: int) -> None:
        """Khóa ngôn ngữ khi CẢ PHIÊN đã đủ chắc: đủ `PIN_MIN_LETTERS` chữ đã chốt và ngôn ngữ dẫn
        đầu hơn ngôn ngữ thứ hai `PIN_MARGIN` nat/chữ. Một bản tin thật không đổi ngôn ngữ giữa chừng,
        nên từ đó mọi chữ viết theo đúng một bảng chữ.

        Bằng chứng là điểm LM mỗi chữ (`language_scores`) của từng lần giải mã, trọng số = số chữ
        lần đó MỚI chốt — mỗi đoạn âm thanh góp đúng một lần, như langid chạy trên cả phần đã nghe.
        Luật cũ ("3 lần giải mã liền nhau cùng một ngôn ngữ") chỉ nhìn bộ đệm ~9,5 s (~30 chữ), dưới
        ngưỡng CP-03: đo 24/09 trên 54 bản tin 2 phút, 26/54 phiên khóa NHẦM (chủ yếu Nga/Kazakh bị
        khóa sang Anh giữa chừng), CER 15–47 % so với 3,5–7 % khi biết trước ngôn ngữ."""
        if self._pinned is not None or new_letters <= 0 or len(scores) < 2:
            return
        for pid, sc in scores.items():
            tot, n = self._evidence.get(pid, (0.0, 0))
            self._evidence[pid] = (tot + float(sc) * new_letters, n + new_letters)
        letters = sum(1 for c in self.committed if not c.isspace()) + \
            sum(1 for w, _ in self._pending for c in w.text if not c.isspace())
        if letters < PIN_MIN_LETTERS or len(self._evidence) < 2:
            return
        ranked = sorted(((tot / n, pid) for pid, (tot, n) in self._evidence.items() if n > 0), reverse=True)
        sure = len(ranked) >= 2 and ranked[0][0] - ranked[1][0] >= PIN_MARGIN
        if not sure and letters < PIN_FORCE_LETTERS:
            return
        self._pin(ranked[0][1])

    def _pin(self, language: str) -> None:
        pin = getattr(self.decoder, "pin_language", None)
        if pin is not None and pin(language):
            self._pinned = language
        # Chốt mọi chữ đã chờ, viết bằng đúng bảng chữ vừa khóa — kể cả khi bộ giải mã không nhận
        # khóa (bộ giả trong test): chữ đã chín thì không giữ mãi ở dạng tạm.
        self._commit_pending(language)

    def _snapshot(self, decoded: bool) -> StreamUpdate:
        return StreamUpdate(committed=self.committed, tentative=self._tentative, decoded=decoded,
                            audio_s=self.audio_s, words=list(self._tentative_words), wpm=self._wpm,
                            tone_hz=self._tone_hz, snr_db=self._snr_db, language=self._language,
                            committed_words=list(self._committed_words), warnings=list(self._warnings))

    def _accept(self, parts: list, decoded_in: str, res) -> None:
        """Nhận các phần đã chín: (Word, nối tiếp từ trước?). Chưa khóa ngôn ngữ thì vào `_pending`."""
        if not parts:
            return
        choosing = self._choosing()
        target = self._pending if choosing else None
        for w, cont in parts:
            src = decoded_in
            w = self._numbers_word(w, src)
            if choosing:
                if cont and target:
                    prev, psrc = target[-1]
                    target[-1] = (_join(prev, w), psrc)
                else:
                    target.append((w, src))
            else:
                w = self._in_alphabet(w, src, self._pinned)
                if cont and self._committed_words:
                    self._committed_words[-1] = _join(self._committed_words[-1], w)
                else:
                    self._committed_words.append(w)
            chars = getattr(w, "chars", None) or []
            self._last_char_s = chars[-1][1] if chars else w.start_s
        if choosing:
            self._maybe_pin_language(getattr(res, "language_scores", None) or {},
                                     sum(1 for w, _ in parts for c in w.text if not c.isspace()))

    def _accept_chars(self, words: list, decoded_in: str, res, final: bool) -> list:
        """Chốt ngay mọi từ đã kết thúc trước mép nhìn trước; từ DÀI chưa kết thúc thì chốt dần từng chữ
        đã có đủ tương lai. Trả các từ còn tạm. Chữ đã nhận nhận ra bằng mốc thời gian của chính nó
        (`_fresh_cut`)."""
        cut, spacing = _fresh_cut(words, self._last_char_s), _char_spacing(words)
        edge = self.audio_s - self.lookahead_s
        # Chốt TỪNG CHỮ cần lùi thêm: mô hình hai chiều phát mốc của một chữ SỚM hơn chính chữ đó (đo
        # 27/09: trước điểm bắt đầu ~0,23 độ dài chữ), nên chữ số dài (5 phần tử, ~1,3 s ở 20 WPM) có
        # mốc trước mép mà đuôi vẫn còn ngoài bộ đệm — chốt vội thì 0 (-----) ra Ш (----) hoặc `#`.
        ripe_edge = edge - 2.0 * spacing
        parts, rest = [], []
        self._glued = False
        for w in words:
            chars = list(getattr(w, "chars", None) or []) or [(w.text, w.start_s)]
            fresh = [(ch, t) for ch, t in chars if t > cut]
            if not fresh:
                continue
            cont = len(fresh) < len(chars)
            part = _part(w, fresh)
            if rest:
                rest.append(part)
                continue
            if final or w.end_s <= edge:
                parts.append((part, cont))
                self._last_char_s = fresh[-1][1]
                continue
            # chưa kết thúc: từ dài thì chốt phần đầu đã chín, phần còn lại tạm (nối tiếp, không cách)
            if cont or self.audio_s - w.start_s >= LONG_WORD_S:
                ripe = [(ch, t) for ch, t in fresh if t <= ripe_edge]
                if ripe:
                    parts.append((_part(w, ripe, end_s=ripe[-1][1]), cont))
                    self._last_char_s = ripe[-1][1]
                    left = fresh[len(ripe):]
                    if left:
                        rest.append(_part(w, left))
                        self._glued = True
                    continue
                self._glued = cont
            rest.append(part)
        if parts:
            self._committed_until = parts[-1][0].end_s
        self._accept(parts, decoded_in, res)
        return rest

    def _numbers_word(self, w, language: str):
        """Số viết tắt theo ngữ cảnh CẢ PHIÊN (từ đã chốt + đang chờ + từ này). Chỉ đổi từ MỚI chốt,
        nên chữ đã chốt không bao giờ tự đổi sau đó."""
        if not self.numbers or not w.text:
            return w
        profile = self._profile(language) if language else None
        if profile is None:
            return w
        from morsedesk.numbers import analyze, expand_cut, letters_of

        context = ([letters_of(x.text) for x in self._committed_words[-CONTEXT_WORDS:]]
                   + [letters_of(x.text) for x, _ in self._pending] + [letters_of(w.text)])
        ctx = analyze(context, profile)
        if not ctx.numeric:
            return w
        letters = letters_of(w.text)
        new = expand_cut(letters, profile, ctx)
        if new == letters:
            return w
        chars = list(getattr(w, "chars", None) or [])
        if len(chars) == len(new):
            chars = [(c, t) for c, (_, t) in zip(new, chars, strict=True)]
        return _with(w, text="".join(new), chars=chars)

    def _decode(self, final: bool = False) -> StreamUpdate:
        if len(self._buf) == 0:
            return self._snapshot(False)
        # Sau khi đã cắt phần đầu, bộ đệm bắt đầu GIỮA tín hiệu: báo để mép đầu được đệm như mép trong.
        more = {"continued": True} if self._dropped_frames > 0 else {}
        res = self.decoder.decode_array(self._buf, self.sample_rate, **more)
        self._wpm = getattr(res, "wpm", None)
        self._tone_hz = getattr(res, "tone_hz", None)
        self._snr_db = getattr(res, "snr_db", None)
        decoded_in = getattr(res, "language", "") or self._language
        self._language = decoded_in
        self._warnings = [getattr(w, "code", str(w)) for w in (getattr(res, "warning_codes", None) or [])]

        # Quy về thời gian TUYỆT ĐỐI của phiên. Buffer chỉ giữ phần đuôi, nên mốc thời gian trong
        # kết quả là tương đối với đầu buffer; cộng số giây đã cắt bỏ mới so được giữa hai lần.
        offset = self._dropped_frames / self.sample_rate
        shifted = {}
        for w in res.words:
            if w.text:
                shifted[round(w.start_s + offset, 3)] = _shift(w, offset)
        words = [(w.start_s, w.end_s, w.text) for w in shifted.values()]

        # Chỉ xét phần CHƯA chốt. So khớp theo chuỗi ký tự thì hỏng ngay khi bản tin có từ lặp
        # ("CQ CQ DE"): mối nối tìm nhầm chỗ và chữ bị nhân đôi. Mốc thời gian không có vấn đề đó.
        fresh = [w for w in words if w[0] >= self._committed_until - _TIME_EPS]

        if final:
            stable, rest = fresh, []
        elif self.local_agreement:
            # LocalAgreement-2: chỉ tin phần mà hai lần giải mã LIÊN TIẾP nói giống nhau.
            stable = _agreeing_prefix(self._prev_fresh, fresh)
            rest = fresh[len(stable):]
            # Chỉ giữ lại phần CHƯA chốt: nếu để nguyên cả danh sách thì lần sau `fresh` đã bỏ
            # những từ vừa chốt, hai dãy lệch pha nhau và mọi từ tiếp theo đều bị coi là bất đồng
            # — biểu hiện ra ngoài là văn bản mất chữ.
            self._prev_fresh = rest
        else:
            stable, rest = [], []           # chốt ngay: xem `_accept_chars`

        if self.local_agreement:
            stable_words = [shifted[round(w[0], 3)] for w in stable]
            rest_words = [shifted[round(w[0], 3)] for w in rest]
            if stable_words:
                self._committed_until = stable_words[-1].end_s
                self._accept([(w, False) for w in stable_words], decoded_in, res)
            self._glued = False
        else:
            rest_words = self._accept_chars(list(shifted.values()), decoded_in, res, final)
        if final and self._pending:
            # Hết phiên: khóa theo ngôn ngữ dẫn đầu (hoặc ngôn ngữ vừa giải) rồi chốt tất cả.
            self._pin(self._leader() or decoded_in)
        shown = self._pinned or self._leader() or decoded_in
        if shown:
            self._language = shown
        pending = [self._in_alphabet(w, src, shown) for w, src in self._pending]
        rest = [self._in_alphabet(w, decoded_in, shown) for w in rest_words]
        if self._glued and pending and rest:          # phần còn lại của từ đang chờ: một từ, không cách
            pending[-1] = _join(pending[-1], rest.pop(0))
            self._glued = False
        self._tentative_words = pending + rest
        return self._snapshot(True)
