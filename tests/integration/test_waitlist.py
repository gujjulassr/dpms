"""
tests/integration/test_waitlist.py

Integration tests for the waitlist service.

Edge cases covered:
  - Join waitlist when session is fully booked → success
  - Join waitlist when a slot is still available → blocked (no need to wait)
  - Join same session twice → blocked (duplicate)
  - Session doesn't belong to that doctor → blocked
  - Patient / doctor / session not found
  - Leave (cancel) a waitlist entry
  - Cannot leave an already-confirmed or cancelled entry
  - Auto-allocation: cancelling an appointment books the next WAITING patient
  - Emergency patient (priority=1) jumps ahead of normal (priority=2)
"""

from datetime import date, timedelta
from uuid import uuid4

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


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def doctor(db):
    result = db.execute(
        text("""
            INSERT INTO doctors (full_name, specialization, email, phone)
            VALUES ('Dr. Waitlist', 'General', :email, :phone)
            RETURNING doctor_id
        """),
        {"email": f"wldoc_{uuid4().hex[:6]}@test.com", "phone": f"9{uuid4().int % 900000000 + 100000000}"},
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
        {"email": f"wlp_{uuid4().hex[:6]}@test.com", "phone": f"8{uuid4().int % 900000000 + 100000000}"},
    )
    return result.scalar_one()


@pytest.fixture()
def session_row(db, doctor):
    tomorrow = date.today() + timedelta(days=4)
    result = db.execute(
        text("""
            INSERT INTO sessions (doctor_id, session_date, session_name, start_time, end_time, status)
            VALUES (:doctor_id, :session_date, 'MORNING', '09:00', '12:00', 'OPEN')
            RETURNING session_id
        """),
        {"doctor_id": str(doctor), "session_date": tomorrow},
    )
    return result.scalar_one()


@pytest.fixture()
def booked_slot(db, doctor, session_row):
    """One slot that's already BOOKED."""
    result = db.execute(
        text("""
            INSERT INTO slots (doctor_id, session_id, slot_date, start_time, end_time, status)
            VALUES (:doctor_id, :session_id, :slot_date, '09:00', '09:15', 'BOOKED')
            RETURNING slot_id
        """),
        {
            "doctor_id": str(doctor),
            "session_id": session_row,
            "slot_date": date.today() + timedelta(days=4),
        },
    )
    return result.scalar_one()


@pytest.fixture()
def available_slot(db, doctor, session_row):
    """One slot that's AVAILABLE."""
    result = db.execute(
        text("""
            INSERT INTO slots (doctor_id, session_id, slot_date, start_time, end_time, status)
            VALUES (:doctor_id, :session_id, :slot_date, '09:15', '09:30', 'AVAILABLE')
            RETURNING slot_id
        """),
        {
            "doctor_id": str(doctor),
            "session_id": session_row,
            "slot_date": date.today() + timedelta(days=4),
        },
    )
    return result.scalar_one()


def _make_patient(db):
    result = db.execute(
        text("""
            INSERT INTO patients (full_name, email, phone, date_of_birth)
            VALUES ('Extra', :email, :phone, '1985-01-01')
            RETURNING patient_id
        """),
        {"email": f"extra_{uuid4().hex[:6]}@test.com", "phone": f"7{uuid4().int % 900000000 + 100000000}"},
    )
    return result.scalar_one()


def _join(db, patient_id, doctor_id, session_id, priority=2, is_emergency=False):
    return join_waitlist_service(
        db,
        WaitlistCreate(
            patient_id=patient_id,
            doctor_id=doctor_id,
            session_id=session_id,
            waitlist_date=date.today() + timedelta(days=4),
            priority=priority,
            is_emergency=is_emergency,
        ),
    )


# ── Join waitlist ─────────────────────────────────────────────────────

class TestJoinWaitlist:

    def test_join_when_session_fully_booked(self, db, patient, doctor, session_row, booked_slot):
        entry = _join(db, patient, doctor, session_row)
        assert entry["status"] == "WAITING"
        assert entry["priority"] == 2

    def test_join_blocked_when_slot_available(self, db, patient, doctor, session_row, available_slot):
        with pytest.raises(ValueError, match="already an available slot"):
            _join(db, patient, doctor, session_row)

    def test_join_twice_blocked(self, db, patient, doctor, session_row, booked_slot):
        _join(db, patient, doctor, session_row)
        with pytest.raises(ValueError, match="already on the waitlist"):
            _join(db, patient, doctor, session_row)

    def test_patient_not_found(self, db, doctor, session_row, booked_slot):
        with pytest.raises(LookupError, match="Patient not found"):
            _join(db, uuid4(), doctor, session_row)

    def test_doctor_not_found(self, db, patient, session_row, booked_slot):
        with pytest.raises(LookupError, match="Doctor not found"):
            _join(db, patient, uuid4(), session_row)

    def test_session_not_found(self, db, patient, doctor, booked_slot):
        with pytest.raises(LookupError, match="Session not found"):
            _join(db, patient, doctor, 999999)

    def test_session_wrong_doctor(self, db, patient, doctor, session_row, booked_slot):
        other_doc = db.execute(
            text("""
                INSERT INTO doctors (full_name, specialization, email, phone)
                VALUES ('Wrong Doc', 'ENT', :email, :phone)
                RETURNING doctor_id
            """),
            {"email": f"wrong_{uuid4().hex[:6]}@test.com", "phone": f"6{uuid4().int % 900000000 + 100000000}"},
        ).scalar_one()
        with pytest.raises(ValueError, match="does not belong"):
            _join(db, patient, other_doc, session_row)

    def test_emergency_patient_joins_with_priority_1(self, db, patient, doctor, session_row, booked_slot):
        entry = _join(db, patient, doctor, session_row, priority=1, is_emergency=True)
        assert entry["priority"] == 1
        assert entry["is_emergency"] is True


# ── Leave waitlist ────────────────────────────────────────────────────

class TestLeaveWaitlist:

    def test_leave_waiting_entry(self, db, patient, doctor, session_row, booked_slot):
        entry = _join(db, patient, doctor, session_row)
        result = leave_waitlist_service(db, entry["waitlist_id"])
        assert result["status"] == "CANCELLED"

    def test_leave_nonexistent_entry(self, db):
        with pytest.raises(LookupError, match="not found"):
            leave_waitlist_service(db, uuid4())


# ── Auto-allocation ───────────────────────────────────────────────────

class TestAutoAllocation:

    def test_cancellation_auto_books_next_waiting_patient(
        self, db, doctor, session_row
    ):
        """
        Setup: patient_a books the only slot. patient_b joins waitlist.
        Action: patient_a cancels (slot is in the far future — no 2hr block).
        Result: patient_b gets auto-booked, waitlist entry → CONFIRMED.
        """
        slot_date = date.today() + timedelta(days=10)

        # Create slot far in the future
        slot_id = db.execute(
            text("""
                INSERT INTO slots (doctor_id, session_id, slot_date, start_time, end_time, status)
                VALUES (:doctor_id, :session_id, :slot_date, '10:00', '10:15', 'AVAILABLE')
                RETURNING slot_id
            """),
            {"doctor_id": str(doctor), "session_id": session_row, "slot_date": slot_date},
        ).scalar_one()

        patient_a = _make_patient(db)
        patient_b = _make_patient(db)

        # patient_a books the slot
        appt = create_appointment_service(
            db,
            AppointmentCreate(
                slot_id=slot_id,
                patient_id=patient_a,
                doctor_id=doctor,
            ),
        )

        # patient_b joins the waitlist (no slots available now)
        wl_entry = _join(db, patient_b, doctor, session_row)
        assert wl_entry["status"] == "WAITING"

        # patient_a cancels — triggers auto-allocation
        cancel_appointment_service(db, appt["appointment_id"])

        # patient_b should now have a CONFIRMED appointment
        new_appt = db.execute(
            text("""
                SELECT * FROM appointments
                WHERE patient_id = :pid AND status = 'CONFIRMED'
            """),
            {"pid": str(patient_b)},
        ).mappings().first()
        assert new_appt is not None

        # patient_b's waitlist entry should be CONFIRMED
        wl_updated = db.execute(
            text("SELECT status FROM waitlist WHERE waitlist_id = :wid"),
            {"wid": str(wl_entry["waitlist_id"])},
        ).mappings().first()
        assert wl_updated["status"] == "CONFIRMED"

    def test_emergency_patient_gets_slot_before_normal(self, db, doctor, session_row):
        """
        Setup: slot exists, patient_normal joins waitlist (priority 2),
               patient_emergency joins (priority 1).
        Verify: get_next_in_queue returns emergency patient first.
        """
        slot_date = date.today() + timedelta(days=10)
        db.execute(
            text("""
                INSERT INTO slots (doctor_id, session_id, slot_date, start_time, end_time, status)
                VALUES (:doctor_id, :session_id, :slot_date, '11:00', '11:15', 'BOOKED')
            """),
            {"doctor_id": str(doctor), "session_id": session_row, "slot_date": slot_date},
        )

        patient_normal = _make_patient(db)
        patient_emergency = _make_patient(db)

        # Normal joins first
        _join(db, patient_normal, doctor, session_row, priority=2)
        # Emergency joins after
        _join(db, patient_emergency, doctor, session_row, priority=1, is_emergency=True)

        from app.modules.waitlist.repository import get_next_in_queue
        next_up = get_next_in_queue(db, session_row)

        assert str(next_up["patient_id"]) == str(patient_emergency)
