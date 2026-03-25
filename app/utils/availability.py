"""
utils/availability.py

On-the-fly availability calculator.

Instead of pre-generating slot rows, this module computes available
time windows from the session time range minus existing appointments,
skipping the lunch break (13:00–13:30).

Used by:
  - appointments/service.py  (booking & suggestion logic)
  - waitlist/service.py      (check if session is full before waitlisting)
"""

from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional

# Lunch break — hardcoded clinic rule
LUNCH_START = time(13, 0)
LUNCH_END   = time(13, 30)


# ── Helpers ──────────────────────────────────────────────────────────

def _parse_time(value) -> time:
    """Normalise to datetime.time. Accepts time, 'HH:MM', or 'HH:MM:SS'."""
    if isinstance(value, time):
        return value
    parts = str(value).split(":")
    return time(int(parts[0]), int(parts[1]))


def _time_to_minutes(t: time) -> int:
    """Convert time to minutes since midnight for easy arithmetic."""
    return t.hour * 60 + t.minute


def _minutes_to_time(mins: int) -> time:
    """Convert minutes since midnight back to time."""
    return time(mins // 60, mins % 60)


def _overlaps_lunch(start_mins: int, end_mins: int) -> bool:
    """Check if a time window overlaps the lunch break."""
    lunch_start = _time_to_minutes(LUNCH_START)
    lunch_end = _time_to_minutes(LUNCH_END)
    return start_mins < lunch_end and end_mins > lunch_start


# ── Core: Compute Available Windows ──────────────────────────────────

def compute_available_windows(
    *,
    session_start: time,
    session_end: time,
    slot_duration_mins: int,
    booked_appointments: List[Dict],
) -> List[Dict]:
    """
    Given a session time range and a list of existing confirmed appointments,
    compute all available time windows of the given duration.

    Parameters
    ----------
    session_start       : Session start time (e.g. 09:00)
    session_end         : Session end time (e.g. 13:00)
    slot_duration_mins  : Doctor's appointment duration in minutes (e.g. 15)
    booked_appointments : List of appointment dicts with 'start_time' and 'end_time'

    Returns
    -------
    List of dicts: [{"start_time": "09:00", "end_time": "09:15"}, ...]
    Sorted by start_time.
    """
    start_mins = _time_to_minutes(_parse_time(session_start))
    end_mins = _time_to_minutes(_parse_time(session_end))
    duration = slot_duration_mins

    # Collect all booked time ranges as (start_mins, end_mins) tuples
    booked_ranges = []
    for appt in booked_appointments:
        appt_start = _time_to_minutes(_parse_time(appt["start_time"]))
        appt_end = _time_to_minutes(_parse_time(appt["end_time"]))
        booked_ranges.append((appt_start, appt_end))

    # Add lunch break as a booked range
    lunch_start = _time_to_minutes(LUNCH_START)
    lunch_end = _time_to_minutes(LUNCH_END)
    if start_mins < lunch_end and end_mins > lunch_start:
        booked_ranges.append((lunch_start, lunch_end))

    # Sort by start time
    booked_ranges.sort()

    # Generate candidate windows and check against booked ranges
    available = []
    current = start_mins

    while current + duration <= end_mins:
        candidate_end = current + duration

        # Check if this window overlaps any booked range
        is_free = True
        for b_start, b_end in booked_ranges:
            if current < b_end and candidate_end > b_start:
                # Overlap — skip to end of this booked range
                is_free = False
                current = b_end
                break

        if is_free:
            available.append({
                "start_time": _minutes_to_time(current).isoformat()[:5],
                "end_time": _minutes_to_time(candidate_end).isoformat()[:5],
            })
            current = candidate_end
        # If not free, current was already moved past the blocking range

    return available


def is_time_available(
    *,
    requested_start: time,
    slot_duration_mins: int,
    session_start: time,
    session_end: time,
    booked_appointments: List[Dict],
) -> bool:
    """
    Check if a specific time is available for booking.

    Returns True if:
      1. The requested time falls within session bounds
      2. It doesn't overlap lunch
      3. It doesn't overlap any existing confirmed appointment
    """
    req_start = _time_to_minutes(_parse_time(requested_start))
    req_end = req_start + slot_duration_mins
    sess_start = _time_to_minutes(_parse_time(session_start))
    sess_end = _time_to_minutes(_parse_time(session_end))

    # Must be within session bounds
    if req_start < sess_start or req_end > sess_end:
        return False

    # Must not overlap lunch
    if _overlaps_lunch(req_start, req_end):
        return False

    # Must not overlap any booked appointment
    for appt in booked_appointments:
        appt_start = _time_to_minutes(_parse_time(appt["start_time"]))
        appt_end = _time_to_minutes(_parse_time(appt["end_time"]))
        if req_start < appt_end and req_end > appt_start:
            return False

    return True


def has_any_availability(
    *,
    session_start: time,
    session_end: time,
    slot_duration_mins: int,
    booked_appointments: List[Dict],
) -> bool:
    """
    Quick check: is there at least one open window in this session?
    Used by waitlist to decide if patient should book directly vs. join waitlist.
    """
    windows = compute_available_windows(
        session_start=session_start,
        session_end=session_end,
        slot_duration_mins=slot_duration_mins,
        booked_appointments=booked_appointments,
    )
    return len(windows) > 0


# ── Suggestion Logic (replaces slot_search.py) ───────────────────────

def find_available_slot(
    *,
    sessions: List[Dict],
    booked_by_session: Dict[int, List[Dict]],
    slot_duration_mins: int,
    preferred_time_str: Optional[str] = None,
) -> Dict:
    """
    Find an available time across one or more sessions on a date.

    Replaces the old find_next_available_slot() that used binary search
    on pre-generated slots.

    Parameters
    ----------
    sessions           : List of session dicts (with session_id, start_time, end_time, session_name)
    booked_by_session  : Dict mapping session_id → list of booked appointment dicts
    slot_duration_mins : Duration in minutes
    preferred_time_str : Optional preferred time as 'HH:MM'

    Returns
    -------
    Dict with keys: exact, suggested, same_session, original_session_id,
                    suggested_session_id, message
    """
    if not sessions:
        return {
            "exact": None,
            "suggested": None,
            "same_session": True,
            "original_session_id": None,
            "original_session_name": None,
            "suggested_session_id": None,
            "message": "No sessions exist for this doctor on that date.",
        }

    # Compute all available windows across all sessions
    all_windows = []  # (session_id, session_name, window_dict)
    for sess in sessions:
        sid = sess["session_id"]
        booked = booked_by_session.get(sid, [])
        windows = compute_available_windows(
            session_start=sess["start_time"],
            session_end=sess["end_time"],
            slot_duration_mins=slot_duration_mins,
            booked_appointments=booked,
        )
        for w in windows:
            all_windows.append((sid, sess.get("session_name", ""), w))

    if not all_windows:
        return {
            "exact": None,
            "suggested": None,
            "same_session": True,
            "original_session_id": None,
            "original_session_name": None,
            "suggested_session_id": None,
            "message": "All sessions are fully booked for this doctor on that date.",
        }

    if preferred_time_str:
        preferred = _parse_time(preferred_time_str)

        # Find which session the preferred time belongs to
        original_session_id = None
        original_session_name = None
        for sess in sessions:
            s_start = _parse_time(sess["start_time"])
            s_end = _parse_time(sess["end_time"])
            if s_start <= preferred < s_end:
                original_session_id = sess["session_id"]
                original_session_name = sess.get("session_name", "")
                break

        # Check if the preferred time is among available windows
        for sid, sname, w in all_windows:
            if _parse_time(w["start_time"]) == preferred:
                return {
                    "exact": {**w, "session_id": sid, "session_name": sname},
                    "suggested": {**w, "session_id": sid, "session_name": sname},
                    "same_session": True,
                    "original_session_id": sid,
                    "original_session_name": sname,
                    "suggested_session_id": sid,
                    "message": f"Time at {preferred_time_str} is available.",
                }

        # Preferred time is taken — find next available
        # Priority: 1) same session after preferred time
        #           2) any session after preferred time
        #           3) earliest overall
        suggested = None
        suggested_sid = None
        suggested_sname = None

        # 1) Try same session first
        if original_session_id is not None:
            for sid, sname, w in all_windows:
                if sid != original_session_id:
                    continue
                w_time = _parse_time(w["start_time"])
                if w_time > preferred:
                    suggested = w
                    suggested_sid = sid
                    suggested_sname = sname
                    break

        # 2) If nothing in same session, try any session after preferred time
        if suggested is None:
            for sid, sname, w in all_windows:
                w_time = _parse_time(w["start_time"])
                if w_time > preferred:
                    suggested = w
                    suggested_sid = sid
                    suggested_sname = sname
                    break

        # 3) If still nothing after preferred time, take earliest overall
        if suggested is None:
            suggested_sid, suggested_sname, suggested = all_windows[0]

        same_session = (suggested_sid == original_session_id) if original_session_id else True

        if same_session:
            msg = (
                f"Time at {preferred_time_str} is taken. "
                f"Next available in the same session: {suggested['start_time']}."
            )
        else:
            orig_name = original_session_name or "the requested session"
            msg = (
                f"Time at {preferred_time_str} is taken and the {orig_name} session is fully booked. "
                f"The nearest available time is {suggested['start_time']} "
                f"in the {suggested_sname} session. "
                f"You can also join the waitlist for the {orig_name} session "
                f"(original_session_id={original_session_id})."
            )

        return {
            "exact": None,
            "suggested": {**suggested, "session_id": suggested_sid, "session_name": suggested_sname},
            "same_session": same_session,
            "original_session_id": original_session_id,
            "original_session_name": original_session_name,
            "suggested_session_id": suggested_sid,
            "message": msg,
        }

    else:
        # No preference — return earliest available
        sid, sname, w = all_windows[0]
        return {
            "exact": {**w, "session_id": sid, "session_name": sname},
            "suggested": {**w, "session_id": sid, "session_name": sname},
            "same_session": True,
            "original_session_id": sid,
            "original_session_name": sname,
            "suggested_session_id": sid,
            "message": f"Earliest available time: {w['start_time']}.",
        }
