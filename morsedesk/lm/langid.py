"""Nhận diện ngôn ngữ theo đoạn: so điểm LM chuẩn hóa của giả thuyết beam tốt nhất giữa các profile."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from morsedesk.lm.beam import BeamParams, Hypothesis, beam_search
from morsedesk.lm.ngram import CharNGramLM
from morsedesk.lm.profile import Profile
from morsedesk.model.vocab import VOCAB

SILENCE_FRAMES = 300   # 3 s ở 100 khung đầu ra/s
MAX_FRAMES = 3000      # 30 s
MIN_MARGIN = 0.15      # nat/ký tự


@dataclass
class Segment:
    start: int
    end: int
    profile_id: str | None
    scores: dict[str, float]
    n_chars: int
    best: dict[str, Hypothesis] = field(default_factory=dict)


@dataclass
class LangIdResult:
    profile_id: str
    scores: dict[str, float]
    segments: list[Segment]


def split_segments(log_probs: np.ndarray, silence_frames: int = SILENCE_FRAMES,
                   max_frames: int = MAX_FRAMES, blank_id: int = VOCAB.blank_id) -> list[tuple[int, int]]:
    n = int(log_probs.shape[0])
    if n == 0:
        return []
    is_blank = log_probs.argmax(axis=1) == blank_id
    cuts: list[int] = []
    run_start = None
    for t in range(n + 1):
        blank = t < n and bool(is_blank[t])
        if blank and run_start is None:
            run_start = t
        elif not blank and run_start is not None:
            if t - run_start >= silence_frames and run_start > 0 and t < n:
                cuts.append((run_start + t) // 2)
            run_start = None
    bounds = [0, *cuts, n]
    segments: list[tuple[int, int]] = []
    for s, e in zip(bounds[:-1], bounds[1:], strict=True):
        parts = max(1, -(-(e - s) // max_frames))
        edges = np.linspace(s, e, parts + 1).astype(int)
        segments += [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:], strict=True) if b > a]
    return segments


def detect(log_probs: np.ndarray, profiles: dict[str, Profile], lms: dict[str, CharNGramLM],
           params: BeamParams | None = None, min_margin: float = MIN_MARGIN,
           silence_frames: int = SILENCE_FRAMES, max_frames: int = MAX_FRAMES) -> LangIdResult:
    params = params or BeamParams()
    segments: list[Segment] = []
    prev: str | None = None
    for s, e in split_segments(log_probs, silence_frames, max_frames, params.blank_id):
        best = {pid: beam_search(log_probs[s:e], prof, lms[pid], params)[0] for pid, prof in profiles.items()}
        scores = {pid: h.lm_logp / h.n_chars for pid, h in best.items() if h.n_chars > 0}
        if not scores:
            segments.append(Segment(s, e, None, {}, 0, best))
            continue
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        chosen = ranked[0][0]
        margin = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else float("inf")
        if margin < min_margin and prev is not None:
            chosen = prev
        segments.append(Segment(s, e, chosen, scores, best[chosen].n_chars, best))
        prev = chosen
    votes: dict[str, int] = defaultdict(int)
    weighted: dict[str, float] = defaultdict(float)
    weight_total = 0
    for seg in segments:
        if seg.profile_id is None:
            continue
        votes[seg.profile_id] += seg.n_chars
        weight_total += seg.n_chars
        for pid, sc in seg.scores.items():
            weighted[pid] += sc * seg.n_chars
    if not votes:
        return LangIdResult(next(iter(profiles)), {}, segments)
    file_pid = max(votes.items(), key=lambda kv: kv[1])[0]
    scores = {pid: weighted[pid] / weight_total for pid in profiles if pid in weighted}
    return LangIdResult(file_pid, scores, segments)
