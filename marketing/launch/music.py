"""Original background score for the launch film, synthesised in code (no third-party music, no licences).

Calm corporate / technology feel: warm pads, soft plucked arpeggio, sub bass and light percussion that enter
with the product demo, a lift for the closing, scene-transition whooshes, and automatic ducking under the
voice-over. Reads build/timeline.json, writes build/music.wav (48 kHz stereo).
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
SR = 48000
BPM = 96
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(7)

# D major colour: Dmaj9 - Bm9 - Gmaj9 - A6sus  (MIDI notes)
CHORDS = [[50, 57, 61, 64, 66], [47, 54, 57, 61, 62], [43, 50, 54, 57, 59], [45, 52, 54, 57, 59]]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = min(int(a * SR), n // 2), min(int(r * SR), n // 2)
    e[:na] = np.linspace(0, 1, na) ** 2
    e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def smooth(x, sec):
    k = max(int(sec * SR), 1)
    return np.convolve(x, np.ones(k) / k, mode="same")


def main() -> None:
    tl = json.loads((BUILD / "timeline.json").read_text())
    total = tl["duration"]
    N = int((total + 1.0) * SR)
    t = np.arange(N) / SR
    sc = {s["id"]: s for s in tl["scenes"]}
    demo_in = sc["exercises"]["start"] - 0.4          # percussion + bass enter with the product demo
    tech_in, tech_out = sc["architecture"]["start"], sc["results"]["end"]
    outro_in = sc["outro"]["start"]
    end_hit = sc["outro"]["lines"][-1]["start"] - 0.2

    pad = np.zeros((N, 2)); arp = np.zeros((N, 2)); bass = np.zeros(N); drums = np.zeros(N); fx = np.zeros((N, 2))

    # ---------- pads: one chord per bar, long crossfades ----------
    nbars = int(total / BAR) + 2
    for b in range(nbars):
        chord = CHORDS[b % 4]
        s, n = int(b * BAR * SR), int((BAR + 1.6) * SR)
        if s >= N:
            break
        n = min(n, N - s)
        tt = np.arange(n) / SR
        e = env_ar(n, 0.9, 1.6)
        for ch, det in ((0, -0.07), (1, 0.07)):
            sig = np.zeros(n)
            for m in chord:
                f = hz(m + 12)
                for d in (-det, 0, det):            # three detuned voices, soft harmonics only
                    ph = 2 * np.pi * f * (1 + d / 100) * tt + rng.uniform(0, 6.28)
                    sig += np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph)
            pad[s:s + n, ch] += sig * e
    for ch in (0, 1):
        pad[:, ch] = lp(pad[:, ch], 2200)
    pad *= 0.010

    # ---------- plucked arpeggio (8th notes) from the identity scene, busier in the tech section ----------
    arp_in = sc["identity"]["start"] + 1.0
    step = BEAT / 2
    k = 0
    tt0 = arp_in
    while tt0 < outro_in + 4 * BAR:
        b = int(tt0 / BAR)
        chord = CHORDS[b % 4]
        pattern = [0, 2, 3, 4, 1, 3, 2, 4]
        m = chord[pattern[k % 8]] + 24
        busy = tech_in <= tt0 < tech_out
        if busy or k % 2 == 0 or rng.random() < 0.35:
            n = int(0.9 * SR)
            s = int(tt0 * SR)
            if s + n < N:
                tt = np.arange(n) / SR
                note = (np.sin(2 * np.pi * hz(m) * tt) + 0.3 * np.sin(4 * np.pi * hz(m) * tt)) * np.exp(-tt * 6.5)
                note *= 0.9 if busy else 0.6
                pan = 0.5 + 0.35 * np.sin(k * 1.7)
                arp[s:s + n, 0] += note * (1 - pan)
                arp[s:s + n, 1] += note * pan
        k += 1
        tt0 += step
    # ping-pong delay
    d = int(BEAT * 0.75 * SR)
    wet = np.zeros_like(arp)
    wet[d:, 1] += arp[:-d, 0] * 0.35
    wet[d:, 0] += arp[:-d, 1] * 0.35
    wet[2 * d:, 0] += arp[:-2 * d, 0] * 0.18
    arp = arp + wet
    for ch in (0, 1):
        arp[:, ch] = lp(arp[:, ch], 5200)
    arp *= 0.020

    # ---------- sub bass (root, quarter-note pulse) ----------
    for b in range(nbars):
        root = CHORDS[b % 4][0] - 12
        for q in range(4):
            st = b * BAR + q * BEAT
            if st < demo_in or st > end_hit + BAR:
                continue
            s, n = int(st * SR), int(BEAT * 0.95 * SR)
            if s + n >= N:
                continue
            tt = np.arange(n) / SR
            bass[s:s + n] += np.sin(2 * np.pi * hz(root) * tt) * env_ar(n, 0.02, 0.25)
    bass = lp(bass, 180) * 0.11

    # ---------- soft kick + hats ----------
    st = demo_in
    i = 0
    while st < end_hit:
        s = int(st * SR)
        if i % 2 == 0:                               # kick on beats 1 and 3
            n = int(0.35 * SR)
            tt = np.arange(n) / SR
            f = 42 + 50 * np.exp(-tt * 28)
            drums[s:s + n] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) * 0.55
        n = int(0.05 * SR)                           # closed hat on the off-beat
        hs = int((st + BEAT / 2) * SR)
        if hs + n < N:
            drums[hs:hs + n] += hp(rng.normal(0, 1, n), 7000) * np.exp(-np.arange(n) / SR * 90) * 0.08
        st += BEAT
        i += 1
    drums *= 0.5

    # ---------- transition whooshes + risers ----------
    for s_ in tl["scenes"][1:]:
        c = s_["start"]
        n = int(1.2 * SR)
        s = int((c - 0.75) * SR)
        if s < 0 or s + n >= N:
            continue
        tt = np.linspace(0, 1, n)
        noise = rng.normal(0, 1, n)
        sweep = np.zeros(n)
        for j, (lo, hi) in enumerate(zip(np.linspace(300, 2500, 12), np.linspace(900, 6000, 12))):
            seg = slice(j * n // 12, (j + 1) * n // 12)
            sweep[seg] = bp(noise, lo, hi)[seg]
        w = sweep * np.sin(np.pi * tt) ** 2 * 0.05
        fx[s:s + n, 0] += w * (1 - tt)
        fx[s:s + n, 1] += w * tt
    for c in (sc["identity"]["start"], outro_in):
        n = int(3.0 * SR)
        s = int(c * SR) - n
        tt = np.linspace(0, 1, n)
        r = bp(rng.normal(0, 1, n), 800, 5000) * tt ** 3 * 0.05
        fx[s:s + n, 0] += r
        fx[s:s + n, 1] += r
    # closing impact: low boom + bright chord
    s = int(end_hit * SR)
    n = min(int(5 * SR), N - s)
    tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (38 + 30 * np.exp(-tt * 6)) * tt) * np.exp(-tt * 1.4) * 0.25
    fx[s:s + n, 0] += boom
    fx[s:s + n, 1] += boom

    # ---------- section dynamics ----------
    def ramp(a, b):
        return np.clip((t - a) / max(b - a, 1e-6), 0, 1)
    pad_gain = 0.55 + 0.45 * ramp(0, 4)
    arp_gain = ramp(sc["identity"]["start"], sc["identity"]["start"] + 3) * (1 - 0.5 * ramp(end_hit + 1, end_hit + 4))
    groove = ramp(demo_in, demo_in + 1.5) * (1 - ramp(end_hit + BAR, end_hit + BAR + 1))
    mix = pad * pad_gain[:, None] + arp * arp_gain[:, None] + ((bass + drums) * groove)[:, None]

    # reverb on the musical part
    ir_n = int(2.6 * SR)
    ir = rng.normal(0, 1, (ir_n, 2)) * np.exp(-np.linspace(0, 7, ir_n))[:, None]
    ir[:, 0] = lp(ir[:, 0], 6000); ir[:, 1] = lp(ir[:, 1], 6000)
    rev = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in (0, 1)], axis=1)
    mix = mix + rev * (0.18 / np.abs(rev).max() * np.abs(mix).max())
    mix = mix + fx

    # ---------- ducking under the voice ----------
    vo = np.zeros(N)
    for s_ in tl["scenes"]:
        for ln in s_["lines"]:
            vo[int(ln["start"] * SR): int(ln["end"] * SR)] = 1
    duck = 1 - 0.45 * np.clip(smooth(vo, 0.35), 0, 1)
    mix *= duck[:, None]

    # fade in / fade out
    fade = np.clip(t / 1.2, 0, 1) * np.clip((total + 0.6 - t) / 3.0, 0, 1)
    mix *= fade[:, None]
    mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.2) * 0.42
    with wave.open(str(BUILD / "music.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"music {N / SR:.1f} s -> build/music.wav")


if __name__ == "__main__":
    main()
