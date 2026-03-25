from datetime import date as date_type
from datetime import datetime, time as time_type
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.appointments.repository import (
    create_appointment,
    create_cancellation_log,
    get_active_appointments_by_date,
    get_available_slots_by_doctor_and_date,
    get_earliest_available_slot_by_doctor,
    get_appointment_by_id,
    get_appointment_by_slot_id,
    get_appointments_by_date,
    get_appointments_by_doctor,
    get_appointments_by_patient,
    get_appointments_by_status,
    get_doctor_by_id,
    get_patient_by_id,
    get_slot_by_id,
    get_slots_by_doctor_and_date,
    get_upcoming_active_appointments,
    list_appointments,
    update_appointment,
    update_slot_status,
)
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate


def create_appointment_service(db: Session, payload: AppointmentCreate) -> Dict:
    patient = get_patient_by_id(db, payload.patient_id)
    if not patient:
        raise LookupError("Patient not found")

    doctor = get_doctor_by_id(db, payload.doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    slot = get_slot_by_id(db, payload.slot_id)
    if not slot:
        raise LookupError("Slot not found")

    if slot["doctor_id"] != str(payload.doctor_id):
        raise ValueError("Slot does not belong to the given doctor")

    if slot["status"] != "AVAILABLE":
        raise ValueError("Slot is not available for booking")

    existing = get_appointment_by_slot_id(db, payload.slot_id)
    if existing and existing["status"] != "CANCELLED":
        raise ValueError("This slot is already booked")

    try:
        appointment = create_appointment(
            db,
            {
                "slot_id": str(payload.slot_id),
                "patient_id": str(payload.patient_id),
                "doctor_id": str(payload.doctor_id),
                "status": "CONFIRMED",
            },
        )
        update_slot_status(db, payload.slot_id, "BOOKED")
        db.commit()

        # Send booking confirmation email (best-effort, never breaks the flow)
        from app.modules.notifications.service import notify_booking_confirmed
        notify_booking_confirmed(db, patient, doctor, slot, str(appointment["appointment_id"]))
        db.commit()

        return appointment
    except Exception as e:
        db.rollback()
        raise e


def get_appointment_service(db: Session, appointment_id: UUID) -> Dict:
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise LookupError("Appointment not found")
    return appointment


def list_appointments_service(db: Session) -> List[Dict]:
    return list_appointments(db)


def get_appointments_by_patient_service(db: Session, patient_id: UUID) -> List[Dict]:
    return get_appointments_by_patient(db, patient_id)


def get_appointments_by_doctor_service(db: Session, doctor_id: UUID) -> List[Dict]:
    return get_appointments_by_doctor(db, doctor_id)


def get_appointments_by_status_service(db: Session, status: str) -> List[Dict]:
    return get_appointments_by_status(db, status)


def get_appointments_by_date_service(db: Session, appointment_date) -> List[Dict]:
    return get_appointments_by_date(db, appointment_date)


def get_active_appointments_by_date_service(
    db: Session, appointment_date, patient_id: Optional[UUID] = None
) -> List[Dict]:
    return get_active_appointments_by_date(db, appointment_date, patient_id)


def get_upcoming_active_appointments_service(
    db: Session, patient_id: Optional[UUID] = None
) -> List[Dict]:
    return get_upcoming_active_appointments(db, patient_id)


def get_available_slots_by_doctor_and_date_service(
    db: Session,
    doctor_id: UUID,
    slot_date: date_type,
) -> List[Dict]:
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    return get_available_slots_by_doctor_and_date(db, doctor_id, slot_date)


def get_earliest_available_slot_by_doctor_service(
    db: Session,
    doctor_id: UUID,
    start_date: Optional[date_type] = None,
) -> Dict:
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    search_date = start_date or date_type.today()
    search_time = datetime.now().time() if search_date == date_type.today() else time_type(0, 0)

    slot = get_earliest_available_slot_by_doctor(db, doctor_id, search_date, search_time)
    if not slot:
        raise LookupError(
            f"No available future slots found for {doctor['full_name']} from {search_date} onward."
        )

    return slot


def update_appointment_service(db: Session, appointment_id: UUID, payload: AppointmentUpdate) -> Dict:
    existing = get_appointment_by_id(db, appointment_id)
    if not existing:
        raise LookupError("Appointment not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValueError("At least one field is required for update")

    merged = {
        "status": update_data.get("status", existing["status"]),
        "reminder_24hr_sent": update_data.get("reminder_24hr_sent", existing["reminder_24hr_sent"]),
        "reminder_2hr_sent": update_data.get("reminder_2hr_sent", existing["reminder_2hr_sent"]),
        "confirmed_at": update_data.get("confirmed_at", existing["confirmed_at"]),
        "cancelled_at": update_data.get("cancelled_at", existing["cancelled_at"]),
    }

    if merged["status"] == "CANCELLED" and merged["cancelled_at"] is None:
        merged["cancelled_at"] = datetime.utcnow()

    try:
        appointment = update_appointment(db, appointment_id, merged)
        if not appointment:
            raise LookupError("Appointment not found")

        if merged["status"] == "CANCELLED":
            update_slot_status(db, UUID(existing["slot_id"]), "AVAILABLE")
        elif merged["status"] == "CONFIRMED":
            update_slot_status(db, UUID(existing["slot_id"]), "BOOKED")

        db.commit()
        return appointment
    except Exception as e:
        db.rollback()
        raise e


def cancel_appointment_service(
    db: Session,
    appointment_id: UUID,
    cancelled_by: str = "PATIENT",
) -> Dict:
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise LookupError("Appointment not found")

    if appointment["status"] == "CANCELLED":
        raise ValueError("Appointment is already cancelled")

    # ── 2-hour cancellation rule ──────────────────────────────────────
    slot = get_slot_by_id(db, UUID(appointment["slot_id"]))
    is_late_cancellation = False
    if slot:
        raw_date = slot["slot_date"]
        raw_time = slot["start_time"]
        slot_date_val = (
            date_type.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
        )
        parts = str(raw_time).split(":")
        slot_time_val = time_type(int(parts[0]), int(parts[1]))
        slot_dt = datetime.combine(slot_date_val, slot_time_val)
        now = datetime.utcnow()
        seconds_until = (slot_dt - now).total_seconds()

        if 0 < seconds_until < 7200:
            raise ValueError(
                f"Cancellation not allowed within 2 hours of appointment. "
                f"Appointment is at {slot['start_time']} on {slot['slot_date']}."
            )
        is_late_cancellation = seconds_until <= 0  # past appointments flagged too

    try:
        # Update appointment to CANCELLED
        merged = {
            "status": "CANCELLED",
            "reminder_24hr_sent": appointment["reminder_24hr_sent"],
            "reminder_2hr_sent": appointment["reminder_2hr_sent"],
            "confirmed_at": appointment["confirmed_at"],
            "cancelled_at": datetime.utcnow(),
        }
        updated = update_appointment(db, appointment_id, merged)
        if not updated:
            raise LookupError("Appointment not found after update")

        # Free the slot
        update_slot_status(db, UUID(appointment["slot_id"]), "AVAILABLE")

        # Write cancellation log
        create_cancellation_log(
            db,
            {
                "appointment_id": str(appointment_id),
                "patient_id": str(appointment["patient_id"]),
                "is_late_cancellation": is_late_cancellation,
                "cancelled_by": cancelled_by,
            },
        )

        # Auto-allocate to next waitlisted patient if any
        try:
            from app.modules.waitlist.service import auto_allocate_from_waitlist
            if slot:
                auto_allocate_from_waitlist(db, slot["session_id"], UUID(appointment["slot_id"]))
        except ImportError:
            pass  # waitlist module not yet available

        db.commit()

        # Send cancellation email (best-effort)
        from app.modules.notifications.service import notify_cancellation
        if slot:
            cancel_patient = get_patient_by_id(db, UUID(appointment["patient_id"]))
            cancel_doctor  = get_doctor_by_id(db, UUID(appointment["doctor_id"]))
            if cancel_patient and cancel_doctor:
                notify_cancellation(
                    db, cancel_patient, cancel_doctor, slot, str(appointment_id)
                )
                db.commit()

        return updated
    except Exception as e:
        db.rollback()
        raise e


def suggest_available_slot_service(
    db: Session,
    doctor_id: UUID,
    slot_date: date_type,
    preferred_time: Optional[str] = None,
) -> Dict:
    from app.utils.slot_search import find_next_available_slot

    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    slots = get_slots_by_doctor_and_date(db, doctor_id, slot_date)
    if not slots:
        raise LookupError(
            f"No sessions scheduled for {doctor['full_name']} on {slot_date}. "
            "Please check another date."
        )

    result = find_next_available_slot(slots, preferred_time)
    result["doctor_name"] = doctor["full_name"]
    result["date"] = str(slot_date)

    return result
