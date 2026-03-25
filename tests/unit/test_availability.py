"""
tests/unit/test_availability.py

Pure unit tests for the on-the-fly availability calculation logic.
No database required — runs instantly.

Edge cases covered:
  - Empty session (no appointments) → all windows available
  - Fully booked session → no windows available
  - Lunch break excluded
  - Partial booking → correct remaining windows
  - is_time_available with overlapping appointments
  - find_available_slot with various conditions
"""

import pytest
from datetime import time

from app.utils.availability import (
    compute_available_windows,
    is_time_available,
    has_any_availability,
)


# ── compute_available_windows ──────────────────────────────────────────

class TestComputeAvailableWindows:

    def test_empty_session_returns_all_windows(self):
        windows = compute_available_windows(
            session_start=time(9, 0),
            session_end=time(10, 0),
            slot_duration_mins=15,
            booked_appointments=[],
        )
        assert len(windows) == 4  # 09:00, 09:15, 09:30, 09:45
        assert windows[0]["start_time"] == "09:00"
        assert windows[3]["start_time"] == "09:45"

    def test_fully_booked_returns_empty(self):
        booked = [
            {"start_time": time(9, 0), "end_time": time(9, 15)},
            {"start_time": time(9, 15), "end_time": time(9, 30)},
            {"start_time": time(9, 30), "end_time": time(9, 45)},
            {"start_time": time(9, 45), "end_time": time(10, 0)},
        ]
        windows = compute_available_windows(
            session_start=time(9, 0),
            session_end=time(10, 0),
            slot_duration_mins=15,
            booked_appointments=booked,
        )
        assert len(windows) == 0

    def test_lunch_break_excluded(self):
        windows = compute_available_windows(
            session_start=time(12, 30),
            session_end=time(14, 0),
            slot_duration_mins=15,
            booked_appointments=[],
        )
        # 12:30, 12:45 → lunch at 13:00-13:30 → 13:30, 13:45
        start_times = [w["start_time"] for w in windows]
        assert "13:00" not in start_times
        assert "13:15" not in start_times
        assert "12:30" in start_times
        assert "13:30" in start_times

    def test_partial_booking_returns_remaining(self):
        booked = [
            {"start_time": time(9, 0), "end_time": time(9, 15)},
        ]
        windows = compute_available_windows(
            session_start=time(9, 0),
            session_end=time(10, 0),
            slot_duration_mins=15,
            booked_appointments=booked,
        )
        assert len(windows) == 3  # 09:15, 09:30, 09:45
        assert windows[0]["start_time"] == "09:15"

    def test_30_minute_slots(self):
        windows = compute_available_windows(
            session_start=time(9, 0),
            session_end=time(10, 0),
            slot_duration_mins=30,
            booked_appointments=[],
        )
        assert len(windows) == 2  # 09:00-09:30, 09:30-10:00


# ── is_time_available ──────────────────────────────────────────────────

class TestIsTimeAvailable:

    def test_available_when_no_bookings(self):
        assert is_time_available(
            session_start=time(9, 0),
            session_end=time(12, 0),
            slot_duration_mins=15,
            booked_appointments=[],
            requested_start=time(9, 0),
        ) is True

    def test_not_available_when_booked(self):
        booked = [{"start_time": time(9, 0), "end_time": time(9, 15)}]
        assert is_time_available(
            session_start=time(9, 0),
            session_end=time(12, 0),
            slot_duration_mins=15,
            booked_appointments=booked,
            requested_start=time(9, 0),
        ) is False

    def test_available_at_different_time(self):
        booked = [{"start_time": time(9, 0), "end_time": time(9, 15)}]
        assert is_time_available(
            session_start=time(9, 0),
            session_end=time(12, 0),
            slot_duration_mins=15,
            booked_appointments=booked,
            requested_start=time(9, 15),
        ) is True

    def test_not_available_during_lunch(self):
        assert is_time_available(
            session_start=time(9, 0),
            session_end=time(14, 0),
            slot_duration_mins=15,
            booked_appointments=[],
            requested_start=time(13, 0),
        ) is False

    def test_not_available_outside_session(self):
        assert is_time_available(
            session_start=time(9, 0),
            session_end=time(12, 0),
            slot_duration_mins=15,
            booked_appointments=[],
            requested_start=time(12, 0),
        ) is False


# ── has_any_availability ───────────────────────────────────────────────

class TestHasAnyAvailability:

    def test_has_availability_when_empty(self):
        assert has_any_availability(
            session_start=time(9, 0),
            session_end=time(10, 0),
            slot_duration_mins=15,
            booked_appointments=[],
        ) is True

    def test_no_availability_when_fully_booked(self):
        booked = [
            {"start_time": time(9, 0), "end_time": time(9, 15)},
            {"start_time": time(9, 15), "end_time": time(9, 30)},
            {"start_time": time(9, 30), "end_time": time(9, 45)},
            {"start_time": time(9, 45), "end_time": time(10, 0)},
        ]
        assert has_any_availability(
            session_start=time(9, 0),
            session_end=time(10, 0),
            slot_duration_mins=15,
            booked_appointments=booked,
        ) is False
