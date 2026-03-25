"""
tests/integration/test_waitlist.py

Integration tests for the waitlist service.

Edge cases covered:
  - Join waitlist when session is fully booked → success
  - Join waitlist when times are still available → blocked (no need to wait)
  - Join same session twice → blocked (duplicate)
  - Session doesn't belong to that doctor → blocked
  - Patient / doctor / session not found
  - Leave (cancel) a waitlist entry
  - Cannot leave an already-confirmed or cancelled entry
  - Auto-allocation: cancelling an appointment books the next WAITING patient
  - Emergency patient (priority=1) jumps ahead of normal (priority=2)
"""

import random
from datetime import date, time, timedelta

import pytest
from sqlalchemy import text

from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import (
    cancel_appointment_service,
    create_appointment_service,
)
from app.modules.waitlist.schemas import WaitlistCreate
from app.modules.waitlist.service import (
    join_waitlist_service,
    leave_waitlist_service,
    get_waitlist_entry_service,
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
            VALUES ('Dr. Waitlist', 'General', :email, :phone, 15, 40)
            RETURNING doctor_id
        """),
        {"email": f"wldoc_{_rand_suffix()}@test.com", "phone": f"9{random.randint(100000000, 999999999)}"},
    )
    return result.scalar_one()


@pytest.fixture()
def patient(db):
    result = db.execute(
        text("""
            INSERT INTO patients (full_name, email, phone, date_of_birth)
            VALUES ('WL Patient', :email, :phone, '1990-06-15')
            RETURNING patient_id
        """),
        {"email": f"wlp_{_rand_suffix()}@test.com", "phone": f"8{random.randint(100000000, 999999999)}"},
    )
    return result.scalar_one()


@pytest.fixture()
def session_row(db, doctor):
    session_date = date.today() + timedelta(days=4)
    result = db.execute(
        text("""
            INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
            VALUES (:doctor_id, :session_date, 'MORNING', '09:00', '09:30', 'OPEN')
            RETURNING session_id
        """),
        {"doctor_id": doctor, "session_date": session_date},
    )
    return {"session_id": result.scalar_one(), "session_date": session_date}


@pytest.fixture()
def fully_booked_session(db, doctor, session_row):
    """Fill the session (09:00-09:30 with 15-min slots = 2 slots: 09:00, 09:15).
    Book both to make the session fully booked."""
    session_date = session_row["session_date"]
    for st, et in [("09:00", "09:15"), ("09:15", "09:30")]:
        pid = _make_patient(db)
        db.execute(
            text("""
                INSERT INTO appointments
                    (session_id, patient_id, doctor_id, appointment_date, start_time, end_time, status)
                VALUES (:sid, :pid, :did, :adate, :st, :et, 'CONFIRMED')
            """),
            {
                "sid": session_row["session_id"],
                "pid": pid,
                "did": doctor,
                "adate": session_date,
                "st": st,
                "et": et,
            },
        )
    return session_row


@pytest.fixture()
def partially_booked_session(db, doctor, session_row):
    """Only book the first time — 09:15 is still available."""
    session_date = session_row["session_date"]
    pid = _make_patient(db)
    db.execute(
        text("""
            INSERT INTO appointments
                (session_id, patient_id, doctor_id, appointment_date, start_time, end_time, status)
            VALUES (:sid, :pid, :did, :adate, '09:00', '09:15', 'CONFIRMED')
        """),
        {
            "sid": session_row["session_id"],
            "pid": pid,
            "did": doctor,
            "adate": session_date,
        },
    )
    return session_row


def _make_patient(db):
    result = db.execute(
        text("""
            INSERT INTO patients (full_name, email, phone, date_of_birth)
            VALUES ('Extra', :email, :phone, '1985-01-01')
            RETURNING patient_id
        """),
        {"email": f"extra_{_rand_suffix()}@test.com", "phone": f"7{random.randint(100000000, 999999999)}"},
    )
    return result.scalar_one()


def _join(db, patient_id, doctor_id, session_id, session_date=None, priority=2, is_emergency=False):
    return join_waitlist_service(
        db,
        WaitlistCreate(
            patient_id=patient_id,
            doctor_id=doctor_id,
            session_id=session_id,
            waitlist_date=session_date or (date.today() + timedelta(days=4)),
            priority=priority,
            is_emergency=is_emergency,
        ),
    )


# ── Join waitlist ─────────────────────────────────────────────────────

class TestJoinWaitlist:

    def test_join_when_session_fully_booked(self, db, patient, doctor, fully_booked_session):
        entry = _join(db, patient, doctor, fully_booked_session["session_id"],
                      session_date=fully_booked_session["session_date"])
        assert entry["status"] == "WAITING"
        assert entry["priority"] == 2

    def test_join_blocked_when_time_available(self, db, patient, doctor, partially_booked_session):
        with pytest.raises(ValueError, match="available time"):
            _join(db, patient, doctor, partially_booked_session["session_id"],
                  session_date=partially_booked_session["session_date"])

    def test_join_twice_blocked(self, db, patient, doctor, fully_booked_session):
        _join(db, patient, doctor, fully_booked_session["session_id"],
              session_date=fully_booked_session["session_date"])
        with pytest.raises(ValueError, match="already on the waitlist"):
            _join(db, patient, doctor, fully_booked_session["session_id"],
                  session_date=fully_booked_session["session_date"])

    def test_patient_not_found(self, db, doctor, fully_booked_session):
        with pytest.raises(LookupError, match="Patient not found"):
            _join(db, 999999, doctor, fully_booked_session["session_id"],
                  session_date=fully_booked_session["session_date"])

    def test_doctor_not_found(self, db, patient, fully_booked_session):
        with pytest.raises(LookupError, match="Doctor not found"):
            _join(db, patient, 999999, fully_booked_session["session_id"],
                  session_date=fully_booked_session["session_date"])

    def test_session_not_found(self, db, patient, doctor):
        with pytest.raises(LookupError, match="Session not found"):
            _join(db, patient, doctor, 999999)

    def test_session_wrong_doctor(self, db, patient, doctor, fully_booked_session):
        other_doc = db.execute(
            text("""
                INSERT INTO doctors (full_name, specialization, email, phone)
                VALUES ('Wrong Doc', 'ENT', :email, :phone)
                RETURNING doctor_id
            """),
            {"email": f"wrong_{_rand_suffix()}@test.com", "phone": f"6{random.randint(100000000, 999999999)}"},
        ).scalar_one()
        with pytest.raises(ValueError, match="does not belong"):
            _join(db, patient, other_doc, fully_booked_session["session_id"],
                  session_date=fully_booked_session["session_date"])

    def test_emergency_patient_joins_with_priority_1(self, db, patient, doctor, fully_booked_session):
        entry = _join(db, patient, doctor, fully_booked_session["session_id"],
                      session_date=fully_booked_session["session_date"],
                      priority=1, is_emergency=True)
        assert entry["priority"] == 1
        assert entry["is_emergency"] is True


# ── Leave waitlist ────────────────────────────────────────────────────

class TestLeaveWaitlist:

    def test_leave_waiting_entry(self, db, patient, doctor, fully_booked_session):
        entry = _join(db, patient, doctor, fully_booked_session["session_id"],
                      session_date=fully_booked_session["session_date"])
        result = leave_waitlist_service(db, entry["waitlist_id"])
        assert result["status"] == "CANCELLED"

    def test_leave_nonexistent_entry(self, db):
        with pytest.raises(LookupError, match="not found"):
            leave_waitlist_service(db, 999999)


# ── Auto-allocation ───────────────────────────────────────────────────

class TestAutoAllocation:

    def test_cancellation_auto_books_next_waiting_patient(self, db, doctor):
        """
        Setup: Create a small session, patient_a books the only time. patient_b joins waitlist.
        Action: patient_a cancels (appointment is far in the future — no 2hr block).
        Result: patient_b gets auto-booked, waitlist entry → CONFIRMED.
        """
        session_date = date.today() + timedelta(days=10)

        # Create session with room for one 15-min appointment (09:00-09:15)
        session_id = db.execute(
            text("""
                INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
                VALUES (:doctor_id, :session_date, 'MORNING', '09:00', '09:15', 'OPEN')
                RETURNING session_id
            """),
            {"doctor_id": doctor, "session_date": session_date},
        ).scalar_one()

        patient_a = _make_patient(db)
        patient_b = _make_patient(db)

        # patient_a books the time
        appt = create_appointment_service(
            db,
            AppointmentCreate(
                session_id=session_id,
                patient_id=patient_a,
                doctor_id=doctor,
                appointment_date=session_date,
                start_time=time(9, 0),
            ),
        )

        # patient_b joins the waitlist (no available times now)
        wl_entry = _join(db, patient_b, doctor, session_id, session_date=session_date)
        assert wl_entry["status"] == "WAITING"

        # patient_a cancels — triggers auto-allocation
        cancel_appointment_service(db, appt["appointment_id"])

        # patient_b should now have a CONFIRMED appointment
        new_appt = db.execute(
            text("""
                SELECT * FROM appointments
                WHERE patient_id = :pid AND status = 'CONFIRMED'
            """),
            {"pid": patient_b},
        ).mappings().first()
        assert new_appt is not None

        # patient_b's waitlist entry should be CONFIRMED
        wl_updated = db.execute(
            text("SELECT status FROM waitlist WHERE waitlist_id = :wid"),
            {"wid": wl_entry["waitlist_id"]},
        ).mappings().first()
        assert wl_updated["status"] == "CONFIRMED"

    def test_emergency_patient_gets_time_before_normal(self, db, doctor):
        """
        Setup: fully booked session. patient_normal joins waitlist (priority 2),
               patient_emergency joins (priority 1).
        Verify: get_next_in_queue returns emergency patient first.
        """
        session_date = date.today() + timedelta(days=10)

        session_id = db.execute(
            text("""
                INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
                VALUES (:doctor_id, :session_date, 'MORNING', '11:00', '11:15', 'OPEN')
                RETURNING session_id
            """),
            {"doctor_id": doctor, "session_date": session_date},
        ).scalar_one()

        # Book the only time so waitlist is valid
        booker = _make_patient(db)
        db.execute(
            text("""
                INSERT INTO appointments
                    (session_id, patient_id, doctor_id, appointment_date, start_time, end_time, status)
                VALUES (:sid, :pid, :did, :adate, '11:00', '11:15', 'CONFIRMED')
            """),
            {"sid": session_id, "pid": booker, "did": doctor, "adate": session_date},
        )

        patient_normal = _make_patient(db)
        patient_emergency = _make_patient(db)

        # Normal joins first
        _join(db, patient_normal, doctor, session_id, session_date=session_date, priority=2)
        # Emergency joins after
        _join(db, patient_emergency, doctor, session_id, session_date=session_date, priority=1, is_emergency=True)

        from app.modules.waitlist.repository import get_next_in_queue
        next_up = get_next_in_queue(db, session_id)

        assert next_up["patient_id"] == patient_emergency
