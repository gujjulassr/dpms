"""
tests/unit/test_slot_search.py

Pure unit tests for the binary search and slot suggestion logic.
No database required — runs instantly.

Edge cases covered:
  - Exact match found and available
  - Exact match found but BOOKED → suggest next
  - Exact match found but BOOKED, rest of session BOOKED → cross-session
  - Target time doesn't exist in any slot
  - All slots fully booked
  - Empty slot list
  - No time preference → earliest available
  - Single slot scenarios
  - Emergency / last slot edge
"""

import pytest

from app.utils.slot_search import (
    binary_search_slot_by_time,
    find_next_available_from,
    find_next_available_slot,
)


# ── Helpers ───────────────────────────────────────────────────────────

def make_slot(start_time: str, status: str, session_id: int = 1, slot_id: str = None) -> dict:
    return {
        "slot_id": slot_id or f"uuid-{start_time}",
        "start_time": start_time,
        "status": status,
        "session_id": session_id,
    }


# ── binary_search_slot_by_time ────────────────────────────────────────

class TestBinarySearch:

    def test_finds_exact_match_at_start(self):
        slots = [make_slot("09:00", "AVAILABLE"), make_slot("09:15", "BOOKED")]
        assert binary_search_slot_by_time(slots, "09:00") == 0

    def test_finds_exact_match_at_end(self):
        slots = [make_slot("09:00", "AVAILABLE"), make_slot("09:15", "BOOKED"), make_slot("09:30", "AVAILABLE")]
        assert binary_search_slot_by_time(slots, "09:30") == 2

    def test_finds_exact_match_in_middle(self):
        slots = [
            make_slot("09:00", "AVAILABLE"),
            make_slot("09:15", "BOOKED"),
            make_slot("09:30", "AVAILABLE"),
            make_slot("09:45", "BOOKED"),
            make_slot("10:00", "AVAILABLE"),
        ]
        assert binary_search_slot_by_time(slots, "09:30") == 2

    def test_returns_minus_one_when_not_found(self):
        slots = [make_slot("09:00", "AVAILABLE"), make_slot("09:15", "BOOKED"), make_slot("09:30", "AVAILABLE")]
        assert binary_search_slot_by_time(slots, "11:00") == -1

    def test_returns_minus_one_on_empty_list(self):
        assert binary_search_slot_by_time([], "09:00") == -1

    def test_single_slot_found(self):
        slots = [make_slot("10:00", "AVAILABLE")]
        assert binary_search_slot_by_time(slots, "10:00") == 0

    def test_single_slot_not_found(self):
        slots = [make_slot("10:00", "AVAILABLE")]
        assert binary_search_slot_by_time(slots, "11:00") == -1

    def test_lunch_time_not_in_slots(self):
        # 13:00-13:30 is always blocked (lunch), should never appear
        slots = [make_slot("12:45", "AVAILABLE"), make_slot("13:30", "AVAILABLE")]
        assert binary_search_slot_by_time(slots, "13:00") == -1

    def test_handles_hh_mm_ss_format(self):
        slots = [make_slot("09:00", "AVAILABLE"), make_slot("09:15", "BOOKED")]
        # Some DB drivers return 'HH:MM:SS'
        assert binary_search_slot_by_time(slots, "09:00") == 0


# ── find_next_available_from ──────────────────────────────────────────

class TestFindNextAvailableFrom:

    def test_returns_first_available_from_start(self):
        slots = [make_slot("09:00", "BOOKED"), make_slot("09:15", "AVAILABLE")]
        result = find_next_available_from(slots, 0)
        assert result["start_time"] == "09:15"

    def test_returns_none_when_all_booked(self):
        slots = [make_slot("09:00", "BOOKED"), make_slot("09:15", "BOOKED")]
        assert find_next_available_from(slots, 0) is None

    def test_skips_cancelled_slots(self):
        slots = [
            make_slot("09:00", "CANCELLED"),
            make_slot("09:15", "BOOKED"),
            make_slot("09:30", "AVAILABLE"),
        ]
        result = find_next_available_from(slots, 0)
        assert result["start_time"] == "09:30"

    def test_from_index_beyond_end(self):
        slots = [make_slot("09:00", "AVAILABLE")]
        assert find_next_available_from(slots, 5) is None


# ── find_next_available_slot ──────────────────────────────────────────

class TestFindNextAvailableSlot:

    # ── Exact slot available ──────────────────────────────────────────

    def test_exact_slot_available(self):
        slots = [make_slot("09:00", "BOOKED"), make_slot("09:15", "AVAILABLE")]
        result = find_next_available_slot(slots, "09:15")
        assert result["exact"]["start_time"] == "09:15"
        assert result["same_session"] is True

    # ── Slot taken, same session has next available ───────────────────

    def test_slot_taken_next_available_same_session(self):
        slots = [
            make_slot("09:00", "BOOKED", session_id=1),
            make_slot("09:15", "BOOKED", session_id=1),
            make_slot("09:30", "AVAILABLE", session_id=1),
        ]
        result = find_next_available_slot(slots, "09:15")
        assert result["exact"] is None
        assert result["suggested"]["start_time"] == "09:30"
        assert result["same_session"] is True

    # ── Slot taken, entire session booked → cross-session ────────────

    def test_cross_session_when_original_session_full(self):
        slots = [
            make_slot("09:00", "BOOKED", session_id=1),
            make_slot("09:15", "BOOKED", session_id=1),
            make_slot("14:00", "AVAILABLE", session_id=2),
            make_slot("14:15", "AVAILABLE", session_id=2),
        ]
        result = find_next_available_slot(slots, "09:15")
        assert result["exact"] is None
        assert result["suggested"]["start_time"] == "14:00"
        assert result["same_session"] is False
        assert result["original_session_id"] == 1
        assert result["suggested_session_id"] == 2

    # ── Target time doesn't exist ─────────────────────────────────────

    def test_time_not_in_any_slot(self):
        slots = [make_slot("09:00", "BOOKED"), make_slot("09:15", "AVAILABLE")]
        result = find_next_available_slot(slots, "11:00")
        assert result["exact"] is None
        assert result["suggested"]["start_time"] == "09:15"

    # ── All slots fully booked ────────────────────────────────────────

    def test_fully_booked_returns_none_suggested(self):
        slots = [
            make_slot("09:00", "BOOKED", session_id=1),
            make_slot("09:15", "BOOKED", session_id=1),
            make_slot("14:00", "BOOKED", session_id=2),
        ]
        result = find_next_available_slot(slots, "09:00")
        assert result["suggested"] is None
        assert result["same_session"] is False

    # ── Empty list ────────────────────────────────────────────────────

    def test_empty_slot_list(self):
        result = find_next_available_slot([], "09:00")
        assert result["exact"] is None
        assert result["suggested"] is None
        assert "No slots exist" in result["message"]

    # ── No time preference ────────────────────────────────────────────

    def test_no_preference_returns_earliest_available(self):
        slots = [
            make_slot("09:00", "BOOKED"),
            make_slot("09:15", "BOOKED"),
            make_slot("09:30", "AVAILABLE"),
        ]
        result = find_next_available_slot(slots)
        assert result["suggested"]["start_time"] == "09:30"

    def test_no_preference_all_booked(self):
        slots = [make_slot("09:00", "BOOKED"), make_slot("09:15", "BOOKED")]
        result = find_next_available_slot(slots)
        assert result["suggested"] is None

    # ── Single slot scenarios ─────────────────────────────────────────

    def test_single_available_slot(self):
        slots = [make_slot("09:00", "AVAILABLE")]
        result = find_next_available_slot(slots, "09:00")
        assert result["exact"]["start_time"] == "09:00"

    def test_single_booked_slot(self):
        slots = [make_slot("09:00", "BOOKED")]
        result = find_next_available_slot(slots, "09:00")
        assert result["exact"] is None
        assert result["suggested"] is None

    # ── Last slot in session is available ─────────────────────────────

    def test_last_slot_available_after_all_others_booked(self):
        slots = [
            make_slot("09:00", "BOOKED"),
            make_slot("09:15", "BOOKED"),
            make_slot("09:30", "BOOKED"),
            make_slot("09:45", "AVAILABLE"),
        ]
        result = find_next_available_slot(slots, "09:00")
        assert result["suggested"]["start_time"] == "09:45"
        assert result["same_session"] is True
