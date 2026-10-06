"""End-to-end browser tests of the running app (real backend + real model + React UI).

Start the backend (:8000) and frontend (:5173) first, then:
    .venv/bin/python -m pytest e2e -q
Skipped automatically when the app is not running.
"""
import secrets
import urllib.request

import pytest
from playwright.sync_api import expect, sync_playwright

BASE = "http://127.0.0.1:5173"


def app_running() -> bool:
    try:
        return urllib.request.urlopen(f"{BASE}/api/health", timeout=3).status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not app_running(), reason="FitBot app is not running on :5173/:8000")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(60000)
    yield pg
    ctx.close()


def ask(page, text):
    n = page.locator(".msg-bot").count()
    page.get_by_role("textbox", name="Message").fill(text)
    page.keyboard.press("Enter")
    page.wait_for_function(f"document.querySelectorAll('.msg-bot').length > {n} && !document.querySelector('.typing')")
    return page.locator(".msg-bot").last


def test_full_user_journey(page):
    email, pwd = f"e2e.{secrets.token_hex(4)}@example.com", "E2e-" + secrets.token_urlsafe(10)

    # register -> profile
    page.goto(f"{BASE}/register")
    inputs = page.locator(".auth-card input")
    for i, v in enumerate(["E2E Tester", email, pwd, pwd]):
        inputs.nth(i).fill(v)
    page.get_by_role("button", name="Create account").click()
    expect(page.locator(".profile-form")).to_be_visible()

    # dashboard shows exercise explorer with images
    page.get_by_role("link", name="Dashboard").click()
    expect(page.locator(".ex-card img").first).to_be_visible()

    # chat: exercise cards with images
    page.get_by_role("button", name="New chat").first.click()
    bot = ask(page, "What exercises can I do for chest?")
    expect(bot.locator(".ex-card").first).to_be_visible()
    assert bot.locator(".ex-card img").count() >= 3

    # follow-up: beginner -> only beginner cards
    bot = ask(page, "I'm a beginner.")
    expect(bot.get_by_text("Follow-up")).to_be_visible()
    badges = bot.locator(".ex-card .badge").all_inner_texts()
    assert badges and all(b == "Beginner" for b in badges)

    # dumbbells -> workout plan
    bot = ask(page, "I only have dumbbells.")
    expect(bot.locator(".plan")).to_be_visible()

    # nutrition -> USDA food cards
    bot = ask(page, "What should I eat after this workout?")
    expect(bot.locator(".food-card").first).to_be_visible()

    # safety + out of domain
    bot = ask(page, "I have chest pain when I exercise")
    expect(bot).to_contain_text("medical help")
    bot = ask(page, "What is the capital of France?")
    expect(bot).to_contain_text("focused on fitness")

    # conversation is listed, survives logout + login
    title = "What exercises can I do for chest?"
    expect(page.locator(".conv-item").first).to_contain_text("What exercises")
    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
    page.locator(".auth-card input").nth(0).fill(email)
    page.locator(".auth-card input").nth(1).fill(pwd)
    page.get_by_role("button", name="Log in").click()
    expect(page.locator(".conv-item").first).to_contain_text("What exercises")
    page.locator(".conv-item").first.click()
    expect(page.locator(".msg-user").first).to_have_text(title)


def test_protected_routes_redirect_to_login(page):
    page.goto(f"{BASE}/chat")
    expect(page).to_have_url(f"{BASE}/login")


def test_wrong_password_shows_error(page):
    page.goto(f"{BASE}/login")
    page.locator(".auth-card input").nth(0).fill("nobody@example.com")
    page.locator(".auth-card input").nth(1).fill("wrong-password")
    page.get_by_role("button", name="Log in").click()
    expect(page.get_by_role("alert")).to_contain_text("Incorrect email or password")


def test_save_plan_log_workouts_and_feedback(page):
    email, pwd = f"e2e.{secrets.token_hex(4)}@example.com", "E2e-" + secrets.token_urlsafe(10)
    page.goto(f"{BASE}/register")
    inputs = page.locator(".auth-card input")
    for i, v in enumerate(["Plan Tester", email, pwd, pwd]):
        inputs.nth(i).fill(v)
    page.get_by_role("button", name="Create account").click()
    expect(page.locator(".profile-form")).to_be_visible()

    # chat answer with a plan -> rate it and save the plan
    page.get_by_role("button", name="New chat").first.click()
    bot = ask(page, "Give me a beginner 3-day gym workout")
    expect(bot.locator(".plan")).to_be_visible()
    bot.get_by_role("button", name="Helpful", exact=True).click()
    expect(bot.get_by_role("button", name="Helpful", exact=True)).to_have_attribute("aria-pressed", "true")
    bot.get_by_role("button", name="Save plan").click()
    expect(bot.get_by_text("Saved to My workouts")).to_be_visible()

    # rating survives a reload
    page.reload()
    expect(page.locator(".msg-bot").last.get_by_role("button", name="Helpful", exact=True)).to_have_attribute("aria-pressed", "true")

    # My workouts: saved plan, log a plan day, log an exercise manually
    page.get_by_role("link", name="My workouts").click()
    expect(page.locator(".saved-plan .plan")).to_have_count(1)
    page.locator(".saved-plan").get_by_role("button", name="as done").click()
    expect(page.locator(".saved-plan").get_by_text("Logged today")).to_be_visible()
    # several exercises in one go
    page.get_by_label("Exercise 1", exact=True).fill("Running")
    page.get_by_label("Minutes 1", exact=True).fill("20")
    page.get_by_role("button", name="Add another exercise").click()
    page.get_by_label("Exercise 2", exact=True).fill("Barbell Squat")
    page.get_by_label("Sets 2", exact=True).fill("3")
    page.get_by_label("Reps 2", exact=True).fill("8")
    page.get_by_label("Weight 2", exact=True).fill("40")
    page.get_by_role("button", name="Log 2 exercises").click()
    expect(page.get_by_text("Logged 2 exercises!")).to_be_visible()
    expect(page.locator(".log-row").filter(has_text="Barbell Squat")).to_contain_text("3 × 8 · 40 kg")

    stats = page.locator(".stats .stat strong")
    expect(stats.nth(0)).to_have_text("1")   # active days this week
    expect(stats.nth(1)).to_have_text("🔥1")  # streak
    entries = int(stats.nth(3).inner_text())
    assert entries >= 5                       # plan day exercises + Running + Squat
    expect(page.locator(".log-row").filter(has_text="Running")).to_contain_text("20 min")

    # delete an entry
    page.locator(".log-row").filter(has_text="Running").get_by_role("button").click()
    expect(page.locator(".log-row").filter(has_text="Running")).to_have_count(0)
    expect(stats.nth(3)).to_have_text(str(entries - 1))


def test_dashboard_quick_start_sends_once(page):
    email, pwd = f"e2e.{secrets.token_hex(4)}@example.com", "E2e-" + secrets.token_urlsafe(10)
    page.goto(f"{BASE}/register")
    inputs = page.locator(".auth-card input")
    for i, v in enumerate(["Quick Tester", email, pwd, pwd]):
        inputs.nth(i).fill(v)
    page.get_by_role("button", name="Create account").click()
    expect(page.locator(".profile-form")).to_be_visible()
    page.get_by_role("link", name="Dashboard").click()
    chats = []
    page.on("request", lambda r: chats.append(r) if r.url.endswith("/api/chat") and r.method == "POST" else None)
    page.get_by_role("button", name="Sleep & recovery").click()
    expect(page.locator(".msg-bot")).to_have_count(1)
    page.wait_for_timeout(2500)              # a duplicate request would have arrived by now
    expect(page.locator(".msg-bot")).to_have_count(1)
    expect(page.locator(".msg-user")).to_have_count(1)
    expect(page.locator(".conv-item")).to_have_count(1)
    assert len(chats) == 1
