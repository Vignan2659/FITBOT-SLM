"""Exercise/food endpoints, intent detection, slots, safety and planner."""
import pytest

from app.services import safety


# ---------------------------------------------------------------- catalog endpoints
def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["database"]["exercises"] >= 35 and r["database"]["foods"] >= 100


def test_exercise_list_and_filters(client):
    all_ = client.get("/exercises").json()
    assert all_["count"] >= 35
    chest = client.get("/exercises", params={"muscle_group": "chest"}).json()["exercises"]
    assert {"Bench Press", "Push-Ups", "Dumbbell Press", "Incline Press", "Chest Fly", "Cable Crossover"} <= {e["name"] for e in chest}
    beg = client.get("/exercises", params={"difficulty": "beginner"}).json()["exercises"]
    assert beg and all(e["difficulty"] == "Beginner" for e in beg)


@pytest.mark.parametrize("name", ["Bench Press", "bench-press", "bench press", "bench", "pull-ups"])
def test_exercise_lookup(client, name):
    r = client.get(f"/exercises/{name}")
    assert r.status_code == 200 and r.json()["image_url"].startswith("https://")


def test_required_exercises_present(client):
    required = ["Bench Press", "Push-Ups", "Dumbbell Press", "Incline Press", "Chest Fly", "Cable Crossover",
                "Lat Pulldown", "Pull-Ups", "Seated Row", "Dumbbell Row", "Deadlift", "Shoulder Press",
                "Lateral Raise", "Front Raise", "Rear Delt Fly", "Squat", "Lunges", "Leg Press", "Leg Extension",
                "Leg Curl", "Calf Raise", "Bicep Curl", "Hammer Curl", "Tricep Pushdown", "Tricep Extension", "Dips",
                "Plank", "Crunches", "Leg Raises", "Russian Twists", "Walking", "Running", "Cycling", "Jump Rope", "Rowing"]
    for n in required:
        assert client.get(f"/exercises/{n}").status_code == 200, n


def test_exercise_404(client):
    assert client.get("/exercises/underwater basket weaving").status_code == 404


def test_food_list_and_lookup(client):
    foods = client.get("/foods").json()
    assert foods["count"] >= 100 and "USDA" in foods["source"]
    egg = client.get("/foods/egg").json()
    assert egg["fdc_id"] == 173424 and egg["per_100g"]["protein_g"] == 12.6   # USDA SR Legacy fdcId 173424
    hp = client.get("/foods", params={"tag": "high protein"}).json()["foods"]
    assert hp and all("High protein" in f["highlights"] for f in hp)
    assert client.get("/foods/unicorn steak").status_code == 404


# ---------------------------------------------------------------- intent detection
@pytest.mark.parametrize("text,expected", [
    ("What exercises can I do for chest?", {"exercise_search"}),
    ("Give me a beginner 3-day gym workout", {"workout_plan", "gym_workout"}),
    ("How much protein does an egg contain?", {"food_search", "nutrition_question"}),
    ("What should I eat after working out?", {"nutrition_question"}),
    ("How much should I sleep?", {"sleep"}),
    ("How much water should I drink a day?", {"hydration"}),
    ("How can I lose belly fat?", {"weight_loss"}),
    ("How do I build muscle?", {"muscle_gain"}),
    ("What is HIIT?", {"cardio"}),
    ("Should I stretch before running?", {"stretching"}),
    ("What equipment do I need for a home gym?", {"equipment"}),
    ("How do I avoid injury when lifting?", {"exercise_safety"}),
    ("Do I need rest days?", {"recovery"}),
    ("What is the capital of France?", {"out_of_domain"}),
    ("Plan a trip to Paris for me", {"out_of_domain"}),
    ("What is Bitcoin?", {"out_of_domain"}),
    ("Hello", {"greeting"}),
])
def test_intent_detection(engine, text, expected):
    intent, conf, _ = engine.nlu.classify(text)
    assert intent in expected, (text, intent, conf)


def test_slot_extraction(engine):
    s = engine.nlu.slots("I'm a beginner and I only have dumbbells at home, 3 day plan to lose weight")
    assert s.level == "beginner" and "dumbbells" in s.equipment and s.location == "home"
    assert s.days == 3 and s.goal == "weight_loss"
    s2 = engine.nlu.slots("How much protein in greek yogurt and chicken breast?")
    assert {f["name"] for f in s2.foods} >= {"Greek yogurt (plain, nonfat)", "Chicken breast (roasted)"}
    assert engine.nlu.slots("I'm a beginner.").constraint_only()


# ---------------------------------------------------------------- safety
@pytest.mark.parametrize("text,category", [
    ("I have chest pain when I run", "emergency"),
    ("I make myself throw up after eating", "eating_disorder"),
    ("Can I eat 500 calories a day to lose weight?", "starvation"),
    ("What's a good steroid cycle for beginners?", "peds"),
    ("How do I dehydrate myself to make weight?", "dehydration"),
    ("Can I take creatine with my antidepressants?", "medication"),
    ("I think I tore my hamstring", "injury_diagnosis"),
    ("I feel hopeless and want to die", "self_harm"),
])
def test_hard_safety(text, category):
    r = safety.screen_input(text)
    assert r.hard and r.category == category and safety.DISCLAIMER in r.response


@pytest.mark.parametrize("text", ["What exercises for chest?", "I broke my PR today", "Do fat burner pills work?",
                                  "How do I cut carbs?", "Best back exercises?"])
def test_no_false_positive_safety(text):
    assert not safety.screen_input(text).hard


def test_output_screen():
    assert safety.screen_output("Just push through the pain and keep squatting.")
    assert safety.screen_output("Try to eat 600 calories a day for fast results.")
    assert not safety.screen_output("Aim for a modest calorie deficit and stop if you feel sharp pain.")


# ---------------------------------------------------------------- planner
def test_planner_respects_equipment(engine):
    p = engine.planner.plan(level="beginner", days=3, equipment=["none"], location="home")
    for d in p["days"]:
        for e in d["exercises"]:
            assert e["equipment"].startswith(("Bodyweight", "None")), e
    g = engine.planner.plan(level="intermediate", days=4, goal="muscle_gain")
    assert g["split"] == "Upper/lower" and len(g["days"]) == 4
