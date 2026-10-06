"""Structured workout planner.

Builds day-by-day plans (exercises, sets, reps/duration, rest, difficulty, image) from
the curated exercise database. Exercise selection respects fitness level and
available equipment. The SLM writes the conversational explanation; this module
guarantees that every exercise in a plan really exists in the database with a real
image, and that sets/reps follow standard guidance (see knowledge base:
strength-basics, rep-ranges, rest-between-sets).
"""
from __future__ import annotations

from typing import Iterable

# Movement roles -> candidate exercises in preference order.
ROLES: dict[str, list[str]] = {
    "squat": ["Squat", "Goblet Squat", "Leg Press", "Bodyweight Squat"],
    "lunge": ["Lunges", "Step-Ups", "Leg Extension"],
    "hinge": ["Romanian Deadlift", "Deadlift", "Glute Bridge"],
    "hams": ["Leg Curl", "Glute Bridge", "Romanian Deadlift"],
    "calves": ["Calf Raise"],
    "push_h": ["Bench Press", "Dumbbell Press", "Push-Ups", "Incline Push-Ups"],
    "push_inc": ["Incline Press", "Incline Push-Ups", "Push-Ups"],
    "chest_iso": ["Chest Fly", "Cable Crossover", "Push-Ups"],
    "pull_v": ["Lat Pulldown", "Pull-Ups", "Dumbbell Row", "Superman"],
    "pull_h": ["Seated Row", "Dumbbell Row", "Bent-Over Dumbbell Row", "Superman"],
    "push_v": ["Shoulder Press", "Arnold Press", "Push-Ups"],
    "delts": ["Lateral Raise", "Rear Delt Fly", "Front Raise"],
    "rear_delts": ["Rear Delt Fly", "Lateral Raise", "Superman"],
    "biceps": ["Bicep Curl", "Hammer Curl"],
    "triceps": ["Tricep Pushdown", "Dumbbell Tricep Extension", "Tricep Extension", "Bench Dips", "Dips", "Push-Ups"],
    "core": ["Plank", "Dead Bug", "Crunches", "Leg Raises", "Russian Twists", "Mountain Climbers"],
    "cardio": ["Walking", "Cycling", "Running", "Rowing", "Jump Rope", "Elliptical"],
}

# Day templates per split: (focus label, roles)
FULL_BODY = [
    ("Full body A", ["squat", "push_h", "pull_h", "hinge", "core"]),
    ("Full body B", ["hinge", "push_v", "pull_v", "lunge", "core"]),
    ("Full body C", ["lunge", "push_inc", "pull_h", "hams", "core"]),
]
UPPER_LOWER = [
    ("Upper body", ["push_h", "pull_v", "push_v", "pull_h", "biceps", "triceps"]),
    ("Lower body", ["squat", "hinge", "lunge", "calves", "core"]),
    ("Upper body", ["push_inc", "pull_h", "delts", "pull_v", "triceps", "biceps"]),
    ("Lower body", ["hinge", "squat", "hams", "calves", "core"]),
]
PPL = [
    ("Push (chest, shoulders, triceps)", ["push_h", "push_inc", "push_v", "delts", "triceps"]),
    ("Pull (back, biceps)", ["pull_v", "pull_h", "rear_delts", "biceps", "core"]),
    ("Legs", ["squat", "hinge", "lunge", "hams", "calves"]),
]
MUSCLE_ROLES = {
    "chest": ["push_h", "push_inc", "chest_iso", "push_h"],
    "back": ["pull_v", "pull_h", "hinge", "rear_delts"],
    "shoulders": ["push_v", "delts", "rear_delts", "delts"],
    "legs": ["squat", "hinge", "lunge", "calves", "hams"],
    "arms": ["biceps", "triceps", "biceps", "triceps"],
    "core": ["core", "core", "core", "core"],
}
TIMED = {"Plank": "20-40 sec", "Mountain Climbers": "30 sec", "Superman": "10-12 reps (2 sec hold)",
         "Walking": "20-30 min", "Cycling": "20-30 min", "Running": "15-25 min", "Rowing": "10-20 min",
         "Jump Rope": "5 x 1 min", "Elliptical": "20-30 min"}
BODYWEIGHT_OK = {"Lunges", "Step-Ups", "Calf Raise", "Bodyweight Squat"}
LEVEL_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}
EQUIP_ALIASES = {
    "none": "bodyweight", "no equipment": "bodyweight", "bodyweight": "bodyweight", "body weight": "bodyweight",
    "dumbbell": "dumbbells", "dumbbells": "dumbbells", "kettlebell": "kettlebells", "kettlebells": "kettlebells",
    "bands": "bands", "resistance bands": "bands", "barbell": "gym", "gym": "gym", "full gym": "gym",
    "machines": "gym", "cable": "gym", "rack": "gym",
}


def normalise_equipment(equipment: Iterable[str] | None, location: str | None) -> set[str]:
    eq = {EQUIP_ALIASES.get(str(e).lower().strip(), str(e).lower().strip()) for e in (equipment or [])}
    eq.discard("")
    if not eq:
        eq = {"bodyweight"} if location == "home" else {"gym"}
    eq.add("bodyweight")
    return eq


def allowed(ex: dict, equipment: set[str]) -> bool:
    if "gym" in equipment:
        return True
    raw = ex.get("equipment_raw") or "body only"
    if raw in ("body only",) or ex["name"] in BODYWEIGHT_OK:
        return True
    if raw == "dumbbell" and "dumbbells" in equipment:
        return True
    if raw == "kettlebells" and ({"kettlebells", "dumbbells"} & equipment):
        return True  # goblet squat works with either
    if raw == "bands" and "bands" in equipment:
        return True
    if ex.get("muscle_group") == "cardio" and ex.get("home_friendly"):
        return True
    return False


def level_ok(ex: dict, level: str) -> bool:
    return LEVEL_RANK.get(ex["difficulty"].lower(), 1) <= LEVEL_RANK.get(level, 0) + (0 if level == "beginner" else 1)


def prescription(level: str, goal: str, main: bool) -> tuple[str, str, str]:
    """(sets, reps, rest) following common guidance."""
    if level == "beginner":
        return ("2-3", "10-12", "60-90 sec")
    if goal == "strength":
        return ("4-5", "4-6", "2-3 min") if main else ("3", "8-10", "90 sec")
    if goal in ("weight_loss", "endurance"):
        return ("3", "12-15", "45-60 sec")
    return ("3-4", "8-12", "60-120 sec") if main else ("3", "10-15", "60 sec")


class Planner:
    def __init__(self, exercises: list[dict]):
        self.by_name = {e["name"]: e for e in exercises}

    def pick(self, role: str, level: str, equipment: set[str], used: set[str], offset: int = 0) -> dict | None:
        cands = [self.by_name[n] for n in ROLES[role] if n in self.by_name]
        ok = [e for e in cands if allowed(e, equipment) and level_ok(e, level) and e["name"] not in used]
        if not ok and level != "beginner":
            ok = [e for e in cands if allowed(e, equipment) and e["name"] not in used]
        if not ok:
            return None
        if "gym" in equipment and level != "beginner":
            # with full equipment, trained lifters get loaded movements over easy bodyweight ones
            loaded = [e for e in ok if not (e["difficulty"] == "Beginner" and e["equipment_raw"] == "body only")]
            ok = loaded or ok
        # rotate between the top two choices across days for variety
        return ok[offset % min(2, len(ok))] if level != "beginner" else ok[0]

    def _item(self, ex: dict, level: str, goal: str, main: bool, equipment: set[str] | None = None) -> dict:
        sets, reps, rest = prescription(level, goal, main)
        label = ex["equipment"]
        if equipment is not None and "gym" not in equipment and ex["name"] in BODYWEIGHT_OK:
            # e.g. lunges / calf raises: show what the user will actually use
            label = "Dumbbells" if ex.get("equipment_raw") == "dumbbell" and "dumbbells" in equipment else "Bodyweight"
        if ex["name"] in TIMED:
            reps = TIMED[ex["name"]]
            sets = "1" if ex["muscle_group"] == "cardio" else sets
        return {
            "name": ex["name"], "sets": sets, "reps": reps, "rest": rest,
            "difficulty": ex["difficulty"], "equipment": label,
            "target_muscles": ex["target_muscles"], "image_url": ex["image_url"],
            "muscle_group": ex["muscle_group"],
        }

    def plan(self, level: str = "beginner", days: int = 3, goal: str = "general_fitness",
             equipment: Iterable[str] | None = None, location: str | None = None) -> dict:
        level = level if level in LEVEL_RANK else "beginner"
        days = max(1, min(int(days or 3), 6))
        eq = normalise_equipment(equipment, location)
        if days <= 3 or level == "beginner":
            template = [FULL_BODY[i % 3] for i in range(days)]
            split = "Full-body"
        elif days == 4:
            template, split = UPPER_LOWER, "Upper/lower"
        else:
            template = [PPL[i % 3] for i in range(days)]
            split = "Push/pull/legs"
        out_days = []
        for i, (focus, roles) in enumerate(template):
            used: set[str] = set()
            items = []
            for j, role in enumerate(roles):
                ex = self.pick(role, level, eq, used, offset=i if j < 2 or role == "core" else 0)
                if ex:
                    used.add(ex["name"])
                    items.append(self._item(ex, level, goal, main=j < 2, equipment=eq))
            if goal in ("weight_loss", "endurance", "general_fitness"):
                cardio = self.pick("cardio", level, eq, used, offset=i)
                if cardio:
                    items.append(self._item(cardio, level, goal, main=False, equipment=eq))
            out_days.append({"day": f"Day {i + 1}", "focus": focus, "exercises": items})
        where = "home" if "gym" not in eq else "gym"
        eq_label = "bodyweight only" if eq == {"bodyweight"} else ", ".join(sorted(eq - {"bodyweight"}))
        return {
            "title": f"{level.title()} {days}-day {where} plan ({split.lower()})",
            "level": level.title(), "goal": goal, "split": split, "location": where, "equipment": eq_label,
            "days": out_days,
            "notes": [
                "Warm up for 5-10 minutes before each session and cool down with light stretching.",
                "Leave 1-3 reps in reserve on each set; add weight or reps gradually when sets feel easier.",
                "Take at least one rest day between sessions that train the same muscles.",
            ],
        }

    def muscle_workout(self, group: str, level: str = "beginner", goal: str = "muscle_gain",
                       equipment: Iterable[str] | None = None, location: str | None = None) -> dict:
        eq = normalise_equipment(equipment, location)
        roles = MUSCLE_ROLES.get(group, MUSCLE_ROLES["chest"])
        used: set[str] = set()
        items = []
        for j, role in enumerate(roles):
            ex = self.pick(role, level, eq, used)
            if ex is not None and group in ("chest", "back", "shoulders", "arms") and ex["muscle_group"] != group:
                ex = None   # keep single-muscle workouts on the requested muscle group
            if ex is None and group in ("chest", "back", "shoulders", "legs", "arms", "core"):
                # fall back to any allowed exercise from the same muscle group
                pool = [e for e in self.by_name.values() if e["muscle_group"] == group
                        and allowed(e, eq) and level_ok(e, level) and e["name"] not in used]
                ex = pool[0] if pool else None
            if ex:
                used.add(ex["name"])
                items.append(self._item(ex, level, goal, main=j == 0, equipment=eq))
        eq_label = "bodyweight only" if eq == {"bodyweight"} else ", ".join(sorted(eq - {"bodyweight"}))
        return {
            "title": f"{level.title()} {group} workout ({eq_label})",
            "level": level.title(), "goal": goal, "split": f"{group} focus", "equipment": eq_label,
            "location": "home" if "gym" not in eq else "gym",
            "days": [{"day": "Workout", "focus": group.title(), "exercises": items}],
            "notes": ["Warm up first with light cardio and a lighter set of the first exercise.",
                      "Increase reps or weight gradually as the workout gets easier."],
        }


def plan_to_context(plan: dict) -> list[str]:
    """Compact text lines describing a plan, given to the SLM as reference info."""
    lines = [f"Workout plan: {plan['title']} | goal: {plan['goal'].replace('_', ' ')}"]
    for d in plan["days"]:
        ex = "; ".join(f"{e['name']} {e['sets']} x {e['reps']}" for e in d["exercises"])
        lines.append(f"{d['day']} ({d['focus']}): {ex}")
    return lines
