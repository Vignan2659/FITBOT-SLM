"""/auth endpoints: register, login, me, logout, profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, ProfileIn, ProfileOut, RegisterIn, TokenOut, UserOut
from app.core.security import (create_access_token, current_token_payload, get_current_user, hash_password,
                               revoke, verify_password)
from app.db.database import get_db
from app.db.models import User, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    token, exp = create_access_token(user.id)
    return TokenOut(access_token=token, expires_at=exp, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    user.profile = UserProfile()
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(payload: dict = Depends(current_token_payload), db: Session = Depends(get_db)):
    revoke(db, payload)
    return {"detail": "Logged out"}


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.profile is None:
        user.profile = UserProfile()
        db.commit()
    return user.profile


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.profile is None:
        user.profile = UserProfile()
    for k, v in body.model_dump().items():
        setattr(user.profile, k, v)
    db.commit()
    db.refresh(user.profile)
    return user.profile
