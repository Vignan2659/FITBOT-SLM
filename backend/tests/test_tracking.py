from datetime import date, timedelta

from tests.conftest import register


def other_headers(client):
    _, _, token = register(client, name="Other")
    return {"Authorization": f"Bearer {token}"}


def test_save_plan_from_chat_answer(client, auth):
    h = auth["headers"]
    plan = client.post("/chat", json={"message": "Give me a beginner 3-day gym workout"}, headers=h).json()["workout_plan"]
    assert plan and len(plan["days"]) == 3
    r = client.post("/plans", json={"plan": plan}, headers=h)
    assert r.status_code == 201 and r.json()["title"] == plan["title"]
    pid = r.json()["id"]
    assert [p["id"] for p in client.get("/plans", headers=h).json()] == [pid]
    # private to the owner
    h2 = other_headers(client)
    assert client.get("/plans", headers=h2).json() == []
    assert client.delete(f"/plans/{pid}", headers=h2).status_code == 404
    assert client.delete(f"/plans/{pid}", headers=h).status_code == 204
    assert client.get("/plans", headers=h).json() == []


def test_plan_validation_and_auth(client, auth):
    assert client.post("/plans", json={"plan": {"days": []}}, headers=auth["headers"]).status_code == 422
    assert client.get("/plans").status_code == 401
    assert client.get("/workouts").status_code == 401


def test_workout_log_and_stats(client, auth):
    h = auth["headers"]
    today = date(2026, 10, 7)  # a Wednesday
    entries = [
        {"day": str(today), "exercise": "Barbell Squat", "sets": 3, "reps": 8, "weight_kg": 60},
        {"day": str(today), "exercise": "Push-Up", "sets": 3, "reps": 12},
        {"day": str(today - timedelta(days=1)), "exercise": "Barbell Squat", "sets": 3, "reps": 8, "weight_kg": 55},
        {"day": str(today - timedelta(days=2)), "exercise": "Running", "minutes": 25},
        {"day": str(today - timedelta(days=9)), "exercise": "Push-Up", "sets": 2, "reps": 10},
    ]
    r = client.post("/workouts", json=entries, headers=h)
    assert r.status_code == 201 and len(r.json()) == 5
    logs = client.get("/workouts", headers=h).json()
    assert len(logs) == 5 and logs[0]["day"] == str(today)

    s = client.get("/workouts/stats", params={"today": str(today), "weeks": 4}, headers=h).json()
    assert s["total_entries"] == 5 and s["active_days"] == 4
    assert s["current_streak"] == 3            # Mon, Tue, Wed
    assert s["this_week"] == 3
    assert [w["active_days"] for w in s["weeks"]] == [0, 0, 1, 3]
    squat = next(t for t in s["top_exercises"] if t["exercise"] == "Barbell Squat")
    assert squat == {"exercise": "Barbell Squat", "times": 2, "best_weight_kg": 60.0}

    # private + deletable
    h2 = other_headers(client)
    assert client.get("/workouts", headers=h2).json() == []
    assert client.delete(f"/workouts/{logs[0]['id']}", headers=h2).status_code == 404
    assert client.delete(f"/workouts/{logs[0]['id']}", headers=h).status_code == 204
    assert len(client.get("/workouts", headers=h).json()) == 4


def test_workout_validation(client, auth):
    h = auth["headers"]
    assert client.post("/workouts", json=[], headers=h).status_code == 422
    assert client.post("/workouts", json=[{"day": "2026-10-07", "exercise": "  "}], headers=h).status_code == 422
    assert client.post("/workouts", json=[{"day": "2026-10-07", "exercise": "Squat", "reps": -1}],
                       headers=h).status_code == 422


def test_message_feedback(client, auth):
    h = auth["headers"]
    r = client.post("/chat", json={"message": "How much should I sleep?"}, headers=h).json()
    mid, cid = r["message_id"], r["conversation_id"]
    assert client.put(f"/messages/{mid}/feedback", json={"rating": 1}, headers=h).json() == {"message_id": mid, "rating": 1}
    msgs = client.get(f"/conversations/{cid}", headers=h).json()["messages"]
    assert [m["feedback"] for m in msgs] == [0, 1]
    client.put(f"/messages/{mid}/feedback", json={"rating": -1}, headers=h)
    assert client.get(f"/conversations/{cid}", headers=h).json()["messages"][1]["feedback"] == -1
    client.put(f"/messages/{mid}/feedback", json={"rating": 0}, headers=h)
    assert client.get(f"/conversations/{cid}", headers=h).json()["messages"][1]["feedback"] == 0
    # invalid rating, user messages, other users
    assert client.put(f"/messages/{mid}/feedback", json={"rating": 5}, headers=h).status_code == 422
    assert client.put(f"/messages/{mid - 1}/feedback", json={"rating": 1}, headers=h).status_code == 404
    assert client.put(f"/messages/{mid}/feedback", json={"rating": 1}, headers=other_headers(client)).status_code == 404
