from datetime import datetime, time, timedelta
from typing import Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.sessions.repository import (
    cancel_available_slots_for_session,
    cancel_confirmed_appointments_for_session,
    create_session,
    create_slot,
    get_doctor_by_id,
    get_session_by_id,
    get_session_by_unique_key,
    get_sessions_by_date,
    get_sessions_by_doctor,
    get_sessions_by_status,
    get_slots_by_session,
    list_sessions,
    update_slot_status,
    update_session,
)
from app.modules.sessions.schemas import SessionCreate, SessionUpdate

LUNCH_START = time(13, 0)
LUNCH_END = time(13, 30)


def _generate_slots(
    db: Session,
    *,
    doctor_id: UUID,
    session_id: int,
    session_date,
    start_time,
    end_time,
    slot_duration_mins: int,
) -> List[Dict]:
    slots = []
    current = datetime.combine(session_date, start_time)
    end_dt = datetime.combine(session_date, end_time)
    lunch_start_dt = datetime.combine(session_date, LUNCH_START)
    lunch_end_dt = datetime.combine(session_date, LUNCH_END)
    step = timedelta(minutes=slot_duration_mins)

    while current + step <= end_dt:
        slot_end = current + step
        overlaps_lunch = current < lunch_end_dt and slot_end > lunch_start_dt

        slots.append(
            create_slot(
                db,
                {
                    "doctor_id": str(doctor_id),
                    "session_id": session_id,
                    "slot_date": session_date,
                    "start_time": current.time(),
                    "end_time": slot_end.time(),
                    "status": "BLOCKED" if overlaps_lunch else "AVAILABLE",
                },
            )
        )
        current = slot_end

    return slots


def create_session_service(db: Session, payload: SessionCreate) -> Dict:
    doctor = get_doctor_by_id(db, payload.doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    if not doctor["is_active"]:
        raise ValueError("Cannot create a session for an inactive doctor")

    if payload.start_time >= payload.end_time:
        raise ValueError("Session start_time must be earlier than end_time")

    if get_session_by_unique_key(db, payload.doctor_id, payload.session_date, payload.session_name):
        raise ValueError("A session already exists for this doctor, date, and session name")

    try:
        session = create_session(
            db,
            {
                "doctor_id": str(payload.doctor_id),
                "session_date": payload.session_date,
                "session_name": payload.session_name,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "status": payload.status or "OPEN",
            },
        )

        slots = _generate_slots(
            db,
            doctor_id=payload.doctor_id,
            session_id=session["session_id"],
            session_date=payload.session_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            slot_duration_mins=int(doctor["slot_duration_mins"]),
        )

        db.commit()
        return {
            "session": session,
            "slots_generated": len(slots),
            "slots": slots,
        }
    except Exception as e:
        db.rollback()
        raise e


def get_session_service(db: Session, session_id: int) -> Dict:
    session = get_session_by_id(db, session_id)
    if not session:
        raise LookupError("Session not found")
    return session


def list_sessions_service(db: Session) -> List[Dict]:
    return list_sessions(db)


def get_sessions_by_doctor_service(db: Session, doctor_id: UUID) -> List[Dict]:
    return get_sessions_by_doctor(db, doctor_id)


def get_sessions_by_date_service(db: Session, session_date) -> List[Dict]:
    return get_sessions_by_date(db, session_date)


def get_sessions_by_status_service(db: Session, status: str) -> List[Dict]:
    return get_sessions_by_status(db, status)


def get_session_slots_service(db: Session, session_id: int) -> List[Dict]:
    session = get_session_by_id(db, session_id)
    if not session:
        raise LookupError("Session not found")
    return get_slots_by_session(db, session_id)


def update_session_service(db: Session, session_id: int, payload: SessionUpdate) -> Dict:
    existing = get_session_by_id(db, session_id)
    if not existing:
        raise LookupError("Session not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValueError("At least one field is required for update")

    merged = {
        "status": update_data.get("status", existing["status"]),
    }

    try:
        session = update_session(db, session_id, merged)
        if not session:
            raise LookupError("Session not found")

        cancelled_appointments = []
        cancelled_slots = []

        if merged["status"] == "CLOSED" and existing["status"] != "CLOSED":
            cancelled_appointments = cancel_confirmed_appointments_for_session(db, session_id)

            for appointment in cancelled_appointments:
                slot = update_slot_status(db, UUID(appointment["slot_id"]), "CANCELLED")
                if slot:
                    cancelled_slots.append(slot)

            cancelled_slots.extend(cancel_available_slots_for_session(db, session_id))

        db.commit()

        if merged["status"] == "CLOSED" and existing["status"] != "CLOSED":
            return {
                "session": session,
                "cancelled_appointments": len(cancelled_appointments),
                "cancelled_slots": len(cancelled_slots),
            }

        return session
    except Exception as e:
        db.rollback()
        raise e
