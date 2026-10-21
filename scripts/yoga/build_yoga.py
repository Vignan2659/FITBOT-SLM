"""Build the FitBot yoga dataset and its motion visuals.

    python3 scripts/yoga/build_yoga.py

Reads the pose files in this folder (poses_beginner.py, poses_intermediate.py, poses_advanced.py) and writes:

    data/yoga/yoga_poses.json        structured pose records used by the backend, the API and the chat pipeline
    frontend/public/yoga/<slug>.svg  animated motion figure (start -> transition -> final), served at /yoga/<slug>.svg
    frontend/public/yoga/<slug>-<n>.svg  one still per key position, used for the "how it moves" strip

Only the Python standard library is needed. The figures are original drawings generated from joint angles, so the
whole module ships under the repository's MIT license with no third party image terms.
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
import poses_intermediate  # noqa: E402
from figure import motion_svgs  # noqa: E402

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
            "breath", "hold", "reps", "easier", "harder", "mistakes", "safety", "avoid", "suitable", "keyframes"]
IMAGE_LICENSE = "Original FitBot motion figure (MIT)"


def categories(p: dict) -> list[str]:
    cats = [GOAL_LABELS[g] for g in p["goals"]]
    cats += [AREA_LABELS[a] for a in p["areas"] if a in ("back", "shoulders", "hips", "core")]
    if any("hamstring" in t.lower() for t in p["target"]):
        cats.append("Hamstrings")
    return list(dict.fromkeys(cats))


def validate(poses: list[dict]) -> None:
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
        assert 2 <= len(p["keyframes"]) <= 3, p["slug"]


def photo_reference(name: str | None, catalog: dict) -> dict | None:
    """A matching photo set from the existing exercise library (free-exercise-db, public domain), when there is one."""
    if not name:
        return None
    e = catalog.get(name.lower())
    if not e:
        print(f"  ! photo reference '{name}' not found in the exercise library")
        return None
    return {"exercise": e["name"], "slug": e["slug"], "image_urls": e["image_urls"], "license": e["image_license"]}


def build() -> list[dict]:
    poses = poses_beginner.POSES + poses_intermediate.POSES + poses_advanced.POSES
    validate(poses)
    known = {p["slug"] for p in poses}
    catalog = {e["name"].lower(): e for e in
               json.loads((ROOT / "data" / "exercises" / "exercises_v2.json").read_text(encoding="utf-8"))}
    out_dir = ROOT / "frontend" / "public" / "yoga"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.svg"):
        old.unlink()

    records = []
    for p in poses:
        anim, stills = motion_svgs(p["keyframes"], p["view"], p["anchor"], p["name"])
        (out_dir / f"{p['slug']}.svg").write_text(anim, encoding="utf-8")
        frames = []
        for n, svg in enumerate(stills, 1):
            (out_dir / f"{p['slug']}-{n}.svg").write_text(svg, encoding="utf-8")
            frames.append(f"/yoga/{p['slug']}-{n}.svg")
        dropped = [r for r in p["related"] if r not in known]
        if dropped:
            print(f"  - {p['slug']}: related poses not in the dataset, skipped: {dropped}")
        labels = ["Start", "Transition", "Final"] if len(frames) == 3 else ["Exhale", "Inhale"] \
            if p.get("kind") == "breathing" else ["Settle", "Rest"]
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
            "image": frames[-1],
            "motion_image": f"/yoga/{p['slug']}.svg",
            "tags": p["tags"],
            # --- FitBot extensions (filters, routine builder, chat pipeline)
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
            "frames": frames,
            "frame_labels": labels,
            "photo_reference": photo_reference(p["photo"], catalog),
            "image_license": IMAGE_LICENSE,
        })
    data_dir = ROOT / "data" / "yoga"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "yoga_poses.json").write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    by = {lvl: sum(r["difficulty"] == lvl for r in records) for lvl in LEVELS}
    size = sum(f.stat().st_size for f in out_dir.glob("*.svg"))
    print(f"{len(records)} poses {by}; {len(list(out_dir.glob('*.svg')))} SVG files, {size / 1024:.0f} KB")
    return records


if __name__ == "__main__":
    build()
