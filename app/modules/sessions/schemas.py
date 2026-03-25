from datetime import date, datetime, time
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

SessionName = Literal["MORNING", "AFTERNOON"]
SessionStatus = Literal["OPEN", "FULL", "CLOSED"]
SlotStatus = Literal["AVAILABLE", "BOOKED", "BLOCKED", "CANCELLED"]


class SessionCreate(BaseModel):
    doctor_id: UUID
    session_date: date
    session_name: SessionName
    start_time: time
    end_time: time
    status: Optional[SessionStatus] = "OPEN"


class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None


class SessionResponse(BaseModel):
    session_id: int
    doctor_id: UUID
    session_date: date
    session_name: SessionName
    start_time: time
    end_time: time
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class SlotResponse(BaseModel):
    slot_id: UUID
    doctor_id: UUID
    session_id: int
    slot_date: date
    start_time: time
    end_time: time
    status: SlotStatus
    version: int
    created_at: datetime
    updated_at: datetime
