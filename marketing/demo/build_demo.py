"""Render the FitBot demo film from stage.html.

    python build_demo.py WORK --stills 3,20,45     # preview frames
    python build_demo.py WORK                       # full film -> WORK/FitBot_Demo_2min.mp4

WORK holds assets/, data.json, timeline.json, voiceover.wav and music.wav. Each scene is rendered to its own file
(two browsers in parallel), then the files are joined and the sound is added.
"""
import argparse, json, os, shutil, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FPS = 30

def prepare(work: Path):
    data = json.loads((work / "data.json").read_text()); tl = json.loads((work / "timeline.json").read_text())
    (work / "data.js").write_text(f"window.DATA = {json.dumps(data)};\nwindow.TL = {json.dumps(tl)};\n")
    shutil.copy(HERE / "stage.html", work / "stage.html")
    return tl

def open_stage(p, work):
    b = p.chromium.launch(args=["--allow-file-access-from-files", "--font-render-hinting=none"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto((work / "stage.html").as_uri()); pg.wait_for_function("window.READY === true", timeout=120000)
    return b, pg, errs

def render_range(args):
    work, name, f0, f1 = args
    work = Path(work); tmp = work / "parts" / f"{name}.tmp.mp4"; out = work / "parts" / f"{name}.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                            "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                            "-r", str(FPS), "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                            str(tmp)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b, pg, errs = open_stage(p, work)
        for f in range(f0, f1):
            pg.evaluate(f"render({f / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=93))
        b.close()
    enc.stdin.close()
    if enc.wait() == 0:
        tmp.rename(out)
    return name, f1 - f0, errs[:3]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("work"); ap.add_argument("--stills"); ap.add_argument("--only")
    a = ap.parse_args(); work = Path(a.work).resolve(); tl = prepare(work)
    if a.stills:
        (work / "stills").mkdir(exist_ok=True)
        with sync_playwright() as p:
            b, pg, errs = open_stage(p, work)
            for t in [float(x) for x in a.stills.split(",")]:
                pg.evaluate(f"render({t})"); pg.screenshot(path=str(work / "stills" / f"t{t:06.2f}.jpg"), type="jpeg", quality=85)
            b.close()
        print("errors:", errs[:5]); return
    (work / "parts").mkdir(exist_ok=True)
    jobs = []
    for s in tl["scenes"]:
        f0, f1 = round(s["start"] * FPS), round(s["end"] * FPS)
        if a.only and s["id"] not in a.only.split(","): continue
        jobs.append((str(work), f"{len(jobs):02d}_{s['id']}" if not a.only else None, f0, f1))
    # stable names regardless of --only
    names = {round(s["start"] * FPS): f"{i:02d}_{s['id']}" for i, s in enumerate(tl["scenes"])}
    jobs = [(w, names[f0], f0, f1) for w, _, f0, f1 in jobs]
    t0 = time.time()
    with ProcessPoolExecutor(2) as ex:
        for name, n, errs in ex.map(render_range, sorted(jobs, key=lambda j: -(j[3] - j[2]))):
            print(f"{name} {n} frames  {time.time() - t0:5.0f}s  {errs or ''}", flush=True)
    parts = sorted((work / "parts").glob("[0-9][0-9]_*.mp4"))
    parts = [p for p in parts if not p.name.endswith(".tmp.mp4")]
    (work / "parts" / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
    silent = work / "video_noaudio.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(work / "parts" / "list.txt"), "-c", "copy", str(silent)], check=True)
    out = work / "FitBot_Demo_2min.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(work / "voiceover.wav"), "-i", str(work / "music.wav"),
                    "-filter_complex", "[1:a]aformat=channel_layouts=stereo,volume=1.0[v];[2:a]volume=0.5[m];[v][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
                    "-t", f"{tl['duration']:.3f}", str(out)], check=True)
    print("done", out, f"{time.time() - t0:.0f}s")

if __name__ == "__main__":
    main()
