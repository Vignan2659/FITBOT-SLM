"""End-to-end checks with the REAL fine-tuned SLM (run: pytest -m slm). Skipped if no model is installed."""
import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.slm


@pytest.fixture(scope="module")
def real_engine():
    s = get_settings()
    path = s.resolve(s.fitbot_model_path)
    if not (path / "config.json").exists():
        pytest.skip(f"no fine-tuned model at {path}")
    from app.main import build_engine
    from app.ml.slm import FitBotSLM
    slm = FitBotSLM(path, s.fitbot_base_model, s.fitbot_device, s.fitbot_max_new_tokens)
    engine, _ = build_engine(s, generate=slm.generate)
    return engine


def test_demo_conversation(real_engine):
    hist, state = [], {}
    turns = ["What exercises can I do for chest?", "I'm a beginner.", "I only have dumbbells.",
             "What should I eat after this workout?", "How much should I sleep?"]
    out = []
    for q in turns:
        r, state = real_engine.respond(q, hist, state, None)
        hist += [{"role": "user", "content": q}, {"role": "assistant", "content": r["answer"]}]
        out.append(r)
        assert r["model"]["generated"] and len(r["answer"]) > 20
        assert "focused on fitness" not in r["answer"]
    assert out[0]["exercises"] and out[1]["is_followup"] and out[2]["workout_plan"]
    assert out[3]["foods"] and "protein" in out[3]["answer"].lower()
    assert "7" in out[4]["answer"] or "seven" in out[4]["answer"].lower()


def test_usda_numbers_are_grounded(real_engine):
    r, _ = real_engine.respond("How much protein does an egg contain?", [], {}, None)
    assert "6.3" in r["answer"]
