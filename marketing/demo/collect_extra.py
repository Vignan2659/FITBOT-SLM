"""Extra real material for the demo film: a saved plan, a week of logged workouts and the My workouts page.
Needs FitBot running on http://127.0.0.1:8000. Writes build/extra.json and build/shots/workouts.jpg."""
import json, secrets
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
from collect_demo import API, BUILD, call, profile, ask

tok = call("/auth/register", {"name": "Arjun Rao", "email": f"demo.{secrets.token_hex(4)}@example.com",
                              "password": "Demo-" + secrets.token_urlsafe(10)})["access_token"]
profile(tok, "intermediate")
plan = ask(tok, "Give me a 3 day gym workout plan")["workout_plan"]
call("/plans", {"plan": plan}, tok)
today, log = date.today(), []
for back in range(4, -1, -1):
    day = plan["days"][(4 - back) % len(plan["days"])]
    for e in day["exercises"]:
        log.append({"day": str(today - timedelta(days=back)), "exercise": e["name"], "notes": f"{e['sets']} x {e['reps']}"})
call("/workouts", log, tok)
stats = call("/workouts/stats?today=" + str(today), tok=tok, method="GET")
(BUILD / "extra.json").write_text(json.dumps({"plan_title": plan.get("title"), "stats": stats, "logged": len(log)}, indent=1))
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
    ctx.add_init_script(f"localStorage.setItem('fitbot_token', '{tok}')")
    pg = ctx.new_page(); pg.goto(API + "/workouts"); pg.wait_for_timeout(3500)
    pg.screenshot(path=str(BUILD / "shots" / "workouts.jpg"), type="jpeg", quality=92)
    b.close()
print("EXTRA-DONE", stats)
