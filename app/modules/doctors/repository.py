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


def create_doctor(db: Session, data: dict) -> dict:
    query = text("""
        INSERT INTO doctors (full_name, specialization, email, phone, slot_duration_mins, max_patients_per_day)
        VALUES (:full_name, :specialization, :email, :phone, :slot_duration_mins, :max_patients_per_day)
        RETURNING *
    """)
    result = db.execute(query, data)
    return _serialize_row(result.mappings().one())


def get_doctor_by_id(db: Session, doctor_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE doctor_id = :doctor_id"),
        {"doctor_id": doctor_id}
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_doctor_by_email(db: Session, email: str) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE email = :email"),
        {"email": email}
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_doctor_by_phone(db: Session, phone: str) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE phone = :phone"),
        {"phone": phone}
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_doctors_by_name(db: Session, name: str) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE full_name ILIKE :name ORDER BY created_at DESC"),
        {"name": f"%{name}%"}
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_doctors_by_specialization(db: Session, specialization: str) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE specialization ILIKE :spec AND is_active = TRUE ORDER BY full_name"),
        {"spec": f"%{specialization}%"}
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def list_doctors(db: Session) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors ORDER BY created_at DESC")
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def update_doctor(db: Session, doctor_id: int, data: dict) -> Optional[Dict]:
    query = text("""
        UPDATE doctors
        SET
            full_name            = :full_name,
            specialization       = :specialization,
            email                = :email,
            phone                = :phone,
            slot_duration_mins   = :slot_duration_mins,
            max_patients_per_day = :max_patients_per_day,
            is_active            = :is_active,
            updated_at           = NOW()
        WHERE doctor_id = :doctor_id
        RETURNING *
    """)
    result = db.execute(query, {"doctor_id": doctor_id, **data})
    row = result.mappings().first()
    return _serialize_row(row) if row else None
