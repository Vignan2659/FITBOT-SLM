"""Test fixtures.

API tests run the full pipeline (safety, intent classifier, slots, dialogue state, retrieval,
planner, database) but replace the SLM with a deterministic stub so tests are fast and do not
depend on model weights. The real fine-tuned model is exercised by tests marked `slm`
(tests/test_slm_integration.py) and by evaluation/run_test_suites.py.
"""
from __future__ import annotations

import os 
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="fitbot-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["FITBOT_LOAD_MODEL"] = "false"
os.environ["JWT_SECRET"] = "test-secret-key-for-fitbot-tests-only-0123456789"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app, build_engine, fastapi_app  # noqa: E402

GENERATED: list[list[dict]] = []   # prompts sent to the stub, for assertions


def stub_generate(messages: list[dict]) -> tuple[str, float]:
    """Test double for the SLM: echoes which reference lines it received."""
    GENERATED.append(messages)
    system = messages[0]["content"]
    refs = [l[2:] for l in system.split("\n") if l.startswith("- ")]
    head = refs[0].split("|")[0].strip() if refs else "general guidance"
    return f"[stub answer] Based on: {head}.", 0.0


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        fastapi_app.state.chat_engine, fastapi_app.state.engine_info = build_engine(get_settings(), generate=stub_generate)
        yield c


@pytest.fixture(scope="session")
def engine(client):
    return fastapi_app.state.chat_engine


def register(client, name="Test User", password="password123"):
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return email, password, r.json()["access_token"]


@pytest.fixture
def auth(client):
    email, password, token = register(client)
    return {"email": email, "password": password, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
