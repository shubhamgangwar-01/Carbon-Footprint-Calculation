from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import User
from app.services.auth import current_user, hash_password, make_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    name: str | None = None


def _out(u: User) -> dict:
    return {"token": make_token(u), "user": {"id": u.id, "email": u.email, "name": u.name, "role": u.role}}


@router.post("/guest")
def guest(db: Session = Depends(get_db)):
    u = User(role="guest", name="Guest")
    db.add(u)
    db.commit()
    return _out(u)


@router.post("/register")
def register(c: Credentials, db: Session = Depends(get_db)):
    email = c.email.lower().strip()
    if "@" not in email:
        raise HTTPException(422, "Invalid email address")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")
    u = User(email=email, name=c.name, password_hash=hash_password(c.password), role="user")
    db.add(u)
    db.commit()
    return _out(u)


@router.post("/upgrade")
def upgrade_guest(c: Credentials, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Turn the current guest account into a registered account, keeping its conferences."""
    if user.role != "guest":
        raise HTTPException(400, "Only guest accounts can be upgraded")
    email = c.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")
    user.email, user.name, user.password_hash, user.role = email, c.name, hash_password(c.password), "user"
    db.commit()
    return _out(user)


@router.post("/login")
def login(c: Credentials, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == c.email.lower().strip()).first()
    if not u or not verify_password(c.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return _out(u)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}
