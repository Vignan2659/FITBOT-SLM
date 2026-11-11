"""Database tables: users, user_profiles, conversations, messages, exercise_metadata,
food_metadata, yoga_poses, revoked_tokens, saved_plans, workout_logs, message_feedback,
wearable_daily, wearable_workouts, wearable_imports."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fitness_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dietary_preference: Mapped[str | None] = mapped_column(String(30), nullable=True)
    equipment: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New chat")
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # dialogue state for follow-ups
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan",
                                                     order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))              # user | assistant
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # structured cards / plan
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ExerciseMetadata(Base):
    __tablename__ = "exercise_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    muscle_group: Mapped[str] = mapped_column(String(30), index=True)
    description: Mapped[str] = mapped_column(Text)
    target_muscles: Mapped[list] = mapped_column(JSON)
    secondary_muscles: Mapped[list] = mapped_column(JSON)
    equipment: Mapped[str] = mapped_column(String(60))
    equipment_raw: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    instructions: Mapped[list] = mapped_column(JSON)
    safety_tips: Mapped[list] = mapped_column(JSON)
    aliases: Mapped[list] = mapped_column(JSON)
    home_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    image_urls: Mapped[list] = mapped_column(JSON)
    image_license: Mapped[str] = mapped_column(String(120))
    source_id: Mapped[str] = mapped_column(String(120))


class FoodMetadata(Base):
    __tablename__ = "food_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    fdc_id: Mapped[int] = mapped_column(Integer, unique=True)
    usda_description: Mapped[str] = mapped_column(String(255))
    group: Mapped[str] = mapped_column(String(30), index=True)
    tags: Mapped[list] = mapped_column(JSON)
    aliases: Mapped[list] = mapped_column(JSON)
    per_100g: Mapped[dict] = mapped_column(JSON)
    portion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    highlights: Mapped[list] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(String(200))


class YogaPose(Base):
    """Yoga pose library (data/yoga/yoga_poses.json, re-synced on every start like the exercise and food tables).
    Filterable fields are columns; the full pose record (instructions, safety, photos and their credits) is kept in
    `details`."""
    __tablename__ = "yoga_poses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sanskrit: Mapped[str] = mapped_column(String(80))
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    kind: Mapped[str] = mapped_column(String(20))                 # pose | breathing | meditation
    phase: Mapped[str] = mapped_column(String(20))                # where it sits in a routine
    category: Mapped[list] = mapped_column(JSON)
    goals: Mapped[list] = mapped_column(JSON)
    body_areas: Mapped[list] = mapped_column(JSON)
    image_path: Mapped[str] = mapped_column(String(200))           # main photo
    image_urls: Mapped[list] = mapped_column(JSON)                  # all photos of the pose
    details: Mapped[dict] = mapped_column(JSON)


class RevokedToken(Base):
    """JWT ids revoked by /auth/logout (checked on every authenticated request)."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SavedPlan(Base):
    """A workout plan the user saved from a chat answer ("My workouts")."""
    __tablename__ = "saved_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    plan: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkoutLog(Base):
    """One logged exercise (or session) on a given day - drives the progress view."""
    __tablename__ = "workout_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    exercise: Mapped[str] = mapped_column(String(80))
    sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MessageFeedback(Base):
    """Thumbs up / down on an assistant answer (scripts/export_feedback.py exports them for review)."""
    __tablename__ = "message_feedback"
    __table_args__ = (UniqueConstraint("user_id", "message_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)      # +1 helpful, -1 not helpful
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WearableDaily(Base):
    """One day of fitness band data from one source (an imported export, manual entry). Several sources can cover
    the same day; they are merged when read (app.services.wearables.merge_sources)."""
    __tablename__ = "wearable_daily"
    __table_args__ = (UniqueConstraint("user_id", "day", "source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(20))               # apple, samsung, google, huawei, ..., manual
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    resting_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress: Mapped[float | None] = mapped_column(Float, nullable=True)      # 0-100, higher = more stress
    sleep_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    spo2: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WearableWorkout(Base):
    """A workout recorded by a band (imported) or by a live heart rate session in the browser."""
    __tablename__ = "wearable_workouts"
    __table_args__ = (UniqueConstraint("user_id", "start", "activity", "source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    start: Mapped[datetime] = mapped_column(DateTime, index=True)            # local wall clock time
    activity: Mapped[str] = mapped_column(String(60))
    minutes: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WearableImport(Base):
    """Log of imported export files (shown on the Bands page)."""
    __tablename__ = "wearable_imports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(160))
    days: Mapped[int] = mapped_column(Integer)
    workouts: Mapped[int] = mapped_column(Integer)
    first_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
