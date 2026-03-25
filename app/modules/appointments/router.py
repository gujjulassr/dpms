from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
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
    update_appointment_service,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    try:
        return create_appointment_service(db, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list)
def list_appointments(db: Session = Depends(get_db)):
    return list_appointments_service(db)


@router.get("/search/patient", response_model=list)
def get_by_patient(patient_id: int, db: Session = Depends(get_db)):
    return get_appointments_by_patient_service(db, patient_id)


@router.get("/search/doctor", response_model=list)
def get_by_doctor(doctor_id: int, db: Session = Depends(get_db)):
    return get_appointments_by_doctor_service(db, doctor_id)


@router.get("/search/status", response_model=list)
def get_by_status(status: str, db: Session = Depends(get_db)):
    return get_appointments_by_status_service(db, status.upper())


@router.get("/active/upcoming", response_model=list)
def get_upcoming_active(db: Session = Depends(get_db)):
    return get_upcoming_active_appointments_service(db)


@router.get("/active/today", response_model=list)
def get_active_today(db: Session = Depends(get_db)):
    return get_active_appointments_by_date_service(db, date.today())


@router.get("/search/date", response_model=list)
def get_by_date(appointment_date: date, db: Session = Depends(get_db)):
    return get_appointments_by_date_service(db, appointment_date)


@router.get("/{appointment_id}", response_model=dict)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    try:
        return get_appointment_service(db, appointment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{appointment_id}", response_model=dict)
def update_appointment(appointment_id: int, payload: AppointmentUpdate, db: Session = Depends(get_db)):
    try:
        return update_appointment_service(db, appointment_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appointment_id}/cancel", response_model=dict)
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    try:
        return cancel_appointment_service(db, appointment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
