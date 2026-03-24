from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
from app.modules.doctors.schemas import DoctorCreate, DoctorResponse, DoctorUpdate
from app.modules.doctors.service import (
    create_doctor_service,
    get_doctor_by_email_service,
    get_doctor_service,
    get_doctors_by_name_service,
    get_doctors_by_specialization_service,
    list_doctors_service,
    update_doctor_service,
)

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_doctor(payload: DoctorCreate, db: Session = Depends(get_db)):
    try:
        return create_doctor_service(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list)
def list_doctors(db: Session = Depends(get_db)):
    return list_doctors_service(db)


@router.get("/search/name", response_model=list)
def get_by_name(full_name: str, db: Session = Depends(get_db)):
    return get_doctors_by_name_service(db, full_name)


@router.get("/search/specialization", response_model=list)
def get_by_specialization(specialization: str, db: Session = Depends(get_db)):
    return get_doctors_by_specialization_service(db, specialization)


@router.get("/search/email", response_model=dict)
def get_by_email(email: str, db: Session = Depends(get_db)):
    try:
        return get_doctor_by_email_service(db, email)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{doctor_id}", response_model=dict)
def get_doctor(doctor_id: UUID, db: Session = Depends(get_db)):
    try:
        return get_doctor_service(db, doctor_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{doctor_id}", response_model=dict)
def update_doctor(doctor_id: UUID, payload: DoctorUpdate, db: Session = Depends(get_db)):
    try:
        return update_doctor_service(db, doctor_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
