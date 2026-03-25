from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def _serialize_value(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


# ── helpers ────────────────────────────────────────────────────────────

def get_patient_by_id(db: Session, patient_id: UUID) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM patients WHERE patient_id = :patient_id"),
        {"patient_id": str(patient_id)},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_doctor_by_id(db: Session, doctor_id: UUID) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE doctor_id = :doctor_id"),
        {"doctor_id": str(doctor_id)},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_session_by_id(db: Session, session_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM sessions WHERE session_id = :session_id"),
        {"session_id": session_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_first_available_slot_for_session(db: Session, session_id: int) -> Optional[Dict]:
    result = db.execute(
        text("""
            SELECT * FROM slots
            WHERE session_id = :session_id
              AND status = 'AVAILABLE'
            ORDER BY start_time
            LIMIT 1
        """),
        {"session_id": session_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


# ── waitlist CRUD ──────────────────────────────────────────────────────

def create_waitlist(db: Session, data: dict) -> Dict:
    result = db.execute(
        text("""
            INSERT INTO waitlist (
                patient_id,
                doctor_id,
                session_id,
                waitlist_date,
                priority,
                is_emergency,
                emergency_declared_by,
                emergency_reason
            )
            VALUES (
                :patient_id,
                :doctor_id,
                :session_id,
                :waitlist_date,
                :priority,
                :is_emergency,
                :emergency_declared_by,
                :emergency_reason
            )
            RETURNING *
        """),
        data,
    )
    return _serialize_row(result.mappings().one())


def get_waitlist_by_id(db: Session, waitlist_id: UUID) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM waitlist WHERE waitlist_id = :waitlist_id"),
        {"waitlist_id": str(waitlist_id)},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_waitlist_by_patient(db: Session, patient_id: UUID) -> List[Dict]:
    result = db.execute(
        text("""
            SELECT * FROM waitlist
            WHERE patient_id = :patient_id
            ORDER BY joined_at DESC
        """),
        {"patient_id": str(patient_id)},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_waitlist_by_session(db: Session, session_id: int) -> List[Dict]:
    """All waitlist entries for a session, ordered by priority then join time."""
    result = db.execute(
        text("""
            SELECT * FROM waitlist
            WHERE session_id = :session_id
            ORDER BY priority ASC, joined_at ASC
        """),
        {"session_id": session_id},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_next_in_queue(db: Session, session_id: int) -> Optional[Dict]:
    """
    Returns the next WAITING patient for a session.
    Emergency (priority=1) patients come first, then by join time.
    """
    result = db.execute(
        text("""
            SELECT * FROM waitlist
            WHERE session_id = :session_id
              AND status = 'WAITING'
            ORDER BY priority ASC, joined_at ASC
            LIMIT 1
        """),
        {"session_id": session_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def list_waitlist(db: Session) -> List[Dict]:
    result = db.execute(
        text("SELECT * FROM waitlist ORDER BY waitlist_date DESC, joined_at DESC")
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def update_waitlist(db: Session, waitlist_id: UUID, data: dict) -> Optional[Dict]:
    result = db.execute(
        text("""
            UPDATE waitlist
            SET
                status              = :status,
                notified_at         = :notified_at,
                response_deadline   = :response_deadline,
                emergency_verified_at = :emergency_verified_at,
                updated_at          = NOW()
            WHERE waitlist_id = :waitlist_id
            RETURNING *
        """),
        {"waitlist_id": str(waitlist_id), **data},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def already_on_waitlist(db: Session, patient_id: UUID, session_id: int) -> bool:
    """Check if patient is already WAITING for this session."""
    result = db.execute(
        text("""
            SELECT 1 FROM waitlist
            WHERE patient_id = :patient_id
              AND session_id = :session_id
              AND status = 'WAITING'
            LIMIT 1
        """),
        {"patient_id": str(patient_id), "session_id": session_id},
    )
    return result.first() is not None
