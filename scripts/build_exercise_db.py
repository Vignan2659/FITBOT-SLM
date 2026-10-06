"""Build FitBot's exercise database from free-exercise-db (Unlicense / public domain).

Source : https://github.com/yuhonas/free-exercise-db  (dist/exercises.json)
Images : https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/<path>

Outputs
  data/exercises/exercises.json   curated exercises used for cards / planner / training
  data/exercises/catalog.json     the full source catalog normalised (searchable fallback)

Instructions, muscles, equipment and image paths come from the source dataset.
Descriptions, safety tips and FitBot difficulty ratings are written for this project.
Every curated image URL is verified with an HTTP HEAD request (use --skip-verify offline).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "free-exercise-db.json"
OUT_DIR = ROOT / "data" / "exercises"
SOURCE_URL = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
IMAGE_BASE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"

EQUIPMENT_LABELS = {
    "body only": "Bodyweight", None: "Bodyweight", "dumbbell": "Dumbbells", "barbell": "Barbell",
    "cable": "Cable machine", "machine": "Machine", "kettlebells": "Kettlebell", "bands": "Resistance bands",
    "medicine ball": "Medicine ball", "exercise ball": "Exercise ball", "foam roll": "Foam roller",
    "e-z curl bar": "EZ curl bar", "other": "Other",
}

# (display name, source id, muscle group, FitBot difficulty, equipment override or None,
#  aliases, description, safety tip)
CURATED: list[tuple] = [
    # ---------------- Chest ----------------
    ("Bench Press", "Barbell_Bench_Press_-_Medium_Grip", "chest", "Intermediate", None,
     ["barbell bench press", "flat bench press", "bench"],
     "A compound pressing movement and one of the most effective exercises for building chest, shoulder and triceps strength.",
     "Use a spotter or safety arms for heavy sets, keep your feet planted and lower the bar under control to mid-chest."),
    ("Push-Ups", "Pushups", "chest", "Beginner", None,
     ["push up", "pushup", "press up", "push-up"],
     "A bodyweight press that trains the chest, shoulders, triceps and core with no equipment.",
     "Keep a straight line from head to heels; if full push-ups are too hard, elevate your hands on a bench or do them from the knees."),
    ("Incline Push-Ups", "Incline_Push-Up", "chest", "Beginner", None,
     ["incline push up", "elevated push up"],
     "An easier push-up variation with the hands raised on a bench or step, ideal for beginners building up to floor push-ups.",
     "Use a stable surface that will not slide and keep your body in one straight line."),
    ("Dumbbell Press", "Dumbbell_Bench_Press", "chest", "Beginner", None,
     ["dumbbell bench press", "db press", "dumbbell chest press"],
     "A chest press with dumbbells that allows a natural range of motion and trains each side independently.",
     "Choose a weight you can control, and bring the dumbbells to your chest before sitting up rather than dropping them to the sides."),
    ("Incline Press", "Incline_Dumbbell_Press", "chest", "Beginner", None,
     ["incline dumbbell press", "incline bench press", "incline chest press"],
     "A pressing movement on an inclined bench that emphasises the upper chest and front shoulders.",
     "Set the bench to a moderate incline (about 30-45 degrees) and keep your shoulder blades pulled back against the bench."),
    ("Chest Fly", "Dumbbell_Flyes", "chest", "Beginner", None,
     ["dumbbell fly", "dumbbell flye", "chest flye", "pec fly"],
     "An isolation exercise that stretches and contracts the chest through a wide arc.",
     "Keep a slight bend in the elbows and avoid lowering the weights so far that you feel strain in the front of the shoulder."),
    ("Cable Crossover", "Cable_Crossover", "chest", "Intermediate", None,
     ["cable fly", "cable chest fly", "crossover"],
     "A cable fly variation that keeps constant tension on the chest throughout the movement.",
     "Stand in a staggered stance for balance and control the return; do not let the cables pull your arms back quickly."),
    # ---------------- Back ----------------
    ("Lat Pulldown", "Wide-Grip_Lat_Pulldown", "back", "Beginner", None,
     ["lat pull down", "pulldown", "lat pull-down"],
     "A machine exercise that builds the lats and upper back and helps develop strength towards pull-ups.",
     "Pull the bar to your upper chest, not behind your neck, and avoid leaning far back or using momentum."),
    ("Pull-Ups", "Pullups", "back", "Intermediate", None,
     ["pull up", "pullup", "chin up", "chin-up"],
     "A bodyweight pulling exercise that strongly develops the lats, upper back and biceps.",
     "Start from a controlled dead hang and use assistance bands or the lat pulldown if you cannot yet do full reps."),
    ("Seated Row", "Seated_Cable_Rows", "back", "Beginner", None,
     ["seated cable row", "cable row", "row machine"],
     "A horizontal pulling exercise for the middle back, lats and rear shoulders.",
     "Keep your torso upright and your lower back neutral; pull with your back rather than rocking your body."),
    ("Dumbbell Row", "One-Arm_Dumbbell_Row", "back", "Beginner", None,
     ["one arm dumbbell row", "single arm row", "db row"],
     "A single-arm row supported on a bench that builds the lats and middle back.",
     "Keep your back flat and parallel to the floor and avoid twisting your torso to lift the weight."),
    ("Bent-Over Dumbbell Row", "Bent_Over_Two-Dumbbell_Row", "back", "Intermediate", None,
     ["two dumbbell row", "bent over row", "bent-over row"],
     "A two-arm dumbbell row performed with a hip hinge, training the whole upper back.",
     "Hinge at the hips with a neutral spine and keep the weight moderate until the position feels stable."),
    ("Deadlift", "Barbell_Deadlift", "back", "Advanced", None,
     ["barbell deadlift", "conventional deadlift"],
     "A full-body hinge that builds the posterior chain - hamstrings, glutes and back - and grip strength.",
     "Learn the hip hinge with light weight first, keep the bar close to your legs and never round your lower back under load."),
    ("Romanian Deadlift", "Stiff-Legged_Dumbbell_Deadlift", "back", "Intermediate", "Dumbbells",
     ["rdl", "dumbbell romanian deadlift", "stiff leg deadlift"],
     "A hip-hinge exercise with dumbbells that targets the hamstrings, glutes and lower back.",
     "Push your hips back while keeping a neutral spine and stop when you feel a stretch in the hamstrings."),
    ("Superman", "Superman", "back", "Beginner", None,
     ["superman hold", "back extension floor"],
     "A floor exercise that strengthens the lower back and glutes without equipment.",
     "Lift slowly and only as high as is comfortable; avoid cranking your neck back."),
    # ---------------- Shoulders ----------------
    ("Shoulder Press", "Dumbbell_Shoulder_Press", "shoulders", "Beginner", None,
     ["overhead press", "dumbbell shoulder press", "military press", "ohp"],
     "An overhead press that builds the deltoids and triceps.",
     "Brace your core, avoid arching your lower back and press in a controlled path without locking out aggressively."),
    ("Lateral Raise", "Side_Lateral_Raise", "shoulders", "Beginner", None,
     ["side lateral raise", "side raise", "lateral raises"],
     "An isolation exercise for the side deltoids that adds shoulder width.",
     "Use light weights, raise only to shoulder height and avoid swinging your body."),
    ("Front Raise", "Front_Dumbbell_Raise", "shoulders", "Beginner", None,
     ["front dumbbell raise", "front raises"],
     "An isolation exercise for the front deltoids.",
     "Lift to roughly shoulder height with control; using momentum shifts stress to the lower back."),
    ("Rear Delt Fly", "Reverse_Flyes", "shoulders", "Beginner", None,
     ["reverse fly", "rear delt raise", "reverse flye", "rear delt flyes"],
     "A bent-over fly that targets the rear deltoids and upper back, supporting good posture.",
     "Keep a slight bend in the elbows, a flat back and use light weights."),
    ("Arnold Press", "Arnold_Dumbbell_Press", "shoulders", "Intermediate", None,
     ["arnold dumbbell press"],
     "A rotating dumbbell press that works all three heads of the deltoid.",
     "Rotate smoothly and keep the weight moderate; stop if you feel pinching in the shoulder."),
    # ---------------- Legs ----------------
    ("Squat", "Barbell_Squat", "legs", "Intermediate", None,
     ["barbell squat", "back squat", "squats"],
     "A fundamental compound lower-body exercise for the quadriceps, glutes and hamstrings.",
     "Keep your chest up, knees tracking over your toes and use safety bars in a squat rack."),
    ("Bodyweight Squat", "Bodyweight_Squat", "legs", "Beginner", None,
     ["air squat", "body weight squat", "squat without weights"],
     "A squat with no external load - the best place to learn squat technique.",
     "Sit back as if into a chair and only go as deep as you can while keeping your heels down and back neutral."),
    ("Goblet Squat", "Goblet_Squat", "legs", "Beginner", "Dumbbell or kettlebell",
     ["dumbbell squat", "goblet squats"],
     "A squat holding one dumbbell or kettlebell at the chest, which naturally encourages an upright torso.",
     "Hold the weight close to your chest and keep your elbows inside your knees at the bottom."),
    ("Lunges", "Dumbbell_Lunges", "legs", "Beginner", "Bodyweight or dumbbells",
     ["lunge", "dumbbell lunges", "forward lunge", "walking lunges"],
     "A single-leg exercise that builds leg strength, balance and coordination. Can be done with or without dumbbells.",
     "Take a long enough step that your front knee stays roughly over your ankle, and start without weights."),
    ("Leg Press", "Leg_Press", "legs", "Beginner", None,
     ["leg press machine"],
     "A machine-based press for the quadriceps and glutes that lets you train the legs with back support.",
     "Do not lock your knees at the top and do not lower so far that your lower back lifts off the pad."),
    ("Leg Extension", "Leg_Extensions", "legs", "Beginner", None,
     ["leg extensions", "quad extension"],
     "A machine isolation exercise for the quadriceps.",
     "Adjust the pad to sit just above your ankles and lift with control rather than kicking."),
    ("Leg Curl", "Lying_Leg_Curls", "legs", "Beginner", None,
     ["hamstring curl", "lying leg curl", "leg curls"],
     "A machine isolation exercise for the hamstrings.",
     "Keep your hips pressed into the pad and avoid jerking the weight."),
    ("Calf Raise", "Standing_Calf_Raises", "legs", "Beginner", None,
     ["standing calf raise", "calf raises", "heel raise"],
     "An exercise for the calf muscles that can be done on a machine, a step or with dumbbells.",
     "Use a full, controlled range of motion and pause briefly at the top."),
    ("Glute Bridge", "Single_Leg_Glute_Bridge", "legs", "Beginner", None,
     ["hip bridge", "glute bridges", "single leg glute bridge"],
     "A floor exercise that strengthens the glutes and hamstrings with no equipment.",
     "Squeeze your glutes to lift, avoid overarching your lower back; start with both feet down before progressing to one leg."),
    ("Step-Ups", "Dumbbell_Step_Ups", "legs", "Beginner", "Step or bench (dumbbells optional)",
     ["step up", "dumbbell step ups"],
     "A single-leg exercise stepping onto a box or bench, building leg strength and balance.",
     "Use a stable, knee-height or lower step and drive through the whole foot of the working leg."),
    # ---------------- Arms ----------------
    ("Bicep Curl", "Dumbbell_Bicep_Curl", "arms", "Beginner", None,
     ["biceps curl", "dumbbell curl", "bicep curls", "curls"],
     "An isolation exercise for the biceps.",
     "Keep your elbows by your sides and avoid swinging your torso to lift the weight."),
    ("Hammer Curl", "Hammer_Curls", "arms", "Beginner", None,
     ["hammer curls", "neutral grip curl"],
     "A curl with palms facing each other that trains the biceps, brachialis and forearms.",
     "Move slowly and keep your wrists neutral and elbows still."),
    ("Tricep Pushdown", "Triceps_Pushdown", "arms", "Beginner", None,
     ["triceps pushdown", "cable pushdown", "rope pushdown"],
     "A cable isolation exercise for the triceps.",
     "Keep your elbows pinned to your sides and only move your forearms."),
    ("Tricep Extension", "Cable_Rope_Overhead_Triceps_Extension", "arms", "Beginner", None,
     ["overhead tricep extension", "triceps extension", "overhead extension"],
     "An overhead extension that emphasises the long head of the triceps.",
     "Keep your elbows pointing forward and use a weight that does not force your lower back to arch."),
    ("Dumbbell Tricep Extension", "Dumbbell_One-Arm_Triceps_Extension", "arms", "Beginner", None,
     ["one arm triceps extension", "dumbbell overhead extension"],
     "An overhead triceps extension with a dumbbell - a good option for home training.",
     "Start light and lower the dumbbell behind your head slowly."),
    ("Dips", "Dips_-_Triceps_Version", "arms", "Intermediate", None,
     ["parallel bar dips", "tricep dips", "triceps dips"],
     "A bodyweight press on parallel bars for the triceps, chest and shoulders.",
     "Only lower until your upper arms are about parallel to the floor; skip or modify dips if they cause shoulder pain."),
    ("Bench Dips", "Bench_Dips", "arms", "Beginner", None,
     ["chair dips", "bench dip"],
     "A triceps exercise using a bench or sturdy chair - easy to do at home.",
     "Keep your hips close to the bench and limit depth if you feel discomfort at the front of the shoulder."),
    # ---------------- Core ----------------
    ("Plank", "Plank", "core", "Beginner", None,
     ["front plank", "planks", "forearm plank"],
     "An isometric hold that trains the deep core muscles and teaches the body to stay rigid.",
     "Keep a straight line from head to heels; stop the set when your hips sag."),
    ("Crunches", "Crunches", "core", "Beginner", None,
     ["crunch", "ab crunch", "sit ups"],
     "A basic abdominal exercise that flexes the spine against gravity.",
     "Lift with your abs rather than pulling on your neck, and keep the movement small and controlled."),
    ("Leg Raises", "Flat_Bench_Lying_Leg_Raise", "core", "Beginner", None,
     ["lying leg raise", "leg raise", "lower ab raises"],
     "A core exercise that targets the lower abdominal region and hip flexors.",
     "Press your lower back into the bench or floor; bend your knees if your back starts to arch."),
    ("Russian Twists", "Russian_Twist", "core", "Intermediate", None,
     ["russian twist", "seated twist"],
     "A rotational core exercise that targets the obliques.",
     "Rotate through your upper back with control; keep your feet on the floor if you feel strain in your lower back."),
    ("Mountain Climbers", "Mountain_Climbers", "core", "Beginner", None,
     ["mountain climber"],
     "A dynamic plank-position exercise that trains the core and raises the heart rate.",
     "Keep your hips level and start slowly before increasing the pace."),
    ("Dead Bug", "Dead_Bug", "core", "Beginner", None,
     ["deadbug", "dead bugs"],
     "A beginner-friendly core exercise that trains stability while keeping the lower back supported.",
     "Keep your lower back pressed into the floor and move slowly."),
    # ---------------- Cardio ----------------
    ("Walking", "Walking_Treadmill", "cardio", "Beginner", "None (or treadmill)",
     ["walk", "brisk walking", "treadmill walking"],
     "Low-impact cardio suitable for almost everyone; brisk walking counts as moderate-intensity activity.",
     "Wear supportive shoes and build duration gradually."),
    ("Running", "Running_Treadmill", "cardio", "Intermediate", "None (or treadmill)",
     ["run", "jogging", "jog", "treadmill running"],
     "Higher-intensity cardio that builds aerobic fitness and endurance.",
     "Increase weekly distance gradually and mix in walking intervals if you are new to running."),
    ("Cycling", "Bicycling_Stationary", "cardio", "Beginner", "Bike or stationary bike",
     ["bike", "biking", "stationary bike", "spin"],
     "Low-impact cardio that is easy on the joints and builds leg endurance.",
     "Adjust the seat height so your knee is slightly bent at the bottom of the pedal stroke."),
    ("Jump Rope", "Rope_Jumping", "cardio", "Intermediate", "Jump rope",
     ["skipping", "rope jumping", "skipping rope"],
     "A high-intensity cardio exercise that also improves coordination and footwork.",
     "Land softly on the balls of your feet and start with short intervals."),
    ("Rowing", "Rowing_Stationary", "cardio", "Intermediate", "Rowing machine",
     ["rowing machine", "rower", "erg"],
     "Full-body, low-impact cardio that uses the legs, back and arms.",
     "Drive mainly with your legs and keep your back neutral; avoid pulling first with the arms."),
    ("Elliptical", "Elliptical_Trainer", "cardio", "Beginner", "Elliptical machine",
     ["elliptical trainer", "cross trainer"],
     "Low-impact cardio machine that is gentle on the knees and hips.",
     "Stand upright and avoid leaning heavily on the handles."),
    # ---------------- Stretching / mobility ----------------
    ("Hamstring Stretch", "Hamstring_Stretch", "stretching", "Beginner", "None",
     ["hamstring stretches"],
     "A static stretch for the back of the thighs, useful after leg workouts and running.",
     "Stretch to mild tension, not pain, and hold steadily without bouncing."),
    ("Quad Stretch", "Standing_Elevated_Quad_Stretch", "stretching", "Beginner", "None",
     ["quadriceps stretch", "standing quad stretch"],
     "A stretch for the front of the thighs.",
     "Hold onto something for balance and keep your knees close together."),
    ("Hip Flexor Stretch", "Kneeling_Hip_Flexor", "stretching", "Beginner", "None",
     ["kneeling hip flexor stretch", "hip stretch"],
     "A kneeling stretch for the hip flexors, helpful for people who sit for long periods.",
     "Use a cushion under the knee and tuck your pelvis slightly rather than arching your back."),
    ("Child's Pose", "Childs_Pose", "stretching", "Beginner", "None",
     ["childs pose", "child pose"],
     "A gentle resting stretch for the back, hips and shoulders.",
     "Widen your knees if you feel pressure in your hips or knees."),
    ("Cat Stretch", "Cat_Stretch", "stretching", "Beginner", "None",
     ["cat cow", "cat-cow"],
     "A gentle spinal mobility exercise performed on hands and knees.",
     "Move slowly through a comfortable range of motion."),
    ("Chest Stretch", "Dynamic_Chest_Stretch", "stretching", "Beginner", "None",
     ["dynamic chest stretch", "pec stretch"],
     "A dynamic stretch that opens up the chest and front of the shoulders.",
     "Move smoothly and stay within a comfortable range."),
    ("Calf Stretch", "Calf_Stretch_Hands_Against_Wall", "stretching", "Beginner", "None",
     ["wall calf stretch"],
     "A wall stretch for the calf muscles, useful after walking or running.",
     "Keep the back heel on the floor and hold the stretch gently."),
    ("Shoulder Stretch", "Shoulder_Stretch", "stretching", "Beginner", "None",
     ["cross body shoulder stretch"],
     "A simple stretch for the shoulders and upper back.",
     "Pull gently and avoid pressing directly on the elbow joint."),
    ("Triceps Stretch", "Triceps_Stretch", "stretching", "Beginner", "None",
     ["tricep stretch", "overhead triceps stretch"],
     "An overhead stretch for the triceps and shoulders.",
     "Keep your head upright and pull gently."),
]

HOME_EQUIPMENT = {"body only", None, "dumbbell", "bands", "kettlebells"}


def title(m: str) -> str:
    return m.replace("_", " ").title()


def load_source() -> list[dict]:
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, RAW)
    return json.loads(RAW.read_text())


def head_ok(url: str, retries: int = 4) -> bool:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-verify", action="store_true", help="skip HTTP image checks")
    args = ap.parse_args()

    source = load_source()
    by_id = {x["id"]: x for x in source}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    curated, missing = [], []
    for (name, sid, group, difficulty, eq_override, aliases, desc, safety) in CURATED:
        src = by_id.get(sid)
        if src is None:
            missing.append(sid)
            continue
        images = [IMAGE_BASE + p for p in src.get("images", [])]
        curated.append({
            "name": name,
            "slug": name.lower().replace("'", "").replace(" ", "-"),
            "source_id": sid,
            "source_name": src["name"],
            "muscle_group": group,
            "target_muscles": [title(m) for m in src.get("primaryMuscles", [])],
            "secondary_muscles": [title(m) for m in src.get("secondaryMuscles", [])],
            "equipment": eq_override or EQUIPMENT_LABELS.get(src.get("equipment"), "Other"),
            "equipment_raw": src.get("equipment") or "body only",
            "home_friendly": (src.get("equipment") in HOME_EQUIPMENT) or group in ("cardio", "stretching") and sid not in ("Rowing_Stationary", "Elliptical_Trainer"),
            "difficulty": difficulty,
            "source_level": src.get("level"),
            "category": src.get("category"),
            "mechanic": src.get("mechanic"),
            "force": src.get("force"),
            "description": desc,
            "instructions": src.get("instructions", []),
            "safety_tips": [safety],
            "aliases": aliases,
            "image_url": images[0] if images else None,
            "image_urls": images,
            "image_license": "Unlicense (public domain) - yuhonas/free-exercise-db",
        })
    if missing:
        sys.exit(f"Source ids not found in free-exercise-db: {missing}")

    if not args.skip_verify:
        urls = [u for e in curated for u in e["image_urls"]]
        with ThreadPoolExecutor(4) as pool:
            ok = dict(zip(urls, pool.map(head_ok, urls)))
        bad = [u for u, v in ok.items() if not v]
        if bad:
            sys.exit(f"{len(bad)} image URLs failed verification, e.g. {bad[:3]}")
        print(f"Verified {len(urls)} image URLs (HTTP 200)")

    catalog = [{
        "name": x["name"], "source_id": x["id"], "level": x.get("level"),
        "equipment": EQUIPMENT_LABELS.get(x.get("equipment"), "Other"), "category": x.get("category"),
        "primary_muscles": [title(m) for m in x.get("primaryMuscles", [])],
        "secondary_muscles": [title(m) for m in x.get("secondaryMuscles", [])],
        "instructions": x.get("instructions", []),
        "image_urls": [IMAGE_BASE + p for p in x.get("images", [])],
    } for x in source]

    (OUT_DIR / "exercises.json").write_text(json.dumps(curated, indent=2, ensure_ascii=False))
    (OUT_DIR / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))
    groups: dict[str, int] = {}
    for e in curated:
        groups[e["muscle_group"]] = groups.get(e["muscle_group"], 0) + 1
    print(f"Curated exercises: {len(curated)} {groups}")
    print(f"Full catalog: {len(catalog)} exercises")


if __name__ == "__main__":
    main()
