"""
notifications/ics.py
--------------------
Generate a minimal iCalendar (.ics) calendar invite string.
No third-party library required — pure stdlib.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date, time, timedelta, timezone


def _fmt_utc(dt: datetime) -> str:
    """Format a datetime as UTC iCal timestamp: 20260325T143000Z."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _fmt_local(dt: datetime) -> str:
    """Format a datetime as local/floating iCal timestamp: 20260325T143000."""
    return dt.strftime("%Y%m%dT%H%M%S")


def build_ics(
    *,
    summary: str,
    description: str,
    location: str,
    slot_date: date | str,
    start_time: time | str,
    duration_mins: int = 30,
    organizer_email: str = "",
    attendee_email: str = "",
) -> str:
    """
    Returns a VCALENDAR string for a single appointment event.

    Parameters
    ----------
    summary         : Event title shown in the calendar app
    description     : Plain-text description body
    location        : Location string (e.g. 'DPMS Clinic')
    slot_date       : date object or ISO string 'YYYY-MM-DD'
    start_time      : time object or HH:MM[:SS] string
    duration_mins   : Appointment duration in minutes (default 30)
    organizer_email : Clinic / system email
    attendee_email  : Patient email
    """

    # Normalise inputs
    if isinstance(slot_date, str):
        slot_date = date.fromisoformat(slot_date)
    if isinstance(start_time, str):
        parts = str(start_time).split(":")
        start_time = time(int(parts[0]), int(parts[1]))

    start_dt = datetime(
        slot_date.year, slot_date.month, slot_date.day,
        start_time.hour, start_time.minute, 0,
    )
    end_dt = start_dt + timedelta(minutes=duration_mins)
    now_dt  = datetime.now(timezone.utc)
    uid     = str(uuid.uuid4())

    # Escape iCal TEXT values (commas, semicolons, newlines)
    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

    organizer_line = (
        f"ORGANIZER;CN=DPMS Clinic:mailto:{organizer_email}"
        if organizer_email else ""
    )
    attendee_line = (
        f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;"
        f"CN={attendee_email}:mailto:{attendee_email}"
        if attendee_email else ""
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DPMS//Doctor Patient Management System//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_fmt_utc(now_dt)}",
        f"DTSTART:{_fmt_local(start_dt)}",
        f"DTEND:{_fmt_local(end_dt)}",
        f"SUMMARY:{_esc(summary)}",
        f"DESCRIPTION:{_esc(description)}",
        f"LOCATION:{_esc(location)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
    ]
    if organizer_line:
        lines.append(organizer_line)
    if attendee_line:
        lines.append(attendee_line)

    lines += ["END:VEVENT", "END:VCALENDAR"]

    # iCal lines must be ≤ 75 octets; fold longer ones
    output = []
    for line in lines:
        while len(line.encode("utf-8")) > 75:
            output.append(line[:75])
            line = " " + line[75:]
        output.append(line)

    return "\r\n".join(output) + "\r\n"
