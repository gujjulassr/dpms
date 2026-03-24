"""
    service.py contains rules like duplicate email/phone checks.

"""


from typing import Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.patients.repository import (
    create_patient,
    get_patient_by_id,
    get_patient_by_email,
    get_patient_by_phone,
    get_patients_by_name,
    list_patients,
    update_patient,
)


from app.modules.patients.schemas import PatientCreate, PatientUpdate


def create_patient_service(db: Session, payload: PatientCreate) -> Dict:
    existing_email = get_patient_by_email(db, payload.email)
    if existing_email:
        raise ValueError("Patient with this email already exists")
    
    existing_phone = get_patient_by_phone(db, payload.phone)
    if existing_phone:
        raise ValueError("Patient with this phone already exists")
    

    try:
        patient = create_patient(db, payload.model_dump())
        db.commit()
        return patient
    
    except Exception as e:
        db.rollback()
        raise e
    

def get_patient_by_name_service(db:Session,full_name:str)->List[Dict]:
    return get_patients_by_name(db, full_name)
    


def get_patient_service(db: Session, patient_id: UUID) -> Dict:
    patient = get_patient_by_id(db, patient_id)
    if not patient:
        raise LookupError("Patient not found")
    return patient



def get_patient_by_email_service(db: Session, email: str) -> Dict:
    patient = get_patient_by_email(db, email)
    if not patient:
        raise LookupError("Patient not found")
    return patient


def list_patients_service(db: Session) -> List[Dict]:
    patients = list_patients(db)
    return patients


def update_patient_service(db: Session, patient_id: UUID, payload: PatientUpdate) -> Dict:

    existing_patient = get_patient_by_id(db, patient_id)
    if not existing_patient:
        raise LookupError("Patient not found")
    

    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise ValueError("At least one field is required for update")
    

    if "email" in update_data:
        patient_with_same_email = get_patient_by_email(db, update_data["email"])

        if patient_with_same_email and str(patient_with_same_email["patient_id"]) != str(patient_id):
            raise ValueError("Another patient with this email already exists")
        

    if "phone" in update_data:
        patient_with_same_phone = get_patient_by_phone(db, update_data["phone"])

        if patient_with_same_phone and str(patient_with_same_phone["patient_id"]) != str(patient_id):
            raise ValueError("Another patient with this phone already exists")

    merged_data = {
        "full_name": update_data.get("full_name", existing_patient["full_name"]),
        "email": update_data.get("email", existing_patient["email"]),
        "phone": update_data.get("phone", existing_patient["phone"]),
        "date_of_birth": update_data.get("date_of_birth", existing_patient["date_of_birth"]),
    }

    try:
        patient = update_patient(db, patient_id, merged_data)

        if not patient:
            raise LookupError("Patient not found")
        
        db.commit()
        return patient
    
    except Exception as e:
        db.rollback()
        raise e
    

