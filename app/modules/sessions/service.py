from datetime import date, timedelta, time
from typing import Dict, List

from sqlalchemy.orm import Session

from app.modules.sessions.repository import (
    cancel_confirmed_appointments_for_session,
    create_session,
    get_doctor_by_id,
    get_session_by_id,
    get_session_by_unique_key,
    get_sessions_by_date,
    get_sessions_by_doctor,
    get_sessions_by_status,
    list_sessions,
    update_session,
)
from app.modules.sessions.schemas import SessionCreate, SessionUpdate


def create_session_service(db: Session, payload: SessionCreate) -> Dict:
    """
    Create a doctor session. No more slot generation —
    just creates the session row. Availability is calculated on-the-fly.
    """
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
                "doctor_id": payload.doctor_id,
                "session_date": payload.session_date,
                "session_name": payload.session_name,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "status": payload.status or "OPEN",
            },
        )

        db.commit()
        return {
            "session": session,
            "message": "Session created. Availability is calculated on-the-fly when patients book.",
        }
    except Exception as e:
        db.rollback()
        raise e


def create_doctor_availability_range_service(
    db: Session,
    *,
    doctor_id: int,
    start_date: date,
    days: int,
    include_morning: bool = True,
    include_afternoon: bool = True,
) -> Dict:
    """
    Create sessions for a doctor over a date range.
    No more slot generation — just creates session rows.
    """
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    if not doctor["is_active"]:
        raise ValueError("Cannot create availability for an inactive doctor")

    if days <= 0:
        raise ValueError("Days must be greater than 0")

    if not include_morning and not include_afternoon:
        raise ValueError("At least one session range must be selected")

    session_templates = []
    if include_morning:
        session_templates.append(("MORNING", time(9, 0), time(13, 0)))
    if include_afternoon:
        session_templates.append(("AFTERNOON", time(14, 0), time(17, 0)))

    created_sessions = []
    skipped_existing = []

    try:
        for offset in range(days):
            session_date = start_date + timedelta(days=offset)

            for session_name, start_time, end_time in session_templates:
                existing = get_session_by_unique_key(db, doctor_id, session_date, session_name)
                if existing:
                    skipped_existing.append(existing)
                    continue

                session = create_session(
                    db,
                    {
                        "doctor_id": doctor_id,
                        "session_date": session_date,
                        "session_name": session_name,
                        "start_time": start_time,
                        "end_time": end_time,
                        "status": "OPEN",
                    },
                )

                created_sessions.append(
                    {
                        "session_id": session["session_id"],
                        "session_date": session["session_date"],
                        "session_name": session["session_name"],
                        "start_time": session["start_time"],
                        "end_time": session["end_time"],
                    }
                )

        db.commit()
        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor["full_name"],
            "specialization": doctor["specialization"],
            "start_date": start_date.isoformat(),
            "days_requested": days,
            "days_covered_until": (start_date + timedelta(days=days - 1)).isoformat(),
            "sessions_created": len(created_sessions),
            "sessions_skipped_existing": len(skipped_existing),
            "created_sessions": created_sessions,
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


def get_sessions_by_doctor_service(db: Session, doctor_id: int) -> List[Dict]:
    return get_sessions_by_doctor(db, doctor_id)


def get_sessions_by_date_service(db: Session, session_date) -> List[Dict]:
    return get_sessions_by_date(db, session_date)


def get_sessions_by_status_service(db: Session, status: str) -> List[Dict]:
    return get_sessions_by_status(db, status)


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

        if merged["status"] == "CLOSED" and existing["status"] != "CLOSED":
            cancelled_appointments = cancel_confirmed_appointments_for_session(db, session_id)

        db.commit()

        if merged["status"] == "CLOSED" and existing["status"] != "CLOSED":
            return {
                "session": session,
                "cancelled_appointments": len(cancelled_appointments),
            }

        return session
    except Exception as e:
        db.rollback()
        raise e
