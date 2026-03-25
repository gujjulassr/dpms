from typing import Dict, List

from sqlalchemy.orm import Session

from app.modules.doctors.repository import (
    create_doctor,
    get_doctor_by_email,
    get_doctor_by_id,
    get_doctor_by_phone,
    get_doctors_by_name,
    get_doctors_by_specialization,
    list_doctors,
    update_doctor,
)
from app.modules.doctors.schemas import DoctorCreate, DoctorUpdate


def create_doctor_service(db: Session, payload: DoctorCreate) -> Dict:
    if get_doctor_by_email(db, payload.email):
        raise ValueError("A doctor with this email already exists")

    if get_doctor_by_phone(db, payload.phone):
        raise ValueError("A doctor with this phone already exists")

    try:
        doctor = create_doctor(db, payload.model_dump())
        db.commit()
        return doctor
    except Exception as e:
        db.rollback()
        raise e


def get_doctor_service(db: Session, doctor_id: int) -> Dict:
    doctor = get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise LookupError("Doctor not found")
    return doctor


def get_doctor_by_email_service(db: Session, email: str) -> Dict:
    doctor = get_doctor_by_email(db, email)
    if not doctor:
        raise LookupError("Doctor not found")
    return doctor


def get_doctors_by_name_service(db: Session, full_name: str) -> List[Dict]:
    return get_doctors_by_name(db, full_name)


def get_doctors_by_specialization_service(db: Session, specialization: str) -> List[Dict]:
    return get_doctors_by_specialization(db, specialization)


def list_doctors_service(db: Session) -> List[Dict]:
    return list_doctors(db)


def update_doctor_service(db: Session, doctor_id: int, payload: DoctorUpdate) -> Dict:
    existing = get_doctor_by_id(db, doctor_id)
    if not existing:
        raise LookupError("Doctor not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValueError("At least one field is required for update")

    if "email" in update_data:
        clash = get_doctor_by_email(db, update_data["email"])
        if clash and clash["doctor_id"] != doctor_id:
            raise ValueError("Another doctor with this email already exists")

    if "phone" in update_data:
        clash = get_doctor_by_phone(db, update_data["phone"])
        if clash and clash["doctor_id"] != doctor_id:
            raise ValueError("Another doctor with this phone already exists")

    # Merge only changed fields on top of existing values
    merged = {
        "full_name":            update_data.get("full_name",            existing["full_name"]),
        "specialization":       update_data.get("specialization",       existing["specialization"]),
        "email":                update_data.get("email",                existing["email"]),
        "phone":                update_data.get("phone",                existing["phone"]),
        "slot_duration_mins":   update_data.get("slot_duration_mins",   existing["slot_duration_mins"]),
        "max_patients_per_day": update_data.get("max_patients_per_day", existing["max_patients_per_day"]),
        "is_active":            update_data.get("is_active",            existing["is_active"]),
    }

    try:
        doctor = update_doctor(db, doctor_id, merged)
        if not doctor:
            raise LookupError("Doctor not found")
        db.commit()
        return doctor
    except Exception as e:
        db.rollback()
        raise e
