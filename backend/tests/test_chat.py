"""Chat pipeline tests through the HTTP API (SLM replaced by a stub, everything else real)."""
from tests.conftest import GENERATED

OOD = "I'm focused on fitness, nutrition and wellness"
DISCLAIMER = "not a substitute for professional medical advice"


def chat(client, h, message, cid=None):
    r = client.post("/chat", json={"message": message, "conversation_id": cid}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_chat_creates_conversation_and_history(client, auth):
    h = auth["headers"]
    r = chat(client, h, "What exercises can I do for chest?")
    assert r["conversation_id"] and r["conversation_title"].startswith("What exercises can I do for chest")
    assert r["disclaimer"].endswith("professional medical advice.")
    conv = client.get(f"/conversations/{r['conversation_id']}", headers=h).json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][1]["payload"]["exercises"], "structured cards are stored with the message"


def test_exercise_cards_with_images(client, auth):
    r = chat(client, auth["headers"], "What exercises can I do for chest?")
    assert r["intent"] == "exercise_search"
    names = [e["name"] for e in r["exercises"]]
    assert "Bench Press" in names and "Push-Ups" in names
    for e in r["exercises"]:
        assert e["image_url"].startswith("https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/")
        assert e["target_muscles"] and e["equipment"] and e["difficulty"] and e["instructions"] and e["safety_tips"]
        assert e["muscle_group"] == "chest"


def test_follow_up_context_beginner_then_dumbbells(client, auth):
    h = auth["headers"]
    r1 = chat(client, h, "What exercises can I do for chest?")
    cid = r1["conversation_id"]
    r2 = chat(client, h, "I'm a beginner.", cid)
    assert r2["is_followup"] and r2["intent"] == "exercise_search"
    assert r2["exercises"] and all(e["difficulty"] == "Beginner" for e in r2["exercises"])
    assert all(e["muscle_group"] == "chest" for e in r2["exercises"])
    r3 = chat(client, h, "I only have dumbbells.", cid)
    assert r3["is_followup"] and r3["workout_plan"] is not None
    plan_ex = r3["workout_plan"]["days"][0]["exercises"]
    assert plan_ex and all(x["equipment"] in ("Dumbbells", "Bodyweight") for x in plan_ex)
    assert all(e["muscle_group"] == "chest" for e in r3["exercises"])
    assert r3["workout_plan"]["level"] == "Beginner"
    # the SLM received the previous turns as history
    last_prompt = GENERATED[-1]
    assert any(m["role"] == "assistant" for m in last_prompt[1:-1])
    r4 = chat(client, h, "What should I eat after this workout?", cid)
    assert r4["intent"] == "nutrition_question" and r4["foods"]
    assert any("post_workout" in str(f) or f["name"] for f in r4["foods"])


def test_food_question_uses_usda_values(client, auth):
    r = chat(client, auth["headers"], "How much protein does an egg contain?")
    assert r["foods"], r
    egg = r["foods"][0]
    assert egg["name"].startswith("Egg") and egg["fdc_id"] in (173424, 171287)
    assert egg["portion"]["description"] == "1 large" and egg["portion"]["grams"] == 50.0
    assert egg["nutrients"]["protein_g"] == 6.3     # 12.6 g/100 g x 50 g large egg (USDA SR Legacy)
    assert "USDA" in egg["source"]
    assert any(s["type"] == "nutrition" for s in r["sources"])


def test_food_topic_cards(client, auth):
    r = chat(client, auth["headers"], "What are good vegetarian protein sources?")
    assert r["foods"] and all("vegetarian" in str(f["group"]) or f["highlights"] for f in r["foods"])
    assert all("High protein" in f["highlights"] for f in r["foods"])


def test_workout_plan_structure(client, auth):
    r = chat(client, auth["headers"], "Give me a beginner 3-day gym workout")
    plan = r["workout_plan"]
    assert r["intent"] == "workout_plan" and plan and len(plan["days"]) == 3
    for d in plan["days"]:
        assert d["day"] and d["exercises"]
        for e in d["exercises"]:
            assert e["sets"] and e["reps"] and e["rest"] and e["difficulty"] and e["image_url"]


def test_out_of_domain(client, auth):
    r = chat(client, auth["headers"], "What is the capital of France?")
    assert r["intent"] == "out_of_domain" and r["answer"].startswith(OOD)
    assert not r["exercises"] and not r["foods"]


def test_safety_guardrail(client, auth):
    r = chat(client, auth["headers"], "I have chest pain when I exercise, what should I do?")
    assert r["intent"] == "medical_safety" and r["safety"]["guardrail"]
    assert "doctor" in r["answer"].lower() and DISCLAIMER in r["answer"]
    assert not r["exercises"], "chest pain must not trigger chest exercise cards"


def test_soft_medical_gets_referral(client, auth):
    r = chat(client, auth["headers"], "I'm pregnant, what exercise is safe for me?")
    assert r["intent"] == "medical_safety" and not r["safety"]["guardrail"]
    assert DISCLAIMER in r["answer"] and "healthcare" in r["answer"].lower()


def test_sleep_question_retrieves_guidance(client, auth):
    r = chat(client, auth["headers"], "How much should I sleep?")
    assert r["intent"] == "sleep"
    assert any("sleep" in s["title"].lower() for s in r["sources"])


def test_chat_history_survives_relogin(client, auth):
    h = auth["headers"]
    r = chat(client, h, "How much water should I drink?")
    cid = r["conversation_id"]
    client.post("/auth/logout", headers=h)
    token = client.post("/auth/login", json={"email": auth["email"], "password": auth["password"]}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {token}"}
    convs = client.get("/conversations", headers=h2).json()
    assert any(c["id"] == cid for c in convs)
    msgs = client.get(f"/conversations/{cid}", headers=h2).json()["messages"]
    assert msgs[0]["content"] == "How much water should I drink?"


def test_profile_personalisation_reaches_prompt(client, auth):
    h = auth["headers"]
    client.put("/auth/profile", json={"fitness_level": "beginner", "goal": "weight_loss", "equipment": ["dumbbells"],
                                      "location": "home"}, headers=h)
    r = chat(client, h, "Make me a workout plan")
    assert r["workout_plan"]["level"] == "Beginner" and r["workout_plan"]["location"] == "home"
    assert "User profile:" in GENERATED[-1][0]["content"] and "weight loss" in GENERATED[-1][0]["content"]


def test_empty_message_rejected(client, auth):
    assert client.post("/chat", json={"message": "   "}, headers=auth["headers"]).status_code == 422


def test_new_request_does_not_reuse_stale_topic(client, auth):
    """Regression: chest -> sleep -> 'beginner 3-day gym workout' must give a full plan, not a chest workout."""
    h = auth["headers"]
    cid = chat(client, h, "What exercises can I do for chest?")["conversation_id"]
    chat(client, h, "How much should I sleep?", cid)
    r = chat(client, h, "Give me a beginner 3-day gym workout", cid)
    assert not r["is_followup"] and r["intent"] in ("workout_plan", "gym_workout")
    assert r["workout_plan"] and len(r["workout_plan"]["days"]) == 3
    groups = {e["muscle_group"] for d in r["workout_plan"]["days"] for e in d["exercises"]}
    assert len(groups) > 2, "should be a full-body plan"
    r2 = chat(client, h, "I'm a beginner.", cid)
    assert all(e["muscle_group"] != "chest" for e in r2["exercises"]) or r2["workout_plan"]


def test_explicit_gym_overrides_remembered_equipment(client, auth):
    h = auth["headers"]
    cid = chat(client, h, "What exercises can I do for chest?")["conversation_id"]
    chat(client, h, "I only have dumbbells.", cid)
    r = chat(client, h, "Give me a beginner 3-day gym workout", cid)
    assert r["workout_plan"]["location"] == "gym"


def test_chat_rate_limit(client, auth, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "chat_rate_per_min", 2)
    h = auth["headers"]
    assert client.post("/chat", json={"message": "How much should I sleep?"}, headers=h).status_code == 200
    assert client.post("/chat", json={"message": "How much should I sleep?"}, headers=h).status_code == 200
    assert client.post("/chat", json={"message": "How much should I sleep?"}, headers=h).status_code == 429


def test_api_prefix_is_accepted(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/exercises/bench press").json()["name"] == "Bench Press"
