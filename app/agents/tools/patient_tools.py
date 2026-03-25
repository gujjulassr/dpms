"""
agents/tools/patient_tools.py

Owns everything about patient chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → patient service call
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.patients.schemas import PatientCreate, PatientUpdate
from app.modules.patients.service import (
    create_patient_service,
    delete_patient_service,
    get_patient_by_email_service,
    get_patient_by_name_service,
    get_patient_service,
    list_patients_service,
    update_patient_service,
)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_patients",
            "description": "List every patient in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_by_email",
            "description": "Look up a single patient by their email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Patient email address"},
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_by_id",
            "description": "Look up a single patient by their UUID.",
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
            "name": "get_patients_by_name",
            "description": "Search patients by name. May return multiple results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Patient full name or partial name"},
                },
                "required": ["full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_patient",
            "description": "Register a brand-new patient in the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":     {"type": "string"},
                    "email":         {"type": "string"},
                    "phone":         {"type": "string"},
                    "date_of_birth": {"type": "string", "description": "YYYY-MM-DD (optional)"},
                },
                "required": ["full_name", "email", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient",
            "description": "Update one or more fields on an existing patient. Only provide fields that need to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id":    {"type": "string", "description": "Patient UUID (required)"},
                    "full_name":     {"type": "string"},
                    "email":         {"type": "string"},
                    "phone":         {"type": "string"},
                    "date_of_birth": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_patient",
            "description": (
                "Permanently delete a patient record and their linked user account from the system. "
                "Use this when an admin explicitly asks to remove, delete, or permanently erase a patient. "
                "This action is irreversible. Always look up the patient first to confirm identity before deleting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient UUID"},
                },
                "required": ["patient_id"],
            },
        },
    },
]


def execute(name: str, args: dict, db: Session):
    if name == "list_patients":
        return list_patients_service(db)

    if name == "get_patient_by_email":
        return get_patient_by_email_service(db, args["email"])

    if name == "get_patient_by_id":
        return get_patient_service(db, UUID(args["patient_id"]))

    if name == "get_patients_by_name":
        return get_patient_by_name_service(db, args["full_name"])

    if name == "create_patient":
        return create_patient_service(db, PatientCreate(
            full_name=args["full_name"],
            email=args["email"],
            phone=args["phone"],
            date_of_birth=args.get("date_of_birth"),
        ))

    if name == "update_patient":
        fields = {}
        if args.get("full_name") is not None:     fields["full_name"]     = args["full_name"]
        if args.get("email") is not None:         fields["email"]         = args["email"]
        if args.get("phone") is not None:         fields["phone"]         = args["phone"]
        if args.get("date_of_birth") is not None: fields["date_of_birth"] = args["date_of_birth"]
        return update_patient_service(db, UUID(args["patient_id"]), PatientUpdate(**fields))

    if name == "delete_patient":
        return delete_patient_service(db, UUID(args["patient_id"]))
