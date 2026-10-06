"""POST /chat – runs the FitBot pipeline and stores both messages."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.conversations import owned_conversation
from app.api.schemas import ChatIn, ChatOut
from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Conversation, Message, User
from app.services.safety import DISCLAIMER

router = APIRouter(tags=["chat"])

_recent: dict[int, deque] = defaultdict(deque)
_lock = threading.Lock()


def check_rate(user_id: int) -> None:
    """Sliding one-minute window per user, so one account cannot monopolise a shared CPU."""
    limit = get_settings().chat_rate_per_min
    if limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        q = _recent[user_id]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                f"Too many messages - please wait a moment (limit {limit} per minute)")
        q.append(now)


def make_title(text: str) -> str:
    t = " ".join(text.split())
    return t if len(t) <= 48 else t[:45].rsplit(" ", 1)[0] + "..."


def profile_dict(user: User) -> dict | None:
    p = user.profile
    if not p:
        return None
    return {"age": p.age, "fitness_level": p.fitness_level, "goal": p.goal, "equipment": p.equipment or [],
            "location": p.location,
            "dietary_preference": None if p.dietary_preference in (None, "none") else p.dietary_preference}


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check_rate(user.id)
    engine = getattr(request.app.state, "chat_engine", None)
    if engine is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "FitBot model is still loading, try again shortly")

    if body.conversation_id is not None:
        conv = owned_conversation(body.conversation_id, user, db)
    else:
        conv = Conversation(user_id=user.id, title="New chat", state={})
        db.add(conv)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in conv.messages]
    result, new_state = engine.respond(body.message, history, conv.state or {}, profile_dict(user))

    if conv.title == "New chat" and not conv.messages:
        conv.title = make_title(body.message)
    db.add(Message(conversation_id=conv.id, role="user", content=body.message, intent=result["intent"]))
    payload = {k: result.get(k) for k in ("exercises", "foods", "workout_plan", "sources", "safety", "category",
                                          "intent_confidence", "is_followup", "model")}
    bot = Message(conversation_id=conv.id, role="assistant", content=result["answer"], intent=result["intent"],
                  payload=payload)
    db.add(bot)
    conv.state = new_state
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bot)

    return ChatOut(conversation_id=conv.id, conversation_title=conv.title, message_id=bot.id,
                   answer=result["answer"], category=result["category"], intent=result["intent"],
                   intent_confidence=result["intent_confidence"], is_followup=result["is_followup"],
                   exercises=result["exercises"], foods=result["foods"], workout_plan=result["workout_plan"],
                   sources=result["sources"], safety=result["safety"], disclaimer=DISCLAIMER, model=result["model"])
