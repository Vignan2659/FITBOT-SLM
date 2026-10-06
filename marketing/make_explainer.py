"""FitBot explainer video: voiceover (macOS 'Samantha', American English), subtitles, real app footage,
real code images, architecture diagram, model / data / results / tech-stack cards.

Inputs : marketing/raw/{demo,extras,mobile}.webm + markers, evaluation/* results, project source files
Outputs: marketing/FitBot_explainer.mp4, marketing/explainer_script.md, marketing/explainer/ (assets)
"""
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from moviepy import (AudioArrayClip, AudioFileClip, ColorClip, CompositeAudioClip, CompositeVideoClip, ImageClip,
                     VideoFileClip, concatenate_videoclips, vfx)
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_for_filename
from pygments.token import Token

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
A = HERE / "explainer"
W, H, FPS = 1920, 1080, 30
XF = 0.4
VOICE, RATE = "Samantha", 190
OUT_NAME, MD_NAME = "FitBot_explainer.mp4", "explainer_script.md"
MAX_SECONDS = None          # if set, refuse to encode a longer video
TEAL, TEAL_D, ORANGE, INK, MUTED = (45, 212, 191), (15, 118, 110), (251, 146, 60), (236, 247, 244), (148, 170, 163)
SANS, MONO = "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/SFNSMono.ttf"


def font(size, weight="Regular", path=SANS):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


# ======================================================================================= SCRIPT
# Each scene: id, visual, optional on-screen title pill, sentences [(subtitle text, spoken override or None)].
SCRIPT = [
    ("intro", {"type": "card", "make": "intro"}, None, [
        ("Meet FitBot: a fitness coach powered by a small language model that runs on your own computer.", None),
        ("In the next few minutes, you'll see what it can do, and exactly how it works under the hood.", None)]),
    ("what", {"type": "card", "make": "capabilities"}, None, [
        ("FitBot answers questions about workouts, exercises, nutrition, hydration, sleep, and recovery.", None),
        ("It shows real exercise photos and real nutrition facts, and it builds personalized workout plans.", None),
        ("And it needs no paid cloud AI service. Everything runs locally.", None)]),
    ("dashboard", {"type": "footage", "src": "demo", "segs": [("dashboard_start", "dashboard_end")]},
     "The dashboard", [
        ("Everything starts on the dashboard, with quick-start prompts, your profile, and an exercise explorer.", None),
        ("Fifty-eight exercises, each with real public-domain photos.", None)]),
    ("chest", {"type": "footage", "src": "demo", "segs": [("chest_start", "chest_end")]},
     "Exercise cards with images", [
        ("Ask: what exercises can I do for chest?", None),
        ("FitBot replies with a short answer and interactive exercise cards: target muscles, equipment, difficulty, "
         "instructions, and a safety tip.", None)]),
    ("followups", {"type": "footage", "src": "demo", "segs": [("beginner_start", "beginner_end"),
                                                            ("dumbbell_start", "dumbbell_end")]},
     "Follow-up conversations", [
        ("It understands follow-ups.", None),
        ("Say, I'm a beginner, and the cards switch to beginner-friendly moves.", None),
        ("Say, I only have dumbbells, and it builds a dumbbell workout with sets, reps, and rest times.", None)]),
    ("food", {"type": "footage", "src": "demo", "segs": [("food_start", "food_end")]},
     "Real nutrition data", [
        ("Ask what to eat after the workout, and you get nutrition cards with calories, protein, carbs, and fat.", None),
        ("Every number comes straight from the U.S.D.A.'s FoodData Central database. FitBot never makes up nutrient "
         "values.", "Every number comes straight from the U S D A's Food Data Central database. FitBot never makes up "
                    "nutrient values.")]),
    ("plan", {"type": "footage", "src": "demo", "segs": [("plan_start", "plan_end")]},
     "Workout plans", [
        ("Need a full program? Ask for a beginner three-day gym workout.", None),
        ("FitBot lays out every day, with exercises, sets, reps, rest, and images, in seconds.", None)]),
    ("arch", {"type": "sequence", "images": ["arch0", "arch1", "arch2", "arch3", "arch4", "arch5"]},
     None, [
        ("So, how does it work? Every message travels through a pipeline.", None),
        ("First, a safety screen checks for high-risk situations.", None),
        ("Next, an intent classifier and slot extractor work out what you're asking, and remember context from "
         "earlier turns.", None),
        ("Then retrieval gathers real facts: exercises, foods, a workout plan, and expert guidance passages.", None),
        ("The fine-tuned language model writes the answer from those facts.", None),
        ("Finally, the answer is checked again for safety and sent to the app, with cards and plans attached.", None)]),
    ("code_prompt", {"type": "sequence", "images": ["code_prompt", "code_prompt"]}, None, [
        ("Here's the heart of it: the prompt builder.", None),
        ("The same function formats the training data and every live request, so the model always sees the format it "
         "learned: the system prompt, your profile, retrieved reference facts, recent history, and your question.", None)]),
    ("code_safety", {"type": "sequence", "images": ["code_safety", "code_safety"]}, None, [
        ("High-risk messages never depend on the model.", None),
        ("Clear rules catch things like chest pain, extreme dieting, or steroid questions, and return a reviewed safe "
         "response that points you to a professional.", None)]),
    ("code_nlu", {"type": "sequence", "images": ["code_nlu", "code_retriever"]}, None, [
        ("Intent detection combines a T F I D F and logistic regression classifier from scikit-learn with a fitness "
         "vocabulary check, so off-topic questions are politely declined.",
         "Intent detection combines a T, F, I, D, F, and logistic regression classifier from psychic learn, with a "
         "fitness vocabulary check, so off-topic questions are politely declined."),
        ("For general guidance, Sentence Transformers embeddings find the most relevant passages in a curated "
         "knowledge base.", None)]),
    ("model", {"type": "sequence", "images": ["model_card", "code_lora"]}, None, [
        ("The language model is SmolLM2 360M Instruct: an open, Apache-licensed model with 362 million parameters, "
         "small enough to run on a laptop.",
         "The language model is Smol L M 2, 360 M, Instruct: an open, Apache licensed model with 362 million "
         "parameters, small enough to run on a laptop."),
        ("We fine-tuned it with LoRA, using Hugging Face PEFT and Transformers, training just 8.7 million parameters, "
         "or 2.3 percent of the model.",
         "We fine-tuned it with Laura, using Hugging Face peft and Transformers, training just 8 point 7 million "
         "parameters, or 2 point 3 percent of the model.")]),
    ("training", {"type": "card", "make": "training"}, None, [
        ("Training ran in a Google Colab notebook on a Tesla T4 GPU, in under eight minutes.", None),
        ("Validation loss fell steadily from 1.71 for the base model to 0.89, with no sign of overfitting.",
         "Validation loss fell steadily from 1 point 7 1 for the base model, to 0 point 8 9, with no sign of "
         "overfitting.")]),
    ("data", {"type": "card", "make": "data"}, None, [
        ("The data matters just as much.", None),
        ("Exercises and photos come from the public-domain free exercise database, and nutrition from USDA SR Legacy.",
         "Exercises and photos come from the public domain free exercise database, and nutrition from U S D A, "
         "S R Legacy."),
        ("916 conversation examples were written and grounded in those sources, then split into training, validation, "
         "and test sets with no overlap.", None)]),
    ("backend", {"type": "sequence", "images": ["code_chat", "code_models"]}, None, [
        ("The backend is built with FastAPI and SQLAlchemy, on SQLite.",
         "The back end is built with Fast A P I and S Q L Alchemy, on S Q Lite."),
        ("Passwords are hashed with bcrypt, sessions use JWT tokens that are revoked on logout, and every user can only "
         "see their own conversations.",
         "Passwords are hashed with B crypt, sessions use J W T tokens that are revoked on log out, and every user can "
         "only see their own conversations.")]),
    ("frontend_code", {"type": "sequence", "images": ["code_card"]}, None, [
        ("The interface is built with React and Vite. Each answer renders structured components, like this exercise "
         "card.", "The interface is built with React and Veet. Each answer renders structured components, like this "
                  "exercise card.")]),
    ("ux", {"type": "footage", "src": "extras", "segs": [("register_start", "register_end"),
                                                       ("profile_start", "profile_end"),
                                                       ("instructions_start", "instructions_end")]},
     "UI and UX", [
        ("Signing up takes seconds.", None),
        ("Your profile stores your level, goal, diet, and equipment, so suggestions are personalized.", None),
        ("And every exercise card expands to show step-by-step instructions and a safety tip.", None)]),
    ("mobile", {"type": "mobile"}, "Works on any screen", [
        ("The design is dark-mode friendly and fully responsive, so FitBot works just as well on a phone.", None)]),
    ("safety", {"type": "footage", "src": "demo", "segs": [("safety_start", "safety_end"), ("ood_start", "ood_end")]},
     "Safe and on topic", [
        ("It stays safe and on topic.", None),
        ("Mention chest pain, and it tells you to stop and get medical help.", None),
        ("Ask about geography, and it politely steers you back to fitness.", None)]),
    ("results", {"type": "card", "make": "results"}, None, [
        ("The results speak for themselves.", None),
        ("On unseen test questions, perplexity dropped from 5.06 to 2.45, and answers became nearly three times closer "
         "to the expert references.", "On unseen test questions, perplexity dropped from 5 point 0 6, to 2 point 4 5, "
                                      "and answers became nearly three times closer to the expert references."),
        ("In end-to-end testing, 91 percent of 163 chat turns passed, with every safety and off-topic case handled "
         "correctly.", None)]),
    ("stack", {"type": "card", "make": "stack"}, None, [
        ("The stack: React, Vite, FastAPI, SQLAlchemy, SQLite, PyTorch, Hugging Face Transformers, PEFT, Sentence "
         "Transformers, and scikit-learn.",
         "The stack: React, Veet, Fast A P I, S Q L Alchemy, S Q Lite, Pie Torch, Hugging Face Transformers, peft, "
         "Sentence Transformers, and psychic learn."),
        ("All open source, and all running on your own machine.", None)]),
    ("outro", {"type": "card", "make": "outro"}, None, [
        ("FitBot. Your AI fitness coach. Train smarter.", None),
        ("FitBot provides general fitness and wellness information, and is not a substitute for professional medical "
         "advice.", None)]),
]


# ======================================================================================= DRAWING
_BG = None


def bg():
    global _BG
    if _BG is None:
        y, x = np.mgrid[0:H, 0:W]
        base = np.zeros((H, W, 3), np.float32)
        t = (x / W * 0.6 + y / H * 0.4)[..., None]
        base += (1 - t) * np.array([10, 18, 16]) + t * np.array([9, 45, 41])
        for cx, cy, r, col, a in ((0.15 * W, 0.2 * H, 700, TEAL, 0.16), (0.9 * W, 0.85 * H, 800, TEAL_D, 0.32)):
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            base += (np.clip(1 - d / r, 0, 1) ** 2)[..., None] * np.array(col) * a
        _BG = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    return _BG.copy()


def logo(d, x, y, s):
    d.rounded_rectangle([x, y, x + s, y + s], radius=int(s * 0.25), fill=TEAL_D)
    u = s / 64
    for r in ((14, 27, 20, 37), (44, 27, 50, 37), (20, 23, 25, 41), (39, 23, 44, 41), (25, 30, 39, 34)):
        d.rectangle([x + r[0] * u, y + r[1] * u, x + r[2] * u, y + r[3] * u], fill="white")


def ctext(d, y, text, f, fill, x0=0, x1=W):
    w = d.textlength(text, font=f)
    d.text((x0 + (x1 - x0 - w) / 2, y), text, font=f, fill=fill)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for word in text.split():
        if d.textlength((cur + " " + word).strip(), font=f) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    return lines + [cur]


def header(d, kicker, title):
    d.text((140, 70), kicker.upper(), font=font(28, "Semibold"), fill=TEAL)
    d.text((140, 110), title, font=font(58, "Bold"), fill=INK)


def save(img, name):
    p = A / f"{name}.png"
    img.save(p)
    return str(p)


def make_intro():
    img = bg(); d = ImageDraw.Draw(img)
    logo(d, W / 2 - 70, 250, 140)
    ctext(d, 430, "FitBot", font(150, "Bold"), INK)
    ctext(d, 620, "How it works — and what it can do", font(56, "Medium"), TEAL)
    ctext(d, 720, "A fitness-domain small language model · fine-tuned · grounded in real data", font(36), MUTED)
    return save(img, "intro")


def make_capabilities():
    img = bg(); d = ImageDraw.Draw(img)
    header(d, "What it can do", "One assistant for training, food and recovery")
    items = [("Exercises", "58 exercises with photos, muscles, equipment, difficulty, instructions"),
             ("Workout plans", "1–6 day plans for gym, home, dumbbells or bodyweight"),
             ("Nutrition", "USDA FoodData Central values for 111 foods — never estimated"),
             ("Sleep & recovery", "Rest days, soreness, hydration, stretching, warm-ups"),
             ("Personalised", "Follow-ups and your profile: level, goal, diet, equipment"),
             ("Safety-first", "Guardrails for medical red flags; stays on topic")]
    for i, (a, b) in enumerate(items):
        x = 140 + (i % 3) * 560
        y = 290 + (i // 3) * 330
        d.rounded_rectangle([x, y, x + 520, y + 290], radius=28, fill=(20, 33, 30), outline=(38, 64, 58), width=2)
        d.ellipse([x + 36, y + 40, x + 66, y + 70], fill=TEAL)
        d.text((x + 86, y + 30), a, font=font(44, "Bold"), fill=INK)
        for j, ln in enumerate(wrap(d, b, font(32), 440)):
            d.text((x + 40, y + 115 + j * 44), ln, font=font(32), fill=MUTED)
    return save(img, "capabilities")


def make_arch(active):
    """Pipeline diagram; `active` = number of highlighted stages (0..5)."""
    img = bg(); d = ImageDraw.Draw(img)
    header(d, "How it works", "From your message to FitBot's answer")
    # top row: user -> UI -> API
    top = [("You", "type a question"), ("React + Vite UI", "chat, cards, plans"), ("FastAPI  /chat", "auth · history · rate limit")]
    for i, (a, b) in enumerate(top):
        x = 330 + i * 450
        d.rounded_rectangle([x, 250, x + 360, 360], radius=22, fill=(20, 33, 30), outline=(55, 85, 78), width=2)
        ctext(d, 266, a, font(36, "Semibold"), INK, x, x + 360)
        ctext(d, 314, b, font(26), MUTED, x, x + 360)
        if i < 2:
            d.line([x + 370, 305, x + 440, 305], fill=MUTED, width=4)
            d.polygon([(x + 440, 295), (x + 452, 305), (x + 440, 315)], fill=MUTED)
    d.line([1410, 360, 1410, 410, 250, 410, 250, 460], fill=MUTED, width=4)
    d.polygon([(240, 455), (250, 470), (260, 455)], fill=MUTED)
    stages = [("1  Safety screen", ["emergencies, eating", "disorders, steroids,", "medication → guardrail"]),
              ("2  Intent + slots", ["scikit-learn classifier", "+ domain check, level,", "equipment, follow-ups"]),
              ("3  Retrieval", ["exercise DB · USDA foods", "workout planner ·", "knowledge passages"]),
              ("4  Fine-tuned SLM", ["SmolLM2-360M + LoRA", "writes the answer", "from the facts"]),
              ("5  Output check", ["unsafe-advice filter,", "referral + disclaimer,", "cards & plan attached"])]
    bw, gap = 300, 40
    x0 = (W - (5 * bw + 4 * gap)) / 2
    for i, (a, lines) in enumerate(stages):
        x = x0 + i * (bw + gap)
        on = i < active
        cur = i == active - 1
        fill = (17, 66, 60) if on else (20, 33, 30)
        outline = TEAL if cur else ((45, 140, 128) if on else (45, 60, 56))
        d.rounded_rectangle([x, 480, x + bw, 760], radius=24, fill=fill, outline=outline, width=5 if cur else 2)
        d.text((x + 24, 504), a, font=font(32, "Bold"), fill=INK if on or active == 0 else MUTED)
        for j, ln in enumerate(lines):
            d.text((x + 24, 574 + j * 44), ln, font=font(27), fill=(200, 230, 222) if on else MUTED)
        if i < 4:
            ax = x + bw + 4
            d.line([ax, 620, ax + gap - 10, 620], fill=TEAL if on else MUTED, width=4)
            d.polygon([(ax + gap - 12, 610), (ax + gap - 2, 620), (ax + gap - 12, 630)], fill=TEAL if on else MUTED)
    out_on = active >= 5
    d.rounded_rectangle([560, 830, 1360, 930], radius=26, fill=(17, 66, 60) if out_on else (20, 33, 30),
                        outline=TEAL if out_on else (45, 60, 56), width=3)
    ctext(d, 852, "Structured answer → text · exercise cards · food cards · workout plan", font(32, "Semibold"),
          INK if out_on else MUTED, 560, 1360)
    return save(img, f"arch{active}")


TOKEN_COLORS = [
    (Token.Comment, (139, 148, 158)), (Token.Literal.String, (165, 214, 255)), (Token.Literal.Number, (121, 192, 255)),
    (Token.Keyword, (255, 123, 114)), (Token.Operator.Word, (255, 123, 114)), (Token.Name.Function, (210, 168, 255)),
    (Token.Name.Class, (240, 136, 62)), (Token.Name.Decorator, (210, 168, 255)), (Token.Name.Builtin, (255, 166, 87)),
    (Token.Name.Tag, (126, 231, 135)), (Token.Name.Attribute, (121, 192, 255)), (Token.Literal, (121, 192, 255)),
]


def color_for(tt):
    for t, c in TOKEN_COLORS:
        if tt in t:
            return c
    return (230, 237, 243)


def make_code(name, rel, ranges, kicker, title, max_chars=None, size=24):
    src = (ROOT / rel).read_text().splitlines()
    if max_chars is None:   # fit the window width exactly (monospace)
        max_chars = int((W - 240 - 150) / font(size, path=MONO).getlength("M"))
    lines, numbers = [], []
    for k, (a, b) in enumerate(ranges):
        if k:
            lines.append("    ...")
            numbers.append(None)
        for n in range(a, min(b, len(src)) + 1):
            ln = src[n - 1]
            if len(ln) > max_chars:
                ln = ln[:max_chars - 1] + "…"
            lines.append(ln)
            numbers.append(n)
    lexer = get_lexer_for_filename(rel)
    img = bg(); d = ImageDraw.Draw(img)
    header(d, kicker, title)
    mono = font(size, path=MONO)
    lh = int(size * 1.42)
    wx, wy, ww = 120, 220, W - 240
    wh = 70 + lh * len(lines) + 40
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([wx + 10, wy + 18, wx + ww + 10, wy + wh + 18], radius=22, fill=(0, 0, 0, 140))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(18)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=22, fill=(13, 17, 23), outline=(48, 54, 61), width=2)
    d.rounded_rectangle([wx, wy, wx + ww, wy + 56], radius=22, fill=(22, 27, 34))
    d.rectangle([wx, wy + 34, wx + ww, wy + 56], fill=(22, 27, 34))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([wx + 24 + i * 30, wy + 19, wx + 42 + i * 30, wy + 37], fill=c)
    d.text((wx + 130, wy + 14), rel, font=font(24, path=MONO), fill=(139, 148, 158))
    y = wy + 76
    for ln, num in zip(lines, numbers):
        if num is not None:
            nstr = str(num).rjust(4)
            d.text((wx + 20, y), nstr, font=mono, fill=(72, 79, 88))
        x = wx + 110
        if ln.strip() == "...":
            d.text((x, y), "⋮", font=mono, fill=(110, 118, 129))
        else:
            for tt, val in lex(ln, lexer):
                val = val.rstrip("\n")
                if not val:
                    continue
                d.text((x, y), val, font=mono, fill=color_for(tt))
                x += d.textlength(val, font=mono)
        y += lh
    return save(img, name)


def make_model_card():
    img = bg(); d = ImageDraw.Draw(img)
    header(d, "The model", "SmolLM2-360M-Instruct, fine-tuned with LoRA")
    facts = [("361.8 M", "parameters — runs on a laptop"), ("Apache-2.0", "open license, ungated"),
             ("8.7 M", "trainable LoRA params (2.3%)"), ("r = 16, α = 32", "on all attention + MLP projections"),
             ("ChatML", "chat template, loss on answers only"), ("~1 s", "per answer on Apple silicon")]
    for i, (a, b) in enumerate(facts):
        x = 140 + (i % 3) * 560
        y = 300 + (i // 3) * 290
        d.rounded_rectangle([x, y, x + 520, y + 250], radius=28, fill=(20, 33, 30), outline=(38, 64, 58), width=2)
        d.text((x + 40, y + 40), a, font=font(64, "Bold"), fill=TEAL)
        for j, ln in enumerate(wrap(d, b, font(32), 440)):
            d.text((x + 40, y + 140 + j * 42), ln, font=font(32), fill=MUTED)
    return save(img, "model_card")


def paste_image(img, path, box, radius=22, bgcol=(255, 255, 255)):
    x0, y0, x1, y1 = box
    im = Image.open(path).convert("RGB")
    im.thumbnail((x1 - x0 - 40, y1 - y0 - 40))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=bgcol)
    img.paste(im, (int(x0 + (x1 - x0 - im.width) / 2), int(y0 + (y1 - y0 - im.height) / 2)))


def make_training():
    img = bg(); d = ImageDraw.Draw(img)
    r = json.loads((ROOT / "evaluation/training_run/results.json").read_text())
    header(d, "Training", "Google Colab · Tesla T4 GPU")
    rows = [("GPU", r["config"]["gpu_name"]), ("Training time", f"{r['train_seconds'] / 60:.1f} min"),
            ("Epochs / steps", "3 / 138"), ("Batch", "4 × 4 accumulation, fp16"),
            ("Best validation loss", f"{r['best_validation_loss']:.3f}"), ("Base model validation loss", "1.713")]
    for i, (a, b) in enumerate(rows):
        y = 290 + i * 100
        d.text((140, y), a, font=font(32), fill=MUTED)
        d.text((140, y + 40), b, font=font(44, "Bold"), fill=INK)
    paste_image(img, ROOT / "evaluation/charts/loss_curves.png", (760, 260, 1800, 900))
    return save(img, "training")


def make_data():
    img = bg(); d = ImageDraw.Draw(img)
    s = json.loads((ROOT / "data/processed/dataset_stats.json").read_text())
    header(d, "The data", "Licensed sources, grounded examples, no test leakage")
    cols = [("free-exercise-db", "Unlicense · public domain", ["876 exercises, 58 curated", "116 image URLs verified",
                                                              "muscles, equipment, steps"]),
            ("USDA FoodData Central", "SR Legacy · CC0", ["111 foods, exact values", "per 100 g + per portion",
                                                        "never estimated"]),
            ("FitBot conversations", "built for this project", [f"{s['cleaning']['clean_records']} cleaned examples",
                                                                f"{s['split_sizes']['train']} / {s['split_sizes']['validation']} / {s['split_sizes']['test']} train / val / test",
                                                                "split by group: no overlap"])]
    for i, (a, b, lines) in enumerate(cols):
        x = 140 + i * 560
        d.rounded_rectangle([x, 290, x + 520, 860], radius=28, fill=(20, 33, 30), outline=(38, 64, 58), width=2)
        d.text((x + 40, 330), a, font=font(42, "Bold"), fill=INK)
        d.text((x + 40, 392), b, font=font(30), fill=TEAL)
        for j, ln in enumerate(lines):
            d.ellipse([x + 42, 500 + j * 100 + 12, x + 62, 500 + j * 100 + 32], fill=TEAL)
            d.text((x + 82, 500 + j * 100), ln, font=font(34), fill=MUTED)
    return save(img, "data")


def make_results():
    img = bg(); d = ImageDraw.Draw(img)
    r = json.loads((ROOT / "evaluation/results.json").read_text())
    s = json.loads((ROOT / "evaluation/test_suite_results.json").read_text())
    rows = [x for v in s["suites"].values() for x in v]
    header(d, "Results", "Base model vs fine-tuned FitBot")
    tiles = [(f"{r['base']['test']['perplexity']:.2f} → {r['fine_tuned']['test']['perplexity']:.2f}", "test perplexity"),
             (f"{r['fine_tuned']['generation']['rougeL_f'] / r['base']['generation']['rougeL_f']:.1f}×", "ROUGE-L vs references"),
             (f"{round(100 * sum(x['passed'] for x in rows) / len(rows))}%", f"of {len(rows)} chat turns pass"),
             ("100%", "safety & off-topic suites")]
    for i, (a, b) in enumerate(tiles):
        y = 280 + i * 165
        d.rounded_rectangle([140, y, 640, y + 140], radius=24, fill=(20, 33, 30), outline=(38, 64, 58), width=2)
        d.text((170, y + 18), a, font=font(52, "Bold"), fill=TEAL)
        d.text((170, y + 86), b, font=font(28), fill=MUTED)
    paste_image(img, ROOT / "evaluation/charts/base_vs_finetuned.png", (700, 270, 1800, 900))
    return save(img, "results")


def make_stack():
    img = bg(); d = ImageDraw.Draw(img)
    header(d, "Tech stack", "Open source, end to end")
    groups = [("Frontend", [("React 18", "UI components"), ("Vite", "dev server & build"), ("React Router", "pages")]),
              ("Backend", [("FastAPI", "REST API"), ("SQLAlchemy + SQLite", "users, chats"), ("bcrypt + PyJWT", "auth")]),
              ("AI / ML", [("PyTorch", "inference"), ("Transformers", "SmolLM2"), ("PEFT (LoRA)", "fine-tuning"),
                           ("Sentence Transformers", "retrieval"), ("scikit-learn", "intent classifier")]),
              ("Training & data", [("Google Colab", "Tesla T4 GPU"), ("Datasets", "loading"),
                                   ("USDA FoodData Central", "nutrition"), ("free-exercise-db", "exercises")])]
    for i, (g, items) in enumerate(groups):
        x = 140 + i * 420
        d.text((x, 270), g.upper(), font=font(30, "Semibold"), fill=TEAL)
        for j, (a, b) in enumerate(items):
            y = 330 + j * 118
            d.rounded_rectangle([x, y, x + 380, y + 100], radius=20, fill=(20, 33, 30), outline=(38, 64, 58), width=2)
            d.text((x + 24, y + 14), a, font=font(32, "Semibold"), fill=INK)
            d.text((x + 24, y + 58), b, font=font(26), fill=MUTED)
    return save(img, "stack")


def make_outro():
    img = bg(); d = ImageDraw.Draw(img)
    logo(d, W / 2 - 60, 290, 120)
    ctext(d, 440, "FitBot", font(130, "Bold"), INK)
    ctext(d, 610, "Your AI fitness coach. Train smarter.", font(58, "Medium"), TEAL)
    ctext(d, 900, "FitBot provides general fitness and wellness information and is not a substitute for professional "
                  "medical advice.", font(28), MUTED)
    return save(img, "outro")


def make_all_images():
    A.mkdir(exist_ok=True)
    for i in range(6):
        make_arch(i)
    make_code("code_prompt", "backend/app/ml/prompting.py", [(98, 103), (106, 115)], "How it works · 1",
              "One prompt builder for training and inference")
    make_code("code_safety", "backend/app/services/safety.py", [(31, 31), (37, 42), (102, 109)], "How it works · 2",
              "Safety guardrails run before the model")
    make_code("code_nlu", "backend/app/services/nlu.py", [(122, 135)], "How it works · 3",
              "Intent detection + out-of-domain check")
    make_code("code_retriever", "backend/app/ml/retriever.py", [(21, 22), (49, 56)], "How it works · 4",
              "Semantic retrieval with Sentence Transformers")
    make_code("code_lora", "training/make_notebook.py", [(356, 364)], "Fine-tuning", "LoRA with Hugging Face PEFT")
    make_code("code_chat", "backend/app/api/chat.py", [(56, 70)], "Backend", "FastAPI chat endpoint")
    make_code("code_models", "backend/app/db/models.py", [(46, 58)], "Backend", "SQLAlchemy models (SQLite)")
    make_code("code_card", "frontend/src/components/ExerciseCard.jsx", [(6, 6), (13, 27)], "Frontend",
              "React exercise card")
    for n in ("intro", "capabilities", "model_card", "training", "data", "results", "stack", "outro"):
        globals()[f"make_{n}"]()


# ======================================================================================= AUDIO
def tts(text, path):
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-v", VOICE, "-r", str(RATE), "-o", str(aiff), text], check=True)
    return aiff


def subtitle_png(text, path):
    f = font(40, "Medium")
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = wrap(tmp, text, f, 1500)
    lh = 54
    bw = int(max(tmp.textlength(l, font=f) for l in lines)) + 80
    bh = lh * len(lines) + 36
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw, bh], radius=18, fill=(5, 10, 9, 205))
    for i, l in enumerate(lines):
        lw = d.textlength(l, font=f)
        d.text(((bw - lw) / 2, 16 + i * lh), l, font=f, fill=(245, 250, 248))
    im.save(path)
    return str(path)


def pill_png(text, path):
    f = font(42, "Semibold")
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    pw, ph = int(tmp.textlength(text, font=f) + 100), 88
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=44, fill=(12, 22, 20, 236), outline=(45, 212, 191, 255), width=3)
    d.ellipse([32, ph / 2 - 9, 50, ph / 2 + 9], fill=TEAL)
    d.text((68, (ph - 52) / 2), text, font=f, fill=INK)
    im.save(path)
    return str(path)


def music(duration):
    sr = 44100
    t = np.arange(int(duration * sr)) / sr
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    out = np.zeros_like(t)
    seg = 4.0
    for i in range(int(math.ceil(duration / seg))):
        fr = chords[i % 4]
        s0, s1 = int(i * seg * sr), int(min((i + 1) * seg + 1.0, duration) * sr)
        tt = t[s0:s1] - i * seg
        env = np.clip(tt / 1.2, 0, 1) * np.clip((seg + 1.0 - tt) / 1.2, 0, 1)
        for k, f in enumerate(fr):
            out[s0:s1] += env * (0.5 * np.sin(2 * np.pi * f * tt) + 0.15 * np.sin(2 * np.pi * 2 * f * tt + k)) / 3
    fade = np.clip(t / 1.5, 0, 1) * np.clip((duration - t) / 3, 0, 1)
    out = 0.055 * out * fade / max(1e-9, np.abs(out).max())   # quiet bed under the voice
    return AudioArrayClip(np.stack([out, out], axis=1), fps=sr)


# ======================================================================================= VIDEO
def fit_footage(clips, target):
    clip = concatenate_videoclips(clips)
    dur = clip.duration
    if dur > target:
        speed = min(dur / target, 1.8)
        clip = clip.with_effects([vfx.MultiplySpeed(speed)])
        if clip.duration > target:
            clip = clip.subclipped(0, target)
    elif dur < target:
        speed = max(dur / target, 0.6)
        clip = clip.with_effects([vfx.MultiplySpeed(speed)])
        if clip.duration < target:
            last = clip.get_frame(max(0, clip.duration - 0.05))
            clip = concatenate_videoclips([clip, ImageClip(last).with_duration(target - clip.duration)])
    return clip.with_duration(target)


def main():
    make_all_images()
    srcs = {"demo": VideoFileClip(str(HERE / "raw/demo.webm")),
            "extras": VideoFileClip(str(HERE / "raw/extras.webm")),
            "mobile": VideoFileClip(str(HERE / "raw/mobile.webm"))}
    mk = {**json.loads((HERE / "raw/markers.json").read_text()),
          **json.loads((HERE / "raw/extras_markers.json").read_text())}

    scene_clips, voice_tracks, md = [], [], ["# FitBot explainer — voiceover script", "",
                                             f"Voice: macOS **{VOICE}** (American English), {RATE} words/min.", ""]
    t_scene = 0.0
    for si, (sid, vis, pill, sentences) in enumerate(SCRIPT):
        # --- narration timing
        cursor, sub_items, auds = 0.45, [], []
        for k, (txt, spoken) in enumerate(sentences):
            aud = AudioFileClip(str(tts(spoken or txt, A / f"vo_{si:02d}_{k}")))
            sub_items.append((cursor, aud.duration, txt))
            auds.append((cursor, aud))
            cursor += aud.duration + 0.22
        dur = cursor + 0.35
        # --- visual
        if vis["type"] == "card":
            p = str(A / f"{vis['make']}.png")
            base = ImageClip(p).with_duration(dur).with_effects([vfx.Resize(lambda t, d=dur: 1 + 0.02 * t / d)])
            base = base.with_position("center")
        elif vis["type"] == "sequence":
            imgs = [str(A / f"{n}.png") for n in vis["images"]]
            parts = []
            starts = [s[0] for s in sub_items] + [dur]
            for k in range(len(imgs)):
                a = 0 if k == 0 else starts[min(k, len(starts) - 1)] - 0.15
                b = dur if k == len(imgs) - 1 else starts[min(k + 1, len(starts) - 1)] - 0.15
                parts.append(ImageClip(imgs[k]).with_start(a).with_duration(b - a))
            base = CompositeVideoClip(parts, size=(W, H))
        elif vis["type"] == "footage":
            src = srcs[vis["src"]]
            segs = [src.subclipped(mk[a] + 0.1, min(mk[b] - 0.5, src.duration - 0.05)).resized((W, H)) for a, b in vis["segs"]]  # markers lag the video slightly
            base = fit_footage(segs, dur)
        elif vis["type"] == "mobile":
            phone = fit_footage([srcs["mobile"].subclipped(mk["mobile_start"] - 1.0, min(mk["mobile_end"], srcs["mobile"].duration - 0.05))], dur)
            phone = phone.resized(height=900)
            frame = Image.new("RGBA", (phone.w + 36, phone.h + 36), (0, 0, 0, 0))
            ImageDraw.Draw(frame).rounded_rectangle([0, 0, frame.width - 1, frame.height - 1], radius=48,
                                                    fill=(30, 30, 32, 255), outline=(80, 84, 88, 255), width=3)
            frame.save(A / "phone_frame.png")
            bgimg = ImageClip(save(bg(), "mobile_bg")).with_duration(dur)
            fr = ImageClip(str(A / "phone_frame.png")).with_duration(dur).with_position(("center", 70))
            base = CompositeVideoClip([bgimg, fr, phone.with_position(("center", 88))], size=(W, H))
        layers = [base]
        if pill:
            layers.append(ImageClip(pill_png(pill, A / f"pill_{si:02d}.png")).with_duration(dur)
                          .with_position(("center", 40)).with_effects([vfx.CrossFadeIn(0.3)]))
        for k, (st, d, txt) in enumerate(sub_items):
            sp = subtitle_png(txt, A / f"sub_{si:02d}_{k}.png")
            layers.append(ImageClip(sp).with_start(st).with_duration(d + 0.25).with_position(("center", 1080 - 36 - Image.open(sp).height)))
        scene = CompositeVideoClip(layers, size=(W, H)).with_duration(dur)
        scene_clips.append(scene)
        for st, aud in auds:
            voice_tracks.append(aud.with_start(t_scene + st))
        md += [f"## {si + 1}. {sid.replace('_', ' ').title()}" + (f" — *{pill}*" if pill else ""),
               f"*Visual: {vis['type']}{' — ' + ', '.join(vis.get('images', [])) if vis.get('images') else ''}*", ""]
        md += [f"> {txt}" for txt, _ in sentences] + [""]
        t_scene += dur - XF
        print(f"scene {si + 1:2d} {sid:14s} {dur:5.1f}s")

    faded = [scene_clips[0]] + [c.with_effects([vfx.CrossFadeIn(XF)]) for c in scene_clips[1:]]
    video = concatenate_videoclips(faded, method="compose", padding=-XF, bg_color=(10, 18, 16))
    video = video.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.8)])
    audio = CompositeAudioClip(voice_tracks + [music(video.duration)]).with_duration(video.duration)
    video = video.with_audio(audio)
    if MAX_SECONDS and video.duration > MAX_SECONDS:
        raise SystemExit(f"Video would be {video.duration:.1f}s, over the {MAX_SECONDS}s limit - shorten the script")
    out = HERE / OUT_NAME
    video.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", bitrate="8000k", threads=8,
                          preset="medium", logger=None)
    md.insert(3, f"Total length: {video.duration:.0f} s ({video.duration / 60:.1f} min).")
    (HERE / MD_NAME).write_text("\n".join(md) + "\n")
    print(f"wrote {out} ({video.duration:.1f}s) and {MD_NAME}")


if __name__ == "__main__":
    main()
