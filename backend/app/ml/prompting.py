"""Prompt construction shared by dataset building, training and inference.

Keeping this in one module guarantees that the fine-tuned model sees prompts at
inference time in exactly the format it was trained on. `scripts/build_dataset.py`
imports this module to write the `messages` field of every JSONL record, and the
Colab notebook trains directly on that field.
"""
from __future__ import annotations

from typing import Iterable

SYSTEM_PROMPT = (
    "You are FitBot, a friendly fitness and nutrition assistant. Give practical, safe, "
    "general fitness and wellness information in clear, concise language. When reference "
    "information is provided, base your answer on it and never invent exact numbers. You are "
    "not a doctor: for injuries, symptoms, medical conditions or medication, recommend a "
    "qualified healthcare professional. If a question is not about fitness, exercise, "
    "nutrition, sleep, recovery or a healthy lifestyle, politely say you can only help with "
    "those topics."
)

# Short instruction kept in the JSONL `instruction` field (matches the project spec).
SHORT_INSTRUCTION = "You are FitBot, a fitness assistant."

PROFILE_FIELDS = [
    ("fitness_level", "fitness level"),
    ("goal", "goal"),
    ("equipment", "available equipment"),
    ("location", "workout location"),
    ("dietary_preference", "dietary preference"),
    ("age", "age"),
]


def format_profile(profile: dict | None) -> str:
    if not profile:
        return ""
    parts = []
    for key, label in PROFILE_FIELDS:
        val = profile.get(key)
        if val in (None, "", []):
            continue
        if isinstance(val, (list, tuple)):
            val = ", ".join(str(v) for v in val)
        parts.append(f"{label}: {str(val).replace('_', ' ')}")
    return "; ".join(parts)


def format_exercise(ex: dict) -> str:
    muscles = ", ".join(ex.get("target_muscles", []) + ex.get("secondary_muscles", [])[:2])
    return (f"Exercise: {ex['name']} | muscles: {muscles} | equipment: {ex['equipment']} | "
            f"difficulty: {ex['difficulty']} | {ex['description']}")


def short_steps(ex: dict, n: int = 3, max_chars: int = 420) -> str:
    """First few source instructions, trimmed to keep prompts short."""
    steps, total = [], 0
    for s in ex.get("instructions", [])[:n]:
        s = s.strip()
        if total + len(s) > max_chars and steps:
            break
        steps.append(s)
        total += len(s)
    return " ".join(steps)


def format_exercise_detail(ex: dict) -> str:
    safety = " ".join(ex.get("safety_tips", []))
    return f"{format_exercise(ex)} | how to: {short_steps(ex)} | safety: {safety}"


def format_food(food: dict) -> str:
    """One line of USDA facts. Uses the household portion when USDA provides one."""
    p = food.get("portion")
    if p:
        n, basis = p["nutrients"], f"per {p['description']} ({p['grams']:g} g)"
    else:
        n, basis = food["per_100g"], "per 100 g"

    def f(key, unit, label):
        v = n.get(key)
        return f"{label} {v:g} {unit}" if v is not None else None

    vals = [x for x in (f("calories_kcal", "kcal", "energy"), f("protein_g", "g", "protein"),
                        f("carbs_g", "g", "carbohydrate"), f("fat_g", "g", "fat"),
                        f("fiber_g", "g", "fiber"), f("sugar_g", "g", "sugars")) if x]
    hl = f" | notes: {', '.join(food['highlights'])}" if food.get("highlights") else ""
    return f"Food (USDA FoodData Central): {food['name']} {basis}: {', '.join(vals)}{hl}"


def format_passage(p: dict) -> str:
    return f"Guidance ({p['title']}): {p['text']}"


def build_system(context_lines: Iterable[str] | None = None, profile: dict | None = None) -> str:
    system = SYSTEM_PROMPT
    prof = format_profile(profile)
    if prof:
        system += f"\n\nUser profile: {prof}"
    lines = [c for c in (context_lines or []) if c]
    if lines:
        system += "\n\nReference information:\n" + "\n".join(f"- {c}" for c in lines)
    return system


def build_messages(question: str, context_lines: Iterable[str] | None = None,
                   profile: dict | None = None, history: list[dict] | None = None) -> list[dict]:
    """Chat messages: system (+profile +reference info), prior turns, current question."""
    msgs = [{"role": "system", "content": build_system(context_lines, profile)}]
    for turn in history or []:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            msgs.append({"role": turn["role"], "content": turn["content"]})
    msgs.append({"role": "user", "content": question})
    return msgs
