"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileIn(BaseModel):
    age: int | None = Field(default=None, ge=13, le=100)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    weight_kg: float | None = Field(default=None, ge=30, le=300)
    fitness_level: Literal["beginner", "intermediate", "advanced"] | None = None
    goal: Literal["weight_loss", "muscle_gain", "strength", "endurance", "general_fitness"] | None = None
    dietary_preference: Literal["none", "vegetarian", "vegan", "non_vegetarian"] | None = None
    equipment: list[str] | None = None
    location: Literal["home", "gym", "outdoors", "mixed"] | None = None


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    created_at: datetime
    profile: ProfileOut | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    intent: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message: str | None = None


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None

    @field_validator("message")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class ChatOut(BaseModel):
    conversation_id: int
    conversation_title: str
    message_id: int
    answer: str
    category: str
    intent: str
    intent_confidence: float
    is_followup: bool = False
    exercises: list[dict[str, Any]] = []
    foods: list[dict[str, Any]] = []
    workout_plan: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = []
    safety: dict[str, Any] | None = None
    disclaimer: str
    model: dict[str, Any] = {}
