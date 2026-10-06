"""Record real FitBot footage for the marketing video (headless Chromium via Playwright).

Requires the app running locally (backend :8000, Vite :5173). Produces marketing/raw/demo.webm and
marketing/raw/markers.json (scene start/end times in seconds from the start of the recording).
Everything on screen is the real app answering with the real fine-tuned model.
"""
import json
import secrets
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = Path(__file__).resolve().parent / "raw"
W, H = 1920, 1080
ZOOM = 1.3333   # page zoom: the UI is laid out like a 1440x810 screen but rendered natively at 1920x1080


def api(path, body):
    req = urllib.request.Request(f"{BASE}/api{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.webm"):
        f.unlink()
    email = f"alex.{secrets.token_hex(3)}@example.com"
    token = api("/auth/register", {"name": "Alex Morgan", "email": email,
                                   "password": "Video-" + secrets.token_urlsafe(10)})["access_token"]
    markers, t0 = {}, None

    def mark(name):
        markers[name] = round(time.monotonic() - t0, 2)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, color_scheme="dark",
                                  record_video_dir=str(OUT), record_video_size={"width": W, "height": H})
        ctx.add_init_script(f"localStorage.setItem('fitbot_token', '{token}');"
                            f"document.addEventListener('DOMContentLoaded', () => {{ document.documentElement.style.zoom = '{ZOOM}' }})")
        page = ctx.new_page()
        t0 = time.monotonic()

        def smooth_scroll(dy, steps=25, pause=0.03, selector=None):
            for _ in range(steps):
                if selector:
                    page.eval_on_selector(selector, f"e => e.scrollBy(0, {dy / steps})")
                else:
                    page.mouse.wheel(0, dy / steps)
                time.sleep(pause)

        def ask(text, wait_after=2.5):
            box = page.locator("textarea[aria-label=Message]")
            box.click()
            n_before = page.locator(".msg-bot").count()
            box.type(text, delay=45)
            time.sleep(0.4)
            page.keyboard.press("Enter")
            page.wait_for_function(f"document.querySelectorAll('.msg-bot').length > {n_before} && !document.querySelector('.typing')",
                                   timeout=60000)
            time.sleep(0.4)
            # bring the new answer to the top of the chat view
            page.eval_on_selector(".chat-scroll", """e => { const bots = e.querySelectorAll('.msg-user');
                const last = bots[bots.length - 1]; e.scrollTo({top: last.offsetTop - 24, behavior: 'smooth'}); }""")
            time.sleep(wait_after)

        # ---- Dashboard
        page.goto(f"{BASE}/dashboard")
        page.wait_for_selector(".hero-card")
        page.wait_for_function("document.querySelectorAll('.ex-card img').length >= 4")
        time.sleep(1.0)
        mark("dashboard_start")
        time.sleep(2.0)
        smooth_scroll(470, selector=".page")
        time.sleep(2.5)
        mark("dashboard_end")

        # ---- Chat demo
        page.goto(f"{BASE}/chat")
        page.wait_for_selector(".empty")
        time.sleep(1.0)
        mark("chest_start")
        ask("What exercises can I do for chest?", wait_after=1.5)
        smooth_scroll(330, selector=".chat-scroll")
        time.sleep(2.0)
        mark("chest_end")

        mark("beginner_start")
        ask("I'm a beginner.", wait_after=3.0)
        mark("beginner_end")

        mark("dumbbell_start")
        ask("I only have dumbbells.", wait_after=1.0)
        smooth_scroll(260, selector=".chat-scroll")
        time.sleep(2.5)
        mark("dumbbell_end")

        mark("food_start")
        ask("What should I eat after this workout?", wait_after=1.0)
        smooth_scroll(300, selector=".chat-scroll")
        time.sleep(2.5)
        mark("food_end")

        mark("sleep_start")
        ask("How much should I sleep?", wait_after=3.0)
        mark("sleep_end")

        # ---- New chat: workout plan with day tabs
        page.goto(f"{BASE}/chat")
        page.wait_for_selector(".empty")
        time.sleep(0.8)
        mark("plan_start")
        ask("Give me a beginner 3-day gym workout", wait_after=1.0)
        smooth_scroll(260, selector=".chat-scroll")
        time.sleep(1.2)
        page.get_by_role("tab", name="Day 2").click()
        time.sleep(1.6)
        page.get_by_role("tab", name="Day 3").click()
        time.sleep(1.8)
        mark("plan_end")

        mark("safety_start")
        ask("I have chest pain when I exercise, what should I do?", wait_after=3.0)
        mark("safety_end")

        mark("ood_start")
        ask("What is the capital of France?", wait_after=2.5)
        mark("ood_end")

        ctx.close()
        browser.close()

    video = next(OUT.glob("*.webm"))
    video.rename(OUT / "demo.webm")
    (OUT / "markers.json").write_text(json.dumps(markers, indent=1))
    print(json.dumps(markers, indent=1))


if __name__ == "__main__":
    main()
