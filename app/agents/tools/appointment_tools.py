"""
agents/tools/appointment_tools.py

Owns everything about appointment chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → appointment service call
"""

from datetime import date, time
from sqlalchemy.orm import Session

from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import (
    cancel_appointment_service,
    create_appointment_service,
    get_active_appointments_by_date_service,
    get_available_times_by_doctor_and_date_service,
    get_earliest_available_time_by_doctor_service,
    get_appointment_service,
    get_appointments_by_date_service,
    get_appointments_by_doctor_service,
    get_appointments_by_patient_service,
    get_appointments_by_status_service,
    get_upcoming_active_appointments_service,
    list_appointments_service,
    suggest_available_time_service,
    update_appointment_service,
)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_appointments",
            "description": "List all appointments in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointment_by_id",
            "description": "Look up a single appointment by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "Appointment ID"},
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointments_by_patient",
            "description": "List appointments for a given patient ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer", "description": "Patient ID"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointments_by_doctor",
            "description": "List appointments for a given doctor ID.",
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
            "name": "get_appointments_by_status",
            "description": "List appointments by status. Valid values are CONFIRMED, CANCELLED, COMPLETED, NO_SHOW.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Appointment status"},
                },
                "required": ["status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_active_appointments",
            "description": "List upcoming active appointments. Active means confirmed appointments in the future from the current time onward.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_appointments_today",
            "description": "List today's upcoming active appointments. Active means confirmed appointments later today from the current time onward.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointments_by_date",
            "description": "List appointments for a given date in YYYY-MM-DD format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_date": {"type": "string", "description": "Appointment date in YYYY-MM-DD format"},
                },
                "required": ["appointment_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_times_by_doctor_and_date",
            "description": (
                "List all currently available time slots for a given doctor on a specific date. "
                "Use this when the user asks for available slots, open slots, active slots, or free times."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                    "appointment_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": ["doctor_id", "appointment_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_earliest_available_time_by_doctor",
            "description": (
                "Find the earliest future available time for a given doctor from a start date onward. "
                "Use this when the user asks for the earliest appointment, next available appointment, or soonest slot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                    "start_date": {
                        "type": "string",
                        "description": "Start searching from this date in YYYY-MM-DD format (optional). Defaults to today.",
                    },
                },
                "required": ["doctor_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_available_time",
            "description": (
                "Find an available time for a doctor on a given date. "
                "If preferred_time (HH:MM) is given, checks that exact time first — if taken, "
                "returns the next available time automatically. "
                "Always call this before create_appointment when booking by doctor name and time. "
                "Do not use this to answer questions asking for all available times or earliest future appointments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                    "appointment_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred start time in HH:MM format (optional)",
                    },
                },
                "required": ["doctor_id", "appointment_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": (
                "Create a confirmed appointment by booking an available time for a patient and doctor. "
                "Requires session_id and start_time. Call suggest_available_time first to find the right session and time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID from suggest_available_time"},
                    "patient_id": {"type": "integer", "description": "Patient ID"},
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                    "appointment_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "start_time": {"type": "string", "description": "Start time in HH:MM format"},
                },
                "required": ["session_id", "patient_id", "doctor_id", "appointment_date", "start_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_appointment",
            "description": "Update one or more fields on an existing appointment. Only provide fields that need to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "Appointment ID"},
                    "status": {"type": "string", "description": "CONFIRMED, CANCELLED, COMPLETED, or NO_SHOW"},
                    "reminder_24hr_sent": {"type": "boolean"},
                    "reminder_2hr_sent": {"type": "boolean"},
                    "confirmed_at": {"type": "string", "description": "ISO datetime"},
                    "cancelled_at": {"type": "string", "description": "ISO datetime"},
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an appointment by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "Appointment ID"},
                },
                "required": ["appointment_id"],
            },
        },
    },
]


def execute(name: str, args: dict, db: Session):
    if name == "list_appointments":
        return list_appointments_service(db)

    if name == "get_appointment_by_id":
        return get_appointment_service(db, int(args["appointment_id"]))

    if name == "get_appointments_by_patient":
        return get_appointments_by_patient_service(db, int(args["patient_id"]))

    if name == "get_appointments_by_doctor":
        return get_appointments_by_doctor_service(db, int(args["doctor_id"]))

    if name == "get_appointments_by_status":
        return get_appointments_by_status_service(db, args["status"].upper())

    if name == "get_upcoming_active_appointments":
        pid = int(args["patient_id"]) if args.get("patient_id") else None
        return get_upcoming_active_appointments_service(db, pid)

    if name == "get_active_appointments_today":
        pid = int(args["patient_id"]) if args.get("patient_id") else None
        return get_active_appointments_by_date_service(db, date.today(), pid)

    if name == "get_appointments_by_date":
        return get_appointments_by_date_service(db, date.fromisoformat(args["appointment_date"]))

    if name == "get_available_times_by_doctor_and_date":
        return get_available_times_by_doctor_and_date_service(
            db,
            int(args["doctor_id"]),
            date.fromisoformat(args["appointment_date"]),
        )

    if name == "get_earliest_available_time_by_doctor":
        start_date = date.fromisoformat(args["start_date"]) if args.get("start_date") else None
        return get_earliest_available_time_by_doctor_service(
            db,
            int(args["doctor_id"]),
            start_date,
        )

    if name == "suggest_available_time":
        return suggest_available_time_service(
            db,
            int(args["doctor_id"]),
            date.fromisoformat(args["appointment_date"]),
            args.get("preferred_time"),
        )

    if name == "create_appointment":
        return create_appointment_service(
            db,
            AppointmentCreate(
                session_id=int(args["session_id"]),
                patient_id=int(args["patient_id"]),
                doctor_id=int(args["doctor_id"]),
                appointment_date=date.fromisoformat(args["appointment_date"]),
                start_time=time.fromisoformat(args["start_time"]),
            ),
        )

    if name == "update_appointment":
        fields = {}
        if args.get("status") is not None:
            fields["status"] = args["status"]
        if args.get("reminder_24hr_sent") is not None:
            fields["reminder_24hr_sent"] = args["reminder_24hr_sent"]
        if args.get("reminder_2hr_sent") is not None:
            fields["reminder_2hr_sent"] = args["reminder_2hr_sent"]
        if args.get("confirmed_at") is not None:
            fields["confirmed_at"] = args["confirmed_at"]
        if args.get("cancelled_at") is not None:
            fields["cancelled_at"] = args["cancelled_at"]

        return update_appointment_service(
            db,
            int(args["appointment_id"]),
            AppointmentUpdate(**fields),
        )

    if name == "cancel_appointment":
        return cancel_appointment_service(db, int(args["appointment_id"]))

    raise ValueError(f"Unknown appointment tool: {name}")
