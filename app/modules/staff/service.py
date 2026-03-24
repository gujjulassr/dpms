from typing import Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.staff.repository import (
    create_staff,
    get_staff_by_email,
    get_staff_by_id,
    get_staff_by_name,
    get_staff_by_phone,
    get_staff_by_role,
    list_staff,
    update_staff,
)
from app.modules.staff.schemas import StaffCreate, StaffUpdate


def create_staff_service(db: Session, payload: StaffCreate) -> Dict:
    if get_staff_by_email(db, payload.email):
        raise ValueError("A staff member with this email already exists")

    if get_staff_by_phone(db, payload.phone):
        raise ValueError("A staff member with this phone already exists")

    try:
        member = create_staff(db, payload.model_dump())
        db.commit()
        return member
    except Exception as e:
        db.rollback()
        raise e


def get_staff_service(db: Session, staff_id: UUID) -> Dict:
    member = get_staff_by_id(db, staff_id)
    if not member:
        raise LookupError("Staff member not found")
    return member


def get_staff_by_email_service(db: Session, email: str) -> Dict:
    member = get_staff_by_email(db, email)
    if not member:
        raise LookupError("Staff member not found")
    return member


def get_staff_by_name_service(db: Session, full_name: str) -> List[Dict]:
    return get_staff_by_name(db, full_name)


def get_staff_by_role_service(db: Session, role: str) -> List[Dict]:
    return get_staff_by_role(db, role)


def list_staff_service(db: Session) -> List[Dict]:
    return list_staff(db)


def update_staff_service(db: Session, staff_id: UUID, payload: StaffUpdate) -> Dict:
    existing = get_staff_by_id(db, staff_id)
    if not existing:
        raise LookupError("Staff member not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValueError("At least one field is required for update")

    if "email" in update_data:
        clash = get_staff_by_email(db, update_data["email"])
        if clash and str(clash["staff_id"]) != str(staff_id):
            raise ValueError("Another staff member with this email already exists")

    if "phone" in update_data:
        clash = get_staff_by_phone(db, update_data["phone"])
        if clash and str(clash["staff_id"]) != str(staff_id):
            raise ValueError("Another staff member with this phone already exists")

    merged = {
        "full_name": update_data.get("full_name", existing["full_name"]),
        "email":     update_data.get("email",     existing["email"]),
        "phone":     update_data.get("phone",     existing["phone"]),
        "role":      update_data.get("role",      existing["role"]),
        "is_active": update_data.get("is_active", existing["is_active"]),
    }

    try:
        member = update_staff(db, staff_id, merged)
        if not member:
            raise LookupError("Staff member not found")
        db.commit()
        return member
    except Exception as e:
        db.rollback()
        raise e
