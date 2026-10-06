"""Build the FitBot conversational dataset (train / validation / test JSONL).

Inputs
  scripts/dataset_content/*.py          hand-written seeds, conversations, safety & OOD examples
  data/exercises/exercises.json         free-exercise-db derived exercise facts
  data/nutrition/foods.json             USDA FoodData Central SR Legacy values
  data/knowledge/knowledge_base.json    general guidance passages (for retrieval context)

Outputs (data/processed/)
  training.jsonl, validation.jsonl, test.jsonl, dataset_stats.json

Each record:
  instruction  short system instruction (spec field)
  input        the user's message
  response     FitBot's reply (training target)
  category     one of the 16 dataset categories (+ medical_safety / out_of_domain / greeting)
  intent       intent label used by the intent classifier
  context      list of reference lines given to the model (retrieval simulation), may be empty
  history      previous turns [{role, content}] for follow-up questions, may be empty
  profile      optional user profile used for personalisation
  group_id     records sharing a group always land in the same split (no paraphrase leakage)
  source       seed | conversation | exercise_db | usda | planner | safety | ood
  messages     full chat (system+context, history, user, assistant) used for fine-tuning
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
                              format_exercise_detail, format_food, format_passage)
from app.ml.retriever import KnowledgeRetriever  # noqa: E402
from app.services.planner import Planner, plan_to_context  # noqa: E402
from dataset_content import seeds_core, seeds_dialogue, seeds_more  # noqa: E402

OUT = ROOT / "data" / "processed"
SEED = 42
rng = random.Random(SEED)

EXERCISES = json.loads((ROOT / "data/exercises/exercises.json").read_text())
FOODS = json.loads((ROOT / "data/nutrition/foods.json").read_text())
KB = json.loads((ROOT / "data/knowledge/knowledge_base.json").read_text())["passages"]
EX_BY_NAME = {e["name"]: e for e in EXERCISES}
FOOD_BY_NAME = {f["name"]: f for f in FOODS}

records: list[dict] = []


def add(inp, resp, category, intent, group, source, context=None, history=None, profile=None):
    records.append({
        "instruction": SHORT_INSTRUCTION, "input": inp.strip(), "response": resp.strip(),
        "category": category, "intent": intent, "context": context or [], "history": history or [],
        "profile": profile or None, "group_id": group, "source": source,
    })


# ---------------------------------------------------------------- retrieval for seeds
RETRIEVER = KnowledgeRetriever(ROOT / "data/knowledge/knowledge_base.json")
print(f"retriever backend: {RETRIEVER.backend}")


def top_passages(question: str, k: int = 2, topic: str | None = None) -> list[dict]:
    return RETRIEVER.search(question, k=k, topic=topic)


# ---------------------------------------------------------------- 1. hand-written seeds
for src_name, seeds in (("core", seeds_core.SEEDS), ("more", seeds_more.SEEDS)):
    for i, (cat, intent, questions, answer) in enumerate(seeds):
        gid = f"seed-{src_name}-{i}"
        for j, q in enumerate(questions):
            ctx = [format_passage(p) for p in top_passages(q, topic=intent)] if j % 2 == 0 else []
            add(q, answer, cat, intent, gid, "seed", context=ctx)

# safety
for i, (cat, intent, questions, answer) in enumerate(seeds_dialogue.SAFETY_SEEDS):
    for q in questions:
        add(q, answer, "medical_safety", intent, f"safety-{i}", "safety")

# out of domain (each question its own group)
for i, q in enumerate(seeds_dialogue.OOD_QUESTIONS):
    add(q, seeds_dialogue.OOD_VARIANTS[i % len(seeds_dialogue.OOD_VARIANTS)], "out_of_domain",
        "out_of_domain", f"ood-{i}", "ood")

# greetings
for i, (questions, answer) in enumerate(seeds_dialogue.GREETINGS):
    for q in questions:
        add(q, answer, "greeting", "greeting", f"greet-{i}", "seed")

# multi-turn conversations: one record per assistant turn, earlier turns as history
for i, (cat, intents, profile, turns) in enumerate(seeds_dialogue.CONVERSATIONS):
    history: list[dict] = []
    for t, (user, assistant) in enumerate(turns):
        add(user, assistant, cat if intents[t] != "out_of_domain" else "out_of_domain", intents[t],
            f"conv-{i}", "conversation", history=list(history), profile=profile)
        history += [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]

# personalised single-turn
for i, (profile, intent, cat, questions, answer) in enumerate(seeds_dialogue.PERSONALISED):
    for q in questions:
        add(q, answer, cat, intent, f"profile-{i}", "seed", profile=profile)


# ---------------------------------------------------------------- 2. exercise-grounded
def lower_first(s: str) -> str:
    return s[0].lower() + s[1:] if s else s


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


HOWTO_Q = ["How do I do {n}?", "How do I perform the {n} correctly?", "Can you explain how to do {n}?",
           "What muscles does the {n} work?", "Show me how to do {n}", "Tips for doing {n} with good form?"]

for ex in EXERCISES:
    n = ex["name"]
    muscles = join_names([m.lower() for m in ex["target_muscles"] + ex["secondary_muscles"][:2]])
    steps = format_exercise_detail(ex).split("| how to: ")[1].split(" | safety:")[0]
    first_steps = " ".join(steps.split(". ")[:2]).rstrip(".") + "."
    qs = rng.sample(HOWTO_Q, 2)
    for k, tmpl in enumerate(qs):
        q = tmpl.format(n=n.lower() if k else n)
        if "muscles" in tmpl:
            resp = (f"The {n} mainly works the {muscles}. {ex['description']} It's rated "
                    f"{ex['difficulty'].lower()} and uses {ex['equipment'].lower()}. "
                    f"Safety tip: {ex['safety_tips'][0]}")
        else:
            resp = (f"{ex['description']} It mainly targets the {muscles}. How to do it: {first_steps} "
                    f"Safety tip: {ex['safety_tips'][0]}")
        add(q, resp, "workout_exercises" if ex["muscle_group"] not in ("cardio", "stretching") else
            ("cardio_endurance" if ex["muscle_group"] == "cardio" else "stretching_flexibility"),
            "exercise_search" if ex["muscle_group"] != "stretching" else "stretching",
            f"howto-{ex['slug']}", "exercise_db", context=[format_exercise_detail(ex)])

GROUP_Q = {
    None: ["What exercises can I do for {g}?", "Best {g} exercises?", "Give me some {g} exercises",
           "Which exercises work the {g}?"],
    "beginner": ["What are good {g} exercises for beginners?", "Beginner {g} exercises?"],
    "dumbbells": ["What {g} exercises can I do with dumbbells?", "Dumbbell {g} exercises?"],
    "bodyweight": ["What {g} exercises can I do at home without equipment?", "Bodyweight {g} exercises?"],
}
GROUP_WORDS = {"chest": "chest", "back": "back", "shoulders": "shoulder", "legs": "leg", "arms": "arm",
               "core": "core", "cardio": "cardio", "stretching": "stretching"}


def filter_group(group, flt):
    exs = [e for e in EXERCISES if e["muscle_group"] == group]
    if flt == "beginner":
        exs = [e for e in exs if e["difficulty"] == "Beginner"]
    elif flt == "dumbbells":
        exs = [e for e in exs if e["equipment_raw"] in ("dumbbell", "body only", "kettlebells")]
    elif flt == "bodyweight":
        exs = [e for e in exs if e["equipment_raw"] == "body only" or e["home_friendly"] and e["muscle_group"] in ("cardio", "stretching")]
    return exs[:6]


FILTER_TIP = {
    None: "Compound movements build the most overall strength; add one or two isolation exercises for extra focus. Aim for 2-4 sets of 8-12 reps.",
    "beginner": "As a beginner, start with light weights or easier variations, do 2-3 sets of 10-12 reps, and focus on controlled, full-range movement before adding load.",
    "dumbbells": "With dumbbells you can progress by adding weight, reps or slower lowering. Try 3 sets of 8-12 reps with 60-90 seconds of rest.",
    "bodyweight": "None of these need equipment. Make them harder over time with more reps, slower tempo or harder variations.",
}

for group in GROUP_WORDS:
    for flt, templates in GROUP_Q.items():
        exs = filter_group(group, flt)
        if len(exs) < 2:
            continue
        ctx = [format_exercise(e) for e in exs]
        names = [e["name"] for e in exs]
        first = exs[0]
        detail = (f"For example, the {first['name']} ({first['difficulty'].lower()}, {first['equipment'].lower()}) "
                  f"targets the {join_names([m.lower() for m in first['target_muscles']])}.")
        tip = FILTER_TIP[flt]
        if group == "cardio":
            tip = "Aim for at least 150 minutes of moderate cardio per week, and start at an easy, conversational pace."
        elif group == "stretching":
            tip = "Hold each static stretch for about 10-30 seconds at mild tension, ideally after your workout."
        intro = {None: f"Here are some effective {GROUP_WORDS[group]} exercises",
                 "beginner": f"Good beginner-friendly {GROUP_WORDS[group]} exercises are",
                 "dumbbells": f"With dumbbells you can do these {GROUP_WORDS[group]} exercises",
                 "bodyweight": f"You can do these {GROUP_WORDS[group]} exercises with no equipment"}[flt]
        resp = f"{intro}: {join_names(names)}. {detail} {tip}"
        for q in templates:
            add(q.format(g=GROUP_WORDS[group]), resp, "workout_exercises" if group not in ("cardio", "stretching")
                else ("cardio_endurance" if group == "cardio" else "stretching_flexibility"),
                {"cardio": "cardio", "stretching": "stretching"}.get(group, "home_workout" if flt == "bodyweight" else "exercise_search"),
                f"group-{group}-{flt}", "exercise_db", context=ctx)


# ---------------------------------------------------------------- 3. USDA-grounded food facts
def fmt(v):
    return f"{v:g}"


def food_fact_answer(food, qtype):
    p = food["portion"]
    n = p["nutrients"] if p else food["per_100g"]
    basis = f"{food['name'].lower()}, {p['description']} ({p['grams']:g} g)," if p else f"{food['name'].lower()}, per 100 g,"
    hl = ""
    if food["highlights"]:
        hl = f" It's noted as {join_names([h.lower() for h in food['highlights']])} based on the USDA values."
    if qtype == "protein":
        return (f"According to USDA FoodData Central, {basis} contains about {fmt(n['protein_g'])} g of protein "
                f"and {fmt(n['calories_kcal'])} kcal.{hl}")
    if qtype == "calories":
        return (f"According to USDA FoodData Central, {basis} provides about {fmt(n['calories_kcal'])} kcal, "
                f"with {fmt(n['protein_g'])} g protein, {fmt(n['carbs_g'])} g carbohydrate and {fmt(n['fat_g'])} g fat.{hl}")
    parts = [f"{fmt(n['calories_kcal'])} kcal", f"{fmt(n['protein_g'])} g protein", f"{fmt(n['carbs_g'])} g carbohydrate",
             f"{fmt(n['fat_g'])} g fat"]
    if n.get("fiber_g") is not None:
        parts.append(f"{fmt(n['fiber_g'])} g fiber")
    if n.get("sugar_g") is not None:
        parts.append(f"{fmt(n['sugar_g'])} g sugars")
    return f"According to USDA FoodData Central, {basis} contains {join_names(parts)}.{hl}"


FOOD_Q = {
    "protein": ["How much protein is in {a}?", "How much protein does {a} have?", "Protein content of {a}?"],
    "calories": ["How many calories are in {a}?", "Calories in {a}?"],
    "general": ["What are the nutrition facts for {a}?", "What nutrients are in {a}?", "Tell me the macros of {a}"],
}
for food in FOODS:
    if food["per_100g"].get("calories_kcal") is None:
        continue
    alias = food["aliases"][0] if food["aliases"] else food["name"].lower()
    if alias in ("egg", "eggs") and "hard-boiled" in food["name"]:
        alias = "an egg"
    qtypes = ["protein", "calories", "general"]
    if food["group"] in ("beverages", "treats", "fruit", "vegetables"):
        qtypes = ["calories", "general"]
    chosen = rng.sample(qtypes, 2 if food["group"] in ("protein", "plant_protein", "dairy", "grains") else 1)
    for qt in chosen:
        q = rng.choice(FOOD_Q[qt]).format(a=alias)
        add(q, food_fact_answer(food, qt), "food", "food_search", f"food-{food['slug']}", "usda",
            context=[format_food(food)])

# food list questions -> context = several USDA foods (+ a guidance passage)
LIST_QUERIES = [
    ("high_protein", ["What foods are high in protein?", "Give me high protein foods", "Best protein sources?"],
     lambda f: "High protein" in f["highlights"] and f["group"] in ("protein", "plant_protein", "dairy"),
     "Good high-protein foods include", "protein-sources", "nutrition", "nutrition_question"),
    ("veg_protein", ["What are good vegetarian protein sources?", "Vegetarian foods high in protein?", "Plant-based protein foods?"],
     lambda f: "vegetarian" in f["fitbot_tags"] and "High protein" in f["highlights"],
     "Good vegetarian protein sources include", "vegetarian-protein", "nutrition", "nutrition_question"),
    ("fiber", ["What foods are high in fiber?", "Which foods have lots of fiber?"],
     lambda f: "High fiber" in f["highlights"] and f["group"] not in ("treats",),
     "Foods high in fiber include", "fiber", "nutrition", "nutrition_question"),
    ("fats", ["What foods contain healthy fats?", "Sources of healthy fats?", "Which foods have good fats?"],
     lambda f: "healthy_fats" in f["fitbot_tags"] or "omega3" in f["fitbot_tags"],
     "Foods with mostly healthy, unsaturated fats include", "fats-role", "nutrition", "nutrition_question"),
    ("snacks", ["What are healthy snacks?", "Give me some healthy snack ideas", "Good snacks for weight loss?"],
     lambda f: "snack" in f["fitbot_tags"] and "limit" not in f["fitbot_tags"],
     "Healthy snack options include", "snacks", "food", "food_search"),
    ("breakfast", ["What should I eat for breakfast?", "Healthy breakfast foods?", "Good breakfast for fitness?"],
     lambda f: "breakfast" in f["fitbot_tags"],
     "Good breakfast foods include", "breakfast", "nutrition", "nutrition_question"),
    ("post", ["What should I eat after working out?", "Good post-workout foods?", "What to eat after the gym?"],
     lambda f: "post_workout" in f["fitbot_tags"],
     "Good post-workout foods include", "post-workout", "pre_post_workout", "nutrition_question"),
    ("pre", ["What should I eat before working out?", "Good pre-workout foods?"],
     lambda f: "pre_workout" in f["fitbot_tags"] and f["group"] != "beverages",
     "Good pre-workout foods include", "pre-workout", "pre_post_workout", "nutrition_question"),
    ("drinks_limit", ["What drinks should I limit?", "Which drinks are bad for weight loss?", "Drinks to avoid when dieting?"],
     lambda f: f["group"] == "beverages" and "limit" in f["fitbot_tags"],
     "Drinks that are worth limiting include", "sugary-drinks", "hydration", "hydration"),
    ("foods_limit", ["What foods should I limit during weight loss?", "Which foods should I eat less of?", "Foods to limit for fat loss?"],
     lambda f: f["group"] == "treats" and "limit" in f["fitbot_tags"],
     "Foods that are often worth limiting include", "limit-foods", "weight_loss", "weight_loss"),
    ("hydrating", ["What are good drinks for hydration?", "Best drinks to stay hydrated?"],
     lambda f: "hydrating" in f["fitbot_tags"],
     "Good choices for hydration include", "hydration-daily", "hydration", "hydration"),
]
KB_BY_ID = {p["id"]: p for p in KB}
for key, questions, pred, intro, pid, cat, intent in LIST_QUERIES:
    foods = [f for f in FOODS if pred(f)]
    rng.shuffle(foods)
    foods = foods[:5]
    if len(foods) < 3:
        continue
    ctx = [format_food(f) for f in foods] + [format_passage(KB_BY_ID[pid])]
    names = [f["name"].split(" (")[0].lower() for f in foods]
    ex = foods[0]
    n = ex["portion"]["nutrients"] if ex["portion"] else ex["per_100g"]
    basis = ex["portion"]["description"] if ex["portion"] else "100 g"
    if key in ("drinks_limit", "foods_limit"):
        fact = (f"For example, {basis} of {ex['name'].lower()} has about {fmt(n['calories_kcal'])} kcal and "
                f"{fmt(n['sugar_g'] or 0)} g of sugars according to USDA data.")
        close = " You don't have to cut them out completely - enjoy them less often and in smaller portions, and choose water, unsweetened drinks and whole foods most of the time."
    elif key in ("fiber",):
        fact = f"For example, {basis} of {ex['name'].lower()} provides about {fmt(n['fiber_g'])} g of fiber (USDA)."
        close = " Increase fiber gradually and drink enough water."
    elif key == "hydrating":
        fact = "Plain water is the best everyday choice, and water-rich foods also contribute to hydration."
        close = " Aim for pale yellow urine as a simple hydration check."
    else:
        fact = (f"For example, {basis} of {ex['name'].lower()} provides about {fmt(n['protein_g'])} g of protein "
                f"and {fmt(n['calories_kcal'])} kcal according to USDA data.")
        close = {"post": " Pair a protein source with carbohydrates within a few hours after training.",
                 "pre": " Eat a larger meal 1-3 hours before, or a small snack 30-60 minutes before training.",
                 "breakfast": " Combine a protein food with fiber-rich carbs and fruit for a balanced breakfast.",
                 "snacks": " Snacks with protein or fiber keep you fuller between meals."}.get(key, " Include a protein source at each meal.")
    resp = f"{intro} {join_names(names)}. {fact}{close}"
    for q in questions:
        add(q, resp, cat, intent, f"foodlist-{key}", "usda", context=ctx)


# ---------------------------------------------------------------- 4. planner-grounded plans
planner = Planner(EXERCISES)
PLAN_CONFIGS = [
    ("beginner", 3, "general_fitness", None, "gym", "Give me a beginner 3-day gym workout"),
    ("beginner", 3, "weight_loss", None, "gym", "I'm a beginner who wants to lose weight, make me a 3 day gym plan"),
    ("beginner", 2, "general_fitness", ["none"], "home", "I need a 2 day home workout plan with no equipment"),
    ("beginner", 3, "general_fitness", ["none"], "home", "Create a beginner home workout plan for 3 days"),
    ("beginner", 3, "muscle_gain", ["dumbbells"], "home", "Beginner dumbbell workout plan for 3 days"),
    ("beginner", 3, "weight_loss", ["dumbbells"], "home", "I want to lose weight and only have dumbbells, give me a plan"),
    ("intermediate", 4, "muscle_gain", None, "gym", "Give me a 4 day muscle building gym plan"),
    ("intermediate", 4, "strength", None, "gym", "Intermediate 4-day strength program please"),
    ("intermediate", 3, "general_fitness", None, "gym", "3 day full body plan for an intermediate lifter"),
    ("intermediate", 5, "muscle_gain", None, "gym", "Make me a 5 day push pull legs routine"),
    ("intermediate", 3, "muscle_gain", ["dumbbells"], "home", "Intermediate dumbbell plan, 3 days a week"),
    ("advanced", 5, "strength", None, "gym", "Advanced 5 day strength split"),
    ("advanced", 4, "muscle_gain", None, "gym", "I'm advanced, give me a 4 day hypertrophy plan"),
    ("advanced", 6, "muscle_gain", None, "gym", "6 day PPL program for advanced lifter"),
    ("beginner", 3, "endurance", ["none"], "home", "Beginner plan to improve endurance at home"),
    ("intermediate", 4, "weight_loss", None, "gym", "4 day fat loss gym workout plan"),
]
PARA = ["Can you create {x}?", "{x}, please", "I'd like {x}"]


def plan_answer(plan: dict) -> str:
    days = plan["days"]
    ex0 = days[0]["exercises"][0]
    parts = []
    for d in days[:3]:
        names = [e["name"].lower() for e in d["exercises"] if e["muscle_group"] != "cardio"]
        parts.append(f"{d['day']} ({d['focus'].lower()}) uses {join_names(names)}")
    more = f", and the remaining {len(days) - 3} days follow the same pattern" if len(days) > 3 else ""
    cardio = " Each session ends with some easy cardio." if any(e["muscle_group"] == "cardio" for e in days[0]["exercises"]) else ""
    return (f"Here's your {plan['title'][0].lower() + plan['title'][1:]}. {'; '.join(parts)}{more}. "
            f"Do {ex0['sets']} sets of {ex0['reps']} reps on the main lifts and rest {ex0['rest']} between sets.{cardio} "
            "Warm up for 5-10 minutes first, leave 1-3 reps in reserve, and add weight or reps gradually as the exercises feel easier.")


for i, (level, days, goal, eq, loc, q) in enumerate(PLAN_CONFIGS):
    plan = planner.plan(level=level, days=days, goal=goal, equipment=eq, location=loc)
    ctx = plan_to_context(plan)
    resp = plan_answer(plan)
    intent = "home_workout" if loc == "home" else "workout_plan"
    add(q, resp, "workout_planning" if loc == "gym" else "home_workouts", intent, f"plan-{i}", "planner", context=ctx)
    add(rng.choice(PARA).format(x=q[0].lower() + q[1:]) if not q.lower().startswith(("give", "make", "create", "i "))
        else q.replace("Give me", "Could you give me").replace("Make me", "Could you make me").replace("Create", "Please create"),
        resp, "workout_planning" if loc == "gym" else "home_workouts", intent, f"plan-{i}", "planner", context=ctx)

MUSCLE_CONFIGS = [(g, lvl, eq) for g in ("chest", "back", "shoulders", "legs", "arms", "core")
                  for lvl, eq in (("beginner", ["dumbbells"]), ("beginner", ["none"]), ("intermediate", None))]
for g, lvl, eq in MUSCLE_CONFIGS:
    w = planner.muscle_workout(g, level=lvl, equipment=eq, location="home" if eq else "gym")
    if len(w["days"][0]["exercises"]) < 2:
        continue
    names = [e["name"].lower() for e in w["days"][0]["exercises"]]
    e0 = w["days"][0]["exercises"][0]
    eq_word = {"dumbbells": "dumbbell", "bodyweight only": "bodyweight"}.get(w["equipment"], "gym")
    q = f"Give me a {lvl} {eq_word} {g} workout"
    resp = (f"Here's a {lvl} {eq_word} {g} workout: {join_names(names)}. Do {e0['sets']} sets of {e0['reps']} reps "
            f"with {e0['rest']} rest between sets. Warm up first, focus on controlled reps, and increase the weight or reps "
            "gradually as it gets easier.")
    add(q, resp, "home_workouts" if eq else "gym_workouts", "home_workout" if eq else "gym_workout",
        f"mw-{g}-{lvl}-{eq_word}", "planner", context=plan_to_context(w))


# ---------------------------------------------------------------- 5. grounded follow-up chains
# Mirrors runtime behaviour: the dialogue state carries the topic (muscle group / food) forward,
# and each follow-up turn is answered from freshly retrieved, constraint-filtered context.
def group_answer(group, flt):
    exs = filter_group(group, flt)
    names = join_names([e["name"] for e in exs])
    word = GROUP_WORDS[group]
    return exs, {
        None: f"Great {word} exercises include {names}. {FILTER_TIP[None]}",
        "beginner": f"Since you're a beginner, start with these {word} exercises: {names}. {FILTER_TIP['beginner']}",
    }[flt]


OPENERS = ["What exercises can I do for {g}?", "What are the best {g} exercises?", "Which exercises train my {g}?"]
BEGINNER_FU = ["I'm a beginner.", "I'm new to working out.", "I'm just starting out."]
DB_FU = ["I only have dumbbells.", "I just have a pair of dumbbells at home.", "What if I only have dumbbells?"]
BW_FU = ["I don't have any equipment.", "What can I do with no equipment?"]
for gi, group in enumerate(["chest", "back", "shoulders", "legs", "arms", "core"]):
    word = GROUP_WORDS[group]
    q1 = OPENERS[gi % 3].format(g=word)
    ex1, a1 = group_answer(group, None)
    q2 = BEGINNER_FU[gi % 3]
    ex2, a2 = group_answer(group, "beginner")
    eq = ["none"] if group == "core" else ["dumbbells"]
    w = planner.muscle_workout(group, level="beginner", equipment=eq, location="home")
    items = w["days"][0]["exercises"]
    e0 = items[0]
    q3 = BW_FU[gi % 2] if group == "core" else DB_FU[gi % 3]
    eq_word = "bodyweight" if group == "core" else "dumbbell"
    a3 = (f"Here's a beginner {eq_word} {word} workout you can do: "
          + "; ".join(f"{e['name']} {e['sets']} sets x {e['reps']}" for e in items)
          + f". Rest {e0['rest']} between sets, start light, and add reps or weight gradually.")
    hist1 = [{"role": "user", "content": q1}, {"role": "assistant", "content": a1}]
    hist2 = hist1 + [{"role": "user", "content": q2}, {"role": "assistant", "content": a2}]
    cat = "workout_exercises"
    gid = f"chain-{group}"
    add(q1, a1, cat, "exercise_search", gid, "conversation", context=[format_exercise(e) for e in ex1])
    add(q2, a2, cat, "exercise_search", gid, "conversation", context=[format_exercise(e) for e in ex2],
        history=hist1, profile={"fitness_level": "beginner"})
    add(q3, a3, "home_workouts", "home_workout", gid, "conversation", context=plan_to_context(w), history=hist2,
        profile={"fitness_level": "beginner", "equipment": eq})
    q4 = "What should I eat after this workout?"
    post = [FOOD_BY_NAME[n] for n in ("Greek yogurt (plain, nonfat)", "Chicken breast (roasted)", "Tofu (firm)", "Banana")]
    a4 = ("After this workout, aim for a meal or snack with about 20-40 g of protein plus some carbohydrates. "
          f"Good options are Greek yogurt with a banana, chicken breast with rice, or tofu with rice and vegetables. "
          f"For reference, {post[0]['portion']['description']} of nonfat Greek yogurt has about "
          f"{fmt(post[0]['portion']['nutrients']['protein_g'])} g of protein according to USDA data. Drink some water too.")
    if gi < 3:
        add(q4, a4, "pre_post_workout", "nutrition_question", gid, "conversation",
            context=[format_food(f) for f in post] + [format_passage(KB_BY_ID["post-workout"])],
            history=hist2 + [{"role": "user", "content": q3}, {"role": "assistant", "content": a3}],
            profile={"fitness_level": "beginner", "equipment": eq})

FOOD_CHAINS = [("Egg (whole, hard-boiled)", "Chicken breast (roasted)"), ("Greek yogurt (plain, nonfat)", "Cottage cheese (low fat, 2%)"),
               ("Lentils (boiled)", "Chickpeas (boiled)"), ("White rice (cooked)", "Brown rice (cooked)"),
               ("Banana", "Apple (with skin)"), ("Almonds", "Peanut butter (smooth)"), ("Tofu (firm)", "Tempeh"),
               ("Oats (dry)", "Whole-wheat bread"), ("Salmon (Atlantic, farmed, cooked)", "Tuna (light, canned in water)"),
               ("Cola (regular)", "Orange juice")]
for ci, (fa, fb) in enumerate(FOOD_CHAINS):
    a_food, b_food = FOOD_BY_NAME[fa], FOOD_BY_NAME[fb]
    qt = "calories" if a_food["group"] in ("beverages", "fruit") else "protein"
    q1 = FOOD_Q[qt][ci % len(FOOD_Q[qt])].format(a=a_food["aliases"][0])
    a1 = food_fact_answer(a_food, qt)
    q2 = ["What about {b}?", "And {b}?", "How does {b} compare?"][ci % 3].format(b=b_food["aliases"][0])
    a2 = food_fact_answer(b_food, qt)
    gid = f"foodchain-{ci}"
    add(q1, a1, "food", "food_search", gid, "conversation", context=[format_food(a_food)])
    add(q2, a2, "food", "food_search", gid, "conversation", context=[format_food(b_food)],
        history=[{"role": "user", "content": q1}, {"role": "assistant", "content": a1}])


# ---------------------------------------------------------------- cleaning
def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


UNSAFE = [r"\bfast(ing)? for \d+ days\b", r"\b(eat|consume) (less than|under) (500|600|800|1000) calories\b",
          r"\bdehydrate yourself\b", r"\bpush through (the )?pain\b", r"\bno need to see a doctor\b",
          r"\bsteroid cycle (is|would be)\b", r"\bguaranteed\b"]

stats = Counter()
stats["raw_records"] = len(records)
clean, seen_key, seen_input = [], set(), {}
for r in records:
    if not r["input"] or not r["response"]:
        stats["removed_empty"] += 1
        continue
    if len(r["response"]) < 25 or len(r["response"]) > 1400:
        stats["removed_length"] += 1
        continue
    if any(re.search(p, r["response"].lower()) for p in UNSAFE):
        stats["removed_unsafe"] += 1
        continue
    hist = " ".join(h["content"] for h in r["history"])
    key = (norm(r["input"]), norm(hist), json.dumps(r["profile"], sort_keys=True))
    if key in seen_key:
        stats["removed_duplicate"] += 1
        continue
    # contradiction check: identical standalone question with a different answer in another group
    if not r["history"] and not r["profile"]:
        prev = seen_input.get(norm(r["input"]))
        if prev and prev[0] != r["group_id"] and norm(prev[1]) != norm(r["response"]):
            stats["removed_conflicting"] += 1
            continue
        seen_input.setdefault(norm(r["input"]), (r["group_id"], r["response"]))
    seen_key.add(key)
    clean.append(r)
stats["clean_records"] = len(clean)

# ---------------------------------------------------------------- grouped, stratified split
groups = defaultdict(list)
for r in clean:
    groups[r["group_id"]].append(r)
by_cat = defaultdict(list)
for gid, rs in groups.items():
    by_cat[rs[0]["category"]].append(gid)

split_of = {}
for cat, gids in sorted(by_cat.items()):
    gids = sorted(gids, key=lambda g: hashlib.md5(f"{SEED}-{g}".encode()).hexdigest())
    n = len(gids)
    n_test = max(1, round(n * 0.10)) if n >= 5 else 0
    n_val = max(1, round(n * 0.10)) if n >= 5 else 0
    for k, g in enumerate(gids):
        split_of[g] = "test" if k < n_test else ("validation" if k < n_test + n_val else "train")

splits = {"train": [], "validation": [], "test": []}
for r in clean:
    r["split"] = split_of[r["group_id"]]
    r["messages"] = build_messages(r["input"], r["context"], r["profile"], r["history"]) + [
        {"role": "assistant", "content": r["response"]}]
    splits[r["split"]].append(r)

# leakage check: no group and no normalised input shared between train and test
train_inputs = {norm(r["input"]) for r in splits["train"] if not r["history"]}
leak = [r["input"] for r in splits["test"] if not r["history"] and norm(r["input"]) in train_inputs]
assert not ({r["group_id"] for r in splits["train"]} & {r["group_id"] for r in splits["test"]}), "group leakage"

OUT.mkdir(parents=True, exist_ok=True)
fname = {"train": "training.jsonl", "validation": "validation.jsonl", "test": "test.jsonl"}
for name, rs in splits.items():
    rng.shuffle(rs)
    with open(OUT / fname[name], "w") as fh:
        for r in rs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

summary = {
    "cleaning": dict(stats),
    "split_sizes": {k: len(v) for k, v in splits.items()},
    "groups": {k: len({r["group_id"] for r in v}) for k, v in splits.items()},
    "test_inputs_also_in_train_after_normalisation": len(leak),
    "by_category": dict(Counter(r["category"] for r in clean).most_common()),
    "by_intent": dict(Counter(r["intent"] for r in clean).most_common()),
    "by_source": dict(Counter(r["source"] for r in clean).most_common()),
    "with_context": sum(1 for r in clean if r["context"]),
    "with_history": sum(1 for r in clean if r["history"]),
    "with_profile": sum(1 for r in clean if r["profile"]),
    "avg_response_words": round(sum(len(r["response"].split()) for r in clean) / len(clean), 1),
}
(OUT / "dataset_stats.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
