from datetime import datetime
from typing import Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.waitlist.repository import (
    already_on_waitlist,
    create_waitlist,
    get_doctor_by_id,
    get_first_available_slot_for_session,
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

    if session["doctor_id"] != str(payload.doctor_id):
        raise ValueError("Session does not belong to the given doctor")

    if already_on_waitlist(db, payload.patient_id, payload.session_id):
        raise ValueError(
            f"{patient['full_name']} is already on the waitlist for this session."
        )

    # Check if there's actually a free slot — no need to waitlist if available
    free_slot = get_first_available_slot_for_session(db, payload.session_id)
    if free_slot:
        raise ValueError(
            f"There is already an available slot at {free_slot['start_time']} for this session. "
            "Please book it directly instead of joining the waitlist."
        )

    try:
        entry = create_waitlist(
            db,
            {
                "patient_id": str(payload.patient_id),
                "doctor_id": str(payload.doctor_id),
                "session_id": payload.session_id,
                "waitlist_date": payload.waitlist_date,
                "priority": payload.priority,
                "is_emergency": payload.is_emergency,
                "emergency_declared_by": (
                    str(payload.emergency_declared_by)
                    if payload.emergency_declared_by
                    else None
                ),
                "emergency_reason": payload.emergency_reason,
            },
        )
        db.commit()
        return entry
    except Exception as e:
        db.rollback()
        raise e


def leave_waitlist_service(db: Session, waitlist_id: UUID) -> Dict:
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


def get_waitlist_by_patient_service(db: Session, patient_id: UUID) -> List[Dict]:
    return get_waitlist_by_patient(db, patient_id)


def get_waitlist_by_session_service(db: Session, session_id: int) -> List[Dict]:
    return get_waitlist_by_session(db, session_id)


def get_waitlist_entry_service(db: Session, waitlist_id: UUID) -> Dict:
    entry = get_waitlist_by_id(db, waitlist_id)
    if not entry:
        raise LookupError("Waitlist entry not found")
    return entry


# ── Auto-allocation ────────────────────────────────────────────────────

def auto_allocate_from_waitlist(
    db: Session,
    session_id: int,
    freed_slot_id: UUID,
) -> bool:
    """
    Called automatically when a cancellation frees a slot.

    Finds the next WAITING patient in the queue (emergency first,
    then by join time), books the freed slot for them, and marks
    their waitlist entry as CONFIRMED.

    Returns True if a patient was allocated, False if queue was empty.

    NOTE: Does NOT call db.commit() — the calling service (cancel_appointment_service)
    commits the whole transaction in one shot.
    """
    next_patient = get_next_in_queue(db, session_id)
    if not next_patient:
        return False  # nobody waiting

    # Import appointment repo directly (avoids circular import with appointments/service)
    from app.modules.appointments.repository import (
        create_appointment,
        update_slot_status,
    )

    # Book the slot for the waitlisted patient
    create_appointment(
        db,
        {
            "slot_id": str(freed_slot_id),
            "patient_id": next_patient["patient_id"],
            "doctor_id": next_patient["doctor_id"],
            "status": "CONFIRMED",
        },
    )
    update_slot_status(db, freed_slot_id, "BOOKED")

    # Mark waitlist entry as CONFIRMED
    update_waitlist(
        db,
        UUID(next_patient["waitlist_id"]),
        {
            "status": "CONFIRMED",
            "notified_at": datetime.utcnow(),
            "response_deadline": None,
            "emergency_verified_at": next_patient.get("emergency_verified_at"),
        },
    )

    return True
