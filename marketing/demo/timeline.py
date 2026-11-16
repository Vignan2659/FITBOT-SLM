"""Place the recorded voice lines on the storyboard: writes build/timeline.json and build/voiceover.wav (48 kHz)."""
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np
from script import SCENES, LINE_GAP

VO = Path(sys.argv[1]); BUILD = Path(sys.argv[2]); BUILD.mkdir(parents=True, exist_ok=True)
SR = 48000

def load(p):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    idx = np.where(np.abs(a) > 0.006)[0]
    return a[max(idx[0] - 200, 0): idx[-1] + 1600]

t, track, scenes = 0.0, [], []
for sid, design, lead, lines, tail in SCENES:
    start = t; cur = t + lead; out = []
    for i, (cap, _) in enumerate(lines):
        a = load(VO / f"{sid}_{i}.wav")
        out.append({"text": cap, "start": round(cur, 3), "end": round(cur + len(a) / SR, 3)})
        track.append((cur, a)); cur += len(a) / SR + LINE_GAP
    end = cur - LINE_GAP + tail
    scenes.append({"id": sid, "start": round(start, 3), "end": round(end, 3), "design": design, "lines": out}); t = end
    print(f"{sid:8s} {start:6.2f} -> {end:6.2f}  ({end - start:5.2f}s for a {design}s animation)")
mix = np.zeros(int(t * SR) + SR, np.float32)
for st, a in track:
    i = int(st * SR); mix[i:i + len(a)] += a
mix = mix / (np.abs(mix).max() or 1) * 0.89
with wave.open(str(BUILD / "voiceover.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
(BUILD / "timeline.json").write_text(json.dumps({"duration": round(t, 3), "scenes": scenes}, indent=1))
print("total", round(t, 2))
