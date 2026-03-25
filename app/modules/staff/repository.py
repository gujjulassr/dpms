from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


def create_staff(db: Session, data: dict) -> dict:
    query = text("""
        INSERT INTO staff (full_name, email, phone, role)
        VALUES (:full_name, :email, :phone, :role)
        RETURNING *
    """)
    result = db.execute(query, data)
    return _serialize_row(result.mappings().one())


def get_staff_by_id(db: Session, staff_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM staff WHERE staff_id = :staff_id"),
        {"staff_id": staff_id}
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_staff_by_email(db: Session, email: str) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM staff WHERE email = :email"),
        {"email": email}
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_staff_by_phone(db: Session, phone: str) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM staff WHERE phone = :phone"),
        {"phone": phone}
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_staff_by_name(db: Session, name: str) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM staff WHERE full_name ILIKE :name ORDER BY created_at DESC"),
        {"name": f"%{name}%"}
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_staff_by_role(db: Session, role: str) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM staff WHERE role = :role AND is_active = TRUE ORDER BY full_name"),
        {"role": role.upper()}
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def list_staff(db: Session) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM staff ORDER BY created_at DESC")
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def update_staff(db: Session, staff_id: int, data: dict) -> Optional[Dict]:
    query = text("""
        UPDATE staff
        SET
            full_name  = :full_name,
            email      = :email,
            phone      = :phone,
            role       = :role,
            is_active  = :is_active,
            updated_at = NOW()
        WHERE staff_id = :staff_id
        RETURNING *
    """)
    result = db.execute(query, {"staff_id": staff_id, **data})
    row = result.mappings().first()
    return _serialize_row(row) if row else None
