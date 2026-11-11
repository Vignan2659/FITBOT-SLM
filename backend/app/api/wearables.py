"""Fitness bands and smartwatches: import the export file of the brand's phone app, read the summary, add a day by
hand, and save live heart rate sessions recorded over Bluetooth in the browser. All data belongs to one user and
stays in the local database."""
from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User, WearableDaily, WearableImport, WearableWorkout
from app.services import wearables as w

router = APIRouter(prefix="/wearables", tags=["wearables"])
MAX_UPLOAD = 3 * 1024 ** 3       # Apple Health exports of long-time users reach 1-2 GB


def daily_rows(user_id: int, db: Session, since: date | None = None) -> list[dict]:
    stmt = select(WearableDaily).where(WearableDaily.user_id == user_id)
    if since:
        stmt = stmt.where(WearableDaily.day >= since)
    return [{"day": r.day, "source": r.source, **{k: getattr(r, k) for k in w.METRICS}} for r in db.scalars(stmt)]


def workout_rows(user_id: int, db: Session, since: date | None = None) -> list[dict]:
    stmt = select(WearableWorkout).where(WearableWorkout.user_id == user_id).order_by(WearableWorkout.start.desc())
    if since:
        stmt = stmt.where(WearableWorkout.start >= datetime(since.year, since.month, since.day))
    return [{"id": r.id, "source": r.source, "start": r.start, "activity": r.activity, "minutes": r.minutes, "kcal": r.kcal,
             "avg_hr": r.avg_hr, "max_hr": r.max_hr, "distance_km": r.distance_km, "steps": r.steps} for r in db.scalars(stmt)]


def user_summary(user_id: int, db: Session, today: date | None = None, days: int = 14) -> dict:
    """The band summary of one user (also used by the chat to ground answers in the person's own numbers)."""
    if today is None:
        # the browser's calendar day can be a day ahead of the server's clock (time zones): follow the newest row
        today = date.today()
        newest = db.scalar(select(func.max(WearableDaily.day)).where(WearableDaily.user_id == user_id))
        if newest and today < newest <= today + timedelta(days=1):
            today = newest
    since = today - timedelta(days=max(days, 14) + 30)          # 4 weeks of history for the personal baseline
    workouts = workout_rows(user_id, db, since)
    summary = w.build_summary(daily_rows(user_id, db, since), workouts, today, days)
    summary["workouts"] = [{**x, "start": x["start"].isoformat(timespec="minutes")} for x in workouts
                           if x["start"].date() >= today - timedelta(days=days)][:30]
    return summary


def upsert_day(db: Session, user_id: int, day: date, source: str, values: dict) -> None:
    row = db.scalar(select(WearableDaily).where(WearableDaily.user_id == user_id, WearableDaily.day == day,
                                                WearableDaily.source == source))
    if row is None:
        row = WearableDaily(user_id=user_id, day=day, source=source)
        db.add(row)
    for k in w.METRICS:
        if values.get(k) is not None:
            setattr(row, k, values[k])


def store(db: Session, user_id: int, source: str, parsed: w.Parsed) -> int:
    for day, values in parsed.daily.items():
        upsert_day(db, user_id, day, source, values)
    have = {(r.start, r.activity) for r in db.scalars(select(WearableWorkout).where(
        WearableWorkout.user_id == user_id, WearableWorkout.source == source))}
    added = 0
    for x in parsed.workouts:
        if (x["start"], x["activity"]) not in have:
            have.add((x["start"], x["activity"]))
            db.add(WearableWorkout(user_id=user_id, source=source, **x))
            added += 1
    return added


@router.get("/brands")
def brands():
    return {"brands": w.BRANDS, "metrics": list(w.METRICS),
            "live_heart_rate": "Works in Chrome or Edge with any band or chest strap that broadcasts heart rate over "
                               "Bluetooth (the standard Heart Rate service)."}


@router.get("/template.csv", response_class=PlainTextResponse)
def template():
    return PlainTextResponse(w.TEMPLATE_CSV, media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="fitbot_band_template.csv"'})


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_file(request: Request, brand: str = Query(default="other", max_length=20),
                      filename: str = Query(default="export", max_length=160),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The request body is the export file itself (zip, xml, csv, json or db), sent as raw bytes."""
    if brand not in w.BRAND_IDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown brand")
    fd, path = tempfile.mkstemp(prefix="fitbot-band-")
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "This file is too large (limit 3 GB).")
                out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file is empty.")
        try:
            parsed = await run_in_threadpool(w.parse_export, path, filename)
        except w.WearableError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    added = store(db, user.id, brand, parsed)
    days = sorted(parsed.daily)
    db.add(WearableImport(user_id=user.id, source=brand, format=parsed.format, filename=os.path.basename(filename)[:160],
                          days=len(days), workouts=len(parsed.workouts), first_day=days[0] if days else None,
                          last_day=days[-1] if days else None))
    db.commit()
    found = sorted({k for row in parsed.daily.values() for k in row})
    return {"format": parsed.format, "days": len(days), "workouts": len(parsed.workouts), "new_workouts": added,
            "first_day": days[0].isoformat() if days else None, "last_day": days[-1].isoformat() if days else None,
            "metrics": found, "notes": parsed.notes}


@router.get("/summary")
def summary(days: int = Query(default=14, ge=7, le=90), today: date | None = None,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = user_summary(user.id, db, today, days)
    imports = db.scalars(select(WearableImport).where(WearableImport.user_id == user.id)
                         .order_by(WearableImport.id.desc()).limit(8)).all()
    out["imports"] = [{"id": i.id, "source": i.source, "format": i.format, "filename": i.filename, "days": i.days,
                       "workouts": i.workouts, "first_day": i.first_day, "last_day": i.last_day,
                       "created_at": i.created_at} for i in imports]
    return out


class DayIn(BaseModel):
    day: date
    steps: int | None = Field(default=None, ge=0, le=150000)
    distance_km: float | None = Field(default=None, ge=0, le=300)
    active_kcal: float | None = Field(default=None, ge=0, le=15000)
    resting_hr: float | None = Field(default=None, ge=25, le=130)
    avg_hr: float | None = Field(default=None, ge=25, le=220)
    max_hr: float | None = Field(default=None, ge=30, le=250)
    hrv_ms: float | None = Field(default=None, ge=3, le=400)
    stress: float | None = Field(default=None, ge=0, le=100)
    sleep_minutes: float | None = Field(default=None, ge=0, le=1200)
    spo2: float | None = Field(default=None, ge=60, le=100)


@router.put("/day")
def save_day(body: DayIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Type a day's numbers in by hand (for bands with no export)."""
    if body.day > date.today() + timedelta(days=1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The day cannot be in the future")
    values = {k: v for k, v in body.model_dump(exclude={"day"}).items() if v}
    if not values:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter at least one number")
    upsert_day(db, user.id, body.day, "manual", values)
    db.commit()
    return {"day": body.day, "saved": sorted(values)}


class LiveIn(BaseModel):
    started_at: datetime
    minutes: float = Field(gt=0, le=600)
    avg_hr: float = Field(ge=25, le=240)
    max_hr: float = Field(ge=25, le=260)
    activity: str = Field(default="Workout", min_length=1, max_length=60)
    device: str | None = Field(default=None, max_length=60)


@router.post("/live", status_code=status.HTTP_201_CREATED)
def save_live(body: LiveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save a live heart rate session measured over Bluetooth in the browser."""
    start = body.started_at.replace(tzinfo=None, microsecond=0)
    row = WearableWorkout(user_id=user.id, source="live", start=start, activity=w.tidy_activity(body.activity),
                          minutes=round(body.minutes, 1), avg_hr=round(body.avg_hr, 1), max_hr=round(body.max_hr, 1))
    db.add(row)
    db.commit()
    return {"id": row.id, "activity": row.activity, "minutes": row.minutes, "avg_hr": row.avg_hr, "max_hr": row.max_hr}


@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
def delete_data(source: str | None = Query(default=None, max_length=20), user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Delete the user's band data (one source, or everything)."""
    for model in (WearableDaily, WearableWorkout, WearableImport):
        stmt = delete(model).where(model.user_id == user.id)
        if source:
            stmt = stmt.where(model.source == source)
        db.execute(stmt)
    db.commit()
