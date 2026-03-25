from datetime import date as date_type
from datetime import datetime, time as time_type, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.appointments.repository import (
    cancel_confirmed_appointments_for_session,
    create_appointment,
    create_cancellation_log,
    get_active_appointment_by_patient_and_doctor,
    get_active_appointments_by_date,
    get_appointment_by_id,
    get_appointments_by_date,
    get_appointments_by_doctor,
    get_appointments_by_patient,
    get_appointments_by_status,
    get_confirmed_appointments_by_doctor_and_date,
    get_confirmed_appointments_for_session,
    get_doctor_by_id,
    get_earliest_available_session_date,
    get_patient_by_id,
    get_session_by_id,
    get_sessions_by_doctor_and_date,
    get_upcoming_active_appointments,
    list_appointments,
    update_appointment,
)
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.utils.availability import (
    compute_available_windows,
    find_available_slot,
    is_time_available,
)


def create_appointment_service(db: Session, payload: AppointmentCreate) -> Dict:
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

    if session["status"] != "OPEN":
        raise ValueError("Session is not open for booking")

    # Check patient doesn't already have an active appointment with this doctor
    active_with_same_doctor = get_active_appointment_by_patient_and_doctor(
        db,
        payload.patient_id,
        payload.doctor_id,
    )
    if active_with_same_doctor:
        raise ValueError("Patient already has an active appointment with this doctor")

    # Calculate end_time from doctor's slot duration
    slot_duration = int(doctor["slot_duration_mins"])
    start_t = payload.start_time
    start_dt = datetime.combine(payload.appointment_date, start_t)
    end_dt = start_dt + timedelta(minutes=slot_duration)
    end_t = end_dt.time()

    # Check availability on-the-fly
    booked = get_confirmed_appointments_for_session(db, payload.session_id)
    if not is_time_available(
        requested_start=start_t,
        slot_duration_mins=slot_duration,
        session_start=time_type.fromisoformat(session["start_time"]) if isinstance(session["start_time"], str) else session["start_time"],
        session_end=time_type.fromisoformat(session["end_time"]) if isinstance(session["end_time"], str) else session["end_time"],
        booked_appointments=booked,
    ):
        raise ValueError(
            f"Time {start_t.isoformat()[:5]} is not available. "
            "It may be outside session hours, overlap lunch (13:00–13:30), "
            "or conflict with an existing appointment."
        )

    try:
        appointment = create_appointment(
            db,
            {
                "session_id": payload.session_id,
                "patient_id": payload.patient_id,
                "doctor_id": payload.doctor_id,
                "appointment_date": payload.appointment_date,
                "start_time": start_t,
                "end_time": end_t,
                "status": "CONFIRMED",
            },
        )
        db.commit()

        # Send booking confirmation email (best-effort, never breaks the flow)
        from app.modules.notifications.service import notify_booking_confirmed
        # Build a slot-like dict for backwards compat with notification templates
        slot_data = {
            "slot_date": str(payload.appointment_date),
            "start_time": start_t.isoformat()[:5],
        }
        notify_booking_confirmed(db, patient, doctor, slot_data, appointment["appointment_id"])
        db.commit()

        return appointment
    except Exception as e:
        db.rollback()
        raise e


def get_appointment_service(db: Session, appointment_id: int) -> Dict:
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise LookupError("Appointment not found")
    return appointment


def list_appointments_service(db: Session) -> List[Dict]:
    return list_appointments(db)


def get_appointments_by_patient_service(db: Session, patient_id: int) -> List[Dict]:
    return get_appointments_by_patient(db, patient_id)


def get_appointments_by_doctor_service(db: Session, doctor_id: int) -> List[Dict]:
    return get_appointments_by_doctor(db, doctor_id)


def get_appointments_by_status_service(db: Session, status: str) -> List[Dict]:
    return get_appointments_by_status(db, status)


def get_appointments_by_date_service(db: Session, appointment_date) -> List[Dict]:
    return get_appointments_by_date(db, appointment_date)


def get_active_appointments_by_date_service(
    db: Session, appointment_date, patient_id: Optional[int] = None
) -> List[Dict]:
    return get_active_appointments_by_date(db, appointment_date, patient_id)


def get_upcoming_active_appointments_service(
    db: Session, patient_id: Optional[int] = None
) -> List[Dict]:
    return get_upcoming_active_appointments(db, patient_id)


def get_available_times_by_doctor_and_date_service(
    db: Session,
    doctor_id: int,
    appt_date: date_type,
) -> List[Dict]:
    """
    Compute all available time windows for a doctor on a date.
    Replaces the old get_available_slots_by_doctor_and_date_service.
    """
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    sessions = get_sessions_by_doctor_and_date(db, doctor_id, appt_date)
    if not sessions:
        return []

    slot_duration = int(doctor["slot_duration_mins"])
    all_windows = []

    for sess in sessions:
        booked = get_confirmed_appointments_for_session(db, sess["session_id"])
        windows = compute_available_windows(
            session_start=sess["start_time"],
            session_end=sess["end_time"],
            slot_duration_mins=slot_duration,
            booked_appointments=booked,
        )
        for w in windows:
            all_windows.append({
                **w,
                "session_id": sess["session_id"],
                "session_name": sess["session_name"],
                "doctor_id": doctor_id,
                "doctor_name": doctor["full_name"],
                "doctor_specialization": doctor.get("specialization", ""),
                "appointment_date": str(appt_date),
            })

    return all_windows


def get_earliest_available_time_by_doctor_service(
    db: Session,
    doctor_id: int,
    start_date: Optional[date_type] = None,
) -> Dict:
    """
    Find the earliest available time for a doctor from start_date onward.
    Replaces the old get_earliest_available_slot_by_doctor_service.
    """
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    search_date = start_date or date_type.today()
    slot_duration = int(doctor["slot_duration_mins"])

    # Get upcoming OPEN sessions for this doctor
    future_sessions = get_earliest_available_session_date(db, doctor_id, search_date)
    if not future_sessions:
        raise LookupError(
            f"No available future sessions found for {doctor['full_name']} from {search_date} onward."
        )

    now = datetime.now()

    for sess in future_sessions:
        sess_date_val = sess["session_date"]
        if isinstance(sess_date_val, str):
            sess_date_val = date_type.fromisoformat(sess_date_val)

        booked = get_confirmed_appointments_for_session(db, sess["session_id"])
        windows = compute_available_windows(
            session_start=sess["start_time"],
            session_end=sess["end_time"],
            slot_duration_mins=slot_duration,
            booked_appointments=booked,
        )

        for w in windows:
            w_time = time_type.fromisoformat(w["start_time"]) if isinstance(w["start_time"], str) else w["start_time"]
            w_dt = datetime.combine(sess_date_val, w_time)

            # Skip past times
            if w_dt <= now:
                continue

            return {
                **w,
                "session_id": sess["session_id"],
                "session_name": sess.get("session_name", ""),
                "appointment_date": str(sess_date_val),
                "doctor_id": doctor_id,
                "doctor_name": doctor["full_name"],
                "doctor_specialization": doctor.get("specialization", ""),
            }

    raise LookupError(
        f"No available future times found for {doctor['full_name']} from {search_date} onward."
    )


def update_appointment_service(db: Session, appointment_id: int, payload: AppointmentUpdate) -> Dict:
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
        db.commit()
        return appointment
    except Exception as e:
        db.rollback()
        raise e


def cancel_appointment_service(
    db: Session,
    appointment_id: int,
    cancelled_by: str = "PATIENT",
) -> Dict:
    appointment = get_appointment_by_id(db, appointment_id)
    if not appointment:
        raise LookupError("Appointment not found")

    if appointment["status"] == "CANCELLED":
        raise ValueError("Appointment is already cancelled")

    # ── 2-hour cancellation rule ──────────────────────────────────────
    is_late_cancellation = False
    raw_date = appointment["appointment_date"]
    raw_time = appointment["start_time"]
    appt_date_val = (
        date_type.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
    )
    parts = str(raw_time).split(":")
    appt_time_val = time_type(int(parts[0]), int(parts[1]))
    appt_dt = datetime.combine(appt_date_val, appt_time_val)
    now = datetime.utcnow()
    seconds_until = (appt_dt - now).total_seconds()

    if 0 < seconds_until < 7200:
        raise ValueError(
            f"Cancellation not allowed within 2 hours of appointment. "
            f"Appointment is at {appointment['start_time']} on {appointment['appointment_date']}."
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

        # Write cancellation log
        create_cancellation_log(
            db,
            {
                "appointment_id": appointment_id,
                "patient_id": appointment["patient_id"],
                "is_late_cancellation": is_late_cancellation,
                "cancelled_by": cancelled_by,
            },
        )

        # Auto-allocate to next waitlisted patient if any
        try:
            from app.modules.waitlist.service import auto_allocate_from_waitlist
            auto_allocate_from_waitlist(
                db,
                session_id=int(appointment["session_id"]),
                freed_start_time=appointment["start_time"],
                freed_end_time=appointment["end_time"],
                freed_date=appointment["appointment_date"],
                doctor_id=appointment["doctor_id"],
            )
        except ImportError:
            pass  # waitlist module not yet available

        db.commit()

        # Send cancellation email (best-effort)
        from app.modules.notifications.service import notify_cancellation
        cancel_patient = get_patient_by_id(db, appointment["patient_id"])
        cancel_doctor = get_doctor_by_id(db, appointment["doctor_id"])
        if cancel_patient and cancel_doctor:
            slot_data = {
                "slot_date": appointment["appointment_date"],
                "start_time": appointment["start_time"],
            }
            notify_cancellation(
                db, cancel_patient, cancel_doctor, slot_data, appointment_id
            )
            db.commit()

        return updated
    except Exception as e:
        db.rollback()
        raise e


def suggest_available_time_service(
    db: Session,
    doctor_id: int,
    appt_date: date_type,
    preferred_time: Optional[str] = None,
) -> Dict:
    """
    Suggest an available time for a doctor on a date.
    Replaces the old suggest_available_slot_service.
    """
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")

    sessions = get_sessions_by_doctor_and_date(db, doctor_id, appt_date)
    if not sessions:
        raise LookupError(
            f"No sessions scheduled for {doctor['full_name']} on {appt_date}. "
            "Please check another date."
        )

    slot_duration = int(doctor["slot_duration_mins"])

    # Build booked_by_session map
    booked_by_session = {}
    for sess in sessions:
        sid = sess["session_id"]
        booked_by_session[sid] = get_confirmed_appointments_for_session(db, sid)

    result = find_available_slot(
        sessions=sessions,
        booked_by_session=booked_by_session,
        slot_duration_mins=slot_duration,
        preferred_time_str=preferred_time,
    )
    result["doctor_name"] = doctor["full_name"]
    result["date"] = str(appt_date)

    return result
