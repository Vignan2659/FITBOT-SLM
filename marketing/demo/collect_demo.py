"""Collect real FitBot output and UI screenshots for the demo film. Needs FitBot running on http://127.0.0.1:8000.

    .venv/bin/python marketing/demo/collect_demo.py

Writes marketing/demo/build/data.json, build/shots/*.jpg and build/img/* (exercise photos of the answer cards).
A fresh demo account is created; its band numbers are typed in as a demo week (shown as UI only).
"""
from __future__ import annotations

import json
import random
import secrets
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
API = "http://127.0.0.1:8000"


def call(path, body=None, tok=None, method="POST"):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method=method if body is not None or method != "POST" else "GET")
    raw = urllib.request.urlopen(req, timeout=300).read()
    return json.loads(raw) if raw else None


def profile(tok, level, equipment=("gym",), location="gym"):
    call("/auth/profile", {"age": 24, "fitness_level": level, "goal": "muscle_gain", "equipment": list(equipment),
                           "location": location}, tok, "PUT")


def ask(tok, q):
    r = call("/chat", {"message": q}, tok)
    print(f"{r['category']:16s} {q}")
    return r


def main() -> None:
    for d in ("shots", "img"):
        (BUILD / d).mkdir(parents=True, exist_ok=True)
    tok = call("/auth/register", {"name": "Arjun Rao", "email": f"demo.{secrets.token_hex(4)}@example.com",
                                  "password": "Demo-" + secrets.token_urlsafe(10)})["access_token"]
    data = {}
    plans = {}
    for level in ("beginner", "intermediate", "advanced"):
        profile(tok, level)
        plans[level] = ask(tok, "Give me a 3 day gym workout plan")["workout_plan"]
    data["plans"] = plans

    chest = ask(tok, "What exercises can I do for chest?")
    data["chest"] = {"question": "What exercises can I do for chest?", "answer": chest["answer"],
                     "exercises": chest["exercises"][:4], "conversation_id": chest["conversation_id"]}
    for i, e in enumerate(chest["exercises"][:4]):
        for j, url in enumerate((e.get("image_urls") or [e["image_url"]])[:2]):
            (BUILD / "img" / f"ex{i}_{j}.jpg").write_bytes(urllib.request.urlopen(url, timeout=60).read())

    food = ask(tok, "How many calories and how much protein are in chicken breast and rice?")
    data["food"] = {"answer": food["answer"], "foods": food["foods"][:2]}
    data["routine"] = call("/yoga/routine?minutes=15&level=Beginner&goal=flexibility", method="GET")

    today = date.today()
    rnd = random.Random(7)
    for back in range(13, 0, -1):
        call("/wearables/day", {"day": str(today - timedelta(days=back)), "steps": rnd.randint(6200, 11800),
                                "sleep_minutes": rnd.randint(380, 480), "resting_hr": rnd.randint(56, 61),
                                "stress": rnd.randint(25, 55), "hrv_ms": rnd.randint(48, 64),
                                "active_kcal": rnd.randint(380, 720)}, tok, "PUT")
    call("/wearables/day", {"day": str(today), "steps": 9321, "sleep_minutes": 388, "resting_hr": 64, "stress": 72,
                            "hrv_ms": 41, "active_kcal": 512}, tok, "PUT")
    band = ask(tok, "Am I recovered enough to train today?")
    data["band"] = {"answer": band["answer"], "card": band["band"], "conversation_id": band["conversation_id"]}
    data["band_summary"] = call("/wearables/summary", tok=tok, method="GET")

    safe1 = ask(tok, "My knee hurts when I squat. What injury do I have?")
    safe2 = ask(tok, "How can I lose 10 kg in one week by not eating?")
    data["safety"] = [{"q": "My knee hurts when I squat. What injury do I have?", "a": safe1["answer"]},
                      {"q": "How can I lose 10 kg in one week by not eating?", "a": safe2["answer"]}]
    (BUILD / "data.json").write_text(json.dumps(data, indent=1))

    profile(tok, "intermediate")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
        ctx.add_init_script(f"localStorage.setItem('fitbot_token', '{tok}')")
        pg = ctx.new_page()

        def shot(name, url, prep=None, wait=3000):
            pg.goto(API + url)
            pg.wait_for_timeout(wait)
            if prep:
                prep()
                pg.wait_for_timeout(700)
            pg.screenshot(path=str(BUILD / "shots" / f"{name}.jpg"), type="jpeg", quality=92)

        shot("dashboard", "/dashboard")
        shot("chat_chest", f"/chat/{chest['conversation_id']}",
             lambda: pg.evaluate("document.querySelector('.chat-scroll').scrollTop = 0"))
        shot("chat_band", f"/chat/{band['conversation_id']}")
        shot("bands", "/bands")
        shot("yoga", "/yoga")
        shot("yoga_pose", "/yoga/warrior-ii")
        shot("yoga_routine", "/yoga?tab=routine")
        b.close()
    print("COLLECT-DONE", sorted(x.name for x in (BUILD / "shots").iterdir()))


if __name__ == "__main__":
    main()
