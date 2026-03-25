from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


# ── Base SELECT ───────────────────────────────────────────────────────
# No more JOIN with slots — time data lives on the appointment itself.

APPOINTMENT_SELECT = """
    SELECT
        a.appointment_id,
        a.session_id,
        a.patient_id,
        p.full_name AS patient_name,
        p.email AS patient_email,
        a.doctor_id,
        d.full_name AS doctor_name,
        d.specialization AS doctor_specialization,
        a.appointment_date,
        a.start_time,
        a.end_time,
        a.booked_at,
        a.status,
        a.reminder_24hr_sent,
        a.reminder_2hr_sent,
        a.confirmed_at,
        a.cancelled_at,
        a.updated_at
    FROM appointments a
    JOIN patients p ON p.patient_id = a.patient_id
    JOIN doctors d ON d.doctor_id = a.doctor_id
"""


# ── Create ────────────────────────────────────────────────────────────

def create_appointment(db: Session, data: dict) -> dict:
    query = text("""
        INSERT INTO appointments (
            session_id,
            patient_id,
            doctor_id,
            appointment_date,
            start_time,
            end_time,
            status
        )
        VALUES (
            :session_id,
            :patient_id,
            :doctor_id,
            :appointment_date,
            :start_time,
            :end_time,
            :status
        )
        RETURNING *
    """)
    result = db.execute(query, data)
    created = _serialize_row(result.mappings().one())
    return get_appointment_by_id(db, created["appointment_id"])


# ── Read ──────────────────────────────────────────────────────────────

def get_appointment_by_id(db: Session, appointment_id: int) -> Optional[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.appointment_id = :appointment_id"),
        {"appointment_id": appointment_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def list_appointments(db: Session) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} ORDER BY a.appointment_date DESC, a.start_time DESC")
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_patient(db: Session, patient_id: int) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.patient_id = :patient_id ORDER BY a.appointment_date DESC, a.start_time DESC"),
        {"patient_id": patient_id},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_doctor(db: Session, doctor_id: int) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.doctor_id = :doctor_id ORDER BY a.appointment_date DESC, a.start_time DESC"),
        {"doctor_id": doctor_id},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_status(db: Session, status: str) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.status = :status ORDER BY a.appointment_date DESC, a.start_time DESC"),
        {"status": status},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_date(db: Session, appointment_date: date) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.appointment_date = :appointment_date ORDER BY a.start_time"),
        {"appointment_date": appointment_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_active_appointments_by_date(
    db: Session, appointment_date: date, patient_id: Optional[int] = None
) -> List[Dict]:
    extra = " AND a.patient_id = :patient_id" if patient_id else ""
    params: dict = {"appointment_date": appointment_date}
    if patient_id:
        params["patient_id"] = patient_id
    result = db.execute(
        text(
            f"{APPOINTMENT_SELECT} "
            "WHERE a.appointment_date = :appointment_date "
            "AND a.status = 'CONFIRMED' "
            "AND (a.appointment_date > CURRENT_DATE OR (a.appointment_date = CURRENT_DATE AND a.start_time >= CURRENT_TIME)) "
            f"{extra} "
            "ORDER BY a.start_time"
        ),
        params,
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_upcoming_active_appointments(
    db: Session, patient_id: Optional[int] = None
) -> List[Dict]:
    extra = " AND a.patient_id = :patient_id" if patient_id else ""
    params: dict = {}
    if patient_id:
        params["patient_id"] = patient_id
    result = db.execute(
        text(
            f"{APPOINTMENT_SELECT} "
            "WHERE a.status = 'CONFIRMED' "
            "AND (a.appointment_date > CURRENT_DATE OR (a.appointment_date = CURRENT_DATE AND a.start_time >= CURRENT_TIME)) "
            f"{extra} "
            "ORDER BY a.appointment_date, a.start_time"
        ),
        params,
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_active_appointment_by_patient_and_doctor(
    db: Session,
    patient_id: int,
    doctor_id: int,
) -> Optional[Dict]:
    result = db.execute(
        text(
            f"{APPOINTMENT_SELECT} "
            "WHERE a.patient_id = :patient_id "
            "AND a.doctor_id = :doctor_id "
            "AND a.status = 'CONFIRMED' "
            "AND (a.appointment_date > CURRENT_DATE OR (a.appointment_date = CURRENT_DATE AND a.start_time >= CURRENT_TIME)) "
            "ORDER BY a.appointment_date, a.start_time "
            "LIMIT 1"
        ),
        {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
        },
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


# ── Availability queries ──────────────────────────────────────────────

def get_confirmed_appointments_for_session(db: Session, session_id: int) -> List[Dict]:
    """Get all CONFIRMED appointments for a session (used for availability calc)."""
    result = db.execute(
        text("""
            SELECT appointment_id, start_time, end_time
            FROM appointments
            WHERE session_id = :session_id
              AND status = 'CONFIRMED'
            ORDER BY start_time
        """),
        {"session_id": session_id},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_confirmed_appointments_by_doctor_and_date(
    db: Session, doctor_id: int, appointment_date: date
) -> List[Dict]:
    """All CONFIRMED appointments for a doctor on a date (across all sessions)."""
    result = db.execute(
        text("""
            SELECT a.appointment_id, a.session_id, a.start_time, a.end_time
            FROM appointments a
            WHERE a.doctor_id = :doctor_id
              AND a.appointment_date = :appointment_date
              AND a.status = 'CONFIRMED'
            ORDER BY a.start_time
        """),
        {"doctor_id": doctor_id, "appointment_date": appointment_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_earliest_available_session_date(
    db: Session, doctor_id: int, start_date: date
) -> Optional[Dict]:
    """
    Find the earliest session from start_date onward that has
    at least one session in OPEN status for this doctor.
    Returns the session dict or None.
    """
    result = db.execute(
        text("""
            SELECT *
            FROM sessions
            WHERE doctor_id = :doctor_id
              AND session_date >= :start_date
              AND status = 'OPEN'
            ORDER BY session_date, start_time
        """),
        {"doctor_id": doctor_id, "start_date": start_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


# ── Lookup helpers ────────────────────────────────────────────────────

def get_patient_by_id(db: Session, patient_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM patients WHERE patient_id = :patient_id"),
        {"patient_id": patient_id},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_doctor_by_id(db: Session, doctor_id: int) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM doctors WHERE doctor_id = :doctor_id"),
        {"doctor_id": doctor_id},
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


def get_sessions_by_doctor_and_date(db: Session, doctor_id: int, appt_date: date) -> List[Dict]:
    """Get all OPEN sessions for a doctor on a specific date."""
    result = db.execute(
        text("""
            SELECT * FROM sessions
            WHERE doctor_id = :doctor_id
              AND session_date = :appt_date
              AND status = 'OPEN'
            ORDER BY start_time
        """),
        {"doctor_id": doctor_id, "appt_date": appt_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


# ── Cancellation log ─────────────────────────────────────────────────

def create_cancellation_log(db: Session, data: dict) -> dict:
    result = db.execute(
        text("""
            INSERT INTO cancellation_log (
                appointment_id,
                patient_id,
                is_late_cancellation,
                cancelled_by
            )
            VALUES (
                :appointment_id,
                :patient_id,
                :is_late_cancellation,
                :cancelled_by
            )
            RETURNING *
        """),
        data,
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else {}


# ── Update ────────────────────────────────────────────────────────────

def update_appointment(db: Session, appointment_id: int, data: dict) -> Optional[Dict]:
    query = text("""
        UPDATE appointments
        SET
            status             = :status,
            reminder_24hr_sent = :reminder_24hr_sent,
            reminder_2hr_sent  = :reminder_2hr_sent,
            confirmed_at       = :confirmed_at,
            cancelled_at       = :cancelled_at,
            updated_at         = NOW()
        WHERE appointment_id = :appointment_id
        RETURNING *
    """)
    result = db.execute(query, {"appointment_id": appointment_id, **data})
    row = result.mappings().first()
    if not row:
        return None
    updated = _serialize_row(row)
    return get_appointment_by_id(db, updated["appointment_id"])


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
