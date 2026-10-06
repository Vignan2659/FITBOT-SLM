"""Extra real-app footage for the explainer video: register -> profile -> exercise instructions (desktop),
and a phone-sized chat (mobile). Requires the app running (backend :8000, Vite :5173).
Outputs marketing/raw/extras.webm, marketing/raw/mobile.webm, marketing/raw/extras_markers.json
"""
import json
import secrets
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = Path(__file__).resolve().parent / "raw"
ZOOM_JS = "document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = '%s' })"


def api(path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}/api{path}", data=json.dumps(body).encode(), headers=headers, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def newest_webm(before):
    after = set(OUT.glob("*.webm")) - before
    return max(after, key=lambda p: p.stat().st_mtime)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    markers = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---------------- desktop: register -> profile -> instructions
        before = set(OUT.glob("*.webm"))
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, color_scheme="dark",
                                  record_video_dir=str(OUT), record_video_size={"width": 1920, "height": 1080})
        ctx.add_init_script(ZOOM_JS % "1.3333")
        page = ctx.new_page()
        t0 = time.monotonic()
        mark = lambda k: markers.__setitem__(k, round(time.monotonic() - t0, 2))  # noqa: E731

        page.goto(f"{BASE}/register")
        page.wait_for_selector(".auth-card")
        time.sleep(0.8)
        mark("register_start")
        fields = page.locator(".auth-card input")
        pwd = "Demo-" + secrets.token_urlsafe(10)
        for i, val in enumerate(["Jordan Lee", f"jordan.{secrets.token_hex(3)}@example.com", pwd, pwd]):
            fields.nth(i).click()
            fields.nth(i).type(val, delay=35)
        time.sleep(0.4)
        page.get_by_role("button", name="Create account").click()
        page.wait_for_selector(".profile-form")
        time.sleep(0.6)
        mark("register_end")

        mark("profile_start")
        page.locator(".profile-form input").nth(0).type("28", delay=60)
        selects = page.locator(".profile-form select")
        for i, v in enumerate(["beginner", "weight_loss", "vegetarian", "home"]):
            selects.nth(i).select_option(v)
            time.sleep(0.35)
        page.get_by_role("button", name="dumbbells").click()
        time.sleep(0.4)
        page.get_by_role("button", name="Save profile").click()
        page.wait_for_selector(".form-ok")
        time.sleep(1.8)
        mark("profile_end")

        mark("instructions_start")
        page.get_by_role("link", name="Dashboard").click()
        page.wait_for_function("document.querySelectorAll('.ex-card img').length >= 4")
        time.sleep(0.8)
        page.eval_on_selector(".page", "e => e.scrollTo({top: 520, behavior: 'smooth'})")
        time.sleep(1.2)
        page.get_by_role("button", name="View instructions").first.click()
        time.sleep(0.5)
        page.eval_on_selector(".page", "e => e.scrollBy({top: 260, behavior: 'smooth'})")
        time.sleep(3.0)
        mark("instructions_end")
        token = page.evaluate("localStorage.getItem('fitbot_token')")
        ctx.close()
        newest_webm(before).rename(OUT / "extras.webm")

        # ---------------- mobile: phone-sized chat with cards + drawer
        conv = api("/chat", {"message": "Give me some leg exercises I can do at home"}, token)["conversation_id"]
        before = set(OUT.glob("*.webm"))
        mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True,
                                   has_touch=True, color_scheme="dark", record_video_dir=str(OUT),
                                   record_video_size={"width": 390, "height": 844})
        mctx.add_init_script(f"localStorage.setItem('fitbot_token', '{token}')")
        m = mctx.new_page()
        t1 = time.monotonic()
        m.goto(f"{BASE}/chat/{conv}")
        m.wait_for_selector(".ex-card img")
        time.sleep(1.5)
        markers["mobile_start"] = round(time.monotonic() - t1, 2)
        for _ in range(30):
            m.eval_on_selector(".chat-scroll", "e => e.scrollBy(0, 22)")
            time.sleep(0.05)
        time.sleep(1.2)
        m.get_by_role("button", name="Open menu").click()
        time.sleep(2.2)
        markers["mobile_end"] = round(time.monotonic() - t1, 2)
        mctx.close()
        newest_webm(before).rename(OUT / "mobile.webm")
        browser.close()

    (OUT / "extras_markers.json").write_text(json.dumps(markers, indent=1))
    print(json.dumps(markers, indent=1))


if __name__ == "__main__":
    main()
