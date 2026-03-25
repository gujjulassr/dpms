from datetime import date, datetime, time
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
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


APPOINTMENT_SELECT = """
    SELECT
        a.appointment_id,
        a.slot_id,
        a.patient_id,
        p.full_name AS patient_name,
        p.email AS patient_email,
        a.doctor_id,
        d.full_name AS doctor_name,
        d.specialization AS doctor_specialization,
        s.session_id,
        s.slot_date,
        s.start_time,
        s.end_time,
        s.status AS slot_status,
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
    JOIN slots s ON s.slot_id = a.slot_id
"""


def create_appointment(db: Session, data: dict) -> dict:
    query = text("""
        INSERT INTO appointments (
            slot_id,
            patient_id,
            doctor_id,
            status
        )
        VALUES (
            :slot_id,
            :patient_id,
            :doctor_id,
            :status
        )
        RETURNING *
    """)
    result = db.execute(query, data)
    created = _serialize_row(result.mappings().one())
    return get_appointment_by_id(db, UUID(created["appointment_id"]))


def get_appointment_by_id(db: Session, appointment_id: UUID) -> Optional[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.appointment_id = :appointment_id"),
        {"appointment_id": str(appointment_id)},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_appointment_by_slot_id(db: Session, slot_id: UUID) -> Optional[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.slot_id = :slot_id"),
        {"slot_id": str(slot_id)},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def list_appointments(db: Session) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} ORDER BY s.slot_date DESC, s.start_time DESC")
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_patient(db: Session, patient_id: UUID) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.patient_id = :patient_id ORDER BY s.slot_date DESC, s.start_time DESC"),
        {"patient_id": str(patient_id)},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_doctor(db: Session, doctor_id: UUID) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.doctor_id = :doctor_id ORDER BY s.slot_date DESC, s.start_time DESC"),
        {"doctor_id": str(doctor_id)},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_status(db: Session, status: str) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE a.status = :status ORDER BY s.slot_date DESC, s.start_time DESC"),
        {"status": status},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_appointments_by_date(db: Session, appointment_date: date) -> List[Dict]:
    result = db.execute(
        text(f"{APPOINTMENT_SELECT} WHERE s.slot_date = :appointment_date ORDER BY s.start_time"),
        {"appointment_date": appointment_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_active_appointments_by_date(db: Session, appointment_date: date) -> List[Dict]:
    result = db.execute(
        text(
            f"{APPOINTMENT_SELECT} "
            "WHERE s.slot_date = :appointment_date "
            "AND a.status = 'CONFIRMED' "
            "AND (s.slot_date > CURRENT_DATE OR (s.slot_date = CURRENT_DATE AND s.start_time >= CURRENT_TIME)) "
            "ORDER BY s.start_time"
        ),
        {"appointment_date": appointment_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


def get_upcoming_active_appointments(db: Session) -> List[Dict]:
    result = db.execute(
        text(
            f"{APPOINTMENT_SELECT} "
            "WHERE a.status = 'CONFIRMED' "
            "AND (s.slot_date > CURRENT_DATE OR (s.slot_date = CURRENT_DATE AND s.start_time >= CURRENT_TIME)) "
            "ORDER BY s.slot_date, s.start_time"
        )
    )
    return [_serialize_row(row) for row in result.mappings().all()]


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


def get_slot_by_id(db: Session, slot_id: UUID) -> Optional[Dict]:
    result = db.execute(
        text("SELECT * FROM slots WHERE slot_id = :slot_id"),
        {"slot_id": str(slot_id)},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def update_slot_status(db: Session, slot_id: UUID, status: str) -> Optional[Dict]:
    result = db.execute(
        text("""
            UPDATE slots
            SET
                status = :status,
                updated_at = NOW()
            WHERE slot_id = :slot_id
            RETURNING *
        """),
        {"slot_id": str(slot_id), "status": status},
    )
    row = result.mappings().first()
    return _serialize_row(row) if row else None


def get_slots_by_doctor_and_date(db: Session, doctor_id: UUID, slot_date: date) -> List[Dict]:
    result = db.execute(
        text("""
            SELECT
                sl.*,
                se.session_name
            FROM slots sl
            JOIN sessions se ON se.session_id = sl.session_id
            WHERE sl.doctor_id = :doctor_id
              AND sl.slot_date = :slot_date
            ORDER BY sl.start_time
        """),
        {"doctor_id": str(doctor_id), "slot_date": slot_date},
    )
    return [_serialize_row(row) for row in result.mappings().all()]


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


def update_appointment(db: Session, appointment_id: UUID, data: dict) -> Optional[Dict]:
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
    result = db.execute(query, {"appointment_id": str(appointment_id), **data})
    row = result.mappings().first()
    if not row:
        return None
    updated = _serialize_row(row)
    return get_appointment_by_id(db, UUID(updated["appointment_id"]))
