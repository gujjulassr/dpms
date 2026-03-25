from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
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

router = APIRouter(prefix="/staff", tags=["Staff"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db)):
    try:
        return create_staff_service(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list)
def list_staff(db: Session = Depends(get_db)):
    return list_staff_service(db)


@router.get("/search/name", response_model=list)
def get_by_name(full_name: str, db: Session = Depends(get_db)):
    return get_staff_by_name_service(db, full_name)


@router.get("/search/role", response_model=list)
def get_by_role(role: str, db: Session = Depends(get_db)):
    return get_staff_by_role_service(db, role)


@router.get("/search/email", response_model=dict)
def get_by_email(email: str, db: Session = Depends(get_db)):
    try:
        return get_staff_by_email_service(db, email)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{staff_id}", response_model=dict)
def get_staff(staff_id: int, db: Session = Depends(get_db)):
    try:
        return get_staff_service(db, staff_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{staff_id}", response_model=dict)
def update_staff(staff_id: int, payload: StaffUpdate, db: Session = Depends(get_db)):
    try:
        return update_staff_service(db, staff_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
