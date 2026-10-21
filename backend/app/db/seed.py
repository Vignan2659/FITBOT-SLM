"""Create tables and load exercise / food / yoga metadata from the processed JSON files."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import ExerciseMetadata, FoodMetadata, YogaPose


def init_db(engine, data_dir: Path, exercises_file: str = "exercises/exercises.json") -> dict:
    Base.metadata.create_all(engine)
    exercises = json.loads((data_dir / exercises_file).read_text(encoding="utf-8"))
    foods = json.loads((data_dir / "nutrition" / "foods.json").read_text())
    with Session(engine) as db:
        # metadata tables are re-synced from data/ on every start (small, keeps DB == source files)
        db.execute(delete(ExerciseMetadata))
        for e in exercises:
            db.add(ExerciseMetadata(**{k: e[k] for k in (
                "name", "slug", "muscle_group", "description", "target_muscles", "secondary_muscles", "equipment",
                "equipment_raw", "difficulty", "category", "instructions", "safety_tips", "aliases", "home_friendly",
                "image_url", "image_urls", "image_license", "source_id")}))
        db.execute(delete(FoodMetadata))
        for f in foods:
            db.add(FoodMetadata(name=f["name"], slug=f["slug"], fdc_id=f["fdc_id"],
                                usda_description=f["usda_description"], group=f["group"], tags=f["fitbot_tags"],
                                aliases=f["aliases"], per_100g=f["per_100g"], portion=f["portion"],
                                highlights=f["highlights"], source=f["source"], source_url=f["source_url"]))
        db.execute(delete(YogaPose))
        yoga_file = data_dir / "yoga" / "yoga_poses.json"
        for y in (json.loads(yoga_file.read_text(encoding="utf-8")) if yoga_file.exists() else []):
            db.add(YogaPose(slug=y["slug"], name=y["name"], sanskrit=y["sanskrit"], difficulty=y["difficulty"],
                            kind=y["kind"], phase=y["phase"], category=y["category"], goals=y["goals"],
                            body_areas=y["body_areas"], image_path=y["image"], motion_asset_path=y["motion_image"],
                            details=y))
        db.commit()
        return {"exercises": db.scalar(select(func.count()).select_from(ExerciseMetadata)),
                "foods": db.scalar(select(func.count()).select_from(FoodMetadata)),
                "yoga_poses": db.scalar(select(func.count()).select_from(YogaPose))}
