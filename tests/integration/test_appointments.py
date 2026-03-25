"""
tests/integration/test_appointments.py

Integration tests for the appointment booking and cancellation services.
Uses a real DB session wrapped in a transaction that rolls back after
each test — no data is permanently written.

Edge cases covered:
  - Happy path booking (time-based, no slots)
  - Time already booked (double-booking prevention)
  - Patient / doctor / session not found
  - Cancel with plenty of notice (allowed)
  - Cancel within 2 hours (blocked)
  - Cancel already-cancelled appointment
  - Cancellation log is written
"""

import random
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import text

from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import (
    cancel_appointment_service,
    create_appointment_service,
    get_appointment_service,
    update_appointment_service,
)


def _rand_suffix():
    return random.randint(100000, 999999)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def doctor(db):
    result = db.execute(
        text("""
            INSERT INTO doctors (full_name, specialization, email, phone,
                                 slot_duration_mins, max_patients_per_day)
            VALUES ('Dr. Test', 'General', :email, :phone, 15, 40)
            RETURNING doctor_id
        """),
        {"email": f"drtest_{_rand_suffix()}@test.com", "phone": f"9{random.randint(100000000, 999999999)}"},
    )
    return {"doctor_id": result.scalar_one()}


@pytest.fixture()
def patient(db):
    result = db.execute(
        text("""
            INSERT INTO patients (full_name, email, phone, date_of_birth)
            VALUES ('Test Patient', :email, :phone, '1990-01-01')
            RETURNING patient_id
        """),
        {"email": f"testpatient_{_rand_suffix()}@test.com", "phone": f"8{random.randint(100000000, 999999999)}"},
    )
    return {"patient_id": result.scalar_one()}


@pytest.fixture()
def session_row(db, doctor):
    session_date = date.today() + timedelta(days=3)
    result = db.execute(
        text("""
            INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
            VALUES (:doctor_id, :session_date, 'MORNING', '09:00', '12:00', 'OPEN')
            RETURNING session_id
        """),
        {"doctor_id": doctor["doctor_id"], "session_date": session_date},
    )
    return {"session_id": result.scalar_one(), "session_date": session_date}


@pytest.fixture()
def future_session(db, doctor):
    session_date = date.today() + timedelta(days=5)
    result = db.execute(
        text("""
            INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
            VALUES (:doctor_id, :session_date, 'MORNING', '09:00', '12:00', 'OPEN')
            RETURNING session_id
        """),
        {"doctor_id": doctor["doctor_id"], "session_date": session_date},
    )
    return {"session_id": result.scalar_one(), "session_date": session_date}


@pytest.fixture()
def imminent_session(db, doctor):
    """Session today — appointments starting soon should be blocked from cancellation."""
    result = db.execute(
        text("""
            INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
            VALUES (:doctor_id, :session_date, 'MORNING', '00:00', '23:59', 'OPEN')
            RETURNING session_id
        """),
        {"doctor_id": doctor["doctor_id"], "session_date": date.today()},
    )
    return {"session_id": result.scalar_one(), "session_date": date.today()}


# ── Booking tests ─────────────────────────────────────────────────────

class TestCreateAppointment:

    def test_happy_path_books_time(self, db, patient, doctor, session_row):
        appt = create_appointment_service(
            db,
            AppointmentCreate(
                session_id=session_row["session_id"],
                patient_id=patient["patient_id"],
                doctor_id=doctor["doctor_id"],
                appointment_date=session_row["session_date"],
                start_time=time(9, 0),
            ),
        )
        assert appt["status"] == "CONFIRMED"
        assert appt["patient_id"] == patient["patient_id"]
        assert appt["doctor_id"] == doctor["doctor_id"]

    def test_patient_not_found_raises(self, db, doctor, session_row):
        with pytest.raises(LookupError, match="Patient not found"):
            create_appointment_service(
                db,
                AppointmentCreate(
                    session_id=session_row["session_id"],
                    patient_id=999999,
                    doctor_id=doctor["doctor_id"],
                    appointment_date=session_row["session_date"],
                    start_time=time(9, 0),
                ),
            )

    def test_doctor_not_found_raises(self, db, patient, session_row):
        with pytest.raises(LookupError, match="Doctor not found"):
            create_appointment_service(
                db,
                AppointmentCreate(
                    session_id=session_row["session_id"],
                    patient_id=patient["patient_id"],
                    doctor_id=999999,
                    appointment_date=session_row["session_date"],
                    start_time=time(9, 0),
                ),
            )

    def test_double_booking_prevented(self, db, patient, doctor, session_row):
        create_appointment_service(
            db,
            AppointmentCreate(
                session_id=session_row["session_id"],
                patient_id=patient["patient_id"],
                doctor_id=doctor["doctor_id"],
                appointment_date=session_row["session_date"],
                start_time=time(9, 0),
            ),
        )
        # Second patient tries same time
        patient2 = db.execute(
            text("""
                INSERT INTO patients (full_name, email, phone, date_of_birth)
                VALUES ('Patient Two', :email, :phone, '1995-05-05')
                RETURNING patient_id
            """),
            {"email": f"p2_{_rand_suffix()}@test.com", "phone": f"6{random.randint(100000000, 999999999)}"},
        ).scalar_one()

        with pytest.raises(ValueError, match="not available|already booked"):
            create_appointment_service(
                db,
                AppointmentCreate(
                    session_id=session_row["session_id"],
                    patient_id=patient2,
                    doctor_id=doctor["doctor_id"],
                    appointment_date=session_row["session_date"],
                    start_time=time(9, 0),
                ),
            )

    def test_same_patient_cannot_book_multiple_active_with_same_doctor(
        self, db, patient, doctor, future_session,
    ):
        create_appointment_service(
            db,
            AppointmentCreate(
                session_id=future_session["session_id"],
                patient_id=patient["patient_id"],
                doctor_id=doctor["doctor_id"],
                appointment_date=future_session["session_date"],
                start_time=time(10, 0),
            ),
        )

        with pytest.raises(ValueError, match="active appointment with this doctor"):
            create_appointment_service(
                db,
                AppointmentCreate(
                    session_id=future_session["session_id"],
                    patient_id=patient["patient_id"],
                    doctor_id=doctor["doctor_id"],
                    appointment_date=future_session["session_date"],
                    start_time=time(10, 30),
                ),
            )


# ── Cancellation tests ────────────────────────────────────────────────

class TestCancelAppointment:

    def _book(self, db, patient, doctor, session_info, start_time=time(10, 0)):
        return create_appointment_service(
            db,
            AppointmentCreate(
                session_id=session_info["session_id"],
                patient_id=patient["patient_id"],
                doctor_id=doctor["doctor_id"],
                appointment_date=session_info["session_date"],
                start_time=start_time,
            ),
        )

    def test_cancel_with_plenty_of_notice(self, db, patient, doctor, future_session):
        appt = self._book(db, patient, doctor, future_session)
        result = cancel_appointment_service(db, appt["appointment_id"])
        assert result["status"] == "CANCELLED"
        assert result["cancelled_at"] is not None

    def test_cancel_within_2_hours_blocked(self, db, patient, doctor, imminent_session):
        now = datetime.utcnow()
        soon = time((now.hour + 0) % 24, (now.minute + 30) % 60)
        appt = self._book(db, patient, doctor, imminent_session, start_time=soon)
        with pytest.raises(ValueError, match="within 2 hours"):
            cancel_appointment_service(db, appt["appointment_id"])

    def test_cancel_already_cancelled_raises(self, db, patient, doctor, future_session):
        appt = self._book(db, patient, doctor, future_session)
        cancel_appointment_service(db, appt["appointment_id"])
        with pytest.raises(ValueError, match="already cancelled"):
            cancel_appointment_service(db, appt["appointment_id"])

    def test_cancel_nonexistent_appointment_raises(self, db):
        with pytest.raises(LookupError, match="Appointment not found"):
            cancel_appointment_service(db, 999999)

    def test_cancellation_log_written(self, db, patient, doctor, future_session):
        appt = self._book(db, patient, doctor, future_session)
        cancel_appointment_service(db, appt["appointment_id"])
        log = db.execute(
            text("SELECT * FROM cancellation_log WHERE appointment_id = :aid"),
            {"aid": appt["appointment_id"]},
        ).mappings().first()
        assert log is not None
        assert log["is_late_cancellation"] is False

    # ── Update appointment ────────────────────────────────────────────

    def test_update_status_to_completed(self, db, patient, doctor, future_session):
        appt = self._book(db, patient, doctor, future_session)
        updated = update_appointment_service(
            db,
            appt["appointment_id"],
            AppointmentUpdate(status="COMPLETED"),
        )
        assert updated["status"] == "COMPLETED"

    def test_update_reminder_flags(self, db, patient, doctor, future_session):
        appt = self._book(db, patient, doctor, future_session)
        updated = update_appointment_service(
            db,
            appt["appointment_id"],
            AppointmentUpdate(reminder_24hr_sent=True, reminder_2hr_sent=True),
        )
        assert updated["reminder_24hr_sent"] is True
        assert updated["reminder_2hr_sent"] is True

    def test_update_with_no_fields_raises(self, db, patient, doctor, future_session):
        appt = self._book(db, patient, doctor, future_session)
        with pytest.raises(ValueError, match="At least one field"):
            update_appointment_service(db, appt["appointment_id"], AppointmentUpdate())
