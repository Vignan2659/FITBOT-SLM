"""/conversations endpoints – users can only access their own conversations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ConversationCreate, ConversationDetail, ConversationOut, MessageOut
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Conversation, MessageFeedback, User

router = APIRouter(prefix="/conversations", tags=["conversations"])


def owned_conversation(conv_id: int, user: User, db: Session) -> Conversation:
    conv = db.get(Conversation, conv_id)
    # 404 (not 403) so other users' conversation ids are not revealed
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


def summary(conv: Conversation) -> ConversationOut:
    last = conv.messages[-1].content if conv.messages else None
    return ConversationOut(id=conv.id, title=conv.title, created_at=conv.created_at, updated_at=conv.updated_at,
                           message_count=len(conv.messages), last_message=(last[:120] if last else None))


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(body: ConversationCreate | None = None, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    conv = Conversation(user_id=user.id, title=(body.title if body and body.title else "New chat"), state={})
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return summary(conv)


@router.get("", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                       .order_by(Conversation.updated_at.desc(), Conversation.id.desc())).all()
    return [summary(c) for c in convs]


@router.get("/{conv_id}", response_model=ConversationDetail)
def get_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = owned_conversation(conv_id, user, db)
    base = summary(conv)
    ratings = dict(db.execute(select(MessageFeedback.message_id, MessageFeedback.rating)
                              .where(MessageFeedback.user_id == user.id,
                                     MessageFeedback.message_id.in_([m.id for m in conv.messages]))).all())
    messages = [MessageOut.model_validate(m).model_copy(update={"feedback": ratings.get(m.id, 0)})
                for m in conv.messages]
    return ConversationDetail(**base.model_dump(), messages=messages)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = owned_conversation(conv_id, user, db)
    db.delete(conv)
    db.commit()
