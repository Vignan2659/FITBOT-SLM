"""Render the voice-over line by line and build the timeline (scene + line start times) from real durations.

    .venv/bin/python marketing/launch/voice.py [--voice Samantha] [--rate 172]

Writes build/vo/*.wav, build/voiceover.wav and build/timeline.json.
`--voice` takes any voice from `say -v '?'` (e.g. "Ava (Premium)" once downloaded in System Settings).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from script import LINE_GAP, SCENES

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
SR = 48000


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def tts(text: str, out: Path, voice: str, rate: int) -> np.ndarray:
    aiff = out.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text], check=True)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(aiff), "-ac", "1", "-ar", str(SR), str(out)], check=True)
    aiff.unlink()
    with wave.open(str(out)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    # trim leading/trailing silence so timings are tight
    idx = np.where(np.abs(a) > 0.004)[0]
    return a[max(idx[0] - 240, 0): idx[-1] + 960] if len(idx) else a


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Samantha")
    ap.add_argument("--rate", type=int, default=172)
    args = ap.parse_args()
    (BUILD / "vo").mkdir(parents=True, exist_ok=True)

    t, track, scenes = 0.0, [], []
    for sid, lead, lines, tail in SCENES:
        start = t
        t += lead
        out_lines = []
        for i, (caption, spoken) in enumerate(lines):
            a = tts(spoken or caption, BUILD / "vo" / f"{sid}_{i}.wav", args.voice, args.rate)
            out_lines.append({"text": caption, "start": round(t, 3), "end": round(t + len(a) / SR, 3)})
            track.append((t, a))
            t += len(a) / SR + (LINE_GAP if i < len(lines) - 1 else 0)
        t += tail
        scenes.append({"id": sid, "start": round(start, 3), "end": round(t, 3), "lines": out_lines})
        print(f"{sid:13s} {start:6.2f} -> {t:6.2f}")

    total = t
    mix = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for st, a in track:
        i = int(st * SR)
        mix[i:i + len(a)] += a
    peak = np.abs(mix).max() or 1
    mix = mix / peak * 0.89
    with wave.open(str(BUILD / "voiceover.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    (BUILD / "timeline.json").write_text(json.dumps({"duration": round(total, 3), "voice": args.voice,
                                                     "scenes": scenes}, indent=1))
    print(f"total {total:.1f} s  voice={args.voice}")


if __name__ == "__main__":
    main()
