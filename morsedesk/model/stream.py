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

import numpy as np

from morsedesk.constants import SAMPLE_RATE

LEFT_CONTEXT_S = 8.0        # quá khứ giữ lại cho BiGRU; 8 s là chỗ số đo hết cải thiện
LOOKAHEAD_S = 1.0           # tương lai phải có trước khi tin phần đuôi; dưới 0,5 s thì sập
CHUNK_S = 0.5               # mỗi lần giải mã lại tiến thêm chừng này


_TIME_EPS = 0.05        # 50 ms: hai lần giải mã không bao giờ đặt mốc trùng nhau đến từng mẫu
PIN_MIN_LETTERS = 50    # khóa ngôn ngữ phiên nghe khi đã chốt ngần này chữ (CP-03: 100 % từ 50)
PIN_MARGIN = 0.15       # ... và ngôn ngữ dẫn đầu hơn ngôn ngữ thứ hai ngần này nat/chữ (= langid.MIN_MARGIN)


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
    """

    committed: str = ""
    tentative: str = ""
    decoded: bool = False       # lần push này có thật sự chạy giải mã không
    audio_s: float = 0.0        # tổng số giây đã nhận
    # Thông số của lần giải mã gần nhất, để trang Nghe hiện đúng những gì trang Giải mã hiện.
    # Không có chúng thì chế độ nghe chỉ là một ô chữ trần, người vận hành không biết máy đang
    # bắt được tone nào, tốc độ bao nhiêu, và có nên tin con chữ trước mắt hay không.
    words: list = field(default_factory=list)   # Word của phần TẠM, kèm độ tin cậy
    wpm: float | None = None
    tone_hz: float | None = None
    snr_db: float | None = None
    language: str = ""

    @property
    def text(self) -> str:
        return self.committed + self.tentative


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

    _buf: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32), init=False)
    _total_frames: int = field(default=0, init=False)       # tổng mẫu đã nhận, kể cả đã bỏ
    _dropped_frames: int = field(default=0, init=False)      # số mẫu đã cắt khỏi đầu buffer
    _since_decode: int = field(default=0, init=False)
    _committed: str = field(default="", init=False)
    _committed_until: float = field(default=0.0, init=False)  # giây tuyệt đối đã chốt tới
    _prev_fresh: list = field(default_factory=list, init=False)   # phần chưa chốt của lần trước
    _tentative: str = field(default="", init=False)
    _wpm: float | None = field(default=None, init=False)
    _tone_hz: float | None = field(default=None, init=False)
    _snr_db: float | None = field(default=None, init=False)
    _language: str = field(default="", init=False)
    _evidence: dict = field(default_factory=dict, init=False)    # pid -> (tổng điểm x chữ, tổng chữ)
    _pinned: str | None = field(default=None, init=False)

    @property
    def committed(self) -> str:
        return self._committed

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
        self._committed = ""
        self._committed_until = 0.0
        self._prev_fresh = []
        self._tentative = ""
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
        up = self._decode(final=True)
        self._committed, self._tentative = up.text.strip(), ""
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
        letters = sum(1 for c in self._committed if not c.isspace())
        if letters < PIN_MIN_LETTERS or len(self._evidence) < 2:
            return
        ranked = sorted(((tot / n, pid) for pid, (tot, n) in self._evidence.items() if n > 0), reverse=True)
        if len(ranked) < 2 or ranked[0][0] - ranked[1][0] < PIN_MARGIN:
            return
        pin = getattr(self.decoder, "pin_language", None)
        if pin is not None and pin(ranked[0][1]):
            self._pinned = ranked[0][1]

    def _snapshot(self, decoded: bool, words=None) -> StreamUpdate:
        return StreamUpdate(self._committed, self._tentative, decoded, self.audio_s,
                            list(words or []), self._wpm, self._tone_hz, self._snr_db,
                            self._language)

    def _decode(self, final: bool = False) -> StreamUpdate:
        if len(self._buf) == 0:
            return self._snapshot(False)
        res = self.decoder.decode_array(self._buf, self.sample_rate)
        self._wpm = getattr(res, "wpm", None)
        self._tone_hz = getattr(res, "tone_hz", None)
        self._snr_db = getattr(res, "snr_db", None)
        self._language = getattr(res, "language", "") or self._language

        # Quy về thời gian TUYỆT ĐỐI của phiên. Buffer chỉ giữ phần đuôi, nên mốc thời gian trong
        # kết quả là tương đối với đầu buffer; cộng số giây đã cắt bỏ mới so được giữa hai lần.
        offset = self._dropped_frames / self.sample_rate
        words = [(w.start_s + offset, w.end_s + offset, w.text) for w in res.words if w.text]

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
            # Chốt ngay, trừ phần nằm trong vùng nhìn trước — chỗ đó còn thiếu tương lai nên
            # mô hình hai chiều chưa quyết được.
            edge = self.audio_s - self.lookahead_s
            stable = [w for w in fresh if w[1] <= edge]
            rest = fresh[len(stable):]

        if stable:
            self._committed = (self._committed + " " if self._committed else "") + \
                " ".join(w[2] for w in stable)
            self._committed_until = stable[-1][1]
            self._maybe_pin_language(getattr(res, "language_scores", None) or {},
                                     sum(1 for w in stable for c in w[2] if not c.isspace()))
        self._tentative = (" " if self._committed and rest else "") + " ".join(w[2] for w in rest)
        # Ghép lại Word cho phần tạm: giao diện cần `confidence` để tô chip theo độ tin cậy.
        by_start = {round(w.start_s + offset, 3): w for w in res.words}
        rest_words = [by_start[k] for k in (round(r[0], 3) for r in rest) if k in by_start]
        return self._snapshot(True, rest_words)
