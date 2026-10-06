"""Natural-language understanding: intent detection, domain check and slot extraction.

Intent = trained classifier (scripts/train_intent_classifier.py): TF-IDF + sentence-embedding features ->
logistic regression (app/ml/intent.py; TF-IDF-only fallback when no encoder is available),
combined with a fitness-domain lexicon guardrail, so that:
  * questions with no fitness vocabulary are treated as out-of-domain, and
  * questions containing clear fitness vocabulary are never refused as out-of-domain.
Slots (muscle group, level, equipment, location, goal, days, diet, foods, exercises) drive the
dialogue state used for follow-up questions such as "I'm a beginner" or "I only have dumbbells".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib

INTENTS = ["exercise_search", "workout_plan", "nutrition_question", "food_search", "weight_loss", "muscle_gain",
           "cardio", "hydration", "sleep", "recovery", "stretching", "home_workout", "gym_workout", "equipment",
           "exercise_safety", "general_fitness", "medical_safety", "greeting", "out_of_domain"]

DOMAIN_STEMS = """fit exercis workout work-out train gym muscl strength strong cardio run jog walk sprint protein carb
fat calor diet eat food meal drink water hydrat sleep nap rest recover sore stretch flexib mobil yoga pilates weight
lose losing lost gain bulk cutting lean abs ab core chest back leg arm shoulder glute bicep tricep quad hamstring calf
calves squat press curl plank lunge deadlift pullup pull-up pushup push-up row health injur pain hurt pregnan supplement
creatine vitamin breakfast lunch dinner snack energy stamina endurance hiit bmi body posture warm cool dumbbell barbell
kettlebell band treadmill bike cycl swim sport athlet motivat habit stress tired fatigu beginner intermediate advanced
rep reps set sets split routine program plan_workout macro fiber sugar sodium caffeine coffee tea alcohol beer wine
juice soda vegan vegetarian keto fasting belly tone toned shred physique heart rate bpm steps marathon 5k 10k jump
skipping rope rowing elliptical stair hike burn metabolism spotter technique nutrition nutrient diabet
asthma surgery steroid sarm doctor physio knee hip ankle wrist elbow spine sweat electrolyt lift overload deload
equipment trainer coach six-pack sixpack bench flexibility posture overtrain workouts exercising
""".split()
DOMAIN_PHRASES = ["work out", "working out", "worked out", "six pack", "blood pressure", "leg day", "rest day",
                  "personal trainer", "get fit", "in shape", "lose weight", "gain weight", "my form", "good form"]

# tokens that start with a fitness stem but are not about fitness
FALSE_FRIENDS = {"programming", "programmer", "programmers", "programmatic", "fitting", "restaurant", "restaurants",
                 "setting", "settings", "setup", "formula", "format", "information", "platform", "transform",
                 "hipster", "spotify", "cutting-edge"}
GREETING_RE = re.compile(r"^\s*(hi|hey|hello|yo|good (morning|afternoon|evening)|thanks?( you)?|thank u|"
                         r"what can you do|who are you|what are you|help)\b[\s!.?]*", re.I)

MUSCLE_GROUPS = {
    "chest": ["chest", "pec", "pecs", "pectoral"],
    "back": ["back", "lats", "lat", "upper back", "lower back"],
    "shoulders": ["shoulder", "shoulders", "delts", "deltoid", "deltoids"],
    "legs": ["leg", "legs", "quads", "quadriceps", "hamstrings", "glutes", "glute", "calves", "calf", "thighs", "butt"],
    "arms": ["arm", "arms", "biceps", "bicep", "triceps", "tricep", "forearms"],
    "core": ["core", "abs", "ab", "abdominal", "abdominals", "obliques", "stomach", "six pack"],
    "cardio": ["cardio", "aerobic"],
    "stretching": ["stretch", "stretches", "stretching", "flexibility", "mobility"],
}
LEVELS = {"beginner": ["beginner", "beginners", "new to", "just starting", "starting out", "never worked out", "novice", "first time",
                       "out of shape", "newbie"],
          "intermediate": ["intermediate", "intermediates", "some experience", "been training for a year", "few months"],
          "advanced": ["advanced", "experienced", "years of training", "competitive"]}
EQUIPMENT = {"dumbbells": ["dumbbell", "dumbbells"], "bands": ["band", "bands", "resistance band"],
             "kettlebells": ["kettlebell", "kettlebells"], "gym": ["full gym", "gym equipment", "machines", "barbell"],
             "bodyweight": ["no equipment", "without equipment", "bodyweight", "body weight", "nothing at home",
                            "don't have any equipment", "dont have any equipment", "no weights"]}
LOCATIONS = {"home": ["at home", "home workout", "in my room", "apartment", "home"], "gym": ["gym"]}
GOALS = {"weight_loss": ["lose weight", "weight loss", "fat loss", "lose fat", "burn fat", "slim", "cut"],
         "muscle_gain": ["build muscle", "gain muscle", "muscle gain", "bulk", "hypertrophy", "get bigger"],
         "strength": ["strength", "stronger", "powerlifting"],
         "endurance": ["endurance", "stamina", "marathon"],
         "general_fitness": ["general fitness", "stay healthy", "get fit", "overall fitness"]}
DIETS = {"vegetarian": ["vegetarian", "veggie"], "vegan": ["vegan", "plant-based", "plant based"],
         "non_vegetarian": ["non-vegetarian", "non vegetarian", "eat meat"]}
DAYS_RE = re.compile(r"\b(\d|one|two|three|four|five|six)[\s-]*(day|days)\b", re.I)
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


@dataclass
class Slots:
    muscle_group: str | None = None
    level: str | None = None
    equipment: list[str] = field(default_factory=list)
    location: str | None = None
    goal: str | None = None
    days: int | None = None
    diet: str | None = None
    foods: list[dict] = field(default_factory=list)
    exercises: list[dict] = field(default_factory=list)

    def constraint_only(self) -> bool:
        return any([self.level, self.equipment, self.location, self.diet]) and not (self.muscle_group or self.foods or self.exercises)


def _has(text: str, phrases: list[str]) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text) for p in phrases)


class NLU:
    def __init__(self, model_path: Path, exercises: list[dict], foods: list[dict], encode=None):
        self.clf = joblib.load(model_path) if model_path.exists() else None
        if encode is not None and hasattr(self.clf, "set_encoder"):
            self.clf.set_encoder(encode)
        self.exercises, self.foods = exercises, foods
        self.ex_names = sorted(((n.lower(), e) for e in exercises for n in [e["name"]] + e["aliases"]),
                               key=lambda x: -len(x[0]))
        self.food_names = sorted(((n.lower(), f) for f in foods for n in [f["name"].split(" (")[0]] + f["aliases"]),
                                 key=lambda x: -len(x[0]))
        # whole exercise / food names (phrases), e.g. "french fries" - single words like "french" do not count
        self.vocab_phrases = sorted({n for n, _ in self.ex_names + self.food_names if len(n) > 3}, key=len, reverse=True)

    # ------------------------------------------------------------------ domain
    def domain_hits(self, text: str) -> int:
        t = text.lower()
        tokens = re.findall(r"[a-z0-9\-]+", t)
        # short stems (<= 3 chars, e.g. "ab", "rep", "fat") must match the whole word (+ optional plural "s")
        # so that "about" or "repeat" do not count; longer stems match as prefixes ("protein" -> "proteins"),
        # and stems of 5+ chars also match inside words ("overtraining")
        def match(tok, stem):
            if len(stem) <= 3:
                return tok in (stem, stem + "s")
            return tok.startswith(stem) or (len(stem) >= 5 and stem in tok)
        hits = sum(1 for tok in tokens if tok not in FALSE_FRIENDS and any(match(tok, s) for s in DOMAIN_STEMS))
        hits += sum(1 for ph in DOMAIN_PHRASES if ph in t)
        hits += sum(1 for ph in self.vocab_phrases if _has(" " + t + " ", [ph]))
        return hits

    # ------------------------------------------------------------------ intent
    def classify(self, text: str) -> tuple[str, float, dict]:
        if GREETING_RE.fullmatch(text.strip()) or (GREETING_RE.match(text) and len(text.split()) <= 4):
            return "greeting", 1.0, {}
        if self.clf is None:
            return ("general_fitness", 0.0, {}) if self.domain_hits(text) else ("out_of_domain", 0.0, {})
        probs = dict(zip(self.clf.classes_, self.clf.predict_proba([text])[0]))
        ranked = sorted(probs.items(), key=lambda kv: -kv[1])
        intent, conf = ranked[0]
        hits = self.domain_hits(text)
        if intent == "out_of_domain" and hits:
            intent, conf = next((k, v) for k, v in ranked if k not in ("out_of_domain", "greeting"))
        elif intent != "out_of_domain" and not hits and intent != "greeting":
            intent, conf = "out_of_domain", probs.get("out_of_domain", 0.0)
        return intent, float(conf), {k: round(float(v), 3) for k, v in ranked[:3]}

    def ood_probability(self, text: str) -> float:
        if self.clf is None:
            return 0.0 if self.domain_hits(text) else 1.0
        probs = dict(zip(self.clf.classes_, self.clf.predict_proba([text])[0]))
        return float(probs.get("out_of_domain", 0.0))

    # ------------------------------------------------------------------ slots
    def slots(self, text: str) -> Slots:
        t = " " + text.lower() + " "
        s = Slots()
        t_mg = re.sub(r"\b(empty|upset|full|sick to my|on an empty) stomach\b", " ", t)
        for name, words in MUSCLE_GROUPS.items():
            if _has(t_mg, words):
                if name == "back" and re.search(r"\b(lower back|back) (pain|hurts|injur)", t_mg):
                    continue
                s.muscle_group = name
                break
        for lvl, words in LEVELS.items():
            if _has(t, words):
                s.level = lvl
                break
        for eq, words in EQUIPMENT.items():
            if _has(t, words):
                s.equipment.append(eq)
        if "bodyweight" in s.equipment:
            s.location = "home"
        for loc, words in LOCATIONS.items():
            if _has(t, words):
                s.location = s.location or loc
                break
        for goal, words in GOALS.items():
            if _has(t, words):
                s.goal = goal
                break
        for diet, words in DIETS.items():
            if _has(t, words):
                s.diet = diet
                break
        m = DAYS_RE.search(t)
        if m:
            v = m.group(1).lower()
            s.days = int(v) if v.isdigit() else WORD_NUM[v]
        seen = set()
        for name, f in self.food_names:
            if f["name"] not in seen and _has(t, [name]):
                s.foods.append(f)
                seen.add(f["name"])
        seen = set()
        for name, e in self.ex_names:
            if e["name"] not in seen and len(name) > 3 and _has(t, [name]):
                s.exercises.append(e)
                seen.add(e["name"])
        # "dumbbell press" etc. should not also count "dumbbells" as the only equipment constraint
        return s
