"""Collect REAL FitBot output for the launch film (nothing on screen is invented).

Needs the app running (backend :8000, frontend :5173). Creates a fresh demo account, asks the real model,
and saves:
  build/data.json      chat answers, exercise cards, workout plan, USDA food cards, training-loss curve
  build/shots/*.png    screenshots of the real UI (dark theme, 2x resolution)
"""
from __future__ import annotations

import json
import secrets
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / "build"
API, UI = "http://127.0.0.1:8000", "http://127.0.0.1:5173"

QUESTIONS = {
    "exercises": "What exercises can I do for chest?",
    "plan": "Give me a 3-day home workout plan. I'm a beginner and I only have dumbbells.",
    "nutrition": "What should I eat after working out?",
    "hydration": "How much water should I drink a day?",
    "sleep": "How much should I sleep?",
}


def call(path, body=None, tok=None, method="POST"):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h, method=method)
    raw = urllib.request.urlopen(req, timeout=120).read()
    return json.loads(raw) if raw else None


def main() -> None:
    (BUILD / "shots").mkdir(parents=True, exist_ok=True)
    tok = call("/auth/register", {"name": "Jordan Lee", "email": f"launch.{secrets.token_hex(4)}@example.com",
                                  "password": "Launch-" + secrets.token_urlsafe(10)})["access_token"]
    call("/auth/profile", {"fitness_level": "beginner", "goal": "muscle_gain", "equipment": ["dumbbells"],
                           "location": "home"}, tok, "PUT")

    answers, convs = {}, {}
    for key, q in QUESTIONS.items():
        r = call("/chat", {"message": q}, tok)
        answers[key] = {"question": q, "answer": r["answer"], "intent": r["intent"], "exercises": r["exercises"],
                        "foods": r["foods"], "workout_plan": r["workout_plan"]}
        convs[key] = r["conversation_id"]
        print(f"{key:10s} {r['intent']:20s} ex={len(r['exercises'])} foods={len(r['foods'])} plan={bool(r['workout_plan'])}")

    # demo usage so the "My workouts" screen is not empty (a demo account, shown as UI only)
    plan = answers["plan"]["workout_plan"]
    call("/plans", {"plan": plan}, tok)
    today = date.today()
    log = []
    for back, day in ((2, plan["days"][0]), (1, plan["days"][1]), (0, plan["days"][2])):
        for e in day["exercises"]:
            log.append({"day": str(today - timedelta(days=back)), "exercise": e["name"], "notes": f"{day['day']}: {e['sets']} × {e['reps']}"})
    call("/workouts", log, tok)

    hist = json.loads((ROOT / "evaluation" / "training_run" / "log_history.json").read_text())
    curve = {"train": [[x["step"], x["loss"]] for x in hist if "loss" in x],
             "validation": [[x["step"], x["eval_loss"]] for x in hist if "eval_loss" in x]}
    (BUILD / "data.json").write_text(json.dumps({"answers": answers, "loss_curve": curve}, indent=1))

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
        ctx.add_init_script(f"localStorage.setItem('fitbot_token', '{tok}')")
        pg = ctx.new_page()

        def shot(name, url, prep=None, wait=2500):
            pg.goto(UI + url)
            pg.wait_for_timeout(wait)
            if prep:
                prep()
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(BUILD / "shots" / f"{name}.png"))

        shot("dashboard", "/dashboard")
        shot("chat_exercises", f"/chat/{convs['exercises']}",
             lambda: pg.evaluate("document.querySelector('.chat-scroll').scrollTop = 0"))
        shot("chat_plan", f"/chat/{convs['plan']}",
             lambda: pg.locator(".plan").first.scroll_into_view_if_needed())
        shot("chat_food", f"/chat/{convs['nutrition']}",
             lambda: pg.locator(".food-grid").first.scroll_into_view_if_needed())
        shot("workouts", "/workouts")
        shot("profile", "/profile")
        ctx2 = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
        pg2 = ctx2.new_page()
        pg2.goto(UI + "/login")
        pg2.wait_for_timeout(2000)
        pg2.screenshot(path=str(BUILD / "shots" / "login.png"))
        b.close()
    print("saved", sorted(x.name for x in (BUILD / "shots").iterdir()))


if __name__ == "__main__":
    main()
