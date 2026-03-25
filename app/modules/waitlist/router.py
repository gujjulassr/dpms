from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
from app.modules.waitlist.schemas import WaitlistCreate, WaitlistUpdate
from app.modules.waitlist.service import (
    get_waitlist_by_patient_service,
    get_waitlist_by_session_service,
    get_waitlist_entry_service,
    join_waitlist_service,
    leave_waitlist_service,
    list_waitlist_service,
)

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def join_waitlist(payload: WaitlistCreate, db: Session = Depends(get_db)):
    try:
        return join_waitlist_service(db, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list)
def list_waitlist(db: Session = Depends(get_db)):
    return list_waitlist_service(db)


@router.get("/search/patient", response_model=list)
def get_by_patient(patient_id: int, db: Session = Depends(get_db)):
    return get_waitlist_by_patient_service(db, patient_id)


@router.get("/search/session", response_model=list)
def get_by_session(session_id: int, db: Session = Depends(get_db)):
    return get_waitlist_by_session_service(db, session_id)


@router.get("/{waitlist_id}", response_model=dict)
def get_waitlist_entry(waitlist_id: int, db: Session = Depends(get_db)):
    try:
        return get_waitlist_entry_service(db, waitlist_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{waitlist_id}/leave", response_model=dict)
def leave_waitlist(waitlist_id: int, db: Session = Depends(get_db)):
    try:
        return leave_waitlist_service(db, waitlist_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
