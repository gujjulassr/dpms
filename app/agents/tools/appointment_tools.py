"""
agents/tools/appointment_tools.py

Owns everything about appointment chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → appointment service call
"""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import (
    cancel_appointment_service,
    create_appointment_service,
    get_active_appointments_by_date_service,
    get_appointment_service,
    get_appointments_by_date_service,
    get_appointments_by_doctor_service,
    get_appointments_by_patient_service,
    get_appointments_by_status_service,
    get_upcoming_active_appointments_service,
    list_appointments_service,
    suggest_available_slot_service,
    update_appointment_service,
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
            "name": "list_appointments",
            "description": "List all appointments in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointment_by_id",
            "description": "Look up a single appointment by its UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment UUID"},
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointments_by_patient",
            "description": "List appointments for a given patient UUID.",
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
            "name": "get_appointments_by_doctor",
            "description": "List appointments for a given doctor UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor UUID"},
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
            "name": "suggest_available_slot",
            "description": (
                "Find an available slot for a doctor on a given date using binary search. "
                "If preferred_time (HH:MM) is given, checks that exact slot first — if taken, "
                "returns the next available slot automatically. "
                "Always call this before create_appointment when booking by doctor name and time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor UUID"},
                    "slot_date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred start time in HH:MM format (optional)",
                    },
                },
                "required": ["doctor_id", "slot_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Create a confirmed appointment by booking an available slot for a patient and doctor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "string", "description": "Slot UUID"},
                    "patient_id": {"type": "string", "description": "Patient UUID"},
                    "doctor_id": {"type": "string", "description": "Doctor UUID"},
                },
                "required": ["slot_id", "patient_id", "doctor_id"],
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
                    "appointment_id": {"type": "string", "description": "Appointment UUID"},
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
            "description": "Cancel an appointment by its UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string", "description": "Appointment UUID"},
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
        return get_appointment_service(db, _as_uuid(args["appointment_id"], "appointment_id"))

    if name == "get_appointments_by_patient":
        return get_appointments_by_patient_service(db, _as_uuid(args["patient_id"], "patient_id"))

    if name == "get_appointments_by_doctor":
        return get_appointments_by_doctor_service(db, _as_uuid(args["doctor_id"], "doctor_id"))

    if name == "get_appointments_by_status":
        return get_appointments_by_status_service(db, args["status"].upper())

    if name == "get_upcoming_active_appointments":
        return get_upcoming_active_appointments_service(db)

    if name == "get_active_appointments_today":
        return get_active_appointments_by_date_service(db, date.today())

    if name == "get_appointments_by_date":
        return get_appointments_by_date_service(db, date.fromisoformat(args["appointment_date"]))

    if name == "suggest_available_slot":
        return suggest_available_slot_service(
            db,
            _as_uuid(args["doctor_id"], "doctor_id"),
            date.fromisoformat(args["slot_date"]),
            args.get("preferred_time"),
        )

    if name == "create_appointment":
        return create_appointment_service(
            db,
            AppointmentCreate(
                slot_id=_as_uuid(args["slot_id"], "slot_id"),
                patient_id=_as_uuid(args["patient_id"], "patient_id"),
                doctor_id=_as_uuid(args["doctor_id"], "doctor_id"),
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
            _as_uuid(args["appointment_id"], "appointment_id"),
            AppointmentUpdate(**fields),
        )

    if name == "cancel_appointment":
        return cancel_appointment_service(db, _as_uuid(args["appointment_id"], "appointment_id"))

    raise ValueError(f"Unknown appointment tool: {name}")
