"""Build the FitBot yoga dataset.

    python3 scripts/yoga/build_yoga.py

Reads the pose texts in this folder (poses_*.py) and the photo credits in data/yoga/photo_credits.json, and writes
data/yoga/yoga_poses.json, the file the backend loads. Only poses that have photos are published. The photos of a pose
are listed in motion order (starting position first, the finished pose last), so the app can play them as a short
motion when the cursor is on the picture. They are stored in frontend/public/yoga/photos/ (served at /yoga/photos/...).
Studio photos are by Margaret Young on Unsplash; gym photos come from the public domain free-exercise-db set. Each record
carries the author, licence and source page so the app can credit them.

To change the photos: edit data/yoga/photo_credits.json, put the new files in frontend/public/yoga/photos/
(scripts/yoga/process_photos.py resizes downloaded originals), then run this script again.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import poses_advanced  # noqa: E402
import poses_beginner  # noqa: E402
import poses_extra  # noqa: E402
import poses_intermediate  # noqa: E402

GOAL_LABELS = {
    "flexibility": "Flexibility", "mobility": "Mobility", "strength": "Strength", "balance": "Balance", "core": "Core",
    "stress_relief": "Stress relief", "relaxation": "Relaxation", "recovery": "Recovery",
    "weight_management": "Weight management", "posture": "Posture", "breathing": "Breathing", "meditation": "Meditation",
}
AREA_LABELS = {"back": "Back", "shoulders": "Shoulders", "hips": "Hips", "legs": "Legs", "core": "Core",
               "full_body": "Full body", "chest": "Chest", "neck": "Neck"}
PHASES = ["centering", "warmup", "standing", "balance", "core", "backbend", "seated", "inversion", "cooldown", "relaxation"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
REQUIRED = ["slug", "name", "sanskrit", "alt", "difficulty", "phase", "goals", "areas", "target", "benefits", "steps",
            "breath", "hold", "reps", "easier", "harder", "mistakes", "safety", "avoid", "suitable"]
PHOTO_DIR = ROOT / "frontend" / "public" / "yoga" / "photos"


def categories(p: dict) -> list[str]:
    cats = [GOAL_LABELS[g] for g in p["goals"]]
    cats += [AREA_LABELS[a] for a in p["areas"] if a in ("back", "shoulders", "hips", "core")]
    if any("hamstring" in t.lower() for t in p["target"]):
        cats.append("Hamstrings")
    return list(dict.fromkeys(cats))


def validate(poses: list[dict], credits: dict) -> None:
    slugs = [p["slug"] for p in poses]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    assert not dupes, f"duplicate slugs: {dupes}"
    for p in poses:
        missing = [f for f in REQUIRED if not p.get(f)]
        assert not missing, f"{p['slug']}: missing {missing}"
        assert p["difficulty"] in LEVELS, p["slug"]
        assert p["phase"] in PHASES, p["slug"]
        assert set(p["goals"]) <= set(GOAL_LABELS), (p["slug"], p["goals"])
        assert set(p["areas"]) <= set(AREA_LABELS), (p["slug"], p["areas"])
        for ph in credits[p["slug"]]:
            assert (PHOTO_DIR / ph["file"]).exists(), f"missing photo file {ph['file']}"
            assert ph["license"] and ph["author"] and ph["source"], f"{ph['file']}: incomplete credit"


def build() -> list[dict]:
    written = poses_beginner.POSES + poses_intermediate.POSES + poses_advanced.POSES + poses_extra.POSES
    credits = json.loads((ROOT / "data" / "yoga" / "photo_credits.json").read_text(encoding="utf-8"))["photos"]
    missing = set(credits) - {p["slug"] for p in written}
    assert not missing, f"photos without a pose text: {missing}"
    poses = [p for p in written if p["slug"] in credits]      # poses without a good photo are left out
    validate(poses, credits)
    known = {p["slug"] for p in poses}
    records = []
    for p in poses:
        photos = [{"url": f"/yoga/photos/{ph['file']}",
                   **{k: ph[k] for k in ("author", "author_url", "license", "license_url", "source", "source_name", "title")}}
                  for ph in credits[p["slug"]]]
        records.append({
            # --- the fields of the requested yoga schema
            "name": p["name"],
            "alternative_names": p["alt"],
            "category": categories(p),
            "difficulty": p["difficulty"],
            "target_areas": p["target"],
            "benefits": p["benefits"],
            "instructions": p["steps"],
            "breathing": p["breath"],
            "duration": p["hold"],
            "recommended_repetitions": p["reps"],
            "beginner_modification": p["easier"],
            "advanced_variation": p["harder"],
            "common_mistakes": p["mistakes"],
            "safety_tips": p["safety"],
            "contraindications": p["avoid"],
            "equipment": p["equipment"],
            "suitable_for": p["suitable"],
            "image": photos[-1]["url"],                     # the finished pose
            "image_urls": [ph["url"] for ph in photos],       # motion order: start position ... finished pose
            "tags": p["tags"],
            # --- FitBot extensions (filters, routine builder, chat pipeline, photo credits)
            "slug": p["slug"],
            "sanskrit": p["sanskrit"],
            "kind": p.get("kind", "pose"),
            "goals": p["goals"],
            "body_areas": p["areas"],
            "phase": p["phase"],
            "time_of_day": p["time"],
            "energy": p["energy"],
            "sides": p["sides"],
            "default_minutes": p["minutes"],
            "related": [r for r in p["related"] if r in known],
            "photos": photos,
        })
    out = ROOT / "data" / "yoga" / "yoga_poses.json"
    out.write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    by = {lvl: sum(r["difficulty"] == lvl for r in records) for lvl in LEVELS}
    n_photos = sum(len(r["photos"]) for r in records)
    print(f"{len(records)} poses {by}, {n_photos} photos")
    return records


if __name__ == "__main__":
    build()
