"""Yoga module: data, API, routine builder and chat pipeline (SLM replaced by the stub)."""
import json
from pathlib import Path

import pytest

from tests.conftest import GENERATED

ROOT = Path(__file__).resolve().parents[2]
POSES = json.loads((ROOT / "data" / "yoga" / "yoga_poses.json").read_text(encoding="utf-8"))
SCHEMA = ["name", "alternative_names", "category", "difficulty", "target_areas", "benefits", "instructions", "breathing",
          "duration", "recommended_repetitions", "beginner_modification", "advanced_variation", "common_mistakes",
          "safety_tips", "contraindications", "equipment", "suitable_for", "image", "motion_image", "tags"]


def chat(client, h, message, cid=None):
    r = client.post("/chat", json={"message": message, "conversation_id": cid}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ data and visuals
def test_dataset_has_full_schema_and_visuals():
    assert len(POSES) >= 50
    levels = {p["difficulty"] for p in POSES}
    assert levels == {"Beginner", "Intermediate", "Advanced"}
    required = {"Mountain Pose", "Child's Pose", "Cat-Cow", "Cobra Pose", "Downward-Facing Dog", "Easy Pose",
                "Standing Forward Fold", "Bridge Pose", "Tree Pose", "Warrior I", "Warrior II", "Triangle Pose",
                "Extended Side Angle", "Half Moon Pose", "Chair Pose", "Boat Pose", "Camel Pose", "Bow Pose",
                "Pigeon Pose", "Crow Pose", "Head-to-Knee Pose"}
    assert required <= {p["name"] for p in POSES}
    for p in POSES:
        for key in SCHEMA:
            assert p[key] not in (None, "", []), (p["slug"], key)
        motion = ROOT / "frontend" / "public" / p["motion_image"].lstrip("/")
        assert motion.exists() and "<animate" in motion.read_text(), p["slug"]
        assert len(p["frames"]) in (2, 3)
        for f in p["frames"]:
            assert (ROOT / "frontend" / "public" / f.lstrip("/")).exists()
        assert set(p["related"]) <= {q["slug"] for q in POSES}


def test_advanced_poses_carry_safety_guidance():
    for p in POSES:
        if p["difficulty"] == "Advanced":
            assert p["contraindications"] and p["safety_tips"]
            assert "teacher" in " ".join(p["instructions"] + p["safety_tips"]).lower()


# ------------------------------------------------------------------ API
def test_yoga_poses_list_filters_and_search(client):
    r = client.get("/yoga/poses").json()
    assert r["count"] == len(POSES)
    assert {"slug", "name", "motion_image", "difficulty", "category"} <= set(r["poses"][0])
    beg = client.get("/yoga/poses", params={"difficulty": "beginner"}).json()
    assert beg["count"] and all(p["difficulty"] == "Beginner" for p in beg["poses"])
    hips = client.get("/yoga/poses", params={"area": "hips", "goal": "flexibility"}).json()
    assert hips["count"] and all("hips" in p["body_areas"] and "flexibility" in p["goals"] for p in hips["poses"])
    assert client.get("/yoga/poses", params={"q": "virabhadrasana"}).json()["count"] >= 3
    assert client.get("/yoga/poses", params={"goal": "flying"}).status_code == 422


def test_yoga_pose_detail_related_and_404(client):
    p = client.get("/yoga/poses/warrior-ii").json()
    assert p["name"] == "Warrior II" and len(p["instructions"]) >= 4 and p["related_poses"]
    assert p["frames"] and p["frame_labels"] == ["Start", "Transition", "Final"]
    assert client.get("/yoga/poses/downward dog").json()["slug"] == "downward-dog"
    assert client.get("/yoga/poses/not-a-pose").status_code == 404


def test_yoga_filters_endpoint(client):
    f = client.get("/yoga/filters").json()
    assert f["total"] == len(POSES)
    assert {d["value"] for d in f["difficulty"]} == {"Beginner", "Intermediate", "Advanced"}
    assert {"flexibility", "stress_relief", "weight_management"} <= {g["value"] for g in f["goals"]}


@pytest.mark.parametrize("minutes,level,goal", [(5, None, None), (15, "beginner", None), (30, "intermediate", "strength"),
                                                (20, None, "relaxation"), (60, "advanced", "flexibility")])
def test_routine_fills_exact_time(client, minutes, level, goal):
    params = {"minutes": minutes, **({"level": level} if level else {}), **({"goal": goal} if goal else {})}
    r = client.get("/yoga/routine", params=params).json()
    assert sum(s["minutes"] for s in r["steps"]) == pytest.approx(minutes)
    assert r["steps"][-1]["slug"] in ("corpse-pose", "body-scan-meditation")
    slugs = [s["slug"] for s in r["steps"]]
    assert len(slugs) == len(set(slugs)), "no pose repeats"
    allowed = {"beginner": {"Beginner"}, "intermediate": {"Beginner", "Intermediate"}}.get(level or "beginner")
    if allowed:
        assert {s["difficulty"] for s in r["steps"]} <= allowed
    assert not any(s["phase"] == "Inversion" for s in r["steps"]), "routines never include inversions"


def test_health_reports_yoga_count(client):
    assert client.get("/health").json()["database"]["yoga_poses"] == len(POSES)


# ------------------------------------------------------------------ chat pipeline
@pytest.mark.parametrize("q,mode", [
    ("Give me a beginner yoga routine.", "routine"),
    ("Which yoga poses can improve flexibility?", "list"),
    ("Give me yoga for recovery after a workout.", "routine"),
    ("I have 15 minutes. Give me a yoga routine.", "routine"),
    ("Give me beginner yoga for the morning.", "routine"),
    ("Which yoga poses target the hips?", "list"),
    ("Explain how to perform Warrior II.", "detail"),
])
def test_chat_yoga_questions(client, auth, q, mode):
    r = chat(client, auth["headers"], q)
    assert r["intent"] == "yoga"
    system = GENERATED[-1][0]["content"]
    assert "yoga" in system.lower(),"yoga facts are passed to the SLM as reference information"
    if mode == "routine":
        rt = r["yoga_routine"]
        assert rt and rt["steps"] and not r["yoga_poses"]
        assert "Yoga routine:" in system
    elif mode == "list":
        assert len(r["yoga_poses"]) >= 4 and r["yoga_routine"] is None
    else:
        assert r["yoga_poses"][0]["name"] == "Warrior II"
        assert "How to do Warrior II" in system


def test_chat_yoga_specifics(client, auth):
    h = auth["headers"]
    r = chat(client, h, "Which yoga poses target the hips?")
    assert all("hips" in p["body_areas"] for p in r["yoga_poses"][:3])
    r = chat(client, h, "Give me beginner yoga for the morning.")
    assert r["yoga_routine"]["time_of_day"] == "morning" and r["yoga_routine"]["level"] == "Beginner"
    r = chat(client, h, "I have 15 minutes. Give me a yoga routine.")
    assert r["yoga_routine"]["minutes"] == 15


def test_chat_yoga_follow_up_changes_routine(client, auth):
    h = auth["headers"]
    first = chat(client, h, "Give me a yoga routine for flexibility")
    second = chat(client, h, "make it 30 minutes", first["conversation_id"])
    assert second["intent"] == "yoga" and second["is_followup"]
    assert second["yoga_routine"]["minutes"] == 30 and second["yoga_routine"]["goal"] == "flexibility"
    conv = client.get(f"/conversations/{first['conversation_id']}", headers=h).json()
    assert conv["messages"][-1]["payload"]["yoga_routine"]["minutes"] == 30, "routine is stored with the message"


def test_chat_yoga_pain_is_gentle_with_referral(client, auth):
    r = chat(client, auth["headers"], "yoga for lower back pain")
    assert r["intent"] == "yoga" and r["safety"]
    assert all(p["difficulty"] == "Beginner" for p in r["yoga_poses"])
    assert "not a substitute for professional medical advice" in r["answer"]


def test_chat_advanced_pose_adds_safety(client, auth):
    r = chat(client, auth["headers"], "how do I do a headstand in yoga?")
    assert r["yoga_poses"][0]["slug"] == "supported-headstand" and r["safety"]


def test_existing_behaviour_unchanged_for_non_yoga_questions(client, auth):
    h = auth["headers"]
    assert chat(client, h, "Is yoga enough exercise?")["intent"] in ("stretching", "general_fitness")
    plank = chat(client, h, "How do I do a plank?")
    assert plank["intent"] != "yoga" and plank["exercises"][0]["name"] == "Plank"
    assert chat(client, h, "What exercises can I do for chest?")["intent"] == "exercise_search"
    assert chat(client, h, "Is yoga safe during pregnancy?")["intent"] == "medical_safety"
    assert chat(client, h, "What is the capital of France?")["intent"] == "out_of_domain"
