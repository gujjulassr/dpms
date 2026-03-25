from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel

SessionName = Literal["MORNING", "AFTERNOON"]
SessionStatus = Literal["OPEN", "FULL", "CLOSED"]


class SessionCreate(BaseModel):
    doctor_id: int
    session_date: date
    session_name: SessionName
    start_time: time
    end_time: time
    status: Optional[SessionStatus] = "OPEN"


class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None


class SessionResponse(BaseModel):
    session_id: int
    doctor_id: int
    session_date: date
    session_name: SessionName
    start_time: time
    end_time: time
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
