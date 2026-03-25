"""
agents/tools/waitlist_tools.py

Owns everything about waitlist chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → waitlist service call
"""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.waitlist.schemas import WaitlistCreate
from app.modules.waitlist.service import (
    get_waitlist_by_patient_service,
    get_waitlist_by_session_service,
    get_waitlist_entry_service,
    join_waitlist_service,
    leave_waitlist_service,
    list_waitlist_service,
)


def _as_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"Please provide a valid {field_name}.")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_waitlist",
            "description": "List all waitlist entries in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_waitlist_entry",
            "description": "Look up a single waitlist entry by its UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "waitlist_id": {"type": "string", "description": "Waitlist entry UUID"},
                },
                "required": ["waitlist_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_waitlist_by_patient",
            "description": "Get all waitlist entries for a given patient UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient UUID"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_waitlist_by_session",
            "description": "Get all waitlist entries for a given session (ordered by priority then join time).",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "join_waitlist",
            "description": (
                "Add a patient to the waitlist for a fully-booked session. "
                "Only call this after confirming no available slots exist. "
                "priority: 2=NORMAL (default), 1=EMERGENCY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient UUID"},
                    "doctor_id": {"type": "string", "description": "Doctor UUID"},
                    "session_id": {"type": "integer", "description": "Session ID"},
                    "waitlist_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "priority": {
                        "type": "integer",
                        "description": "1=EMERGENCY, 2=NORMAL (default 2)",
                    },
                    "is_emergency": {"type": "boolean", "description": "True if emergency case"},
                    "emergency_reason": {
                        "type": "string",
                        "description": "Reason for emergency (required if is_emergency=true)",
                    },
                },
                "required": ["patient_id", "doctor_id", "session_id", "waitlist_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leave_waitlist",
            "description": "Remove (cancel) a patient from the waitlist by waitlist entry UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "waitlist_id": {"type": "string", "description": "Waitlist entry UUID"},
                },
                "required": ["waitlist_id"],
            },
        },
    },
]


def execute(name: str, args: dict, db: Session):
    if name == "list_waitlist":
        return list_waitlist_service(db)

    if name == "get_waitlist_entry":
        return get_waitlist_entry_service(db, _as_uuid(args["waitlist_id"], "waitlist_id"))

    if name == "get_waitlist_by_patient":
        return get_waitlist_by_patient_service(db, _as_uuid(args["patient_id"], "patient_id"))

    if name == "get_waitlist_by_session":
        return get_waitlist_by_session_service(db, int(args["session_id"]))

    if name == "join_waitlist":
        return join_waitlist_service(
            db,
            WaitlistCreate(
                patient_id=_as_uuid(args["patient_id"], "patient_id"),
                doctor_id=_as_uuid(args["doctor_id"], "doctor_id"),
                session_id=int(args["session_id"]),
                waitlist_date=date.fromisoformat(args["waitlist_date"]),
                priority=args.get("priority", 2),
                is_emergency=args.get("is_emergency", False),
                emergency_reason=args.get("emergency_reason"),
            ),
        )

    if name == "leave_waitlist":
        return leave_waitlist_service(db, _as_uuid(args["waitlist_id"], "waitlist_id"))

    raise ValueError(f"Unknown waitlist tool: {name}")
