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

    @property
    def committed(self) -> str:
        return self._committed

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

    def push(self, block: np.ndarray) -> StreamUpdate:
        """Nhận một khối audio mono. Chỉ giải mã lại khi đã dồn đủ `chunk_s`."""
        b = np.asarray(block, dtype=np.float32).reshape(-1)
        if len(b):
            self._buf = np.concatenate([self._buf, b])
            self._total_frames += len(b)
            self._since_decode += len(b)
        self._trim()
        if self._since_decode < int(self.chunk_s * self.sample_rate):
            return StreamUpdate(self._committed, self._tentative, False, self.audio_s)
        self._since_decode = 0
        return self._decode()

    def flush(self) -> StreamUpdate:
        """Kết thúc phiên: giải mã nốt phần đuôi và chốt tất cả.

        Lúc này không còn tương lai để chờ nên `lookahead` hết ý nghĩa — cái gì đọc được thì chốt.
        """
        self._since_decode = 0
        up = self._decode(final=True)
        self._committed, self._tentative = up.text.strip(), ""
        return StreamUpdate(self._committed, "", True, self.audio_s)

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

    def _decode(self, final: bool = False) -> StreamUpdate:
        if len(self._buf) == 0:
            return StreamUpdate(self._committed, self._tentative, False, self.audio_s)
        res = self.decoder.decode_array(self._buf, self.sample_rate)

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
            self._committed = (self._committed + " " if self._committed else "") +                 " ".join(w[2] for w in stable)
            self._committed_until = stable[-1][1]
        self._tentative = (" " if self._committed and rest else "") + " ".join(w[2] for w in rest)
        return StreamUpdate(self._committed, self._tentative, True, self.audio_s)
