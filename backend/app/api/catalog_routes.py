"""Public read-only endpoints for the exercise and food databases (served from SQLite)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ExerciseMetadata, FoodMetadata

router = APIRouter(tags=["catalog"])

EX_FIELDS = ("name", "slug", "muscle_group", "description", "target_muscles", "secondary_muscles", "equipment",
             "difficulty", "category", "instructions", "safety_tips", "home_friendly", "image_url", "image_urls",
             "image_license")
FOOD_FIELDS = ("name", "slug", "fdc_id", "usda_description", "group", "tags", "aliases", "per_100g", "portion",
               "highlights", "source", "source_url")


def ex_dict(e: ExerciseMetadata) -> dict:
    return {k: getattr(e, k) for k in EX_FIELDS}


def food_dict(f: FoodMetadata) -> dict:
    return {k: getattr(f, k) for k in FOOD_FIELDS}


@router.get("/exercises")
def list_exercises(muscle_group: str | None = None, difficulty: str | None = None, equipment: str | None = None,
                   q: str | None = Query(default=None, max_length=80), db: Session = Depends(get_db)):
    stmt = select(ExerciseMetadata)
    if muscle_group:
        stmt = stmt.where(ExerciseMetadata.muscle_group == muscle_group.lower())
    if difficulty:
        stmt = stmt.where(func.lower(ExerciseMetadata.difficulty) == difficulty.lower())
    if equipment:
        stmt = stmt.where(func.lower(ExerciseMetadata.equipment).contains(equipment.lower()))
    if q:
        stmt = stmt.where(or_(func.lower(ExerciseMetadata.name).contains(q.lower()),
                              func.lower(ExerciseMetadata.description).contains(q.lower())))
    rows = db.scalars(stmt.order_by(ExerciseMetadata.muscle_group, ExerciseMetadata.id)).all()
    return {"count": len(rows), "exercises": [ex_dict(e) for e in rows]}


@router.get("/exercises/{name}")
def get_exercise(name: str, db: Session = Depends(get_db)):
    key = name.lower().strip()
    e = db.scalar(select(ExerciseMetadata).where(or_(func.lower(ExerciseMetadata.name) == key,
                                                     ExerciseMetadata.slug == key.replace(" ", "-"))))
    if e is None:
        for cand in db.scalars(select(ExerciseMetadata)).all():
            if key in [a.lower() for a in cand.aliases]:
                e = cand
                break
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Exercise '{name}' not found")
    return ex_dict(e)


@router.get("/foods")
def list_foods(group: str | None = None, tag: str | None = None, q: str | None = Query(default=None, max_length=80),
               db: Session = Depends(get_db)):
    rows = db.scalars(select(FoodMetadata).order_by(FoodMetadata.group, FoodMetadata.id)).all()
    if group:
        rows = [f for f in rows if f.group == group]
    if tag:
        t = tag.lower()
        rows = [f for f in rows if t in f.tags or t in [h.lower() for h in f.highlights]]
    if q:
        ql = q.lower()
        rows = [f for f in rows if ql in f.name.lower() or any(ql in a for a in f.aliases)]
    return {"count": len(rows), "source": "USDA FoodData Central SR Legacy (CC0)", "foods": [food_dict(f) for f in rows]}


@router.get("/foods/{name}")
def get_food(name: str, db: Session = Depends(get_db)):
    key = name.lower().strip()
    rows = db.scalars(select(FoodMetadata)).all()
    match = next((f for f in rows if key in (f.name.lower(), f.slug, f.name.split(" (")[0].lower())), None) or \
        next((f for f in rows if key in [a.lower() for a in f.aliases]), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"'{name}' is not in FitBot's USDA food database - no values are estimated")
    return food_dict(match)
