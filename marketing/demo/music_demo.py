"""Original score for the demo film, synthesised in code (no third-party music). 120 BPM electronic: pads and a
pulse for the intro, the beat drops when FitBot appears, a lighter break for safety, a build into the end card.
Whooshes on scene changes, ducking under the voice. Usage: python music_demo.py build/   (reads timeline.json)"""
import json, sys, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

B = Path(sys.argv[1]); SR = 48000; BPM = 120; BEAT = 60 / BPM; BAR = 4 * BEAT
tl = json.loads((B / "timeline.json").read_text()); DUR = tl["duration"]; N = int((DUR + 1) * SR)
sc = {s["id"]: s for s in tl["scenes"]}; rng = np.random.default_rng(3)
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
filt = lambda x, f, k="low", o=2: sosfilt(butter(o, f, k, fs=SR, output="sos"), x)
# A minor colour: Am9 - Fmaj7 - C - G6
CH = [[57, 64, 67, 71, 72], [53, 60, 64, 67, 69], [48, 55, 60, 64, 67], [55, 62, 67, 71, 64]]
BASS = [45, 41, 48, 43]

def env(n, a, r):
    e = np.ones(n); a = min(int(a * SR), n); r = min(int(r * SR), n - a)
    e[:a] = np.linspace(0, 1, a); e[n - r:] *= np.linspace(1, 0, r); return e

def place(buf, x, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf): return
    x = x[: len(buf) - i]; buf[i:i + len(x)] += x * gain

def saw(f, n, det=0.0):
    t = np.arange(n) / SR; out = 0
    for d in (-det, 0, det):
        ph = (t * f * (1 + d)) % 1; out = out + (2 * ph - 1)
    return out / 3

pads, bass, arp, kick, hats, clap, fx = (np.zeros(N) for _ in range(7))
bars = int(DUR / BAR) + 2
for b in range(bars):
    t0 = b * BAR; ch = CH[b % 4]; n = int(BAR * SR)
    p = sum(saw(hz(m), n, 0.004) for m in ch) / len(ch)
    place(pads, filt(p, 1800) * env(n, 0.6, 0.6), t0)
    bn = int(BEAT * 0.9 * SR)
    for k in range(8):                                  # off-beat eighth bass
        tt = t0 + k * BEAT / 2
        s = np.sin(2 * np.pi * hz(BASS[b % 4]) * np.arange(bn // 2) / SR) + 0.4 * saw(hz(BASS[b % 4]), bn // 2)
        place(bass, filt(s, 600) * env(bn // 2, 0.005, 0.12), tt + (BEAT / 4 if k % 2 == 0 else 0))
    for k in range(16):                                 # sixteenth arpeggio
        m = ch[[0, 2, 4, 1, 3, 4, 2, 1][k % 8]] + 12; an = int(BEAT / 4 * SR)
        s = np.sign(np.sin(2 * np.pi * hz(m) * np.arange(an) / SR)) * 0.5 + np.sin(2 * np.pi * hz(m) * np.arange(an) / SR)
        place(arp, filt(s, 3500) * env(an, 0.003, 0.09) * np.exp(-np.arange(an) / SR * 14), t0 + k * BEAT / 4)
    for k in range(4):
        kn = int(0.35 * SR); tt = np.arange(kn) / SR
        f = 45 + 120 * np.exp(-tt * 30); s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)
        place(kick, s, t0 + k * BEAT)
        hn = int(0.05 * SR); h = filt(rng.standard_normal(hn), 7000, "high") * np.exp(-np.arange(hn) / SR * 70)
        place(hats, h, t0 + k * BEAT + BEAT / 2)
        if k in (1, 3):
            cn = int(0.18 * SR); c = filt(rng.standard_normal(cn), 1500, "high") * np.exp(-np.arange(cn) / SR * 22)
            place(clap, c, t0 + k * BEAT)

t = np.arange(N) / SR
def ramp(a, b, t0, t1):  # value a before t0, b after t1
    return np.clip((t - t0) / max(t1 - t0, 1e-3), 0, 1) * (b - a) + a
def seg(on, off, fade=0.4):
    return np.clip((t - on) / fade, 0, 1) * np.clip((off - t) / fade, 0, 1)

drop = sc["meet"]["start"]; brk = sc["safe"]["start"]; build = sc["why"]["start"]; endc = sc["end"]["start"]
g_pad = 0.55 * np.ones(N)
g_kick = seg(drop, brk) + seg(build, endc + 0.05, 0.05)
g_bass = ramp(0, 1, sc["problem"]["start"], drop) * (1 - seg(brk, build, 0.3) * 0.7) * (t < endc + 0.05)
g_arp = ramp(0.25, 1, 0, drop) * (t < endc + 0.05)
g_hats = seg(drop + BAR, brk) + seg(build, endc + 0.05, 0.05)
g_clap = seg(sc["chat"]["start"], brk) + seg(build + BAR, endc + 0.05, 0.05)
mix = (pads * g_pad * 0.5 + bass * g_bass * 0.55 + arp * g_arp * 0.16 + kick * g_kick * 0.9 + hats * g_hats * 0.18
       + clap * g_clap * 0.22)
# riser into the drop and into the end card, final hit, scene whooshes
for t1, length in ((drop, 4.0), (endc, BAR * 2)):
    n = int(length * SR); r = filt(rng.standard_normal(n), 900, "high") * np.linspace(0, 1, n) ** 2
    place(fx, r * 0.25, t1 - length)
hn = int(3.5 * SR); tt = np.arange(hn) / SR
hit = (np.sin(2 * np.pi * 50 * tt) * np.exp(-tt * 2.2) + sum(saw(hz(m), hn, .005) for m in CH[0]) / 5 * np.exp(-tt * 0.9) * 0.6)
place(fx, hit, endc)
for s in tl["scenes"][1:]:
    if s["id"] in ("meet", "end"): continue
    n = int(0.6 * SR); w = filt(rng.standard_normal(n), 2500) * np.sin(np.linspace(0, np.pi, n)) ** 2
    place(fx, w * 0.18, s["start"] - 0.35)
mix = mix + fx
# small room reverb
ir = rng.standard_normal(int(1.2 * SR)) * np.exp(-np.arange(int(1.2 * SR)) / SR * 4) * 0.02
mix = mix + fftconvolve(mix, ir)[:N] * 0.6
# duck under the voice
vo = np.zeros(N)
for s in tl["scenes"]:
    for l in s["lines"]:
        vo[int((l["start"] - 0.15) * SR): int((l["end"] + 0.25) * SR)] = 1
k = int(0.25 * SR); vo = np.convolve(vo, np.ones(k) / k, "same")
mix = mix * (1 - 0.45 * vo)
mix = mix * np.clip((DUR - t) / 2.5, 0, 1) * np.clip(t / 0.8, 0, 1)
mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.6) * 0.85
st = np.stack([mix, np.roll(mix, int(0.004 * SR))], 1)[: int(DUR * SR)]
with wave.open(str(B / "music.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
print("music", DUR)
