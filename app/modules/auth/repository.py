from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text


def _row(row) -> Optional[dict]:
    return dict(row) if row else None


def get_user_by_username(db: Session, username: str) -> Optional[dict]:
    row = db.execute(
        text("SELECT * FROM users WHERE username = :u AND is_active = TRUE"),
        {"u": username},
    ).mappings().first()
    return _row(row)


def get_user_by_id(db: Session, user_id: str) -> Optional[dict]:
    row = db.execute(
        text("SELECT * FROM users WHERE user_id = :id"),
        {"id": user_id},
    ).mappings().first()
    return _row(row)


def create_user(db: Session, data: dict) -> dict:
    row = db.execute(
        text("""
            INSERT INTO users
                (username, password_hash, role, display_name,
                 staff_id, patient_id, doctor_id)
            VALUES
                (:username, :password_hash, :role, :display_name,
                 :staff_id, :patient_id, :doctor_id)
            RETURNING *
        """),
        data,
    ).mappings().one()
    return dict(row)


def update_last_login(db: Session, user_id: str) -> None:
    db.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE user_id = :id"),
        {"id": user_id},
    )


def list_users(db: Session) -> list:
    rows = db.execute(
        text("""
            SELECT user_id, username, role, display_name,
                   is_active, last_login_at, created_at
            FROM   users
            ORDER  BY created_at
        """)
    ).mappings().all()
    return [dict(r) for r in rows]
