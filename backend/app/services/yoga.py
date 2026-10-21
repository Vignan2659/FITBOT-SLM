"""Yoga library: pose lookup, filters, search, routine builder and the chat pipeline helpers.

The pose records come from data/yoga/yoga_poses.json (built by scripts/yoga/build_yoga.py). Like the exercise
catalog, everything the user sees on a yoga card or in a routine comes straight from that data; the SLM only writes
the conversational answer around it.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

LEVELS = ["Beginner", "Intermediate", "Advanced"]
GOALS = {
    "flexibility": "Flexibility", "mobility": "Mobility", "strength": "Strength", "balance": "Balance", "core": "Core",
    "stress_relief": "Stress relief", "relaxation": "Relaxation", "recovery": "Recovery",
    "weight_management": "Weight management", "posture": "Posture", "breathing": "Breathing", "meditation": "Meditation",
}
AREAS = {"back": "Back", "shoulders": "Shoulders", "hips": "Hips", "legs": "Legs", "core": "Core",
         "full_body": "Full body", "chest": "Chest", "neck": "Neck"}
PHASE_LABEL = {"centering": "Centre", "warmup": "Warm up", "standing": "Standing", "balance": "Balance", "core": "Core",
               "backbend": "Backbend", "seated": "Seated", "inversion": "Inversion", "cooldown": "Cool down",
               "relaxation": "Relax"}

# ---------------------------------------------------------------------------------------------- text understanding
YOGA_WORD_RE = re.compile(r"\b(yoga|yogi|asanas?|pranayama|vinyasa|hatha|yin|savasana|shavasana|sun salutations?|"
                          r"surya namaskar)\b", re.I)
ROUTINE_RE = re.compile(r"\b(routine|sequence|flow|session|class|practice|plan|program|programme|workout|"
                        r"\d+\s*-?\s*(min|mins|minute|minutes)\b|morning|evening|night|bedtime|before bed|wake up)", re.I)
POSES_RE = re.compile(r"\b(poses?|asanas?|positions?|stretch(es)?|postures?|moves?)\b", re.I)
ASK_RE = re.compile(r"\b(yoga (for|to|that|which|poses?|stretch|routine|flow|sequence|session|class|practice|plan)|"
                    r"(beginner|beginners|easy|gentle|morning|evening|bedtime|quick|short|restorative|relaxing|calming)"
                    r"\s+yoga|(which|what|best|good|some|any|give me|show me|suggest|recommend|teach me)\b.*\byoga\b|"
                    r"\byoga\b.*\b(poses?|routine|flow|sequence)\b)", re.I)
HOW_RE = re.compile(r"\b(how (do|to|can|should) (i |you )?(do|perform|practi[cs]e|get into|hold)|explain|"
                    r"steps? (for|to|of)|instructions?|technique|what is|what's|tell me about|benefits? of)\b", re.I)
MINUTES_RE = re.compile(r"\b(\d{1,2})\s*-?\s*(min|mins|minute|minutes)\b", re.I)
# foundational poses preferred when a routine has no specific goal
STAPLES = {"mountain-pose", "cat-cow", "downward-dog", "low-lunge", "warrior-ii", "childs-pose", "bridge-pose",
           "seated-forward-fold", "corpse-pose", "easy-pose", "tree-pose", "supine-twist"}
GENTLE_RE = re.compile(r"\b(pain|painful|hurts?|injur\w*|stiff|arthritis|condition|older|senior|elderly|"
                       r"recovering|rehab)\b", re.I)
GOAL_WORDS = [
    ("flexibility", r"flexib|stretch(y|ier)?\b|hamstring|touch my toes|limber"),
    ("mobility", r"mobil|stiff|range of motion|joints?"),
    ("relaxation", r"relax|sleep|bedtime|before bed|unwind|wind down|insomnia|rest(ful|orative)"),
    ("stress_relief", r"stress|anxi|calm|tension|overwhelm|mind"),
    ("recovery", r"recover|sore|after (a |my |the )?(workout|run|running|training|gym|game|lifting|session)|rest day|post[- ]workout"),
    ("weight_management", r"weight|fat|calorie|slim|burn"),
    ("strength", r"strength|strong|tone|toning|power"),
    ("core", r"\bcore\b|\babs?\b|abdominal|stomach|six pack"),
    ("balance", r"balanc|stability|steady"),
    ("posture", r"posture|desk|sitting all day|slouch|hunch|office"),
    ("breathing", r"breath|pranayama|lungs?"),
    ("meditation", r"meditat|mindful|focus|concentrat"),
]
AREA_WORDS = [
    ("back", r"\b(lower back|upper back|back|spine|spinal)\b"),
    ("shoulders", r"\b(shoulders?|delts?)\b"),
    ("neck", r"\bneck\b"),
    ("hips", r"\b(hips?|hip flexors?|glutes?|groin|piriformis)\b"),
    ("legs", r"\b(legs?|hamstrings?|quads?|quadriceps|calves|calf|thighs?|knees?)\b"),
    ("core", r"\b(core|abs|abdominals?|stomach|obliques)\b"),
    ("chest", r"\b(chest|pecs?)\b"),
    ("full_body", r"\b(full|whole|total)[ -]body\b"),
]
NUM_WORDS = {"1": "i", "one": "i", "2": "ii", "two": "ii", "3": "iii", "three": "iii"}


def normalise(text: str) -> str:
    t = " " + text.lower().replace("’", "'").replace("-", " ") + " "
    t = re.sub(r"\bwarrior (1|one|2|two|3|three)\b", lambda m: "warrior " + NUM_WORDS[m.group(1)], t)
    t = re.sub(r"\bdown dog\b", "downward dog", t)
    t = re.sub(r"\s+", " ", t)
    return t


@dataclass
class YogaQuery:
    mode: str                       # detail | list | routine
    poses: list[dict] = field(default_factory=list)
    level: str | None = None
    goal: str | None = None
    area: str | None = None
    minutes: int | None = None
    time_of_day: str | None = None
    gentle: bool = False


class YogaLibrary:
    def __init__(self, path: Path, exercise_names: set[str] | None = None):
        self.poses: list[dict] = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else []
        self.by_slug = {p["slug"]: p for p in self.poses}
        exercise_names = {n.lower() for n in (exercise_names or set())}
        # names a user could say without meaning yoga (they are also exercises in the main library, e.g. "plank")
        generic = {"plank", "high plank", "glute bridge", "bird dog", "superman", "butterfly", "v sit", "forward bend",
                   "horse stance", "shoulder stand", "handstand", "splits", "headstand", "monkey pose"}
        names: list[tuple[str, dict, bool]] = []
        for p in self.poses:
            for n in [p["name"]] + p["alternative_names"] + [p["sanskrit"]]:
                key = normalise(n).strip()
                key = re.sub(r"\s*\(.*?\)", "", key)
                if len(key) < 4:
                    continue
                ambiguous = key in exercise_names or key in generic
                names.append((key, p, ambiguous))
        # longest names first so "half forward fold" wins over "forward fold"
        self.names = sorted(set((n, p["slug"], a) for n, p, a in names), key=lambda x: -len(x[0]))

    # ------------------------------------------------------------------ lookup
    def get(self, slug: str) -> dict | None:
        return self.by_slug.get(slug)

    def find_in_text(self, text: str, allow_ambiguous: bool = False) -> list[dict]:
        t = normalise(text)
        hits: list[tuple[int, str]] = []
        spans: list[tuple[int, int]] = []
        for name, slug, ambiguous in self.names:
            if ambiguous and not allow_ambiguous:
                continue
            for m in re.finditer(rf"(?<![a-z]){re.escape(name)}(?![a-z])", t):
                if any(m.start() < e and s < m.end() for s, e in spans):
                    continue
                spans.append((m.start(), m.end()))
                hits.append((m.start(), slug))
        out: list[dict] = []
        for _, slug in sorted(hits):          # in the order the user mentioned them
            if self.by_slug[slug] not in out:
                out.append(self.by_slug[slug])
        return out

    def filter(self, difficulty: str | None = None, goal: str | None = None, area: str | None = None,
               category: str | None = None, q: str | None = None, kind: str | None = None) -> list[dict]:
        rows = self.poses
        if difficulty:
            rows = [p for p in rows if p["difficulty"].lower() == difficulty.lower()]
        if goal:
            rows = [p for p in rows if goal in p["goals"]]
        if area:
            rows = [p for p in rows if area in p["body_areas"] or (area == "full_body" and len(p["body_areas"]) >= 3)]
        if category:
            rows = [p for p in rows if category.lower() in [c.lower() for c in p["category"]]]
        if kind:
            rows = [p for p in rows if p["kind"] == kind]
        if q:
            words = [w for w in re.findall(r"[a-z0-9']+", q.lower()) if len(w) > 1]
            def hay(p):
                return " ".join([p["name"], p["sanskrit"], " ".join(p["alternative_names"]), " ".join(p["category"]),
                                 " ".join(p["target_areas"]), " ".join(p["tags"]), " ".join(p["benefits"])]).lower()
            rows = [p for p in rows if all(w in hay(p) for w in words)]
        return rows

    def facets(self) -> dict:
        def count(key, values):
            return [{"value": v, "label": label, "count": sum(v in p[key] for p in self.poses)} for v, label in values.items()]
        return {
            "total": len(self.poses),
            "difficulty": [{"value": lvl, "label": lvl, "count": sum(p["difficulty"] == lvl for p in self.poses)}
                           for lvl in LEVELS],
            "goals": [g for g in count("goals", GOALS) if g["count"]],
            "body_areas": [a for a in count("body_areas", AREAS) if a["count"]],
            "categories": sorted({c for p in self.poses for c in p["category"]}),
        }

    def related(self, pose: dict) -> list[dict]:
        return [self.by_slug[s] for s in pose.get("related", []) if s in self.by_slug]

    # ------------------------------------------------------------------ chat understanding
    def understand(self, message: str, level: str | None = None) -> YogaQuery | None:
        """Is this a yoga request, and what kind? Returns None for questions that only mention yoga in passing
        (e.g. "Is yoga enough exercise?"), which stay with the normal pipeline."""
        t = normalise(message)
        word = bool(YOGA_WORD_RE.search(t))
        poses = self.find_in_text(t, allow_ambiguous=word)
        if not poses and not (word and (ASK_RE.search(t) or POSES_RE.search(t) or ROUTINE_RE.search(t))):
            return None
        goal = next((g for g, rx in GOAL_WORDS if re.search(rx, t)), None)
        area = next((a for a, rx in AREA_WORDS if re.search(rx, t)), None)
        m = MINUTES_RE.search(t)
        minutes = int(m.group(1)) if m else None
        tod = "morning" if re.search(r"\b(morning|wake up|start (of )?(the|my) day)\b", t) else \
            "evening" if re.search(r"\b(evening|night|bedtime|before bed|sleep|wind down)\b", t) else None
        if level is None:
            level = next((lvl for lvl in LEVELS if re.search(rf"\b{lvl.lower()}s?\b", t)), None)
            if level is None and re.search(r"\b(new to|never done|first time|easy|gentle|simple)\b", t):
                level = "Beginner"
        gentle = bool(GENTLE_RE.search(t))
        if poses and not ROUTINE_RE.search(t) and not minutes:
            mode = "detail"
        elif minutes or ROUTINE_RE.search(t) or (re.search(r"\b(give me|create|build|make|plan|i want|i need)\b", t)
                                                 and not POSES_RE.search(t)):
            mode = "routine"
        else:
            mode = "list"
        return YogaQuery(mode=mode, poses=poses[:2], level=level, goal=goal, area=area, minutes=minutes,
                         time_of_day=tod, gentle=gentle)

    def suggest(self, goal: str | None = None, area: str | None = None, level: str | None = None,
                ranked: list[str] | None = None, gentle: bool = False, limit: int = 6) -> list[dict]:
        """Poses for a goal / body area question, ordered by the semantic ranking when one is given."""
        allowed = LEVELS[:LEVELS.index(level) + 1] if level in LEVELS else LEVELS[:2]
        if gentle:
            allowed = ["Beginner"]
        pool = [p for p in self.poses if p["difficulty"] in allowed and p["kind"] == "pose"]
        if gentle:
            pool = [p for p in pool if not _unsuitable(p, area)] or pool
        rank = {s: i for i, s in enumerate(ranked or [])}

        def score(p):
            s = 0.0
            if goal and goal in p["goals"]:
                s += 3 + (1 if p["goals"][0] == goal else 0)
            if area and (area in p["body_areas"] or (area == "full_body" and len(p["body_areas"]) >= 3)):
                s += 3 + (1 if p["body_areas"][0] == area else 0)
            if p["slug"] in rank:
                s += 2.0 * (1 - rank[p["slug"]] / max(len(rank), 1))
            s -= 0.3 * LEVELS.index(p["difficulty"])
            return -s
        return sorted(pool, key=score)[:limit]

    # ------------------------------------------------------------------ routine builder
    def routine(self, minutes: int = 15, level: str | None = None, goal: str | None = None, area: str | None = None,
                time_of_day: str | None = None, gentle: bool = False) -> dict:
        minutes = max(5, min(int(minutes or 15), 60))
        level = level if level in LEVELS else "Beginner"
        if gentle:
            level = "Beginner"
        allowed = LEVELS[:LEVELS.index(level) + 1]
        calm = goal in ("relaxation", "stress_relief", "recovery", "meditation", "breathing") or time_of_day == "evening"
        strong = goal in ("strength", "weight_management", "core", "balance")
        if calm:
            plan = [("centering", .12), ("warmup", .18), ("seated", .20), ("cooldown", .30), ("relaxation", .20)]
        elif strong:
            plan = [("centering", .07), ("warmup", .18), ("standing", .35), ("balance" if goal == "balance" else "core", .18),
                    ("cooldown", .12), ("relaxation", .10)]
        else:
            plan = [("centering", .08), ("warmup", .20), ("standing", .30), ("backbend", .10), ("cooldown", .20),
                    ("relaxation", .12)]
        phase_groups = {"standing": {"standing", "balance"}, "core": {"core"}, "balance": {"balance", "standing"},
                        "seated": {"seated", "backbend", "cooldown"}, "cooldown": {"cooldown", "seated"},
                        "backbend": {"backbend"}, "warmup": {"warmup"}, "centering": {"centering"},
                        "relaxation": {"relaxation"}}

        def score(p):
            s = 0.0
            if goal and goal in p["goals"]:
                s += 3
            if area and (area in p["body_areas"]):
                s += 2.5
            if time_of_day == "morning" and p["energy"] == "energizing" or calm and p["energy"] == "calming":
                s += 1
            if calm and p["energy"] == "energizing":
                s -= 2
            if time_of_day and p["time_of_day"] == time_of_day:
                s += .5
            if p["kind"] != "pose":
                s -= .5
            if not goal and p["slug"] in STAPLES:
                s += 1.5
            if gentle and _unsuitable(p, area):
                s -= 10
            s -= .4 * LEVELS.index(p["difficulty"])
            return s

        used: set[str] = set()
        steps: list[dict] = []
        for phase, share in plan:
            budget = minutes * share
            pool = [p for p in self.poses if p["phase"] in phase_groups[phase] and p["difficulty"] in allowed
                    and p["slug"] not in used and p["phase"] != "inversion"]
            if phase == "centering" and time_of_day == "morning" and not calm:
                pool.sort(key=lambda p: p["slug"] != "mountain-pose")
            else:
                pool.sort(key=lambda p: -score(p))
            if phase == "relaxation":
                final = "body-scan-meditation" if calm and minutes >= 20 else "corpse-pose"
                pool = [self.by_slug[final]] + [p for p in pool if p["slug"] != final]
            spent = 0.0
            for p in pool:
                dur = p["default_minutes"] * (2 if p["sides"] else 1)
                if spent and spent + dur > budget + 0.25:
                    continue
                steps.append({"pose": p, "phase": phase, "minutes": dur})
                used.add(p["slug"])
                spent += dur
                if spent >= budget - 0.25 or phase in ("relaxation", "centering"):
                    break
        # fit the total exactly: stretch or trim holds in half minute steps, never below the pose's own minimum
        total = sum(s["minutes"] for s in steps)
        i = 0
        guard = 0
        while abs(total - minutes) >= 0.5 and guard < 400:
            guard += 1
            s = steps[i % len(steps)]
            step = 0.5 * (2 if s["pose"]["sides"] else 1)
            if total < minutes:
                s["minutes"] += step
                total += step
            elif s["minutes"] - step >= max(0.5, s["pose"]["default_minutes"] * (2 if s["pose"]["sides"] else 1) / 2):
                s["minutes"] -= step
                total -= step
            i += 1
        if total != minutes and steps:            # absorb a leftover half minute in the final relaxation
            steps[-1]["minutes"] += minutes - total
        out_steps = []
        for n, s in enumerate(steps, 1):
            p, mins = s["pose"], s["minutes"]
            per_side = mins / 2 if p["sides"] else None
            note = f"{_fmt(per_side)} each side" if per_side else _fmt(mins)
            out_steps.append({"order": n, "slug": p["slug"], "name": p["name"], "sanskrit": p["sanskrit"],
                              "difficulty": p["difficulty"], "phase": PHASE_LABEL[s["phase"]], "minutes": mins,
                              "per_side": per_side, "duration": note, "breathing": p["breathing"],
                              "motion_image": p["motion_image"], "image": p["image"],
                              "cue": p["instructions"][min(2, len(p["instructions"]) - 1)]})
        title_bits = [f"{minutes}-Minute", level, "Yoga"]
        if time_of_day:
            title_bits.insert(1, time_of_day.capitalize())
        title = " ".join(title_bits)
        if goal:
            title += f" for {GOALS[goal]}"
        elif area:
            title += f" for the {AREAS[area]}" if area != "full_body" else " for the Full Body"
        notes = ["Move slowly and stay within a comfortable range; stop any pose that causes pain.",
                 "Breathe through the nose and keep the breath smooth and unforced."]
        if gentle:
            notes.insert(0, "Kept to gentle beginner poses. Yoga is not a treatment for pain or medical conditions; "
                            "please check with a doctor or physiotherapist first.")
        if any(st["per_side"] for st in out_steps):
            notes.append("Poses marked 'each side' are done on the right and then the left.")
        return {"title": title, "minutes": minutes, "level": level, "goal": goal, "area": area,
                "time_of_day": time_of_day, "steps": out_steps, "notes": notes}


def _unsuitable(p: dict, area: str | None) -> bool:
    """For questions that mention pain: skip poses whose contraindications name that body area."""
    word = {"back": "back", "neck": "neck", "shoulders": "shoulder", "hips": "hip", "legs": "knee"}.get(area or "")
    return bool(word) and any(word in c.lower() for c in p["contraindications"])


def _fmt(m: float | None) -> str:
    if m is None:
        return ""
    if m < 1:
        return f"{int(round(m * 60))} sec"
    whole = math.floor(m)
    return f"{whole} min" if m == whole else f"{whole} min 30 sec"


# ---------------------------------------------------------------------------------------------- formatting
def yoga_card(p: dict) -> dict:
    keys = ("slug", "name", "sanskrit", "alternative_names", "difficulty", "category", "goals", "body_areas",
            "target_areas", "benefits", "instructions", "breathing", "duration", "recommended_repetitions",
            "beginner_modification", "advanced_variation", "common_mistakes", "safety_tips", "contraindications",
            "equipment", "suitable_for", "image", "motion_image", "frames", "frame_labels", "related", "kind", "sides",
            "photo_reference", "image_license", "tags")
    return {k: p[k] for k in keys}


def format_yoga_pose(p: dict) -> str:
    return (f"Yoga pose: {p['name']} ({p['sanskrit']}) | level: {p['difficulty']} | targets: {', '.join(p['target_areas'][:4])} | "
            f"benefits: {'; '.join(p['benefits'][:2])} | hold: {p['duration']}")


def format_yoga_detail(p: dict) -> list[str]:
    """Reference lines for "how do I do X" questions, written as guidance passages (the format the model paraphrases
    best; one long line of fields tends to be copied back verbatim)."""
    steps = " ".join(f"{i}. {s}" for i, s in enumerate(p["instructions"][:5], 1))
    return [
        f"Guidance (How to do {p['name']}, {p['sanskrit']}, {p['difficulty'].lower()} yoga pose): {steps} "
        f"Hold for {p['duration']}. Breathing: {p['breathing']}",
        f"Guidance ({p['name']}: benefits): {' '.join(b.rstrip('.') + '.' for b in p['benefits'])} "
        f"Targets: {', '.join(p['target_areas']).lower()}.",
        f"Guidance ({p['name']}: easier version and safety): Easier version: {p['beginner_modification']} "
        f"{' '.join(p['safety_tips'][:2])} Skip or modify it with: {'; '.join(p['contraindications'][:2])}.",
    ]


def format_routine(r: dict) -> str:
    steps = "; ".join(f"{s['order']}. {s['name']} {s['duration']}" for s in r["steps"])
    return f"Yoga routine: {r['title']} ({r['minutes']} min total) | {steps} | note: {r['notes'][0]}"


def pose_passages(poses: list[dict]) -> list[dict]:
    """One retrieval document per pose, so semantic search can find poses for goals and body areas."""
    out = []
    for p in poses:
        text = (f"{p['name']} ({p['sanskrit']}), {p['difficulty']} yoga pose. Good for {', '.join(GOALS[g].lower() for g in p['goals'])}. "
                f"Targets {', '.join(p['target_areas'])}; body areas {', '.join(AREAS[a].lower() for a in p['body_areas'])}. "
                f"{' '.join(p['benefits'])}. Suitable for {', '.join(p['suitable_for']).lower()}.")
        out.append({"id": f"yoga-pose:{p['slug']}", "topic": "yoga_pose", "title": f"{p['name']} (yoga pose)",
                    "source": "FitBot yoga library", "text": text, "slug": p["slug"]})
    return out
