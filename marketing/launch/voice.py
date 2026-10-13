"""Render the voice-over line by line and build the timeline (scene + line start times) from real durations.

    .venv/bin/python marketing/launch/voice.py [--voice Samantha] [--rate 172]

Writes build/vo/*.wav, build/voiceover.wav and build/timeline.json.
`--voice auto` (default) uses the Kokoro neural voice when marketing/launch/.venv-tts exists, else the best
macOS voice. `--voice` also takes any voice from `say -v '?'` (e.g. "Ava (Premium)" once downloaded in System Settings).
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


KOKORO_PY = HERE / ".venv-tts" / "bin" / "python"


def kokoro_batch(jobs: list[tuple[str, Path]]) -> bool:
    """Render every line with the Kokoro neural voice in one process. False if it is not available / fails."""
    if not KOKORO_PY.exists():
        return False
    spec = BUILD / "vo" / "kokoro_jobs.json"
    spec.write_text(json.dumps([{"text": t, "out": str(o.with_suffix(".k24.wav"))} for t, o in jobs]))
    r = subprocess.run([str(KOKORO_PY), str(HERE / "tts_kokoro.py"), str(spec)])
    return r.returncode == 0 and all(o.with_suffix(".k24.wav").exists() for _, o in jobs)


def tts(text: str, out: Path, voice: str, rate: int) -> np.ndarray:
    k24 = out.with_suffix(".k24.wav")
    if voice == "kokoro" and k24.exists():
        src = k24
    else:
        src = out.with_suffix(".aiff")
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(src), text], check=True)
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(SR), str(out)], check=True)
    src.unlink()
    with wave.open(str(out)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    # trim leading/trailing silence so timings are tight
    idx = np.where(np.abs(a) > 0.004)[0]
    return a[max(idx[0] - 240, 0): idx[-1] + 960] if len(idx) else a


PREFERRED = ["Ava", "Zoe", "Evan", "Nathan", "Joelle", "Noelle", "Tom", "Allison", "Susan", "Samantha"]


def best_voice() -> str:
    """Most natural installed en_US voice: any Premium, then Enhanced, then Samantha."""
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout.splitlines()
    names = [l.split("  ")[0].strip() for l in out if " en_US " in l or "en_US" in l.split("#")[0]]
    for tier in ("(Premium)", "(Enhanced)"):
        tiered = [n for n in names if n.endswith(tier)]
        for pref in PREFERRED:
            if f"{pref} {tier}" in tiered:
                return f"{pref} {tier}"
        if tiered:
            return tiered[0]
    return "Samantha"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="auto")
    ap.add_argument("--rate", type=int, default=172)
    args = ap.parse_args()
    (BUILD / "vo").mkdir(parents=True, exist_ok=True)
    if args.voice in ("auto", "kokoro"):
        jobs = [(spoken or caption, BUILD / "vo" / f"{sid}_{i}.wav")
                for sid, _, lines, _ in SCENES for i, (caption, spoken) in enumerate(lines)]
        args.voice = "kokoro" if kokoro_batch(jobs) else best_voice()
    print("voice:", args.voice)

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
