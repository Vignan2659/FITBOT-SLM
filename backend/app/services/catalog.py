"""Structured retrieval over the exercise and food databases (no LLM involved, no invented values)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.planner import allowed, normalise_equipment


class Catalog:
    def __init__(self, data_dir: Path):
        self.exercises: list[dict] = json.loads((data_dir / "exercises" / "exercises.json").read_text())
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
        if level == "beginner":
            pool = [e for e in pool if e["difficulty"] == "Beginner"] or pool
        elif level == "advanced":
            pool = sorted(pool, key=lambda e: {"Advanced": 0, "Intermediate": 1}.get(e["difficulty"], 2))
        return pool[:limit]

    def search_exercises(self, q: str | None = None, muscle_group: str | None = None, difficulty: str | None = None,
                         equipment: str | None = None) -> list[dict]:
        out = self.exercises
        if muscle_group:
            out = [e for e in out if e["muscle_group"] == muscle_group.lower()]
        if difficulty:
            out = [e for e in out if e["difficulty"].lower() == difficulty.lower()]
        if equipment:
            out = [e for e in out if equipment.lower() in e["equipment"].lower() or equipment.lower() in e["equipment_raw"]]
        if q:
            ql = q.lower()
            out = [e for e in out if ql in e["name"].lower() or any(ql in a for a in e["aliases"])
                   or any(ql in m.lower() for m in e["target_muscles"])]
        return out

    # ------------------------------------------------------------------ foods
    def find_food(self, key: str) -> dict | None:
        k = key.lower().strip()
        for f in self.foods:
            if k in (f["name"].lower(), f["slug"], f["name"].split(" (")[0].lower()) or k in [a.lower() for a in f["aliases"]]:
                return f
        return None

    def search_foods(self, q: str | None = None, group: str | None = None, tag: str | None = None) -> list[dict]:
        out = self.foods
        if group:
            out = [f for f in out if f["group"] == group]
        if tag:
            out = [f for f in out if tag in f["fitbot_tags"] or tag.lower() in [h.lower() for h in f["highlights"]]]
        if q:
            ql = q.lower()
            out = [f for f in out if ql in f["name"].lower() or any(ql in a for a in f["aliases"])
                   or ql in f["usda_description"].lower()]
        return out

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
