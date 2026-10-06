"""Saved plans, workout log + progress stats, and answer feedback. Every row belongs to one user;
other users' ids return 404 (not 403) so they are not revealed."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (FeedbackIn, FeedbackOut, PlanIn, PlanOut, WorkoutIn, WorkoutOut, WorkoutStats)
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Conversation, Message, MessageFeedback, SavedPlan, User, WorkoutLog

plans_router = APIRouter(prefix="/plans", tags=["plans"])
workouts_router = APIRouter(prefix="/workouts", tags=["workouts"])
feedback_router = APIRouter(prefix="/messages", tags=["feedback"])


def owned(model, row_id: int, user: User, db: Session):
    row = db.get(model, row_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return row


# ------------------------------------------------------------------ saved plans
@plans_router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def save_plan(body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = SavedPlan(user_id=user.id, title=body.title or body.plan.get("title") or "Workout plan", plan=body.plan)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@plans_router.get("", response_model=list[PlanOut])
def list_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(SavedPlan).where(SavedPlan.user_id == user.id).order_by(SavedPlan.id.desc())).all()


@plans_router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(owned(SavedPlan, plan_id, user, db))
    db.commit()


# ------------------------------------------------------------------ workout log
@workouts_router.post("", response_model=list[WorkoutOut], status_code=status.HTTP_201_CREATED)
def log_workouts(body: list[WorkoutIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Log one or more exercises (a whole plan day can be logged at once)."""
    if not 1 <= len(body) <= 30:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Log between 1 and 30 entries at a time")
    rows = [WorkoutLog(user_id=user.id, **w.model_dump()) for w in body]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


@workouts_router.get("", response_model=list[WorkoutOut])
def list_workouts(limit: int = Query(50, ge=1, le=500), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return db.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user.id)
                      .order_by(WorkoutLog.day.desc(), WorkoutLog.id.desc()).limit(limit)).all()


@workouts_router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(log_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(owned(WorkoutLog, log_id, user, db))
    db.commit()


@workouts_router.get("/stats", response_model=WorkoutStats)
def workout_stats(today: date | None = None, weeks: int = Query(8, ge=1, le=52),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Active days per week (Monday-based), current streak and most-logged exercises.
    `today` lets the browser pass its local date so streaks match the user's calendar."""
    today = today or date.today()
    logs = db.scalars(select(WorkoutLog).where(WorkoutLog.user_id == user.id)).all()
    days = {l.day for l in logs}
    monday = today - timedelta(days=today.weekday())
    week_starts = [monday - timedelta(weeks=i) for i in reversed(range(weeks))]
    per_week = [{"week_start": ws, "active_days": sum(1 for d in days if ws <= d < ws + timedelta(days=7))}
                for ws in week_starts]
    streak, d = 0, today if today in days else today - timedelta(days=1)
    while d in days:
        streak, d = streak + 1, d - timedelta(days=1)
    best: dict[str, float] = {}
    for l in logs:
        if l.weight_kg is not None:
            best[l.exercise] = max(best.get(l.exercise, 0.0), l.weight_kg)
    top = [{"exercise": name, "times": n, "best_weight_kg": best.get(name)}
           for name, n in Counter(l.exercise for l in logs).most_common(5)]
    return WorkoutStats(total_entries=len(logs), active_days=len(days), current_streak=streak,
                        this_week=per_week[-1]["active_days"], weeks=per_week, top_exercises=top)


# ------------------------------------------------------------------ feedback on answers
@feedback_router.put("/{message_id}/feedback", response_model=FeedbackOut)
def rate_message(message_id: int, body: FeedbackIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    msg = db.get(Message, message_id)
    conv = db.get(Conversation, msg.conversation_id) if msg else None
    if msg is None or conv is None or conv.user_id != user.id or msg.role != "assistant":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    fb = db.scalar(select(MessageFeedback).where(MessageFeedback.user_id == user.id,
                                                 MessageFeedback.message_id == message_id))
    if body.rating == 0:
        if fb:
            db.delete(fb)
            db.commit()
        return FeedbackOut(message_id=message_id, rating=0)
    if fb is None:
        fb = MessageFeedback(user_id=user.id, message_id=message_id, rating=body.rating)
        db.add(fb)
    else:
        fb.rating = body.rating
    db.commit()
    return FeedbackOut(message_id=message_id, rating=fb.rating)
