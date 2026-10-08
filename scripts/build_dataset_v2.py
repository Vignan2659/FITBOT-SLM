"""Build FitBot dataset v2 (for the 3.5-4B model): v1 (916 records) + ~4,500 new records, balanced by topic.

    .venv/bin/python scripts/build_exercise_catalog_v2.py   # 871 exercises (needs data/image_dataset)
    .venv/bin/python scripts/build_dataset_v2.py            # -> data/processed_v2/

Sources (no external AI APIs, nothing invented):
  * v1 dataset data/processed/*.jsonl - kept unchanged, including its split (the 97-record v1 test set stays a
    test set so the old 360M model and the new 4B model can be compared on identical questions)
  * data/exercises/exercises_v2.json - 871 exercises (free-exercise-db facts: muscles, equipment, level,
    instructions, images); exercise questions are grounded in these records
  * data/nutrition/foods.json - USDA FoodData Central values (every number in a food answer is copied from it)
  * backend planner (workout plans), knowledge base passages (guidance context)
  * scripts/dataset_content_v2/*.py - hand-written topics (general fitness, beginner, lifestyle, goals,
    nutrition, medical-safety referrals, off-topic, greetings); casual / typo variants are added automatically
Records use exactly the v1 schema and app.ml.prompting.build_messages, so training prompts match the app.
Each record also has `table_category` (the 11 rows of the dataset plan) and `dataset_version`.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.ml.prompting import (SHORT_INSTRUCTION, build_messages, format_exercise,  # noqa: E402
                              format_exercise_detail, format_food, format_passage, short_steps)
from app.ml.retriever import KnowledgeRetriever  # noqa: E402
from app.services.planner import Planner, plan_to_context  # noqa: E402
from dataset_content_v2 import general, safety_ood, topics  # noqa: E402

OUT = ROOT / "data" / "processed_v2"
V1 = ROOT / "data" / "processed"
SEED = 2026
rng = random.Random(SEED)

EX = json.loads((ROOT / "data/exercises/exercises_v2.json").read_text())
EX_V1 = json.loads((ROOT / "data/exercises/exercises.json").read_text())
FOODS = [f for f in json.loads((ROOT / "data/nutrition/foods.json").read_text()) if f["per_100g"].get("calories_kcal") is not None]
FOOD_BY_NAME = {f["name"]: f for f in FOODS}
KB = {p["id"]: p for p in json.loads((ROOT / "data/knowledge/knowledge_base.json").read_text())["passages"]}
RETRIEVER = KnowledgeRetriever(ROOT / "data/knowledge/knowledge_base.json")

TABLE = ["exercises", "form_safety", "plans", "beginner", "general_fitness", "nutrition", "lifestyle", "goals",
         "medical", "off_topic", "multi_turn"]
records: list[dict] = []


def fix_article(text: str) -> str:
    return re.sub(r"\b([Aa]) (?=[aeiouAEIOU])", r"\1n ", text)


def add(inp, resp, category, intent, group, source, table, context=None, history=None, profile=None, split=None):
    inp, resp = fix_article(inp), fix_article(resp).replace("- i'm focused", "- I'm focused")
    records.append({
        "instruction": SHORT_INSTRUCTION, "input": inp.strip(), "response": resp.strip(), "category": category,
        "intent": intent, "context": context or [], "history": history or [], "profile": profile or None,
        "group_id": group, "source": source, "table_category": table, "dataset_version": "v2",
        "_split": split,
    })


def h(s: str) -> int:
    return int(hashlib.md5(f"{SEED}-{s}".encode()).hexdigest(), 16)


def join(names: list[str]) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def low(s: str) -> str:
    return s[0].lower() + s[1:] if s else s


# ---------------------------------------------------------------- casual / typo variants of a question
def typo(q: str, k: int) -> str | None:
    words = q.split()
    idx = [i for i, w in enumerate(words) if i > 0 and len(re.sub(r"\W", "", w)) >= 5]
    if not idx:
        return None
    i = idx[k % len(idx)]
    w = words[i]
    j = 1 + k % (len(w) - 3)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def variants(q: str, n: int, key: str) -> list[str]:
    base = q.rstrip("?!. ")
    lowq = low(base)
    w0 = lowq.split()[0]
    cands = [f"hey, {lowq}?", f"{lowq} pls", f"quick question: {lowq}?", typo(q, h(key) % 7), f"hi fitbot, {lowq}?",
             f"can you tell me {lowq}?" if w0 in ("what", "how", "which", "when", "why") else f"{lowq}? thanks",
             f"I was wondering, {lowq}?", typo(lowq.lower(), h(key) % 5 + 2), f"{lowq} - any advice?"]
    cands = [c for c in cands if c and c.lower() != q.lower()]
    start = h(key) % len(cands)
    return (cands[start:] + cands[:start])[:n]


def add_topic(items, table, source, extra=2, split_key="topic"):
    for i, (cat, intent, qs, ans) in enumerate(items):
        gid = f"{table}-{source}-{i}"
        allq = list(qs) + variants(qs[0], extra, gid)
        for j, q in enumerate(allq):
            ctx = [format_passage(p) for p in RETRIEVER.search(q, k=2, topic=intent)] if j % 2 == 0 else []
            add(q, ans, cat, intent, gid, source, table, context=ctx)


# ================================================================ hand-written topics
add_topic(general.T, "general_fitness", "seed_v2", extra=4)
add_topic(topics.BEGINNER, "beginner", "seed_v2", extra=4)
add_topic(topics.LIFESTYLE, "lifestyle", "seed_v2", extra=4)
add_topic(topics.GOALS, "goals", "seed_v2", extra=4)
add_topic(topics.NUTRITION, "nutrition", "seed_v2", extra=2)
for i, (cat, intent, qs, ans) in enumerate(safety_ood.MEDICAL):
    gid = f"medical-{i}"
    for q in list(qs) + variants(qs[0], 3, gid):
        add(q, ans, cat, intent, gid, "safety", "medical")
for i, q in enumerate(safety_ood.OOD_QUESTIONS):
    add(q, safety_ood.OOD_VARIANTS[h(q) % len(safety_ood.OOD_VARIANTS)], "out_of_domain", "out_of_domain",
        f"ood-v2-{i}", "ood", "off_topic")
for i, (qs, ans) in enumerate(safety_ood.GREETINGS):
    for q in qs:
        add(q, ans, "greeting", "greeting", f"greet-v2-{i}", "seed_v2", "general_fitness")

# personalised goal answers (profile in the system prompt)
PROFILE_GOALS = [
    ({"fitness_level": "beginner", "goal": "weight_loss", "equipment": ["none"], "location": "home"},
     ["How should I start losing weight?", "What should my week look like?"],
     "Since you're a beginner training at home without equipment, start with 3 short full-body sessions a week - bodyweight squats, incline push-ups, glute bridges, reverse lunges and planks for 2 sets of 10-12 - plus a brisk walk most days. Pair this with a modest calorie deficit and protein at each meal, and aim to lose about 0.5-1 kg per week."),
    ({"fitness_level": "intermediate", "goal": "muscle_gain", "equipment": ["gym"], "location": "gym"},
     ["How should I structure my training to build muscle?", "What's the best way for me to gain size?"],
     "With your gym access and intermediate experience, an upper/lower split 4 days a week works well: train each muscle group twice weekly with 10-20 hard sets per week, mostly 6-12 reps, 1-3 reps from failure. Add weight or reps steadily, eat about 1.6 g of protein per kg of body weight daily and a small calorie surplus, and sleep 7-9 hours."),
    ({"fitness_level": "beginner", "goal": "muscle_gain", "equipment": ["dumbbells"], "location": "home"},
     ["Can I build muscle at home?", "How do I gain muscle with what I have?"],
     "Yes - with dumbbells at home you can build muscle well as a beginner. Do 3 full-body sessions a week: goblet squats, dumbbell presses, one-arm rows, Romanian deadlifts and shoulder presses, 3 sets of 8-12 reps. When you can do 12 reps with good form, use a heavier dumbbell or slow the lowering phase. Eat enough protein and sleep well."),
    ({"fitness_level": "advanced", "goal": "strength", "equipment": ["gym"], "location": "gym"},
     ["How do I keep getting stronger?", "My lifts are stalling, what should I do?"],
     "At an advanced level, progress comes from structured programming: train the main lifts 2-3 times a week with heavy sets of 3-6 reps, vary intensity across the week, plan a deload every 4-8 weeks, and add small, consistent load increases. Make sure sleep, protein and total calories support the training, and track every session."),
    ({"fitness_level": "beginner", "goal": "endurance", "equipment": ["none"], "location": "outdoors"},
     ["How do I improve my stamina?", "How should I start running?"],
     "As a beginner training outdoors, start with run-walk intervals - 1 minute easy jogging and 2 minutes walking for 20-30 minutes, 3 times a week - and increase the running portions gradually. Keep the pace conversational, add total time by about 10% a week, and include 2 short bodyweight strength sessions for your legs and core."),
]
for i, (prof, qs, ans) in enumerate(PROFILE_GOALS):
    for q in qs + variants(qs[0], 1, f"pg{i}"):
        add(q, ans, "weight_loss" if prof["goal"] == "weight_loss" else "muscle_building",
            {"weight_loss": "weight_loss", "endurance": "cardio"}.get(prof["goal"], "muscle_gain"),
            f"profile-goal-{i}", "seed_v2", "goals", profile=prof)

# ================================================================ 871-exercise grounded questions
GROUP_WORD = {"chest": "chest", "back": "back", "shoulders": "shoulder", "legs": "leg", "arms": "arm", "core": "core",
              "stretching": "stretching", "cardio": "cardio", "neck": "neck"}
CAT_OF_GROUP = {"cardio": ("cardio_endurance", "cardio"), "stretching": ("stretching_flexibility", "stretching")}


def cat_intent(ex):
    return CAT_OF_GROUP.get(ex["muscle_group"], ("workout_exercises", "exercise_search"))


def muscles(ex, k=2):
    return join([m.lower() for m in ex["target_muscles"] + ex["secondary_muscles"][:k]] or ["several muscle groups"])


def eq_phrase(ex):
    e = ex["equipment"]
    return "no equipment - just your body weight" if e == "Bodyweight" else {
        "Dumbbells": "a pair of dumbbells", "Barbell": "a barbell", "Kettlebell": "a kettlebell", "Cable machine": "a cable machine",
        "Machine": "a machine at the gym", "Resistance bands": "a resistance band", "Medicine ball": "a medicine ball",
        "Exercise ball": "an exercise (stability) ball", "Foam roller": "a foam roller", "EZ curl bar": "an EZ curl bar"}.get(e, "some equipment")


def alternatives(ex, k=3, beginner=False):
    pm = set(ex["target_muscles"])
    pool = [e for e in EX if e is not ex and set(e["target_muscles"]) & pm and e["muscle_group"] == ex["muscle_group"]
            and (not beginner or e["difficulty"] == "Beginner")]
    pool.sort(key=lambda e: (not e["curated_v1"], h(ex["name"] + e["name"])))
    return pool[:k]


def ex_answer(ex, kind):
    n, d = ex["name"], ex["difficulty"].lower()
    if kind == "muscles":
        return (f"The {n} mainly works the {join([m.lower() for m in ex['target_muscles']])}"
                + (f", with help from the {join([m.lower() for m in ex['secondary_muscles'][:3]])}" if ex["secondary_muscles"] else "")
                + f". It's rated {d} and uses {eq_phrase(ex)}."), [format_exercise(ex)]
    if kind == "equipment":
        where = " You can do it at home." if ex["home_friendly"] else (" It's a gym exercise." if ex["equipment_raw"] in ("machine", "cable", "barbell") else "")
        return (f"For the {n} you need {eq_phrase(ex)}.{where} It targets the {muscles(ex)} and is rated {d}."), [format_exercise(ex)]
    if kind == "beginner":
        if ex["difficulty"] == "Beginner":
            a = f"Yes - the {n} is rated beginner-friendly. It works the {muscles(ex)} using {eq_phrase(ex)}. Start light, learn the movement slowly, and do 2-3 sets of 10-12 controlled reps."
            return a, [format_exercise(ex)]
        alts = alternatives(ex, 3, beginner=True)
        if not alts:
            a = f"The {n} is rated {d}, so build a base with simpler exercises for the {join([m.lower() for m in ex['target_muscles']])} first and learn it with light weight, ideally with a coach."
            return a, [format_exercise(ex)]
        a = (f"The {n} is rated {d}, so it's not the best place to start. Beginner-friendly options for the same muscles are "
             f"{join([e['name'] for e in alts])}. Build a base with those first, then try the {n} "
             + ("with good control and a smaller range of motion." if ex["equipment"] == "Bodyweight" else "with light weight and good form."))
        return a, [format_exercise(ex)] + [format_exercise(e) for e in alts]
    if kind == "what":
        return f"{ex['description']} It's rated {d}.", [format_exercise(ex)]
    if kind == "alternative":
        alts = alternatives(ex, 3)
        if len(alts) < 2:
            return None, None
        return (f"Good alternatives to the {n} that also train the {join([m.lower() for m in ex['target_muscles']])} are "
                f"{join([e['name'] for e in alts])}. Choose one that matches your equipment and level, and keep the same "
                "sets and reps."), [format_exercise(ex)] + [format_exercise(e) for e in alts]


EX_Q = {"muscles": ["What muscles does the {n} work?", "Which muscles do {n} target?", "What does the {n} train?"],
        "equipment": ["What equipment do I need for the {n}?", "Do I need any equipment for {n}?", "What do I need to do the {n}?"],
        "beginner": ["Is the {n} good for beginners?", "Can a beginner do the {n}?", "Is {n} too hard for a beginner?"],
        "what": ["What is the {n}?", "What kind of exercise is the {n}?", "Tell me about the {n}"],
        "alternative": ["What can I do instead of the {n}?", "Alternative to the {n}?", "What's a substitute for {n}?"]}

for ex in EX:
    kinds = sorted(EX_Q, key=lambda k: h(ex["name"] + k))[:2 if ex["curated_v1"] or h(ex["name"]) % 3 == 0 else 1]
    for kind in kinds:
        ans, ctx = ex_answer(ex, kind)
        if not ans:
            continue
        q = EX_Q[kind][h(ex["name"] + kind + "q") % 3].format(n=ex["name"])
        cat, intent = cat_intent(ex)
        add(q, ans, cat, intent, f"ex-{ex['slug']}", "exercise_db_v2", "exercises", context=ctx, split=ex["split"])

# how-to / form & safety (instructions + safety tip), for exercises that have instructions
HOWTO_Q = ["How do I do the {n}?", "How do I perform {n} with good form?", "Can you explain how to do the {n}?",
           "What's the proper form for {n}?", "Tips for doing the {n} safely?"]
howto_pool = [e for e in EX if e["instructions"]]
howto_pool.sort(key=lambda e: (not e["curated_v1"], h("howto" + e["name"])))
for ex in howto_pool[:520]:
    steps = short_steps(ex, n=4, max_chars=480)
    q = HOWTO_Q[h(ex["name"] + "how") % len(HOWTO_Q)].format(n=ex["name"])
    ans = f"{ex['description']} How to do it: {steps} Safety tip: {ex['safety_tips'][0]}"
    cat = "exercise_safety" if "safely" in q or "form" in q else cat_intent(ex)[0]
    intent = "exercise_safety" if cat == "exercise_safety" else cat_intent(ex)[1]
    add(q, ans, cat, intent, f"ex-{ex['slug']}", "exercise_db_v2", "form_safety",
        context=[format_exercise_detail(ex)], split=ex["split"])

# list questions by muscle group x filter, and by target muscle
FILTERS = {
    None: (lambda e: True, ["What exercises can I do for {g}?", "Best {g} exercises?", "Give me some {g} exercises"],
           "Here are some effective {g} exercises", "Mix compound and isolation movements, and aim for 2-4 sets of 8-12 reps."),
    "beginner": (lambda e: e["difficulty"] == "Beginner", ["Beginner {g} exercises?", "What {g} exercises are good for beginners?"],
                 "Good beginner-friendly {g} exercises are", "Start light, do 2-3 sets of 10-12 controlled reps, and focus on form before adding load."),
    "dumbbells": (lambda e: e["equipment_raw"] == "dumbbell", ["Dumbbell {g} exercises?", "What {g} exercises can I do with dumbbells?"],
                  "With dumbbells you can do these {g} exercises", "Progress by adding weight, reps or slower lowering; 3 sets of 8-12 reps works well."),
    "barbell": (lambda e: e["equipment_raw"] == "barbell", ["Barbell {g} exercises?", "Which {g} exercises use a barbell?"],
                "Barbell {g} exercises include", "Warm up with lighter sets, use collars, and use a spotter or safety bars for heavy sets."),
    "cable": (lambda e: e["equipment_raw"] == "cable", ["Cable {g} exercises?", "What {g} exercises can I do on the cable machine?"],
              "On the cable machine you can do these {g} exercises", "Cables keep tension through the whole movement - control the weight on the way back."),
    "machine": (lambda e: e["equipment_raw"] == "machine", ["{G} machine exercises at the gym?", "Which gym machines work the {g}?"],
                "Gym machine options for the {g} include", "Adjust the seat so your joints line up with the machine's pivot, and start light."),
    "kettlebell": (lambda e: e["equipment_raw"] == "kettlebells", ["Kettlebell {g} exercises?", "What {g} exercises can I do with a kettlebell?"],
                   "Kettlebell {g} exercises include", "Drive the movement from your hips and legs and keep a neutral spine."),
    "bands": (lambda e: e["equipment_raw"] == "bands", ["Resistance band {g} exercises?", "What {g} exercises can I do with bands?"],
              "With resistance bands you can do these {g} exercises", "Check the band for tears and anchor it securely before each set."),
    "bodyweight": (lambda e: e["equipment_raw"] == "body only", ["Bodyweight {g} exercises?", "{G} exercises with no equipment?", "What {g} exercises can I do at home without equipment?"],
                   "You can do these {g} exercises with no equipment", "Make them harder over time with more reps, slower tempo or harder variations."),
    "outdoor": (lambda e: e["outdoor_friendly"], ["{G} exercises I can do at the park?", "Outdoor {g} exercises?"],
                "Good {g} exercises for the park or outdoors are", "Use a pull-up bar, bench or open space, and warm up properly in cooler weather."),
}


def pick(pool, key, k=5):
    pool = sorted(pool, key=lambda e: (not e["curated_v1"], h(key + e["name"])))
    return pool[:k]


def list_answer(exs, intro, tip):
    e0 = exs[0]
    return (f"{intro}: {join([e['name'] for e in exs])}. For example, the {e0['name']} ({e0['difficulty'].lower()}, "
            f"{e0['equipment'].lower()}) targets the {join([m.lower() for m in e0['target_muscles']])}. {tip}")


for group, gword in GROUP_WORD.items():
    for fkey, (pred, qs, intro, tip) in FILTERS.items():
        pool = [e for e in EX if e["muscle_group"] == group and pred(e)]
        if len(pool) < 3:
            continue
        key = f"list-{group}-{fkey}"
        exs = pick(pool, key)
        ans = list_answer(exs, intro.format(g=gword), tip)
        if group == "stretching":
            ans = list_answer(exs, intro.format(g=gword).replace("stretching exercises", "stretches"),
                              "Hold each stretch 15-30 seconds at mild tension, ideally after your workout.")
        cat, intent = CAT_OF_GROUP.get(group, ("home_workouts" if fkey in ("bodyweight", "outdoor") else
                                               "gym_workouts" if fkey in ("machine", "cable", "barbell") else "workout_exercises",
                                               "home_workout" if fkey == "bodyweight" else "exercise_search"))
        ctx = [format_exercise(e) for e in exs]
        table = "lifestyle" if group in ("stretching", "cardio") else "beginner" if fkey == "beginner" else "exercises"
        for q in qs:
            add(q.format(g=gword, G=gword.capitalize()), ans, cat, intent, key, "exercise_db_v2", table, context=ctx)
        if fkey in (None, "beginner", "dumbbells", "bodyweight"):
            for v in variants(qs[0].format(g=gword, G=gword.capitalize()), 2 if table != "exercises" else 1, key):
                add(v, ans, cat, intent, key, "exercise_db_v2", table, context=ctx)

MUSCLE_Q = {None: ["What exercises work the {m}?", "Best exercises for {m}?"],
            "beginner": ["Beginner exercises for the {m}?"],
            "dumbbells": ["Dumbbell exercises for the {m}?"],
            "bodyweight": ["How can I train my {m} without equipment?"]}
for m in sorted({m for e in EX for m in e["target_muscles"]}):
    ml = m.lower()
    for fkey, qs in MUSCLE_Q.items():
        pool = [e for e in EX if m in e["target_muscles"] and e["muscle_group"] not in ("stretching",) and FILTERS[fkey][0](e)]
        if len(pool) < 3:
            continue
        key = f"muscle-{ml}-{fkey}"
        exs = pick(pool, key)
        intro = {None: f"Exercises that target the {ml} include", "beginner": f"Beginner-friendly exercises for the {ml} are",
                 "dumbbells": f"Dumbbell exercises for the {ml} include", "bodyweight": f"With no equipment you can train the {ml} with"}[fkey]
        ans = list_answer(exs, intro, FILTERS[fkey][3])
        for q in qs:
            add(q.format(m=ml), ans, "workout_exercises", "home_workout" if fkey == "bodyweight" else "exercise_search",
                key, "exercise_db_v2", "beginner" if fkey == "beginner" else "exercises", context=[format_exercise(e) for e in exs])
            if fkey == "beginner":
                for v in variants(qs[0].format(m=ml), 2, key):
                    add(v, ans, "workout_exercises", "exercise_search", key, "exercise_db_v2", "beginner", context=[format_exercise(e) for e in exs])

EQUIP_Q = {"dumbbell": "dumbbells", "barbell": "a barbell", "kettlebells": "a kettlebell", "bands": "resistance bands",
           "medicine ball": "a medicine ball", "exercise ball": "an exercise ball", "cable": "the cable machine",
           "foam roll": "a foam roller", "e-z curl bar": "an EZ curl bar"}
for raw, word in EQUIP_Q.items():
    pool = [e for e in EX if e["equipment_raw"] == raw]
    by_group = defaultdict(list)
    for e in pick(pool, f"equip-{raw}", k=len(pool)):
        by_group[e["muscle_group"]].append(e)
    exs = [g[0] for g in by_group.values()][:6]
    if len(exs) < 3:
        exs = pick(pool, f"equip-{raw}", 5)
    ans = (f"With {word} you can train your whole body - for example {join([f'{e['name']} ({e['muscle_group']})' for e in exs])}. "
           "Pick 4-6 exercises that cover your legs, push, pull and core, and do 2-4 sets of 8-12 reps.")
    if raw == "foam roll":
        ans = (f"A foam roller is mainly for self-massage and mobility - for example {join([e['name'] for e in exs])}. "
               "Roll slowly for 30-60 seconds per area and avoid rolling directly on joints or the lower spine.")
    for q in (f"What exercises can I do with {word}?", f"Full body workout with {word}?"):
        add(q, ans, "fitness_equipment", "equipment", f"equip-{raw}", "exercise_db_v2", "exercises", context=[format_exercise(e) for e in exs])

# ================================================================ USDA nutrition (every number from foods.json)
def fmt(v):
    return f"{v:g}"


def basis_and_n(f, per100=False):
    p = f.get("portion")
    if p and not per100:
        return f"{f['name'].lower()}, {p['description']} ({p['grams']:g} g),", p["nutrients"]
    return f"{f['name'].lower()}, per 100 g,", f["per_100g"]


FOOD_QT = {
    "calories": (["How many calories are in {a}?", "Calories in {a}?"], lambda b, n: f"According to USDA FoodData Central, {b} provides about {fmt(n['calories_kcal'])} kcal."),
    "protein": (["How much protein is in {a}?", "Protein in {a}?"], lambda b, n: f"According to USDA FoodData Central, {b} contains about {fmt(n['protein_g'])} g of protein and {fmt(n['calories_kcal'])} kcal."),
    "carbs": (["How many carbs are in {a}?", "Carbohydrates in {a}?"], lambda b, n: f"According to USDA FoodData Central, {b} contains about {fmt(n['carbs_g'])} g of carbohydrate" + (f", including {fmt(n['fiber_g'])} g of fiber" if n.get('fiber_g') is not None else "") + "."),
    "fat": (["How much fat is in {a}?", "Fat content of {a}?"], lambda b, n: f"According to USDA FoodData Central, {b} contains about {fmt(n['fat_g'])} g of fat" + "."),
    "fiber": (["How much fiber is in {a}?", "Is {a} high in fiber?"], lambda b, n: f"According to USDA FoodData Central, {b} contains about {fmt(n['fiber_g'])} g of fiber."),
    "macros": (["What are the macros of {a}?", "Nutrition facts for {a}?", "Tell me the nutrients in {a}"],
               lambda b, n: f"According to USDA FoodData Central, {b} contains {join([x for x in (fmt(n['calories_kcal']) + ' kcal', fmt(n['protein_g']) + ' g protein', fmt(n['carbs_g']) + ' g carbohydrate', fmt(n['fat_g']) + ' g fat', (fmt(n['fiber_g']) + ' g fiber') if n.get('fiber_g') is not None else None, (fmt(n['sugar_g']) + ' g sugars') if n.get('sugar_g') is not None else None) if x])}."),
}
for f in FOODS:
    alias = f["aliases"][0] if f["aliases"] else f["name"].split(" (")[0].lower()
    kinds = ["calories", "protein", "macros", ["carbs", "fat", "fiber"][h(f["name"]) % 3]]
    if f["group"] in ("beverages",):
        kinds = ["calories", "macros", "carbs"]
    for k, kind in enumerate(kinds):
        b, n = basis_and_n(f, per100=(k % 3 == 2))
        key_val = {"calories": "calories_kcal", "protein": "protein_g", "carbs": "carbs_g", "fat": "fat_g", "fiber": "fiber_g"}.get(kind)
        if key_val and n.get(key_val) is None:
            continue
        ans = FOOD_QT[kind][1](b, n)
        if f["highlights"] and kind in ("macros", "protein"):
            ans += f" It's noted as {join([x.lower() for x in f['highlights']])} based on the USDA values."
        q = FOOD_QT[kind][0][h(f["name"] + kind) % len(FOOD_QT[kind][0])].format(a=alias)
        ctx_food = dict(f) if k % 3 != 2 else {**f, "portion": None}
        add(q, ans, "food", "food_search", f"food-v2-{f['slug']}", "usda", "nutrition", context=[format_food(ctx_food)])

# comparisons between foods of the same group (protein or calories)
by_group = defaultdict(list)
for f in FOODS:
    by_group[f["group"]].append(f)
pairs = []
for g, fs in by_group.items():
    fs = sorted(fs, key=lambda f: h("cmp" + f["name"]))
    pairs += [(fs[i], fs[i + 1]) for i in range(0, len(fs) - 1, 1)][:8]
for a, b in pairs:
    na, nb = a["per_100g"], b["per_100g"]
    metric = "protein" if a["group"] in ("protein", "plant_protein", "dairy", "dairy_alternative", "grains") else "calories"
    kk = "protein_g" if metric == "protein" else "calories_kcal"
    unit = "g of protein" if metric == "protein" else "kcal"
    if na.get(kk) is None or nb.get(kk) is None or na[kk] == nb[kk]:
        continue
    hi, lo = (a, b) if na[kk] > nb[kk] else (b, a)
    an = a["name"].split(" (")[0].lower()
    bn = b["name"].split(" (")[0].lower()
    q = (f"Which has more protein, {an} or {bn}?" if metric == "protein" else f"Which has fewer calories, {an} or {bn}?")
    ans = (f"Per 100 g, USDA FoodData Central lists {a['name'].lower()} at {fmt(na[kk])} {unit} and {b['name'].lower()} at "
           f"{fmt(nb[kk])} {unit}, so {(hi if metric == 'protein' else lo)['name'].split(' (')[0].lower()} "
           f"{'has more protein' if metric == 'protein' else 'has fewer calories'}. Portion sizes differ, so compare what you actually eat.")
    add(q, ans, "food", "food_search", f"cmp-{a['slug']}-{b['slug']}", "usda", "nutrition",
        context=[format_food({**a, "portion": None}), format_food({**b, "portion": None})])

# food lists by tag / highlight
FOOD_LISTS = [
    (["Which foods are high in protein?", "High protein foods list?", "Best foods for protein?"], lambda f: "High protein" in f["highlights"], "Foods high in protein include", "protein-sources"),
    (["Which foods are high in fiber?", "High fiber foods?", "Foods with lots of fiber?"], lambda f: "High fiber" in f["highlights"], "Foods high in fiber include", "fiber"),
    (["Low calorie foods that fill you up?", "Filling foods for weight loss?"], lambda f: f["group"] in ("vegetables", "fruit") and f["per_100g"]["calories_kcal"] < 60, "Filling, low-calorie foods include", "weight-loss-basics"),
    (["Vegan protein sources?", "Plant foods with protein?"], lambda f: "vegan" in f["fitbot_tags"] and f["per_100g"]["protein_g"] >= 5, "Plant-based protein sources include", "vegetarian-protein"),
    (["Good carbs for athletes?", "Healthy carbohydrate sources?"], lambda f: f["group"] in ("grains", "starchy_vegetable") and "limit" not in f["fitbot_tags"], "Good carbohydrate sources include", "carbs-role"),
    (["Foods high in healthy fats?", "Where do I get good fats?"], lambda f: "Mostly unsaturated fat" in f["highlights"], "Foods with mostly unsaturated fat include", "fats-role"),
    (["Which foods are high in sugar?", "Foods to watch for sugar?"], lambda f: "High sugar" in f["highlights"], "Foods high in sugar include", "sugary-drinks"),
    (["Foods high in sodium?", "Which foods have lots of salt?"], lambda f: "High sodium" in f["highlights"], "Foods high in sodium include", "limit-foods"),
]
for i, (qs, pred, intro, pid) in enumerate(FOOD_LISTS):
    fs = sorted([f for f in FOODS if pred(f)], key=lambda f: h(intro + f["name"]))[:5]
    if len(fs) < 3:
        continue
    f0 = fs[0]
    b, n = basis_and_n(f0)
    ans = (f"{intro} {join([f['name'].split(' (')[0].lower() for f in fs])}. For example, according to USDA data, {b} provides "
           f"{fmt(n['calories_kcal'])} kcal, {fmt(n['protein_g'])} g protein and {fmt(n['fiber_g'] or 0)} g fiber.")
    ctx = [format_food(f) for f in fs] + ([format_passage(KB[pid])] if pid in KB else [])
    for q in qs + variants(qs[0], 1, f"fl{i}"):
        add(q, ans, "nutrition", "nutrition_question", f"foodlist-v2-{i}", "usda", "nutrition", context=ctx)

# ================================================================ planner (workout plans and combinations)
planner = Planner(EX_V1)


def plan_answer(plan: dict) -> str:
    days = plan["days"]
    ex0 = days[0]["exercises"][0]
    parts = []
    for d in days[:3]:
        names = [e["name"].lower() for e in d["exercises"] if e["muscle_group"] != "cardio"]
        parts.append(f"{d['day']} ({d['focus'].lower()}) uses {join(names)}")
    more = f", and the remaining {len(days) - 3} days follow the same pattern" if len(days) > 3 else ""
    cardio = " Each session ends with some easy cardio." if any(e["muscle_group"] == "cardio" for e in days[0]["exercises"]) else ""
    return (f"Here's your {low(plan['title'])}. {'; '.join(parts)}{more}. Do {ex0['sets']} sets of {ex0['reps']} reps on "
            f"the main lifts and rest {ex0['rest']} between sets.{cardio} Warm up for 5-10 minutes first, leave 1-3 reps in "
            "reserve, and add weight or reps gradually as the exercises feel easier.")


GOAL_WORD = {"general_fitness": "", "weight_loss": "fat loss ", "muscle_gain": "muscle building ", "strength": "strength ", "endurance": "endurance "}
EQ_SET = {"gym": (None, "gym", "gym"), "dumbbells": (["dumbbells"], "home", "dumbbell"), "none": (["none"], "home", "bodyweight"),
          "bands": (["bands"], "home", "resistance band"), "kettlebell": (["kettlebells"], "home", "kettlebell")}
PLAN_Q = ["Give me a {lvl} {d}-day {g}{eq} workout plan", "Can you make me a {d} day {g}{eq} plan? I'm {lvl}",
          "{lvl} {eq} program, {d} days a week, {g}please", "I want a {d}-day {g}routine with {eqs}, {lvl} level"]
seen_plans = set()
cfgs = [(l, d, g, e) for l in ("beginner", "intermediate", "advanced") for d in (2, 3, 4, 5, 6)
        for g in GOAL_WORD for e in EQ_SET if not (l == "advanced" and e in ("none", "bands"))]
cfgs.sort(key=lambda c: h(str(c)))
for lvl, d, goal, eqk in cfgs:
    eq, loc, eqw = EQ_SET[eqk]
    plan = planner.plan(level=lvl, days=d, goal=goal, equipment=eq, location=loc)
    sig = json.dumps([[(e["name"], e["sets"], e["reps"]) for e in day["exercises"]] for day in plan["days"]]) + plan["title"]
    if sig in seen_plans:
        continue
    seen_plans.add(sig)
    q = PLAN_Q[h(str((lvl, d, goal, eqk))) % len(PLAN_Q)].format(lvl=lvl, d=d, g=GOAL_WORD[goal], eq=eqw,
                                                                    eqs={"gym": "a full gym", "dumbbell": "only dumbbells", "bodyweight": "no equipment", "resistance band": "resistance bands", "kettlebell": "a kettlebell"}[eqw])
    q = re.sub(r"\s+", " ", q).replace(" ,", ",").strip()
    q = q[0].upper() + q[1:]
    for qq in [q] + variants(q, 1, sig):
        add(qq, plan_answer(plan), "workout_planning" if eqk == "gym" else "home_workouts",
            "workout_plan" if eqk == "gym" else "home_workout", f"plan-v2-{len(seen_plans)}", "planner", "plans", context=plan_to_context(plan))
    if len(seen_plans) >= 330:
        break
for g in ("chest", "back", "shoulders", "legs", "arms", "core"):
    for lvl in ("beginner", "intermediate", "advanced"):
        for eqk in ("gym", "dumbbells", "none", "bands"):
            eq, loc, eqw = EQ_SET[eqk]
            w = planner.muscle_workout(g, level=lvl, equipment=eq, location=loc)
            items = w["days"][0]["exercises"]
            if len(items) < 2:
                continue
            sig = json.dumps([e["name"] for e in items]) + lvl + g
            if sig in seen_plans:
                continue
            seen_plans.add(sig)
            e0 = items[0]
            ans = (f"Here's a {lvl} {eqw} {g} workout: " + "; ".join(f"{e['name']} {e['sets']} x {e['reps']}" for e in items)
                   + f". Rest {e0['rest']} between sets, warm up first, and add weight or reps gradually as it gets easier.")
            add(f"Give me a {lvl} {eqw} {g} workout", ans, "gym_workouts" if eqk == "gym" else "home_workouts",
                "gym_workout" if eqk == "gym" else "home_workout", f"mw-v2-{g}-{lvl}-{eqk}", "planner", "plans",
                context=plan_to_context(w))

# ================================================================ multi-turn conversations (grounded chains)
OPEN = ["What exercises can I do for {g}?", "Which {g} exercises should I do?", "Give me some {g} exercises"]
LVL_FU = {"beginner": ["I'm a beginner.", "I'm new to this.", "I'm just starting out."],
          "intermediate": ["I've been training for a year.", "I'm intermediate.", "I'm not a beginner, I've lifted for a while."]}
EQ_FU = {"dumbbell": ["I only have dumbbells.", "Just dumbbells at home."], "body only": ["I don't have any equipment.", "No equipment, at home."],
         "bands": ["I only have resistance bands.", "Just bands."], "kettlebells": ["I only have a kettlebell."],
         "gym": ["I have a full gym.", "I train at a gym."]}
conv_n = 0
for group in ("chest", "back", "shoulders", "legs", "arms", "core"):
    gw = GROUP_WORD[group]
    for lvl in ("beginner", "intermediate"):
        for eqraw in ("dumbbell", "body only", "bands", "kettlebells", "gym"):
            key = f"conv-v2-{group}-{lvl}-{eqraw}"
            pool0 = [e for e in EX if e["muscle_group"] == group]
            ex1 = pick(pool0, key + "a")
            lv_ok = (lambda e: e["difficulty"] == "Beginner") if lvl == "beginner" else (lambda e: e["difficulty"] in ("Beginner", "Intermediate"))
            ex2 = pick([e for e in pool0 if lv_ok(e)], key + "b")
            eqpred = (lambda e: e["equipment_raw"] in ("barbell", "cable", "machine", "dumbbell")) if eqraw == "gym" else (lambda e, r=eqraw: e["equipment_raw"] == r)
            ex3 = pick([e for e in pool0 if lv_ok(e) and eqpred(e)], key + "c", 4)
            if len(ex2) < 3 or len(ex3) < 2:
                continue
            conv_n += 1
            q1 = OPEN[h(key) % 3].format(g=gw)
            a1 = list_answer(ex1, f"Here are some effective {gw} exercises", "Mix compound and isolation movements for 2-4 sets of 8-12 reps.")
            q2 = LVL_FU[lvl][h(key + "l") % len(LVL_FU[lvl])]
            a2 = (f"Since you're a beginner, start with these {gw} exercises: {join([e['name'] for e in ex2])}. Do 2-3 sets of 10-12 controlled reps and learn the form before adding weight."
                  if lvl == "beginner" else f"With some training experience, good {gw} options are {join([e['name'] for e in ex2])}. Work in the 6-12 rep range, 3-4 sets, and add load gradually.")
            q3 = EQ_FU[eqraw][h(key + "e") % len(EQ_FU[eqraw])]
            sets = "2-3 sets of 10-12" if lvl == "beginner" else "3-4 sets of 8-12"
            a3 = (f"With that setup, try this {gw} workout: " + "; ".join(f"{e['name']} {sets}" for e in ex3)
                  + f". Rest 60-90 seconds between sets and progress by adding reps or weight once all sets feel controlled.")
            prof = {"fitness_level": lvl}
            h1 = [{"role": "user", "content": q1}, {"role": "assistant", "content": a1}]
            h2 = h1 + [{"role": "user", "content": q2}, {"role": "assistant", "content": a2}]
            h3 = h2 + [{"role": "user", "content": q3}, {"role": "assistant", "content": a3}]
            add(q1, a1, "workout_exercises", "exercise_search", key, "conversation_v2", "multi_turn", context=[format_exercise(e) for e in ex1])
            add(q2, a2, "workout_exercises", "exercise_search", key, "conversation_v2", "multi_turn", context=[format_exercise(e) for e in ex2], history=h1, profile=prof)
            add(q3, a3, "home_workouts" if eqraw != "gym" else "gym_workouts", "home_workout" if eqraw != "gym" else "gym_workout",
                key, "conversation_v2", "multi_turn", context=[format_exercise(e) for e in ex3], history=h2,
                profile={**prof, "equipment": [{"body only": "none", "dumbbell": "dumbbells"}.get(eqraw, eqraw)]})
            # 4th turn: how to do the first exercise, or what to eat after
            e0 = ex3[0]
            if h(key + "4") % 2 and e0["instructions"]:
                q4 = ["How do I do the first one?", f"How do I do the {e0['name']}?", "Can you explain the first exercise?"][h(key + "q4") % 3]
                a4 = f"{e0['description']} How to do it: {short_steps(e0, n=3, max_chars=380)} Safety tip: {e0['safety_tips'][0]}"
                add(q4, a4, "exercise_safety", "exercise_safety", key, "conversation_v2", "multi_turn", context=[format_exercise_detail(e0)], history=h3, profile=prof)
            else:
                fs = [FOOD_BY_NAME[n] for n in ("Greek yogurt (plain, nonfat)", "Chicken breast (roasted)", "Tofu (firm)", "Banana", "White rice (cooked)")]
                f0 = fs[h(key) % 3]
                b, n = basis_and_n(f0)
                q4 = ["What should I eat after this workout?", "What's a good meal after this?", "Any food tips after training?"][h(key + "q4") % 3]
                a4 = (f"After this workout, aim for a meal with about 20-40 g of protein plus some carbohydrates - for example Greek yogurt with a banana, "
                      f"chicken breast with rice, or tofu with rice and vegetables. For reference, USDA data lists {b} at about {fmt(n['protein_g'])} g of protein. Drink some water too.")
                add(q4, a4, "pre_post_workout", "nutrition_question", key, "conversation_v2", "multi_turn",
                    context=[format_food(f) for f in fs] + [format_passage(KB["post-workout"])], history=h3, profile=prof)

# food follow-up chains: A -> "what about B?" -> "which is better for protein?"
food_chain_pairs = [(a, b) for a, b in pairs if a["group"] in ("protein", "plant_protein", "dairy", "grains", "fruit", "snacks", "fats")][:40]
for i, (a, b) in enumerate(food_chain_pairs):
    key = f"foodconv-v2-{i}"
    aa = a["aliases"][0] if a["aliases"] else a["name"].split(" (")[0].lower()
    bb = b["aliases"][0] if b["aliases"] else b["name"].split(" (")[0].lower()
    ba, na = basis_and_n(a)
    bbs, nb = basis_and_n(b)
    q1 = f"How much protein is in {aa}?"
    a1 = f"According to USDA FoodData Central, {ba} contains about {fmt(na['protein_g'])} g of protein and {fmt(na['calories_kcal'])} kcal."
    q2 = ["What about {b}?", "And {b}?", "How about {b}?"][i % 3].format(b=bb)
    a2 = f"According to USDA FoodData Central, {bbs} contains about {fmt(nb['protein_g'])} g of protein and {fmt(nb['calories_kcal'])} kcal."
    pa, pb = a["per_100g"], b["per_100g"]
    better = a if pa["protein_g"] >= pb["protein_g"] else b
    q3 = ["Which one has more protein per 100 g?", "Which is better for protein?", "So which has more protein?"][i % 3]
    a3 = (f"Per 100 g, {a['name'].lower()} has {fmt(pa['protein_g'])} g of protein and {b['name'].lower()} has {fmt(pb['protein_g'])} g "
          f"(USDA), so {better['name'].split(' (')[0].lower()} has more. Both can fit a balanced diet - choose based on your portion, taste and overall meal.")
    h1 = [{"role": "user", "content": q1}, {"role": "assistant", "content": a1}]
    h2 = h1 + [{"role": "user", "content": q2}, {"role": "assistant", "content": a2}]
    add(q1, a1, "food", "food_search", key, "conversation_v2", "multi_turn", context=[format_food(a)])
    add(q2, a2, "food", "food_search", key, "conversation_v2", "multi_turn", context=[format_food(b)], history=h1)
    add(q3, a3, "food", "food_search", key, "conversation_v2", "multi_turn",
        context=[format_food({**a, "portion": None}), format_food({**b, "portion": None})], history=h2)

# plan follow-up chains: plan -> change days -> change equipment
for i, (lvl, d1, d2, goal) in enumerate([(l, a, b, g) for l in ("beginner", "intermediate") for a, b in ((3, 4), (4, 3), (2, 3), (3, 5))
                                           for g in ("general_fitness", "weight_loss", "muscle_gain")][:24]):
    key = f"planconv-v2-{i}"
    p1 = planner.plan(level=lvl, days=d1, goal=goal, location="gym")
    p2 = planner.plan(level=lvl, days=d2, goal=goal, location="gym")
    p3 = planner.plan(level=lvl, days=d2, goal=goal, equipment=["dumbbells"], location="home")
    q1 = f"Make me a {lvl} {d1}-day {GOAL_WORD[goal]}gym plan".replace("  ", " ")
    q2 = [f"Can you make it {d2} days instead?", f"Actually I can train {d2} days a week.", f"Change it to {d2} days please."][i % 3]
    q3 = ["What if I train at home with only dumbbells?", "I can't get to the gym this month, I only have dumbbells.", "Make it a home version with dumbbells."][i % 3]
    a1, a2, a3 = plan_answer(p1), plan_answer(p2), plan_answer(p3)
    h1 = [{"role": "user", "content": q1}, {"role": "assistant", "content": a1}]
    h2 = h1 + [{"role": "user", "content": q2}, {"role": "assistant", "content": a2}]
    prof = {"fitness_level": lvl, "goal": goal}
    add(q1, a1, "workout_planning", "workout_plan", key, "conversation_v2", "multi_turn", context=plan_to_context(p1), profile=prof)
    add(q2, a2, "workout_planning", "workout_plan", key, "conversation_v2", "multi_turn", context=plan_to_context(p2), history=h1, profile=prof)
    add(q3, a3, "home_workouts", "home_workout", key, "conversation_v2", "multi_turn", context=plan_to_context(p3), history=h2,
        profile={**prof, "equipment": ["dumbbells"], "location": "home"})


# ================================================================ cleaning, merge with v1, split
def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


UNSAFE = [r"\bfast(ing)? for \d+ days\b(?! to lose)", r"\b(eat|consume) (less than|under) (500|600|800|1000) calories\b",
          r"\bdehydrate yourself\b", r"\bpush through (the )?pain\b", r"\bno need to see a doctor\b", r"\bguaranteed\b"]
NUM = re.compile(r"\d+(?:\.\d+)?")

v1 = []
for fname, sp in (("training.jsonl", "train"), ("validation.jsonl", "validation"), ("test.jsonl", "test")):
    for line in (V1 / fname).read_text().splitlines():
        r = json.loads(line)
        r.pop("messages", None)
        r["split"], r["dataset_version"] = sp, "v1"
        r["table_category"] = {"food": "nutrition", "nutrition": "nutrition", "pre_post_workout": "nutrition",
                               "workout_exercises": "exercises", "gym_workouts": "exercises", "fitness_equipment": "exercises",
                               "home_workouts": "plans" if r["source"] == "planner" else "exercises",
                               "workout_planning": "plans", "exercise_safety": "form_safety", "medical_safety": "medical",
                               "out_of_domain": "off_topic", "weight_loss": "goals", "muscle_building": "goals",
                               "cardio_endurance": "lifestyle", "stretching_flexibility": "lifestyle", "hydration": "lifestyle",
                               "recovery_sleep": "lifestyle", "healthy_lifestyle": "general_fitness", "greeting": "general_fitness"}.get(r["category"], "general_fitness")
        if r["history"] and r["source"] == "conversation":
            r["table_category"] = "multi_turn"
        v1.append(r)

stats = Counter(raw_new=len(records))
seen_key = {(norm(r["input"]), norm(" ".join(x["content"] for x in r["history"])), json.dumps(r["profile"], sort_keys=True)) for r in v1}
seen_input = {norm(r["input"]): (r["group_id"], r["response"]) for r in v1 if not r["history"] and not r["profile"]}
clean = []
for r in records:
    if len(r["response"]) < 25 or len(r["response"]) > 1600:
        stats["removed_length"] += 1
        continue
    if any(re.search(p, r["response"].lower()) for p in UNSAFE):
        stats["removed_unsafe"] += 1
        continue
    key = (norm(r["input"]), norm(" ".join(x["content"] for x in r["history"])), json.dumps(r["profile"], sort_keys=True))
    if key in seen_key:
        stats["removed_duplicate"] += 1
        continue
    if not r["history"] and not r["profile"]:
        prev = seen_input.get(norm(r["input"]))
        if prev and prev[0] != r["group_id"] and norm(prev[1]) != norm(r["response"]):
            stats["removed_conflicting"] += 1
            continue
        seen_input.setdefault(norm(r["input"]), (r["group_id"], r["response"]))
    # grounding check: every number in a USDA answer must appear in its context
    if r["source"] == "usda":
        ctx = " ".join(r["context"])
        if any(n not in ctx for n in NUM.findall(r["response"]) if n not in ("100",)):
            stats["removed_ungrounded_number"] += 1
            continue
    seen_key.add(key)
    clean.append(r)
stats["clean_new"] = len(clean)

# split new records: exercise-specific groups follow the image-dataset split of that exercise; other groups are
# split 80/10/10 per table category by a stable hash of the group id (paraphrases/variants never cross splits)
group_split = {}
by_table = defaultdict(set)
for r in clean:
    if r["_split"]:
        group_split[r["group_id"]] = r["_split"]
    else:
        by_table[r["table_category"]].add(r["group_id"])
for t, gids in by_table.items():
    gids = sorted(gids, key=lambda g: h(g))
    n = len(gids)
    for k, g in enumerate(gids):
        group_split.setdefault(g, "test" if k < round(n * .1) else "validation" if k < round(n * .2) else "train")
for r in clean:
    r["split"] = group_split[r["group_id"]]
    del r["_split"]

allr = v1 + clean
for r in allr:
    r["messages"] = build_messages(r["input"], r["context"], r["profile"], r["history"]) + [{"role": "assistant", "content": r["response"]}]

splits = {s: [r for r in allr if r["split"] == s] for s in ("train", "validation", "test")}
# leakage checks
gs = {s: {r["group_id"] for r in v} for s, v in splits.items()}
assert not (gs["train"] & gs["test"]) and not (gs["train"] & gs["validation"]), "group leakage"
train_inputs = {norm(r["input"]) for r in splits["train"] if not r["history"]}
leak = sum(1 for r in splits["test"] if not r["history"] and norm(r["input"]) in train_inputs)

OUT.mkdir(parents=True, exist_ok=True)
fname = {"train": "training.jsonl", "validation": "validation.jsonl", "test": "test.jsonl"}
for s, rs in splits.items():
    random.Random(SEED).shuffle(rs)
    with open(OUT / fname[s], "w") as fh:
        for r in rs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(OUT / "test_v1.jsonl", "w") as fh:          # the original 97 v1 test records, for old-vs-new comparison
    for r in splits["test"]:
        if r["dataset_version"] == "v1":
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

table = Counter(r["table_category"] for r in allr)
summary = {
    "total_records": len(allr), "v1_records": len(v1), "new_v2_records": len(clean), "cleaning_new": dict(stats),
    "split_sizes": {s: len(v) for s, v in splits.items()},
    "test_v1_records": sum(1 for r in splits["test"] if r["dataset_version"] == "v1"),
    "test_inputs_also_in_train_after_normalisation": leak,
    "by_table_category": {t: table[t] for t in TABLE},
    "by_table_category_and_split": {t: {s: sum(1 for r in splits[s] if r["table_category"] == t) for s in splits} for t in TABLE},
    "by_intent": dict(Counter(r["intent"] for r in allr).most_common()),
    "by_source": dict(Counter(r["source"] for r in allr).most_common()),
    "exercises_covered": len({r["group_id"] for r in allr if r["group_id"].startswith("ex-")}),
    "with_context": sum(1 for r in allr if r["context"]), "with_history": sum(1 for r in allr if r["history"]),
    "with_profile": sum(1 for r in allr if r["profile"]),
    "avg_response_words": round(sum(len(r["response"].split()) for r in allr) / len(allr), 1),
}
(OUT / "dataset_stats.json").write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k not in ("by_intent", "by_table_category_and_split")}, indent=2))
