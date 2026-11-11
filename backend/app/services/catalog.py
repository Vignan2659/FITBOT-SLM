"""Structured retrieval over the exercise and food databases (no LLM involved, no invented values)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.planner import LEVEL_RANK, allowed, normalise_equipment


# Hand picked exercises per muscle group for trained people, shown first when the person's level is intermediate or
# advanced (the public exercise set labels very few movements "Advanced", so the level label alone is not enough).
LEVEL_PICKS: dict[str, dict[str, list[str]]] = {
    "chest": {"intermediate": ["Bench Press", "Cable Crossover", "Wide-Grip Barbell Bench Press", "Clock Push-Up",
                               "Bent-Arm Dumbbell Pullover"],
              "advanced": ["Plyo Kettlebell Pushups", "Single-Arm Push-Up", "Wide-Grip Decline Barbell Bench Press",
                           "Bench Press", "Cable Crossover"]},
    "back": {"intermediate": ["Pull-Ups", "Bent-Over Dumbbell Row", "Reverse Grip Bent-Over Rows", "Rack Pulls",
                              "Wide-Grip Rear Pull-Up"],
             "advanced": ["Deadlift", "Mixed Grip Chin", "Alternating Renegade Row", "One Arm Chin-Up", "Deficit Deadlift"]},
    "shoulders": {"intermediate": ["Arnold Press", "Barbell Shoulder Press", "Cuban Press", "Clean and Press",
                                   "Seated Bent-Over Rear Delt Raise"],
                  "advanced": ["Push Press", "Handstand Push-Ups", "Clean and Jerk", "One-Arm Kettlebell Snatch",
                               "Barbell Shoulder Press"]},
    "legs": {"intermediate": ["Squat", "Romanian Deadlift", "Barbell Lunge", "Front Squat (Clean Grip)",
                              "Barbell Hip Thrust", "Freehand Jump Squat"],
             "advanced": ["Front Barbell Squat", "Overhead Squat", "Kettlebell Pistol Squat", "Zercher Squats",
                          "One Leg Barbell Squat", "Power Snatch"]},
    "arms": {"intermediate": ["Dips", "Zottman Curl", "Drag Curl", "Lying Dumbbell Tricep Extension",
                              "Push-Ups – Close Triceps Position", "Tate Press"],
             "advanced": ["Bench Press with Chains", "Dips", "Tate Press", "Drag Curl", "Zottman Curl"]},
    "core": {"intermediate": ["Russian Twists", "Decline Crunch", "Barbell Ab Rollout", "Frog Sit-Ups"],
             "advanced": ["Hanging Leg Raise", "Hanging Pike", "Barbell Ab Rollout – On Knees", "Press Sit-Up",
                          "Bent Press"]},
}


def order_for_level(pool: list[dict], level: str | None, group: str | None = None) -> list[dict]:
    """Exercises that fit a person's level, best fit first.
    beginner: beginner movements only; intermediate: intermediate first, then beginner, nothing advanced;
    advanced: advanced first, then intermediate, then beginner. Unknown level: the list is returned unchanged."""
    lvl = LEVEL_RANK.get((level or "").lower())
    if lvl is None:
        return pool
    rank = lambda e: LEVEL_RANK.get(e["difficulty"].lower(), 0)
    if lvl == 0:
        return [e for e in pool if rank(e) == 0] or pool
    pool = [e for e in pool if rank(e) <= lvl] or pool
    picks = {n: i for i, n in enumerate(LEVEL_PICKS.get(group or "", {}).get(level.lower(), []))}
    return sorted(pool, key=lambda e: (e["name"] not in picks, picks.get(e["name"], 0), lvl - rank(e)))


class Catalog:
    def __init__(self, data_dir: Path, exercises_file: str = "exercises/exercises.json"):
        exercises = json.loads((data_dir / exercises_file).read_text(encoding="utf-8"))
        # v2 lists all 871 exercises alphabetically; put the 58 hand-curated ones first, in their v1 order, so
        # lists and cards lead with the well-known movements (v1 entries have no flag and keep their order)
        v1_file = data_dir / "exercises" / "exercises.json"
        v1_order = {e["name"]: i for i, e in enumerate(json.loads(v1_file.read_text(encoding="utf-8")))} \
            if v1_file.exists() else {}
        self.exercises: list[dict] = sorted(
            exercises, key=lambda e: (not e.get("curated_v1", True), v1_order.get(e["name"], len(v1_order))))
        self.foods: list[dict] = json.loads((data_dir / "nutrition" / "foods.json").read_text())
        self.ex_by_slug = {e["slug"]: e for e in self.exercises}
        self.ex_by_name = {e["name"].lower(): e for e in self.exercises}

    # ------------------------------------------------------------------ exercises
    def find_exercise(self, key: str) -> dict | None:
        k = key.lower().strip().replace("_", " ")
        if k in self.ex_by_name:
            return self.ex_by_name[k]
        if k.replace(" ", "-") in self.ex_by_slug:
            return self.ex_by_slug[k.replace(" ", "-")]
        for e in self.exercises:
            if k in [a.lower() for a in e["aliases"]]:
                return e
        return None

    def exercises_for(self, group: str | None, level: str | None = None, equipment: list[str] | None = None,
                      location: str | None = None, limit: int = 6) -> list[dict]:
        pool = [e for e in self.exercises if group is None or e["muscle_group"] == group]
        if equipment or location == "home":
            eq = normalise_equipment(equipment, location)
            pool = [e for e in pool if allowed(e, eq)]
        pool = order_for_level(pool, level, group)
        return pool[:limit]

    # ------------------------------------------------------------------ foods
    TOPICS = [  # (pattern in question, predicate) - mirrors the dataset's food-list questions
        (r"vegetarian|vegan|plant[- ]based", lambda f: "vegetarian" in f["fitbot_tags"] and "High protein" in f["highlights"]),
        (r"protein", lambda f: "High protein" in f["highlights"] and f["group"] in ("protein", "plant_protein", "dairy")),
        (r"fib(er|re)", lambda f: "High fiber" in f["highlights"] and f["group"] != "treats"),
        (r"healthy fats?|good fats?|omega", lambda f: "healthy_fats" in f["fitbot_tags"] or "omega3" in f["fitbot_tags"]),
        (r"snack", lambda f: "snack" in f["fitbot_tags"] and "limit" not in f["fitbot_tags"]),
        (r"breakfast", lambda f: "breakfast" in f["fitbot_tags"]),
        (r"after (a |my |this |the )?(work ?out|working out|training|gym|exercise|session|lifting|run)|post[- ]?workout|recover",
         lambda f: "post_workout" in f["fitbot_tags"]),
        (r"before (a |my |the )?(work ?out|working out|training|gym|exercise|run|lifting)|pre[- ]?workout", lambda f: "pre_workout" in f["fitbot_tags"] and f["group"] != "beverages"),
        (r"drinks?.*(avoid|limit|bad|less)|(avoid|limit|bad).*drinks?|sugary drink|soda", lambda f: f["group"] == "beverages" and "limit" in f["fitbot_tags"]),
        (r"(avoid|limit|bad|less|cut).*(food|eat)|(food|eat).*(avoid|limit|bad)|junk", lambda f: f["group"] == "treats" and "limit" in f["fitbot_tags"]),
        (r"hydrat|drink", lambda f: "hydrating" in f["fitbot_tags"]),
        (r"carb", lambda f: f["group"] in ("grains", "starchy_vegetable") and (f["per_100g"].get("carbs_g") or 0) > 15),
    ]

    def foods_for_topic(self, text: str, diet: str | None = None, limit: int = 5) -> list[dict]:
        t = text.lower()
        for pattern, pred in self.TOPICS:
            if re.search(pattern, t):
                foods = [f for f in self.foods if pred(f)]
                if diet in ("vegetarian", "vegan"):
                    foods = [f for f in foods if "vegetarian" in f["fitbot_tags"] or f["group"] in ("beverages",)] or foods
                    if diet == "vegan":
                        foods = [f for f in foods if "vegan" in f["fitbot_tags"] or f["group"] == "beverages"] or foods
                return foods[:limit]
        return []


def exercise_card(e: dict) -> dict:
    return {k: e[k] for k in ("name", "slug", "muscle_group", "image_url", "image_urls", "target_muscles",
                              "secondary_muscles", "equipment", "difficulty", "description", "instructions",
                              "safety_tips", "image_license")}


def food_card(f: dict) -> dict:
    p = f.get("portion")
    return {
        "name": f["name"], "fdc_id": f["fdc_id"], "group": f["group"], "highlights": f["highlights"],
        "portion": {"description": p["description"], "grams": p["grams"]} if p else None,
        "nutrients": p["nutrients"] if p else f["per_100g"],
        "basis": f"per {p['description']} ({p['grams']:g} g, computed from USDA per-100 g values)" if p else "per 100 g",
        "per_100g": f["per_100g"], "usda_description": f["usda_description"],
        "source": f["source"], "source_url": f["source_url"],
    }
