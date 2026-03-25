"""
notifications/service.py
------------------------
High-level notification functions.

Each function:
  1. Builds the email (and optional attachment) from the template
  2. Sends it (silently no-ops if SMTP not configured)
  3. Writes a row to notification_log
  4. Never raises — wrapped in try/except so it never breaks the caller
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.notifications.email import send_email
from app.modules.notifications import templates
from app.modules.notifications.ics import build_ics

log = logging.getLogger(__name__)

# JWT config (same key as auth module so we can decode review tokens there)
_SECRET  = os.getenv("JWT_SECRET_KEY", "dpms-secret-change-in-production")
_ALG     = "HS256"
_API_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
_SMTP_FROM_EMAIL = os.getenv("SMTP_USER", "")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _doctor_label(name: str) -> str:
    n = (name or "").strip()
    if n.lower().startswith("dr."):
        return n
    return f"Dr. {n}" if n else "Doctor"

def _log_notification(
    db: Session,
    patient_id: int,
    notification_type: str,
    appointment_id: Optional[int] = None,
    waitlist_id: Optional[int] = None,
) -> None:
    db.execute(
        text("""
            INSERT INTO notification_log
                (patient_id, appointment_id, waitlist_id, notification_type, channel)
            VALUES
                (:pid, :aid, :wid, :ntype, 'EMAIL')
        """),
        {
            "pid":   patient_id,
            "aid":   appointment_id,
            "wid":   waitlist_id,
            "ntype": notification_type,
        },
    )


def _make_review_token(appointment_id: int, patient_id: int, doctor_id: int) -> str:
    """Return a signed JWT review token valid for 7 days."""
    payload = {
        "purpose":        "doctor_review",
        "appointment_id": appointment_id,
        "patient_id":     patient_id,
        "doctor_id":      doctor_id,
        "exp":            datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALG)


# ── Public notification functions ─────────────────────────────────────────────
# These accept a `slot` dict for backward compatibility.
# The dict just needs "slot_date" (or "appointment_date") and "start_time".

def _get_date(slot: dict) -> str:
    return str(slot.get("slot_date") or slot.get("appointment_date", ""))

def _get_time(slot: dict) -> str:
    return str(slot.get("start_time", ""))[:5]


def notify_booking_confirmed(
    db: Session,
    patient: dict,
    doctor: dict,
    slot: dict,
    appointment_id: int,
) -> None:
    """Send booking confirmation email with .ics calendar invite, then log it."""
    try:
        doctor_label = _doctor_label(doctor["full_name"])
        date_str = _get_date(slot)
        time_str = _get_time(slot)

        html = templates.booking_confirmation(
            patient_name   = patient["full_name"],
            doctor_name    = doctor["full_name"],
            specialization = doctor.get("specialization", ""),
            date           = date_str,
            time_str       = time_str,
        )

        ics = None
        try:
            ics = build_ics(
                summary        = f"Appointment with {doctor_label}",
                description    = (
                    f"DPMS Clinic appointment\n"
                    f"Doctor: {doctor_label} ({doctor.get('specialization', '')})\n"
                    f"Patient: {patient['full_name']}"
                ),
                location       = "DPMS Clinic",
                slot_date      = date_str,
                start_time     = time_str,
                duration_mins  = 30,
                organizer_email= _SMTP_FROM_EMAIL,
                attendee_email = patient.get("email", ""),
            )
        except Exception as exc:
            log.warning("ICS generation failed for booking confirmation: %s", exc)

        send_email(
            to           = patient.get("email", ""),
            subject      = f"Appointment Confirmed — {doctor_label} on {date_str}",
            html_body    = html,
            ics_content  = ics,
            ics_filename = "appointment.ics",
        )
        _log_notification(db, patient["patient_id"], "BOOKING_CONFIRM", appointment_id=appointment_id)
    except Exception as exc:
        log.warning("notify_booking_confirmed failed: %s", exc)


def notify_cancellation(
    db: Session,
    patient: dict,
    doctor: dict,
    slot: dict,
    appointment_id: int,
) -> None:
    """Send cancellation email and log it."""
    try:
        doctor_label = _doctor_label(doctor["full_name"])
        date_str = _get_date(slot)
        time_str = _get_time(slot)

        html = templates.cancellation(
            patient_name = patient["full_name"],
            doctor_name  = doctor["full_name"],
            date         = date_str,
            time_str     = time_str,
        )
        send_email(
            to        = patient.get("email", ""),
            subject   = f"Appointment Cancelled — {doctor_label} on {date_str}",
            html_body = html,
        )
        _log_notification(db, patient["patient_id"], "CANCELLATION", appointment_id=appointment_id)
    except Exception as exc:
        log.warning("notify_cancellation failed: %s", exc)


def notify_waitlist_allocated(
    db: Session,
    patient: dict,
    doctor: dict,
    slot: dict,
    waitlist_id: int,
    appointment_id: Optional[int] = None,
) -> None:
    """Send waitlist-slot-confirmed email with .ics calendar invite, then log it."""
    try:
        doctor_label = _doctor_label(doctor["full_name"])
        date_str = _get_date(slot)
        time_str = _get_time(slot)

        html = templates.waitlist_allocated(
            patient_name   = patient["full_name"],
            doctor_name    = doctor["full_name"],
            specialization = doctor.get("specialization", ""),
            date           = date_str,
            time_str       = time_str,
        )

        ics = None
        try:
            ics = build_ics(
                summary        = f"Appointment with {doctor_label}",
                description    = (
                    f"DPMS Clinic appointment (waitlist confirmed)\n"
                    f"Doctor: {doctor_label} ({doctor.get('specialization', '')})\n"
                    f"Patient: {patient['full_name']}"
                ),
                location       = "DPMS Clinic",
                slot_date      = date_str,
                start_time     = time_str,
                duration_mins  = 30,
                organizer_email= _SMTP_FROM_EMAIL,
                attendee_email = patient.get("email", ""),
            )
        except Exception as exc:
            log.warning("ICS generation failed for waitlist notification: %s", exc)

        send_email(
            to           = patient.get("email", ""),
            subject      = f"🎉 Waitlist Confirmed — {doctor_label} on {date_str}",
            html_body    = html,
            ics_content  = ics,
            ics_filename = "appointment.ics",
        )
        _log_notification(db, patient["patient_id"], "WAITLIST_NOTIFY", waitlist_id=waitlist_id)
        # Keep booking-confirm audit complete even when booking originates from waitlist allocation.
        if appointment_id:
            _log_notification(db, patient["patient_id"], "BOOKING_CONFIRM", appointment_id=appointment_id)
    except Exception as exc:
        log.warning("notify_waitlist_allocated failed: %s", exc)


def notify_2hr_reminder(
    db: Session,
    patient: dict,
    doctor: dict,
    slot: dict,
    appointment_id: str,
) -> None:
    """Send 2-hour reminder email and log it."""
    try:
        doctor_label = _doctor_label(doctor["full_name"])
        date_str = _get_date(slot)
        time_str = _get_time(slot)

        html = templates.reminder_2hr(
            patient_name   = patient["full_name"],
            doctor_name    = doctor["full_name"],
            specialization = doctor.get("specialization", ""),
            date           = date_str,
            time_str       = time_str,
        )
        send_email(
            to        = patient.get("email", ""),
            subject   = f"⏰ Reminder: Appointment in 2 hours — {doctor_label}",
            html_body = html,
        )
        _log_notification(db, patient["patient_id"], "REMINDER_2HR", appointment_id=appointment_id)
    except Exception as exc:
        log.warning("notify_2hr_reminder failed: %s", exc)


def notify_review_request(
    db: Session,
    patient: dict,
    doctor: dict,
    slot: dict,
    appointment_id: int,
) -> None:
    """
    Send a polite post-appointment review request email.
    Includes quick 1–5 star links + a full review page link.
    Logs to notification_log with type REVIEW_REQUEST.
    """
    try:
        doctor_label = _doctor_label(doctor["full_name"])
        token = _make_review_token(appointment_id, patient["patient_id"], doctor["doctor_id"])
        rating_url = f"{_API_URL}/rate/{token}"

        date_str = _get_date(slot)
        time_str = _get_time(slot)

        html = templates.review_request(
            patient_name   = patient["full_name"],
            doctor_name    = doctor["full_name"],
            specialization = doctor.get("specialization", ""),
            date           = date_str,
            time_str       = time_str,
            rating_url     = rating_url,
        )
        send_email(
            to        = patient.get("email", ""),
            subject   = f"⭐ How was your visit with {doctor_label}?",
            html_body = html,
        )
        _log_notification(db, patient["patient_id"], "REVIEW_REQUEST", appointment_id=appointment_id)
    except Exception as exc:
        log.warning("notify_review_request failed: %s", exc)


# ── Scheduler jobs (called by APScheduler background thread) ──────────────────

def send_pending_2hr_reminders() -> None:
    """
    Finds all CONFIRMED appointments starting within the next 2 hours
    that haven't been reminded yet, sends each patient a reminder email,
    and marks reminder_2hr_sent = TRUE.

    Called every 5 minutes by the APScheduler background job.
    Creates its own DB session so it's safe to call from a thread.
    """
    from app.database.connection.database import get_session

    db: Session = get_session()
    try:
        # No more JOIN with slots — time data is on the appointment itself
        rows = db.execute(text("""
            SELECT
                a.appointment_id,
                a.patient_id,
                a.doctor_id,
                a.appointment_date,
                a.start_time,
                p.full_name  AS patient_name,
                p.email      AS patient_email,
                d.full_name  AS doctor_name,
                d.specialization
            FROM appointments a
            JOIN patients p ON p.patient_id = a.patient_id
            JOIN doctors  d ON d.doctor_id  = a.doctor_id
            WHERE a.status              = 'CONFIRMED'
              AND a.reminder_2hr_sent   = FALSE
              AND (a.appointment_date::timestamp + a.start_time::time)
                  BETWEEN NOW() AND (NOW() + INTERVAL '2 hours 15 minutes')
        """)).mappings().all()

        for row in rows:
            r = dict(row)
            patient = {"full_name": r["patient_name"], "email": r["patient_email"],
                       "patient_id": r["patient_id"]}
            doctor  = {"full_name": r["doctor_name"], "specialization": r["specialization"]}
            slot    = {"slot_date": r["appointment_date"], "start_time": r["start_time"]}

            notify_2hr_reminder(db, patient, doctor, slot, r["appointment_id"])

            db.execute(
                text("UPDATE appointments SET reminder_2hr_sent = TRUE WHERE appointment_id = :aid"),
                {"aid": r["appointment_id"]},
            )
            db.commit()
            log.info("2hr reminder sent → %s (%s)", r["patient_email"], r["appointment_id"])

    except Exception as exc:
        db.rollback()
        log.warning("send_pending_2hr_reminders failed: %s", exc)
    finally:
        db.close()


def mark_completed_and_send_reviews() -> None:
    """
    Scheduler job (every 10 minutes):
      1. Finds CONFIRMED appointments whose time has now passed.
      2. Marks them COMPLETED.
      3. Sends a review-request email to each patient (once).

    Creates its own DB session so it's safe to call from a background thread.
    """
    from app.database.connection.database import get_session

    db: Session = get_session()
    try:
        # No more JOIN with slots — time data is on the appointment itself
        rows = db.execute(text("""
            SELECT
                a.appointment_id,
                a.patient_id,
                a.doctor_id,
                a.review_sent,
                a.appointment_date,
                a.start_time,
                p.full_name     AS patient_name,
                p.email         AS patient_email,
                d.full_name     AS doctor_name,
                d.doctor_id     AS doctor_id_val,
                d.specialization
            FROM appointments a
            JOIN patients p ON p.patient_id = a.patient_id
            JOIN doctors  d ON d.doctor_id  = a.doctor_id
            WHERE a.status = 'CONFIRMED'
              AND (a.appointment_date::timestamp + a.start_time::time) < NOW()
        """)).mappings().all()

        for row in rows:
            r = dict(row)
            aid = r["appointment_id"]

            # Mark appointment COMPLETED
            db.execute(
                text("""
                    UPDATE appointments
                       SET status       = 'COMPLETED',
                           completed_at = NOW()
                     WHERE appointment_id = :aid
                """),
                {"aid": aid},
            )

            # Send review request only once
            if not r["review_sent"]:
                patient = {
                    "full_name":  r["patient_name"],
                    "email":      r["patient_email"],
                    "patient_id": r["patient_id"],
                }
                doctor = {
                    "full_name":      r["doctor_name"],
                    "doctor_id":      r["doctor_id_val"],
                    "specialization": r["specialization"],
                }
                slot = {"slot_date": r["appointment_date"], "start_time": r["start_time"]}

                notify_review_request(db, patient, doctor, slot, aid)

                db.execute(
                    text("UPDATE appointments SET review_sent = TRUE WHERE appointment_id = :aid"),
                    {"aid": aid},
                )

            db.commit()
            log.info("Appointment completed → %s", aid)

    except Exception as exc:
        db.rollback()
        log.warning("mark_completed_and_send_reviews failed: %s", exc)
    finally:
        db.close()
