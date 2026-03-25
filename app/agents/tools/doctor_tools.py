"""
agents/tools/doctor_tools.py

Owns everything about doctor chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → doctor service call
"""

from sqlalchemy.orm import Session

from app.modules.doctors.schemas import DoctorCreate, DoctorUpdate
from app.modules.doctors.service import (
    create_doctor_service,
    get_doctor_by_email_service,
    get_doctor_service,
    get_doctors_by_name_service,
    get_doctors_by_specialization_service,
    list_doctors_service,
    update_doctor_service,
)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_doctors",
            "description": "List all doctors in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_by_id",
            "description": "Look up a single doctor by their ID.",
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
            "name": "get_doctor_by_email",
            "description": "Look up a single doctor by their email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Doctor email address"},
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctors_by_name",
            "description": "Search doctors by name. May return multiple results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Doctor full name or partial name"},
                },
                "required": ["full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctors_by_specialization",
            "description": "Find all active doctors by their specialization (e.g. Cardiology, Dermatology).",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialization": {"type": "string", "description": "Medical specialization"},
                },
                "required": ["specialization"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_doctor",
            "description": "Register a new doctor in the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":            {"type": "string"},
                    "specialization":       {"type": "string"},
                    "email":                {"type": "string"},
                    "phone":                {"type": "string"},
                    "slot_duration_mins":   {"type": "integer", "description": "Slot duration in minutes (default 15)"},
                    "max_patients_per_day": {"type": "integer", "description": "Max patients per day (default 40)"},
                },
                "required": ["full_name", "specialization", "email", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_doctor",
            "description": "Update one or more fields on an existing doctor. Only provide fields that need to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id":            {"type": "integer", "description": "Doctor ID (required)"},
                    "full_name":            {"type": "string"},
                    "specialization":       {"type": "string"},
                    "email":                {"type": "string"},
                    "phone":                {"type": "string"},
                    "slot_duration_mins":   {"type": "integer"},
                    "max_patients_per_day": {"type": "integer"},
                    "is_active":            {"type": "boolean", "description": "Set false to deactivate the doctor"},
                },
                "required": ["doctor_id"],
            },
        },
    },
]


def execute(name: str, args: dict, db: Session):
    if name == "list_doctors":
        return list_doctors_service(db)

    if name == "get_doctor_by_id":
        return get_doctor_service(db, int(args["doctor_id"]))

    if name == "get_doctor_by_email":
        return get_doctor_by_email_service(db, args["email"])

    if name == "get_doctors_by_name":
        return get_doctors_by_name_service(db, args["full_name"])

    if name == "get_doctors_by_specialization":
        return get_doctors_by_specialization_service(db, args["specialization"])

    if name == "create_doctor":
        return create_doctor_service(db, DoctorCreate(
            full_name=args["full_name"],
            specialization=args["specialization"],
            email=args["email"],
            phone=args["phone"],
            slot_duration_mins=args.get("slot_duration_mins", 15),
            max_patients_per_day=args.get("max_patients_per_day", 40),
        ))

    if name == "update_doctor":
        fields = {}
        if args.get("full_name") is not None:            fields["full_name"]            = args["full_name"]
        if args.get("specialization") is not None:       fields["specialization"]       = args["specialization"]
        if args.get("email") is not None:                fields["email"]                = args["email"]
        if args.get("phone") is not None:                fields["phone"]                = args["phone"]
        if args.get("slot_duration_mins") is not None:   fields["slot_duration_mins"]   = args["slot_duration_mins"]
        if args.get("max_patients_per_day") is not None: fields["max_patients_per_day"] = args["max_patients_per_day"]
        if args.get("is_active") is not None:            fields["is_active"]            = args["is_active"]
        return update_doctor_service(db, int(args["doctor_id"]), DoctorUpdate(**fields))
