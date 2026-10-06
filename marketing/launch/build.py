"""Render the FitBot × Veltris launch film.

    .venv/bin/python marketing/launch/collect.py          # once: real answers + UI screenshots (app must be running)
    .venv/bin/python marketing/launch/voice.py            # voice-over + timeline   (--voice "Ava (Premium)" to change)
    .venv/bin/python marketing/launch/music.py            # original score, synced to the timeline
    .venv/bin/python marketing/launch/build.py            # frames -> marketing/FitBot_Veltris_Launch.mp4
    .venv/bin/python marketing/launch/build.py --stills 3,20,45   # preview frames as PNG in build/stills/

Every frame is produced by stage.html's render(t) (deterministic), captured with headless Chromium.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / "build"
OUT = ROOT / "marketing" / "FitBot_Veltris_Launch.mp4"
FPS = 30


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def write_data_js() -> dict:
    data = json.loads((BUILD / "data.json").read_text())
    tl = json.loads((BUILD / "timeline.json").read_text())
    rows = [json.loads(l) for l in (ROOT / "data" / "processed" / "training.jsonl").read_text().splitlines()]
    # three real, short, in-domain training examples for the dataset scene
    want = ["Dumbbell leg exercises?", "Calories in chicken thigh?", "What should I eat before a workout?"]
    samples = [next(r for r in rows if r["input"] == w) for w in want if any(r["input"] == w for r in rows)]
    data["samples"] = [{"input": r["input"], "intent": r["intent"], "response": r["response"]} for r in samples]
    (BUILD / "data.js").write_text(f"window.DATA = {json.dumps(data)};\nwindow.TL = {json.dumps(tl)};\n")
    return tl


def open_stage(p):
    b = p.chromium.launch(args=["--disable-web-security", "--allow-file-access-from-files", "--font-render-hinting=none"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto((HERE / "stage.html").as_uri())
    pg.wait_for_function("window.READY === true", timeout=120000)
    if errors:
        print("page errors:", errors[:5])
    return b, pg


def stills(times: list[float], tag: str) -> None:
    write_data_js()
    out = BUILD / "stills" / tag
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b, pg = open_stage(p)
        for t in times:
            pg.evaluate(f"render({t})")
            pg.screenshot(path=str(out / f"t{t:07.2f}.png"))
        b.close()
    print("stills ->", out)


def render_film() -> None:
    tl = write_data_js()
    dur = tl["duration"]
    n = int(dur * FPS)
    silent = BUILD / "video_noaudio.mp4"
    enc = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
                            "-i", "-", "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                            "-crf", "16", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                            "-movflags", "+faststart", str(silent)], stdin=subprocess.PIPE)
    t0 = time.time()
    with sync_playwright() as p:
        b, pg = open_stage(p)
        for f in range(n):
            pg.evaluate(f"render({f / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=95))
            if f % 300 == 0:
                el = time.time() - t0
                print(f"frame {f}/{n}  {el:5.0f}s  eta {el / max(f, 1) * (n - f):5.0f}s", flush=True)
        b.close()
    enc.stdin.close()
    enc.wait()
    # mix: voice (mono, centred) + score (stereo), loudness-normalised for online playback
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(silent), "-i", str(BUILD / "voiceover.wav"),
                    "-i", str(BUILD / "music.wav"), "-filter_complex",
                    "[1:a]aformat=channel_layouts=stereo,volume=1.0[v];[2:a]volume=0.55[m];"
                    "[v][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-t", f"{dur:.3f}", str(OUT)], check=True)
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", help="comma-separated times in seconds")
    ap.add_argument("--tag", default="preview", help="sub-folder for the stills")
    a = ap.parse_args()
    if a.stills:
        stills([float(x) for x in a.stills.split(",")], a.tag)
    else:
        render_film()
