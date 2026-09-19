"""Sinh ma trận test T1 (seed cố định) và manifest JSONL.

Ô = SNR × WPM × kiểu gõ × kênh. Mặc định chỉ vùng gate (SNR >= 0, WPM 10–35); --full sinh toàn bộ.
Kênh "mp3" cần ffmpeg; nếu thiếu, clip vẫn sinh nhưng channel_actual = "clean".
Kiểu gõ "farnsworth" chỉ có nghĩa khi WPM <= 18; trên đó nó trùng "machine".
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from morsedesk.audio.io import save_audio
from morsedesk.data.channel import ChannelParams, clean
from morsedesk.data.keyer import KeyerParams, machine
from morsedesk.data.synth import SynthConfig, SynthGenerator
from morsedesk.textio import force_utf8_streams
from tools.make_t2_manifest import write_jsonl

SNR_FULL = [-6.0, -3.0, 0.0, 3.0, 6.0, 10.0, 20.0]
WPM_FULL = [5.0, 8.0, 12.0, 18.0, 25.0, 35.0, 45.0, 60.0]
SNR_GATE = [0.0, 3.0, 6.0, 10.0, 20.0]
WPM_GATE = [12.0, 18.0, 25.0, 35.0]
KEYING = ("machine", "farnsworth", "jitter", "bug", "drift")
CHANNELS = ("clean", "qsb", "qrm", "qrn", "mp3")
PROFILES = ("en", "ru", "kk-cyrl-ru")


def keyer_for(name: str, wpm: float) -> KeyerParams:
    if name == "machine":
        return machine(wpm)
    if name == "farnsworth":
        far = max(5.0, wpm / 2.0) if wpm <= 18.0 else None
        return KeyerParams(wpm, far, 3.0, 0.0, False, 0.0, 0.0, "farnsworth")
    if name == "jitter":
        return KeyerParams(wpm, None, 3.0, 0.15, False, 0.0, 0.05, "jitter")
    if name == "bug":
        return KeyerParams(wpm, None, 3.5, 0.10, True, 0.0, 0.0, "bug")
    if name == "drift":
        return KeyerParams(wpm, None, 3.0, 0.05, False, 0.15, 0.0, "drift")
    raise ValueError(f"kiểu gõ lạ: {name}")


def channel_for(name: str, snr_db: float, tone_hz: float) -> ChannelParams:
    base = clean(snr_db, tone_hz, name)
    if name == "clean":
        return base
    if name == "qsb":
        return replace(base, qsb_depth_db=20.0, qsb_period_s=4.0)
    if name == "qrm":
        return replace(base, qrm_offset_hz=300.0, qrm_level_db=6.0, qrm_kind="morse")
    if name == "qrn":
        return replace(base, qrn_rate_per_s=20.0)
    if name == "mp3":
        return replace(base, mp3_kbps=64)
    raise ValueError(f"kênh lạ: {name}")


def build_cells(full: bool) -> list[dict]:
    snrs = SNR_FULL if full else SNR_GATE
    wpms = WPM_FULL if full else WPM_GATE
    return [
        {"snr": s, "wpm": w, "keying": k, "channel": c}
        for s in snrs for w in wpms for k in KEYING for c in CHANNELS
    ]


def generate_matrix(out_dir: Path, full: bool = False, clips: int = 1, seed_base: int = 1000) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gen = SynthGenerator(SynthConfig(min_seconds=5.0, max_seconds=8.0))
    rows: list[dict] = []
    index = 0
    for cell in build_cells(full):
        for i in range(clips):
            seed = seed_base + index
            profile = PROFILES[index % len(PROFILES)]
            tone = 500.0 + (index * 97) % 600
            keyer = keyer_for(cell["keying"], cell["wpm"])
            channel = channel_for(cell["channel"], cell["snr"], tone)
            ex = gen.generate(seed, profile_id=profile, keyer=keyer, channel=channel)
            name = f"{int(cell['snr']):+03d}db_{int(cell['wpm']):02d}wpm_{cell['keying']}_{cell['channel']}_{i}.wav"
            path = out_dir / name
            save_audio(path, ex.audio, ex.sample_rate)
            actual = cell["channel"]
            if actual == "mp3" and ex.channel.mp3_kbps is None:
                actual = "clean"
            rows.append({
                "path": str(path.resolve()), "text": ex.text, "profile": profile,
                "snr": cell["snr"], "wpm": cell["wpm"], "keying": cell["keying"],
                "channel": cell["channel"], "channel_actual": actual, "seed": seed,
            })
            index += 1
    write_jsonl(rows, out_dir / "manifest.jsonl")
    return rows


def main(argv: list[str] | None = None) -> int:
    force_utf8_streams()
    ap = argparse.ArgumentParser(description="Sinh ma trận T1")
    ap.add_argument("--out", type=Path, default=Path("testdata/generated/t1"))
    ap.add_argument("--full", action="store_true", help="toàn bộ SNR/WPM thay vì chỉ vùng gate")
    ap.add_argument("--clips", type=int, default=1, help="số clip mỗi ô")
    a = ap.parse_args(argv)
    rows = generate_matrix(a.out, a.full, a.clips)
    print(f"{len(rows)} clip -> {a.out / 'manifest.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
