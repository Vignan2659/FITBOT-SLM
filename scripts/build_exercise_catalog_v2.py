"""FitBot exercise catalog v2: all 871 cleaned exercises (was 58 curated) for dataset v2 / the 4B model.

Input : data/image_dataset/exercises.json   (871 exercises that passed image dedup + cleaning)
        data/exercises/exercises.json        (the 58 hand-curated v1 exercises: richer descriptions, aliases, tips)
Output: data/exercises/exercises_v2.json

Fields follow the v1 schema (so app.ml.prompting.format_exercise works unchanged), plus `split` (the image dataset
split, reused for the text dataset so an exercise's test questions never appear in training) and
`outdoor_friendly`. Every fact comes from free-exercise-db; FitBot's own classifications are rule-based and
documented below (muscle_group, home/outdoor flags, generated description, equipment safety tip).
The running app still uses the v1 file; nothing here changes it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "data" / "image_dataset"
OUT = ROOT / "data" / "exercises" / "exercises_v2.json"
IMAGE_BASE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"

EQUIPMENT_LABELS = {
    "body only": "Bodyweight", None: "Bodyweight", "dumbbell": "Dumbbells", "barbell": "Barbell",
    "cable": "Cable machine", "machine": "Machine", "kettlebells": "Kettlebell", "bands": "Resistance bands",
    "medicine ball": "Medicine ball", "exercise ball": "Exercise ball", "foam roll": "Foam roller",
    "e-z curl bar": "EZ curl bar", "other": "Other",
}
# primary muscle -> FitBot muscle group
GROUP = {"chest": "chest", "lats": "back", "middle back": "back", "lower back": "back", "traps": "back",
         "shoulders": "shoulders", "neck": "neck", "quadriceps": "legs", "hamstrings": "legs", "glutes": "legs",
         "calves": "legs", "adductors": "legs", "abductors": "legs", "biceps": "arms", "triceps": "arms",
         "forearms": "arms", "abdominals": "core"}
LEVEL = {"beginner": "Beginner", "intermediate": "Intermediate", "expert": "Advanced"}
HOME_EQUIPMENT = {"body only", None, "dumbbell", "bands", "kettlebells", "exercise ball", "foam roll", "medicine ball"}
# no-equipment or park-bar movements that suit a park / outdoors (FitBot classification, by name + equipment)
OUTDOOR_WORDS = r"\b(pull-?ups?|chin-?ups?|dips?|push-?ups?|lunges?|step-?ups?|sprints?|running|run|jog|jogging|walk|walking|jumps?|hops?|bounds?|skip|skipping|squats?|planks?|burpees?|crawl|mountain climbers?|leap|butt kicks?|high knees?|carioca|shuffle)\b"
SAFETY = {  # one general tip per equipment type (FitBot guidance, not from the source)
    "barbell": "Use collars on the bar, warm up with lighter sets, and use a spotter or safety pins for heavy pressing or squatting.",
    "dumbbell": "Pick a weight you can control through the full range, and set the dumbbells down carefully rather than dropping them.",
    "cable": "Check the pin is fully inserted and the attachment is secure, and control the weight on the way back.",
    "machine": "Adjust the seat and pads so the joint lines up with the machine's pivot, and move through a pain-free range.",
    "kettlebells": "Keep a neutral spine, drive the movement from your hips and legs, and clear space around you.",
    "bands": "Check the band for nicks or tears before use and anchor it securely so it cannot snap back.",
    "medicine ball": "Use a ball weight you can throw and catch with control, and throw against a solid wall or open space.",
    "exercise ball": "Use a correctly inflated ball on a non-slip surface and start near a wall for balance.",
    "foam roll": "Roll slowly over muscle, avoid rolling directly on joints or the lower spine, and ease off if it hurts sharply.",
    "e-z curl bar": "Keep your elbows steady and your back neutral, and start with a load you can lift without swinging.",
    "body only": "Move with control, keep good alignment, and use an easier variation if you cannot keep your form.",
    "other": "Learn the movement with a light load first and make sure the equipment is stable and secure.",
}
CATEGORY_TIP = {
    "stretching": "Stretch to mild tension only, breathe slowly, and never bounce or force the position.",
    "plyometrics": "Land softly with knees tracking over the toes, and only add volume once your landings stay quiet and controlled.",
    "olympic weightlifting": "This is a technical lift - learn it with a coach and an empty bar or PVC pipe before adding weight.",
    "strongman": "Brace hard, keep the load close to your body, and build up gradually with an experienced partner nearby.",
    "cardio": "Start at an easy, conversational pace and build duration before intensity.",
}


def clean_name(n: str) -> str:
    return re.sub(r"\s+", " ", n.replace(" - ", " – ")).strip()


def slugify(n: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", n.lower())).strip("-")


def describe(e: dict, group: str, eq_label: str) -> str:
    pm = [m.lower() for m in e["primary_muscles"]]
    prim = (pm[0] if len(pm) == 1 else ", ".join(pm[:-1]) + " and " + pm[-1]) if pm else "several muscle groups"
    sec = [m.lower() for m in e["secondary_muscles"]][:3]
    cat = e["category"]
    kind = {"stretching": "A stretch", "plyometrics": "A plyometric (jumping/explosive) exercise",
            "cardio": "A cardio exercise", "olympic weightlifting": "An Olympic weightlifting movement",
            "strongman": "A strongman exercise", "powerlifting": "A powerlifting movement"}.get(cat, "A strength exercise")
    tool = "with no equipment" if eq_label == "Bodyweight" else f"using a {eq_label.lower().rstrip('s')}" \
        if eq_label in ("Barbell", "Kettlebell", "Machine", "Cable machine", "Medicine ball", "Exercise ball", "Foam roller", "EZ curl bar") \
        else f"with {eq_label.lower()}"
    s = f"{kind} for the {prim}, done {tool}."
    if sec:
        s += " It also works the " + (sec[0] if len(sec) == 1 else ", ".join(sec[:-1]) + " and " + sec[-1]) + "."
    return s


def main() -> None:
    imgs = json.loads((IMG / "exercises.json").read_text())
    v1 = {e["source_id"]: e for e in json.loads((ROOT / "data/exercises/exercises.json").read_text())}
    out, names = [], set()
    for e in imgs:
        raw_eq = e["equipment"]
        eq = EQUIPMENT_LABELS.get(raw_eq, "Other")
        prim = [m.lower() for m in e["primary_muscles"]]
        if e["category"] == "stretching":
            group = "stretching"
        elif e["category"] == "cardio":
            group = "cardio"
        else:
            group = GROUP.get(prim[0], "core") if prim else "core"
        cur = v1.get(e["exercise_id"])
        name = cur["name"] if cur else clean_name(e["exercise"])
        if name.lower() in names:            # keep names unique
            name = clean_name(e["exercise"])
        names.add(name.lower())
        urls = [f"{IMAGE_BASE}{e['exercise_id']}/{Path(p).stem.split('_')[-1]}.jpg" for p in e["images"]]
        outdoor = (raw_eq in ("body only", None) and bool(re.search(OUTDOOR_WORDS, e["exercise"].lower()))
                   and e["category"] in ("strength", "plyometrics", "cardio"))
        tip = (cur["safety_tips"][0] if cur else CATEGORY_TIP.get(e["category"]) or SAFETY.get(raw_eq or "body only", SAFETY["other"]))
        out.append({
            "name": name,
            "slug": slugify(name),
            "source_id": e["exercise_id"],
            "source_name": e["exercise"],
            "muscle_group": cur["muscle_group"] if cur else group,
            "target_muscles": [m.title() for m in e["primary_muscles"]],
            "secondary_muscles": [m.title() for m in (e["secondary_muscles"] or [])],
            "equipment": cur["equipment"] if cur else eq,
            "equipment_raw": raw_eq or "body only",
            "home_friendly": (raw_eq in HOME_EQUIPMENT),
            "outdoor_friendly": outdoor,
            "difficulty": cur["difficulty"] if cur else LEVEL.get(e["level"], "Intermediate"),
            "source_level": e["level"],
            "category": e["category"],
            "description": cur["description"] if cur else describe(e, group, eq),
            "instructions": e["instructions"] or [],
            "safety_tips": [tip],
            "aliases": cur["aliases"] if cur else [],
            "image_url": urls[0] if urls else None,
            "image_urls": urls,
            "local_images": e["images"],
            "image_license": "Unlicense (public domain) - yuhonas/free-exercise-db",
            "split": e["split"],
            "curated_v1": bool(cur),
        })
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    from collections import Counter
    print(len(out), "exercises ->", OUT.relative_to(ROOT))
    print("groups", dict(Counter(x["muscle_group"] for x in out)))
    print("difficulty", dict(Counter(x["difficulty"] for x in out)), "home", sum(x["home_friendly"] for x in out),
          "outdoor", sum(x["outdoor_friendly"] for x in out), "v1 curated kept", sum(x["curated_v1"] for x in out))
    print("no instructions", sum(not x["instructions"] for x in out))


if __name__ == "__main__":
    main()
