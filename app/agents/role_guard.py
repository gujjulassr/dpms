from app.agents.schemas import RoleType

ROLE_PERMISSIONS = {
    "ADMIN": {
        # Patient tools
        "list_patients",
        "get_patient_by_id",
        "get_patient_by_email",
        "get_patients_by_name",
        "create_patient",
        "update_patient",
        # Doctor tools
        "list_doctors",
        "get_doctor_by_id",
        "get_doctor_by_email",
        "get_doctors_by_name",
        "get_doctors_by_specialization",
        "create_doctor",
        "update_doctor",
        # Staff tools
        "list_staff",
        "get_staff_by_id",
        "get_staff_by_email",
        "get_staff_by_name",
        "get_staff_by_role",
        "create_staff",
        "update_staff",
    },
    "STAFF": set(),
    "PATIENT": set(),
}


def is_action_allowed(role: RoleType, action_name: str) -> bool:
    return action_name in ROLE_PERMISSIONS.get(role, set())
