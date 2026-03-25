"""
utils/slot_search.py

Binary search and next-available-slot logic for sorted slot lists.

Slots within a session are always ordered by start_time (the slot
generator loops in fixed 15-min increments), so binary search is the
correct algorithm for finding a target time in O(log n) rather than
scanning all slots linearly.
"""

from datetime import time
from typing import List, Optional


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _parse_time(value) -> time:
    """
    Normalise a start_time value to a datetime.time object.
    Accepts: time object, 'HH:MM', or 'HH:MM:SS' strings.
    """
    if isinstance(value, time):
        return value
    parts = str(value).split(":")
    return time(int(parts[0]), int(parts[1]))


# ──────────────────────────────────────────────────────────────────────
# Core algorithm: Binary Search
# ──────────────────────────────────────────────────────────────────────

def binary_search_slot_by_time(slots: List[dict], target_time_str: str) -> int:
    """
    Binary search on a list of slot dicts sorted by start_time.

    Args:
        slots:           Sorted list of slot dicts (start_time ascending).
        target_time_str: Target time as 'HH:MM' string.

    Returns:
        Index of the matching slot, or -1 if no slot starts at that time.

    Complexity: O(log n)  vs  O(n) for a linear scan.
    """
    target = _parse_time(target_time_str)
    low, high = 0, len(slots) - 1

    while low <= high:
        mid = (low + high) // 2
        mid_time = _parse_time(slots[mid]["start_time"])

        if mid_time == target:
            return mid          # exact match found
        elif mid_time < target:
            low = mid + 1       # target is in the right half
        else:
            high = mid - 1      # target is in the left half

    return -1  # no slot starts at exactly that time


# ──────────────────────────────────────────────────────────────────────
# Next-available forward scan (runs after binary search)
# ──────────────────────────────────────────────────────────────────────

def find_next_available_from(slots: List[dict], from_index: int) -> Optional[dict]:
    """
    Starting at from_index, scan forward and return the first AVAILABLE slot.
    Returns None if every remaining slot is BOOKED/CANCELLED.
    """
    for i in range(from_index, len(slots)):
        if slots[i]["status"] == "AVAILABLE":
            return slots[i]
    return None


# ──────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────

def find_next_available_slot(
    slots: List[dict],
    preferred_time_str: str = None,
) -> dict:
    """
    Main function used by suggest_available_slot_service.

    Flow:
      1. If preferred_time given:
         a. Binary-search for that exact slot.
         b. If found and AVAILABLE  → return it (same session, book directly).
         c. If found but BOOKED     → forward-scan from next index for first AVAILABLE.
         d. If not found at all     → forward-scan from index=0 for first AVAILABLE.
      2. If no preferred_time → return first AVAILABLE slot in the list.

    Returns a dict:
      {
        "exact":                slot dict if the requested time was available, else None,
        "suggested":            next available slot dict, or None if fully booked,
        "same_session":         True if suggested is in the same session as the preferred slot,
        "original_session_id":  session_id of the preferred slot (int or None),
        "suggested_session_id": session_id of the suggested slot (int or None),
        "message":              human-readable status string,
      }

    When same_session is False the agent must offer the patient three choices:
      (1) book the suggested slot in the different session,
      (2) join the waitlist for the original session,
      (3) join the waitlist for the suggested/next session.
    The patient decides — nothing is booked or waitlisted automatically.
    """
    if not slots:
        return {
            "exact": None,
            "suggested": None,
            "same_session": True,
            "original_session_id": None,
            "suggested_session_id": None,
            "message": "No slots exist for this doctor on that date.",
        }

    if preferred_time_str:
        index = binary_search_slot_by_time(slots, preferred_time_str)

        if index == -1:
            # No slot starts at that exact time — find first available from beginning
            suggested = find_next_available_from(slots, 0)
            original_session_id = None  # no target slot found, so no session to anchor to
            suggested_session_id = suggested["session_id"] if suggested else None
            return {
                "exact": None,
                "suggested": suggested,
                "same_session": True,  # no original session to compare against
                "original_session_id": original_session_id,
                "suggested_session_id": suggested_session_id,
                "message": (
                    f"No slot exists at {preferred_time_str}. "
                    f"Next available: {suggested['start_time'] if suggested else 'none — fully booked'}."
                ),
            }

        target_slot = slots[index]
        original_session_id = target_slot["session_id"]

        if target_slot["status"] == "AVAILABLE":
            return {
                "exact": target_slot,
                "suggested": target_slot,
                "same_session": True,
                "original_session_id": original_session_id,
                "suggested_session_id": original_session_id,
                "message": f"Slot at {preferred_time_str} is available.",
            }

        # Slot is BOOKED — scan forward for next available
        suggested = find_next_available_from(slots, index + 1)
        suggested_session_id = suggested["session_id"] if suggested else None
        same_session = (suggested_session_id == original_session_id) if suggested else False

        if suggested is None:
            msg = (
                f"Slot at {preferred_time_str} is taken and no further slots are available "
                f"for this doctor on that date."
            )
        elif same_session:
            msg = (
                f"Slot at {preferred_time_str} is taken. "
                f"Next available in the same session: {suggested['start_time']}."
            )
        else:
            msg = (
                f"Slot at {preferred_time_str} is taken and the rest of that session is fully booked. "
                f"The earliest available slot is {suggested['start_time']} "
                f"in a different session (session_id={suggested_session_id})."
            )

        return {
            "exact": None,
            "suggested": suggested,
            "same_session": same_session,
            "original_session_id": original_session_id,
            "suggested_session_id": suggested_session_id,
            "message": msg,
        }

    else:
        # No time preference — return earliest available slot
        suggested = find_next_available_from(slots, 0)
        session_id = suggested["session_id"] if suggested else None
        return {
            "exact": suggested,
            "suggested": suggested,
            "same_session": True,
            "original_session_id": session_id,
            "suggested_session_id": session_id,
            "message": (
                f"Earliest available slot: {suggested['start_time'] if suggested else 'none — fully booked'}."
            ),
        }
