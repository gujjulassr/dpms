from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


def get_doctor_by_id(db: Session, doctor_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE doctor_id = :doctor_id"),
        {"doctor_id": doctor_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def create_session(db: Session, data: dict) -> dict:
    query = text("""
        INSERT INTO sessions (
            doctor_id,
            session_date,
            session_name,
            start_time,
            end_time,
            status
        )
        VALUES (
            :doctor_id,
            :session_date,
            :session_name,
            :start_time,
            :end_time,
            :status
        )
        RETURNING *
    """)
    result = db.execute(query, data)
    return _serialize_row(result.mappings().one())


def get_session_by_id(db: Session, session_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM sessions WHERE session_id = :session_id"),
        {"session_id": session_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_session_by_unique_key(
    db: Session,
    doctor_id: int,
    session_date: date,
    session_name: str,
) -> Optional[Dict]:
    result = db.execute(
        text("""
            SELECT * FROM sessions
            WHERE doctor_id = :doctor_id
              AND session_date = :session_date
              AND session_name = :session_name
        """),
        {
            "doctor_id": doctor_id,
            "session_date": session_date,
            "session_name": session_name,
        },
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def list_sessions(db: Session) -> List[Dict]:
    result = db.execute(
        text("""
            SELECT
                s.*,
                d.full_name     AS doctor_name,
                d.specialization,
                d.is_active     AS doctor_is_active
            FROM sessions s
            JOIN doctors d ON d.doctor_id = s.doctor_id
            ORDER BY s.session_date DESC, s.start_time DESC
        """)
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_sessions_by_doctor(db: Session, doctor_id: int) -> List[Dict]:
    result = db.execute(
        text("""
            SELECT
                s.*,
                d.full_name     AS doctor_name,
                d.specialization,
                d.is_active     AS doctor_is_active
            FROM sessions s
            JOIN doctors d ON d.doctor_id = s.doctor_id
            WHERE s.doctor_id = :doctor_id
            ORDER BY s.session_date DESC, s.start_time DESC
        """),
        {"doctor_id": doctor_id},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_sessions_by_date(db: Session, session_date: date) -> List[Dict]:
    result = db.execute(
        text("""
            SELECT
                s.*,
                d.full_name     AS doctor_name,
                d.specialization,
                d.is_active     AS doctor_is_active
            FROM sessions s
            JOIN doctors d ON d.doctor_id = s.doctor_id
            WHERE s.session_date = :session_date
            ORDER BY s.start_time
        """),
        {"session_date": session_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_sessions_by_status(db: Session, status: str) -> List[Dict]:
    result = db.execute(
        text("""
            SELECT
                s.*,
                d.full_name     AS doctor_name,
                d.specialization,
                d.is_active     AS doctor_is_active
            FROM sessions s
            JOIN doctors d ON d.doctor_id = s.doctor_id
            WHERE s.status = :status
            ORDER BY s.session_date DESC, s.start_time DESC
        """),
        {"status": status},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def update_session(db: Session, session_id: int, data: dict) -> Optional[Dict]:
    result = db.execute(
        text("""
            UPDATE sessions
            SET
                status = :status,
                updated_at = NOW()
            WHERE session_id = :session_id
            RETURNING *
        """),
        {"session_id": session_id, **data},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def cancel_confirmed_appointments_for_session(db: Session, session_id: int) -> List[Dict]:
    """Cancel all CONFIRMED appointments in a session (used when closing a session)."""
    result = db.execute(
        text("""
            UPDATE appointments
            SET
                status = 'CANCELLED',
                cancelled_at = COALESCE(cancelled_at, NOW()),
                updated_at = NOW()
            WHERE session_id = :session_id
              AND status = 'CONFIRMED'
            RETURNING
                appointment_id,
                patient_id,
                doctor_id,
                session_id,
                start_time,
                end_time,
                status,
                cancelled_at,
                updated_at
        """),
        {"session_id": session_id},
    )
    return [_serialize_row(row) for row in result.mappings().all()]
