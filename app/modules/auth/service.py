"""
Auth service — login, JWT creation/verification, user registration.

Dependencies (add to requirements.txt):
    PyJWT>=2.8.0
    passlib[bcrypt]>=1.7.4
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.modules.auth.repository import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_last_login,
)
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserInfo

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY    = os.getenv("JWT_SECRET_KEY", "dpms-secret-change-in-production")
ALGORITHM     = "HS256"
TOKEN_EXPIRE_HOURS = 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    data["iat"] = datetime.utcnow()
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Returns decoded payload or None if invalid/expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# ── Services ──────────────────────────────────────────────────────────────────

def login_service(db: Session, payload: LoginRequest) -> TokenResponse:
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise ValueError("Invalid username or password")

    token = create_access_token({
        "user_id":      str(user["user_id"]),
        "username":     user["username"],
        "role":         user["role"],
        "display_name": user["display_name"],
        "staff_id":     str(user["staff_id"])   if user.get("staff_id")   else None,
        "patient_id":   str(user["patient_id"]) if user.get("patient_id") else None,
        "doctor_id":    str(user["doctor_id"])  if user.get("doctor_id")  else None,
    })

    update_last_login(db, str(user["user_id"]))
    db.commit()

    return TokenResponse(
        access_token=token,
        role=user["role"],
        username=user["username"],
        user_id=str(user["user_id"]),
        display_name=user["display_name"],
    )


def get_current_user_service(db: Session, token: str) -> UserInfo:
    payload = decode_token(token)
    if not payload:
        raise PermissionError("Invalid or expired token")

    user = get_user_by_id(db, payload["user_id"])
    if not user or not user["is_active"]:
        raise PermissionError("User not found or inactive")

    return UserInfo(
        user_id=str(user["user_id"]),
        username=user["username"],
        role=user["role"],
        display_name=user["display_name"],
        staff_id=str(user["staff_id"])   if user.get("staff_id")   else None,
        patient_id=str(user["patient_id"]) if user.get("patient_id") else None,
        doctor_id=str(user["doctor_id"])  if user.get("doctor_id")  else None,
        is_active=user["is_active"],
    )


def register_user_service(db: Session, payload: UserCreate) -> dict:
    """ADMIN-only: create a new login account."""
    existing = get_user_by_username(db, payload.username)
    if existing:
        raise ValueError(f"Username '{payload.username}' already exists")

    data = {
        "username":      payload.username,
        "password_hash": hash_password(payload.password),
        "role":          payload.role,
        "display_name":  payload.display_name,
        "staff_id":      payload.staff_id,
        "patient_id":    payload.patient_id,
        "doctor_id":     payload.doctor_id,
    }
    user = create_user(db, data)
    db.commit()
    return user


def list_users_service(db: Session) -> list:
    return list_users(db)
