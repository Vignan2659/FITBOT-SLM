"""Create tables and load exercise / food metadata from the processed JSON files."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import ExerciseMetadata, FoodMetadata


def init_db(engine, data_dir: Path) -> dict:
    Base.metadata.create_all(engine)
    exercises = json.loads((data_dir / "exercises" / "exercises.json").read_text())
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
        db.commit()
        return {"exercises": db.scalar(select(func.count()).select_from(ExerciseMetadata)),
                "foods": db.scalar(select(func.count()).select_from(FoodMetadata))}
