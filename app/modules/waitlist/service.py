from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session

from app.modules.waitlist.repository import (
    already_on_waitlist,
    create_waitlist,
    get_doctor_by_id,
    get_next_in_queue,
    get_patient_by_id,
    get_session_by_id,
    get_waitlist_by_id,
    get_waitlist_by_patient,
    get_waitlist_by_session,
    list_waitlist,
    update_waitlist,
)
from app.modules.waitlist.schemas import WaitlistCreate, WaitlistUpdate


def join_waitlist_service(db: Session, payload: WaitlistCreate) -> Dict:
    patient = get_patient_by_id(db, payload.patient_id)
    if not patient:
        raise LookupError("Patient not found")

    doctor = get_doctor_by_id(db, payload.doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    session = get_session_by_id(db, payload.session_id)
    if not session:
        raise LookupError("Session not found")

    if session["doctor_id"] != payload.doctor_id:
        raise ValueError("Session does not belong to the given doctor")

    if already_on_waitlist(db, payload.patient_id, payload.session_id):
        raise ValueError(
            f"{patient['full_name']} is already on the waitlist for this session."
        )

    # Check if there's actually a free time window — no need to waitlist if available
    from app.modules.appointments.repository import get_confirmed_appointments_for_session
    from app.utils.availability import has_any_availability

    booked = get_confirmed_appointments_for_session(db, payload.session_id)
    if has_any_availability(
        session_start=session["start_time"],
        session_end=session["end_time"],
        slot_duration_mins=int(doctor["slot_duration_mins"]),
        booked_appointments=booked,
    ):
        raise ValueError(
            "There are still available times in this session. "
            "Please book directly instead of joining the waitlist."
        )

    try:
        entry = create_waitlist(
            db,
            {
                "patient_id": payload.patient_id,
                "doctor_id": payload.doctor_id,
                "session_id": payload.session_id,
                "waitlist_date": payload.waitlist_date,
                "priority": payload.priority,
                "is_emergency": payload.is_emergency,
                "emergency_declared_by": payload.emergency_declared_by,
                "emergency_reason": payload.emergency_reason,
            },
        )
        db.commit()
        return entry
    except Exception as e:
        db.rollback()
        raise e


def leave_waitlist_service(db: Session, waitlist_id: int) -> Dict:
    entry = get_waitlist_by_id(db, waitlist_id)
    if not entry:
        raise LookupError("Waitlist entry not found")

    if entry["status"] in ("CONFIRMED", "CANCELLED", "EXPIRED"):
        raise ValueError(f"Cannot cancel a waitlist entry with status {entry['status']}")

    merged = {
        "status": "CANCELLED",
        "notified_at": entry.get("notified_at"),
        "response_deadline": entry.get("response_deadline"),
        "emergency_verified_at": entry.get("emergency_verified_at"),
    }
    try:
        updated = update_waitlist(db, waitlist_id, merged)
        db.commit()
        return updated
    except Exception as e:
        db.rollback()
        raise e


def list_waitlist_service(db: Session) -> List[Dict]:
    return list_waitlist(db)


def get_waitlist_by_patient_service(db: Session, patient_id: int) -> List[Dict]:
    return get_waitlist_by_patient(db, patient_id)


def get_waitlist_by_session_service(db: Session, session_id: int) -> List[Dict]:
    return get_waitlist_by_session(db, session_id)


def get_waitlist_entry_service(db: Session, waitlist_id: int) -> Dict:
    entry = get_waitlist_by_id(db, waitlist_id)
    if not entry:
        raise LookupError("Waitlist entry not found")
    return entry


# ── Auto-allocation ────────────────────────────────────────────────────

def auto_allocate_from_waitlist(
    db: Session,
    session_id: int,
    freed_start_time,
    freed_end_time,
    freed_date,
    doctor_id: str,
) -> bool:
    """
    Called automatically when a cancellation frees a time slot.

    Finds the next WAITING patient in the queue (emergency first,
    then by join time), books the freed time for them, and marks
    their waitlist entry as CONFIRMED.

    Returns True if a patient was allocated, False if queue was empty.

    NOTE: Does NOT call db.commit() — the calling service (cancel_appointment_service)
    commits the whole transaction in one shot.
    """
    next_patient = get_next_in_queue(db, session_id)
    if not next_patient:
        return False  # nobody waiting

    # Import appointment repo directly (avoids circular import with appointments/service)
    from app.modules.appointments.repository import create_appointment

    # Book the freed time for the waitlisted patient
    created_appointment = create_appointment(
        db,
        {
            "session_id": session_id,
            "patient_id": next_patient["patient_id"],
            "doctor_id": next_patient["doctor_id"],
            "appointment_date": freed_date,
            "start_time": freed_start_time,
            "end_time": freed_end_time,
            "status": "CONFIRMED",
        },
    )

    # Mark waitlist entry as CONFIRMED
    update_waitlist(
        db,
        next_patient["waitlist_id"],
        {
            "status": "CONFIRMED",
            "notified_at": datetime.utcnow(),
            "response_deadline": None,
            "emergency_verified_at": next_patient.get("emergency_verified_at"),
        },
    )

    # Send waitlist-allocated notification email (best-effort)
    try:
        from app.modules.notifications.service import notify_waitlist_allocated
        patient = get_patient_by_id(db, next_patient["patient_id"])
        doctor = get_doctor_by_id(db, next_patient["doctor_id"])
        if patient and doctor:
            slot_data = {
                "slot_date": freed_date,
                "start_time": freed_start_time,
            }
            notify_waitlist_allocated(
                db,
                patient,
                doctor,
                slot_data,
                next_patient["waitlist_id"],
                appointment_id=created_appointment["appointment_id"],
            )
    except Exception:
        pass  # never let notification failures block the allocation

    return True
