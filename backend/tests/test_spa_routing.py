"""Browser page loads of client-side routes (e.g. /workouts) must reach the web app, not the API route."""
import asyncio

from app.main import SPA_PREFIX, StripApiPrefix


def route(path: str, accept: bytes, method: str = "GET", serve_spa: bool = True) -> str:
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["path"])

    asyncio.run(StripApiPrefix(inner, serve_spa)({"type": "http", "method": method, "path": path,
                                                  "headers": [(b"accept", accept)]}, None, None))
    return seen[0]


def test_page_load_goes_to_web_app():
    assert route("/workouts", b"text/html,application/xhtml+xml") == SPA_PREFIX + "/workouts"
    assert route("/chat/3", b"text/html") == SPA_PREFIX + "/chat/3"


def test_api_calls_unchanged():
    assert route("/api/workouts", b"*/*") == "/workouts"
    assert route("/workouts", b"application/json") == "/workouts"
    assert route("/workouts", b"text/html", method="POST") == "/workouts"
    for p in ("/health", "/docs", "/openapi.json", "/assets/index.js"):
        assert route(p, b"text/html") == p


def test_no_rewrite_without_built_frontend():
    assert route("/workouts", b"text/html", serve_spa=False) == "/workouts"
