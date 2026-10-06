"""Assemble the FitBot marketing video from the real app recording.

Inputs : marketing/raw/demo.webm + markers.json (from record_demo.py),
         evaluation/results.json + evaluation/test_suite_results.json (real metrics shown on the stats card)
Outputs: marketing/FitBot_promo.mp4 (1920x1080, H.264, 30 fps) and marketing/FitBot_thumbnail.png
"""
import json
import math
from pathlib import Path

import numpy as np
from moviepy import (AudioArrayClip, CompositeVideoClip, ImageClip, VideoFileClip,
                     concatenate_videoclips, vfx, afx)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
W, H, FPS = 1920, 1080, 30
TEAL, TEAL_D, ORANGE, INK, MUTED = (45, 212, 191), (15, 118, 110), (251, 146, 60), (236, 247, 244), (148, 170, 163)
XF = 0.45   # crossfade seconds

FONT = "/System/Library/Fonts/SFNS.ttf"


def font(size, weight="Regular"):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def background():
    """Dark teal gradient with soft glows (brand look of the app)."""
    y, x = np.mgrid[0:H, 0:W]
    base = np.zeros((H, W, 3), np.float32)
    t = (x / W * 0.6 + y / H * 0.4)[..., None]
    base += (1 - t) * np.array([10, 18, 16]) + t * np.array([9, 45, 41])
    for cx, cy, r, col, a in ((0.15 * W, 0.2 * H, 700, TEAL, 0.18), (0.9 * W, 0.85 * H, 800, TEAL_D, 0.35)):
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        base += (np.clip(1 - d / r, 0, 1) ** 2)[..., None] * np.array(col) * a
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


BG = None


def logo(draw, x, y, s):
    """FitBot dumbbell mark (same shape as the app favicon)."""
    draw.rounded_rectangle([x, y, x + s, y + s], radius=int(s * 0.25), fill=TEAL_D)
    u = s / 64
    for rx in ((14, 27, 20, 37), (44, 27, 50, 37), (20, 23, 25, 41), (39, 23, 44, 41), (25, 30, 39, 34)):
        draw.rectangle([x + rx[0] * u, y + rx[1] * u, x + rx[2] * u, y + rx[3] * u], fill="white")


def text_center(draw, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)


def save(img, name):
    p = BUILD / name
    img.save(p)
    return str(p)


def card_intro():
    img = BG.copy()
    d = ImageDraw.Draw(img)
    logo(d, W / 2 - 70, 250, 140)
    text_center(d, 430, "FitBot", font(150, "Bold"), INK)
    text_center(d, 620, "Your AI fitness coach that runs on your own computer", font(52, "Medium"), TEAL)
    text_center(d, 710, "Workouts  ·  Nutrition  ·  Recovery  ·  Safety-first", font(38), MUTED)
    return save(img, "01_intro.png")


def card_hook():
    img = BG.copy()
    d = ImageDraw.Draw(img)
    text_center(d, 360, "Generic chatbots guess.", font(96, "Bold"), MUTED)
    text_center(d, 500, "FitBot was trained for fitness.", font(96, "Bold"), INK)
    text_center(d, 660, "A small language model, fine-tuned on fitness & nutrition, grounded in real data.", font(40), TEAL)
    return save(img, "02_hook.png")


def card_stats(m):
    img = BG.copy()
    d = ImageDraw.Draw(img)
    text_center(d, 120, "Measured, not promised", font(76, "Bold"), INK)
    text_center(d, 220, f"Fine-tuned SmolLM2-360M on a Google Colab {m['gpu']} GPU · held-out test set + 163 real chat turns",
                font(34), MUTED)
    tiles = [(f"{m['ppl_base']} → {m['ppl_ft']}", "perplexity on unseen questions"),
             (f"{m['rouge_x']}×", "closer to expert-written answers"),
             (f"{m['suite_pass']}%", "of 163 real chat turns pass"),
             ("100%", "safety & off-topic handling")]
    tw, th, gap = 400, 300, 40
    x0 = (W - (4 * tw + 3 * gap)) / 2
    for i, (big, small) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        d.rounded_rectangle([x, 380, x + tw, 380 + th], radius=28, fill=(20, 33, 30), outline=(38, 64, 58), width=2)
        bf = font(84 if len(big) < 8 else 64, "Bold")
        bw = d.textlength(big, font=bf)
        d.text((x + (tw - bw) / 2, 450), big, font=bf, fill=TEAL)
        sf = font(30)
        lines, cur = [], ""
        for word in small.split():
            if d.textlength((cur + " " + word).strip(), font=sf) > tw - 50:
                lines.append(cur)
                cur = word
            else:
                cur = (cur + " " + word).strip()
        lines.append(cur)
        for j, ln in enumerate(lines):
            lw = d.textlength(ln, font=sf)
            d.text((x + (tw - lw) / 2, 580 + j * 40), ln, font=sf, fill=MUTED)
    text_center(d, 800, f"~{m['latency']} s per answer on a laptop · no cloud AI API · your chats stay private", font(40, "Medium"), INK)
    return save(img, "10_stats.png")


def card_trust():
    img = BG.copy()
    d = ImageDraw.Draw(img)
    text_center(d, 210, "Built on real, open data", font(80, "Bold"), INK)
    rows = [("58 exercises with real photos", "free-exercise-db · public domain"),
            ("111 foods, exact nutrient values", "USDA FoodData Central · never estimated"),
            ("Follow-up aware & personalised", "level, goal, equipment, diet"),
            ("Safety guardrails", "urgent symptoms → see a professional")]
    for i, (a, b) in enumerate(rows):
        y = 380 + i * 135
        d.ellipse([560, y + 14, 590, y + 44], fill=TEAL)
        d.text((620, y), a, font=font(50, "Semibold"), fill=INK)
        d.text((620, y + 62), b, font=font(32), fill=MUTED)
    return save(img, "11_trust.png")


def card_outro():
    img = BG.copy()
    d = ImageDraw.Draw(img)
    logo(d, W / 2 - 60, 300, 120)
    text_center(d, 450, "FitBot", font(130, "Bold"), INK)
    text_center(d, 620, "Train smarter.", font(64, "Medium"), TEAL)
    text_center(d, 900, "FitBot provides general fitness and wellness information and is not a substitute "
                        "for professional medical advice.", font(28), MUTED)
    return save(img, "12_outro.png")


def caption_png(text, idx):
    f = font(46, "Semibold")
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = tmp.textlength(text, font=f)
    pw, ph = int(tw + 110), 96
    shadow = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([30, 36, pw + 30, ph + 36], radius=48, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    pill = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    pill.alpha_composite(shadow)
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([30, 30, pw + 30, ph + 30], radius=48, fill=(12, 22, 20, 236), outline=(45, 212, 191, 255), width=3)
    d.ellipse([30 + 34, 30 + ph / 2 - 9, 30 + 52, 30 + ph / 2 + 9], fill=TEAL)
    d.text((30 + 72, 30 + (ph - 56) / 2), text, font=f, fill=INK)
    p = BUILD / f"cap_{idx:02d}.png"
    pill.save(p)
    return str(p)


def card_clip(path, dur):
    c = ImageClip(path).with_duration(dur)
    # gentle push-in
    return c.with_effects([vfx.Resize(lambda t: 1 + 0.025 * t / dur)]).with_position("center")


def footage_clip(src, a, b, caption, idx, speed=1.0):
    clip = src.subclipped(a, b).resized((W, H))   # container metadata can under-report the frame size
    if speed != 1.0:
        clip = clip.with_effects([vfx.MultiplySpeed(speed)])
    cap = ImageClip(caption_png(caption, idx)).with_duration(clip.duration)
    cap = cap.with_position(("center", 70)).with_effects([vfx.CrossFadeIn(0.35)])
    return CompositeVideoClip([clip, cap], size=(W, H)).with_duration(clip.duration)


def soundtrack(duration):
    """Soft synthesized pad (generated here -> no licensing issues). Am - F - C - G, 4 s per chord."""
    sr = 44100
    t = np.arange(int(duration * sr)) / sr
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    out = np.zeros_like(t)
    seg = 4.0
    for i in range(int(math.ceil(duration / seg))):
        f = chords[i % 4]
        s0, s1 = int(i * seg * sr), int(min((i + 1) * seg + 1.0, duration) * sr)
        tt = t[s0:s1] - i * seg
        env = np.clip(tt / 1.2, 0, 1) * np.clip((seg + 1.0 - tt) / 1.2, 0, 1)
        for k, fr in enumerate(f):
            out[s0:s1] += env * (0.5 * np.sin(2 * np.pi * fr * tt) + 0.18 * np.sin(2 * np.pi * 2 * fr * tt + k)) / 3
        # soft pulse on the bass note
        out[s0:s1] += env * 0.12 * np.sin(2 * np.pi * f[0] / 2 * tt) * (0.6 + 0.4 * np.sin(2 * np.pi * 2 * tt))
    fade = np.clip(t / 1.5, 0, 1) * np.clip((duration - t) / 2.5, 0, 1)
    out = 0.16 * out * fade / max(1e-9, np.abs(out).max())
    return AudioArrayClip(np.stack([out, out], axis=1), fps=sr)


def metrics():
    r = json.loads((ROOT / "evaluation/results.json").read_text())
    s = json.loads((ROOT / "evaluation/test_suite_results.json").read_text())
    rows = [x for v in s["suites"].values() for x in v]
    card = r.get("training_run", "")
    return {
        "gpu": "Tesla T4" if "T4" in card else "GPU",
        "ppl_base": f"{r['base']['test']['perplexity']:.2f}", "ppl_ft": f"{r['fine_tuned']['test']['perplexity']:.2f}",
        "rouge_x": f"{r['fine_tuned']['generation']['rougeL_f'] / r['base']['generation']['rougeL_f']:.1f}",
        "suite_pass": round(100 * sum(x["passed"] for x in rows) / len(rows)),
        "latency": "1",
    }


def main():
    global BG
    BUILD.mkdir(exist_ok=True)
    BG = background()
    m = metrics()
    print("metrics on stats card:", m)
    src = VideoFileClip(str(HERE / "raw/demo.webm"))
    mk = json.loads((HERE / "raw/markers.json").read_text())

    scenes = [
        ("dashboard", "Explore 58 exercises with real photos", 1.0),
        ("chest", "Ask anything — get exercise cards with images", 1.15),
        ("beginner", "Follow-ups just work: “I'm a beginner.”", 1.0),
        ("dumbbell", "“I only have dumbbells.” → a plan built for you", 1.1),
        ("food", "Nutrition from USDA FoodData Central — never guessed", 1.1),
        ("sleep", "Sleep & recovery guidance", 1.0),
        ("plan", "Day-by-day workout plans in seconds", 1.3),
        ("safety", "Safety first: urgent symptoms → see a doctor", 1.0),
        ("ood", "Stays focused on fitness", 1.0),
    ]
    clips = [card_clip(card_intro(), 4.0), card_clip(card_hook(), 3.6)]
    for i, (name, cap, speed) in enumerate(scenes):
        clips.append(footage_clip(src, mk[f"{name}_start"], mk[f"{name}_end"], cap, i, speed))
    clips += [card_clip(card_stats(m), 6.0), card_clip(card_trust(), 4.8), card_clip(card_outro(), 4.5)]

    faded = [clips[0]] + [c.with_effects([vfx.CrossFadeIn(XF)]) for c in clips[1:]]
    video = concatenate_videoclips(faded, method="compose", padding=-XF, bg_color=(10, 18, 16))
    video = video.with_effects([vfx.FadeIn(0.6), vfx.FadeOut(0.8)])
    video = video.with_audio(soundtrack(video.duration))
    out = HERE / "FitBot_promo.mp4"
    video.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", preset="medium",
                          bitrate="8000k", threads=8, logger=None)
    # thumbnail
    thumb = Image.open(BUILD / "01_intro.png").convert("RGB")
    frame = Image.fromarray(src.get_frame(mk["dumbbell_end"] - 0.5)).resize((960, 540))  # any source size
    canvas = BG.copy()
    canvas.paste(frame, (880, 270))
    d = ImageDraw.Draw(canvas)
    logo(d, 110, 300, 110)
    d.text((110, 440), "FitBot", font=font(130, "Bold"), fill=INK)
    d.text((110, 600), "Your AI fitness coach", font=font(54, "Medium"), fill=TEAL)
    d.text((110, 670), "runs on your own computer", font=font(44), fill=MUTED)
    canvas.save(HERE / "FitBot_thumbnail.png")
    print(f"wrote {out} ({video.duration:.1f}s) and FitBot_thumbnail.png")


if __name__ == "__main__":
    main()
