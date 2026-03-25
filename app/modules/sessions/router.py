from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection.database import get_db
from app.modules.sessions.schemas import SessionCreate, SessionUpdate
from app.modules.sessions.service import (
    create_session_service,
    get_session_service,
    get_session_slots_service,
    get_sessions_by_date_service,
    get_sessions_by_doctor_service,
    get_sessions_by_status_service,
    list_sessions_service,
    update_session_service,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    try:
        return create_session_service(db, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list)
def list_sessions(db: Session = Depends(get_db)):
    return list_sessions_service(db)


@router.get("/search/doctor", response_model=list)
def get_by_doctor(doctor_id: UUID, db: Session = Depends(get_db)):
    return get_sessions_by_doctor_service(db, doctor_id)


@router.get("/search/date", response_model=list)
def get_by_date(session_date: date, db: Session = Depends(get_db)):
    return get_sessions_by_date_service(db, session_date)


@router.get("/search/status", response_model=list)
def get_by_status(status: str, db: Session = Depends(get_db)):
    return get_sessions_by_status_service(db, status.upper())


@router.get("/{session_id}", response_model=dict)
def get_session(session_id: int, db: Session = Depends(get_db)):
    try:
        return get_session_service(db, session_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{session_id}/slots", response_model=list)
def get_session_slots(session_id: int, db: Session = Depends(get_db)):
    try:
        return get_session_slots_service(db, session_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{session_id}", response_model=dict)
def update_session(session_id: int, payload: SessionUpdate, db: Session = Depends(get_db)):
    try:
        return update_session_service(db, session_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
