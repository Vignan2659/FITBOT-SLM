"""Public read-only yoga endpoints: pose library (served from SQLite), filters and the routine builder."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import YogaPose
from app.services.yoga import AREAS, GOALS, LEVELS, YogaLibrary, yoga_card

router = APIRouter(prefix="/yoga", tags=["yoga"])

LIST_FIELDS = ("slug", "name", "sanskrit", "difficulty", "kind", "category", "goals", "body_areas", "target_areas",
               "image", "motion_image", "duration", "sides", "benefits")


def library(request: Request) -> YogaLibrary:
    lib = getattr(request.app.state, "yoga", None)
    if lib is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Yoga library is not loaded")
    return lib


def summary(details: dict) -> dict:
    return {k: details[k] for k in LIST_FIELDS}


@router.get("/poses")
def list_poses(difficulty: str | None = None, goal: str | None = None, area: str | None = None,
               category: str | None = None, kind: str | None = None,
               q: str | None = Query(default=None, max_length=80), db: Session = Depends(get_db)):
    """Pose summaries for cards. Filters combine (AND); `q` searches names, Sanskrit, targets and tags."""
    if difficulty and difficulty.capitalize() not in LEVELS:
        raise HTTPException(422, f"difficulty must be one of {LEVELS}")
    if goal and goal not in GOALS:
        raise HTTPException(422, f"goal must be one of {list(GOALS)}")
    if area and area not in AREAS:
        raise HTTPException(422, f"area must be one of {list(AREAS)}")
    stmt = select(YogaPose)
    if difficulty:
        stmt = stmt.where(YogaPose.difficulty == difficulty.capitalize())
    if kind:
        stmt = stmt.where(YogaPose.kind == kind)
    rows = db.scalars(stmt.order_by(YogaPose.id)).all()
    if goal:
        rows = [r for r in rows if goal in r.goals]
    if area:
        rows = [r for r in rows if area in r.body_areas or (area == "full_body" and len(r.body_areas) >= 3)]
    if category:
        rows = [r for r in rows if category.lower() in [c.lower() for c in r.category]]
    if q:
        words = [w for w in q.lower().split() if w]
        def hay(d):
            return " ".join([d["name"], d["sanskrit"], " ".join(d["alternative_names"]), " ".join(d["category"]),
                             " ".join(d["target_areas"]), " ".join(d["tags"])]).lower()
        rows = [r for r in rows if all(w in hay(r.details) for w in words)]
    return {"count": len(rows), "poses": [summary(r.details) for r in rows]}


@router.get("/filters")
def filters(request: Request):
    """Filter options with counts (difficulty, goals, body areas, categories)."""
    return library(request).facets()


@router.get("/poses/{slug}")
def get_pose(slug: str, request: Request, db: Session = Depends(get_db)):
    key = slug.lower().strip()
    row = db.scalar(select(YogaPose).where(or_(YogaPose.slug == key, YogaPose.name.ilike(key.replace("-", " ")))))
    if row is None:
        hits = library(request).find_in_text(key.replace("-", " "), allow_ambiguous=True)
        row = db.scalar(select(YogaPose).where(YogaPose.slug == hits[0]["slug"])) if hits else None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Yoga pose '{slug}' not found")
    lib = library(request)
    pose = yoga_card(row.details)
    pose["related_poses"] = [summary(p) for p in lib.related(row.details)]
    return pose


@router.get("/routine")
def routine(request: Request, minutes: int = Query(default=15, ge=5, le=60), level: str | None = None,
            goal: str | None = None, area: str | None = None, time_of_day: str | None = None):
    """A timed routine built from the library (same builder the chat uses)."""
    if level and level.capitalize() not in LEVELS:
        raise HTTPException(422, f"level must be one of {LEVELS}")
    if goal and goal not in GOALS:
        raise HTTPException(422, f"goal must be one of {list(GOALS)}")
    if area and area not in AREAS:
        raise HTTPException(422, f"area must be one of {list(AREAS)}")
    if time_of_day and time_of_day not in ("morning", "evening"):
        raise HTTPException(422, "time_of_day must be morning or evening")
    return library(request).routine(minutes=minutes, level=level.capitalize() if level else None, goal=goal,
                                    area=area, time_of_day=time_of_day)
