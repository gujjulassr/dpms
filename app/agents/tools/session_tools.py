"""
agents/tools/session_tools.py

Owns everything about session chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → session service call
"""

from datetime import date, time
from sqlalchemy.orm import Session

from app.modules.sessions.schemas import SessionCreate, SessionUpdate
from app.modules.sessions.service import (
    create_session_service,
    get_session_service,
    get_sessions_by_date_service,
    get_sessions_by_doctor_service,
    get_sessions_by_status_service,
    list_sessions_service,
    update_session_service,
)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_sessions",
            "description": "List all doctor sessions in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_by_id",
            "description": "Look up a single session by its numeric session ID.",
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
            "name": "get_sessions_by_doctor",
            "description": "List sessions for a given doctor ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                },
                "required": ["doctor_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sessions_by_date",
            "description": "List sessions for a given date in YYYY-MM-DD format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_date": {"type": "string", "description": "Session date in YYYY-MM-DD format"},
                },
                "required": ["session_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sessions_by_status",
            "description": "List sessions by status. Valid values are OPEN, FULL, CLOSED.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Session status"},
                },
                "required": ["status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_session",
            "description": (
                "Create a doctor session for a specific day and time range. "
                "Availability is calculated on-the-fly when patients book — no slots are pre-generated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                    "session_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "session_name": {"type": "string", "description": "MORNING or AFTERNOON"},
                    "start_time": {"type": "string", "description": "Start time in HH:MM or HH:MM:SS"},
                    "end_time": {"type": "string", "description": "End time in HH:MM or HH:MM:SS"},
                    "status": {"type": "string", "description": "Optional session status: OPEN, FULL, or CLOSED"},
                },
                "required": ["doctor_id", "session_date", "session_name", "start_time", "end_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_session",
            "description": "Update the status of an existing session. Use this to change a session to OPEN, FULL, or CLOSED. Closing a session also cancels confirmed appointments inside that session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"},
                    "status": {"type": "string", "description": "OPEN, FULL, or CLOSED"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_session",
            "description": "Cancel or close an entire doctor session by setting its status to CLOSED. This also cancels confirmed appointments inside that session. Use this for requests like cancel the session, close the session, or shut the session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"},
                },
                "required": ["session_id"],
            },
        },
    },
]


def execute(name: str, args: dict, db: Session):
    if name == "list_sessions":
        return list_sessions_service(db)

    if name == "get_session_by_id":
        return get_session_service(db, int(args["session_id"]))

    if name == "get_sessions_by_doctor":
        return get_sessions_by_doctor_service(db, int(args["doctor_id"]))

    if name == "get_sessions_by_date":
        return get_sessions_by_date_service(db, date.fromisoformat(args["session_date"]))

    if name == "get_sessions_by_status":
        return get_sessions_by_status_service(db, args["status"].upper())

    if name == "create_session":
        return create_session_service(
            db,
            SessionCreate(
                doctor_id=int(args["doctor_id"]),
                session_date=date.fromisoformat(args["session_date"]),
                session_name=args["session_name"].upper(),
                start_time=time.fromisoformat(args["start_time"]),
                end_time=time.fromisoformat(args["end_time"]),
                status=args.get("status", "OPEN").upper(),
            ),
        )

    if name == "update_session":
        fields = {}
        if args.get("status") is not None:
            fields["status"] = args["status"].upper()
        return update_session_service(db, int(args["session_id"]), SessionUpdate(**fields))

    if name == "cancel_session":
        return update_session_service(
            db,
            int(args["session_id"]),
            SessionUpdate(status="CLOSED"),
        )

    raise ValueError(f"Unknown session tool: {name}")
