"""Minimal, dependency-free authentication.

* Passwords: PBKDF2-HMAC-SHA256 (600k iterations, OWASP 2023 guidance) with per-user salt.
* Tokens: HMAC-SHA256-signed `user_id.role.expiry` strings keyed by SECRET_KEY.
* Guests: a guest account is created on demand so the calculator works without
  sign-up; guests can later register to keep their conferences.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db
from app.models import User

ITER = 600_000


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2_sha256${ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, it, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except ValueError:
        return False


def make_token(user: User) -> str:
    exp = int(time.time()) + get_settings().token_ttl_hours * 3600
    payload = f"{user.id}.{user.role}.{exp}"
    sig = hmac.new(get_settings().secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token: str) -> Optional[int]:
    try:
        uid, role, exp, sig = token.split(".")
    except ValueError:
        return None
    payload = f"{uid}.{role}.{exp}"
    good = hmac.new(get_settings().secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or int(exp) < time.time():
        return None
    return int(uid)


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    uid = parse_token(authorization.split(" ", 1)[1].strip())
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return user


def ensure_admin(db: Session):
    s = get_settings()
    if not (s.admin_email and s.admin_password):
        return
    u = db.query(User).filter(User.email == s.admin_email.lower()).first()
    if not u:
        db.add(User(email=s.admin_email.lower(), name="Administrator", password_hash=hash_password(s.admin_password), role="admin"))
        db.commit()
    elif u.role != "admin":
        u.role = "admin"
        db.commit()
