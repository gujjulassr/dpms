"""
agents/tools/staff_tools.py

Owns everything about staff chatbot tools:
  SCHEMAS   — what OpenAI sees
  execute() — dispatches tool name → staff service call
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.staff.schemas import StaffCreate, StaffUpdate
from app.modules.staff.service import (
    create_staff_service,
    get_staff_by_email_service,
    get_staff_by_name_service,
    get_staff_by_role_service,
    get_staff_service,
    list_staff_service,
    update_staff_service,
)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_staff",
            "description": "List all staff members in the system.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_by_id",
            "description": "Look up a single staff member by their UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "staff_id": {"type": "string", "description": "Staff UUID"},
                },
                "required": ["staff_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_by_email",
            "description": "Look up a single staff member by their email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Staff email address"},
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_by_name",
            "description": "Search staff members by name. May return multiple results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Staff full name or partial name"},
                },
                "required": ["full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_by_role",
            "description": "Find all active staff members by role. Role must be RECEPTIONIST, DOCTOR, or ADMIN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["RECEPTIONIST", "DOCTOR", "ADMIN"],
                        "description": "Staff role",
                    },
                },
                "required": ["role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_staff",
            "description": "Register a new staff member in the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "email":     {"type": "string"},
                    "phone":     {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": ["RECEPTIONIST", "DOCTOR", "ADMIN"],
                        "description": "Staff role",
                    },
                },
                "required": ["full_name", "email", "phone", "role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_staff",
            "description": "Update one or more fields on an existing staff member. Only provide fields that need to change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "staff_id":  {"type": "string", "description": "Staff UUID (required)"},
                    "full_name": {"type": "string"},
                    "email":     {"type": "string"},
                    "phone":     {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": ["RECEPTIONIST", "DOCTOR", "ADMIN"],
                    },
                    "is_active": {"type": "boolean", "description": "Set false to deactivate the staff member"},
                },
                "required": ["staff_id"],
            },
        },
    },
]


def execute(name: str, args: dict, db: Session):
    if name == "list_staff":
        return list_staff_service(db)

    if name == "get_staff_by_id":
        return get_staff_service(db, UUID(args["staff_id"]))

    if name == "get_staff_by_email":
        return get_staff_by_email_service(db, args["email"])

    if name == "get_staff_by_name":
        return get_staff_by_name_service(db, args["full_name"])

    if name == "get_staff_by_role":
        return get_staff_by_role_service(db, args["role"])

    if name == "create_staff":
        return create_staff_service(db, StaffCreate(
            full_name=args["full_name"],
            email=args["email"],
            phone=args["phone"],
            role=args["role"],
        ))

    if name == "update_staff":
        fields = {}
        if args.get("full_name") is not None: fields["full_name"] = args["full_name"]
        if args.get("email") is not None:     fields["email"]     = args["email"]
        if args.get("phone") is not None:     fields["phone"]     = args["phone"]
        if args.get("role") is not None:      fields["role"]      = args["role"]
        if args.get("is_active") is not None: fields["is_active"] = args["is_active"]
        return update_staff_service(db, UUID(args["staff_id"]), StaffUpdate(**fields))
