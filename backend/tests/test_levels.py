"""Level customisation: beginners get beginner exercises and poses, intermediate and advanced people get harder ones."""
from __future__ import annotations

from app.services.planner import LEVEL_RANK

RANK = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}


def plan_names(engine, level, equipment=None, location="gym"):
    plan = engine.planner.plan(level=level, days=3, goal="muscle_gain", equipment=equipment or ["gym"], location=location)
    return plan, [x for d in plan["days"] for x in d["exercises"]]


def test_beginner_plans_only_use_beginner_movements(engine):
    plan, items = plan_names(engine, "beginner")
    assert items and all(x["difficulty"] == "Beginner" for x in items)
    assert any("Beginner level" in n for n in plan["notes"])


def test_harder_levels_get_harder_exercises_and_more_volume(engine):
    _, beg = plan_names(engine, "beginner")
    _, inter = plan_names(engine, "intermediate")
    _, adv = plan_names(engine, "advanced")
    score = lambda items: sum(RANK[x["difficulty"]] for x in items) / len(items)
    assert score(beg) < score(inter) < score(adv)
    assert all(x["difficulty"] != "Advanced" for x in inter)                 # nothing above the person's level
    assert {x["name"] for x in adv} & {"Deadlift", "Front Barbell Squat", "Push Press", "Mixed Grip Chin", "Bench Press"}
    assert {x["name"] for x in beg}.isdisjoint({x["name"] for x in adv} - {"Plank"})
    assert any(x["sets"] == "4-5" for x in adv) and all(x["sets"] == "2-3" for x in beg)


def test_muscle_workout_and_exercise_lists_follow_the_level(engine):
    for level in ("beginner", "intermediate", "advanced"):
        w = engine.planner.muscle_workout("chest", level=level, equipment=["gym"], location="gym")
        assert all(LEVEL_RANK[x["difficulty"].lower()] <= LEVEL_RANK[level] for x in w["days"][0]["exercises"])
    beg = engine.catalog.exercises_for("back", "beginner", ["gym"], "gym")
    adv = engine.catalog.exercises_for("back", "advanced", ["gym"], "gym")
    assert all(e["difficulty"] == "Beginner" for e in beg)
    assert adv[0]["name"] in ("Deadlift", "Mixed Grip Chin", "Alternating Renegade Row", "One Arm Chin-Up", "Deficit Deadlift")


def test_exercise_api_orders_by_level(client):
    beg = client.get("/exercises?muscle_group=legs&level=beginner").json()["exercises"]
    inter = client.get("/exercises?muscle_group=legs&level=intermediate").json()["exercises"]
    assert beg and all(e["difficulty"] == "Beginner" for e in beg)
    assert inter[0]["difficulty"] == "Intermediate" and all(e["difficulty"] != "Advanced" for e in inter)
    assert client.get("/exercises?level=expert").status_code == 422


def test_chat_uses_the_profile_level(client, auth):
    client.put("/auth/profile", json={"fitness_level": "advanced", "goal": "strength", "equipment": ["gym"], "location": "gym"},
               headers=auth["headers"])
    out = client.post("/chat", json={"message": "Give me a 3 day gym workout plan"}, headers=auth["headers"]).json()
    items = [x for d in out["workout_plan"]["days"] for x in d["exercises"]]
    assert sum(x["difficulty"] != "Beginner" for x in items) > len(items) / 2


def test_yoga_routines_match_the_level(client):
    def main_levels(level):
        r = client.get(f"/yoga/routine?minutes=15&level={level}").json()
        return [s["difficulty"] for s in r["steps"] if s["phase"] not in ("Centre", "Warm up", "Cool down", "Relax")]
    beg, inter, adv = main_levels("Beginner"), main_levels("Intermediate"), main_levels("Advanced")
    assert beg and all(d == "Beginner" for d in beg)
    assert inter.count("Intermediate") >= len(inter) / 2 and "Advanced" not in inter
    assert "Advanced" in adv and adv.count("Beginner") <= len(adv) / 3
