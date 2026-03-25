from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

WaitlistStatus = Literal["WAITING", "NOTIFIED", "CONFIRMED", "EXPIRED", "CANCELLED"]


class WaitlistCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    session_id: int
    waitlist_date: date
    priority: int = 2            # 2 = NORMAL  |  1 = EMERGENCY
    is_emergency: bool = False
    emergency_declared_by: Optional[UUID] = None
    emergency_reason: Optional[str] = None


class WaitlistUpdate(BaseModel):
    status: Optional[WaitlistStatus] = None
    notified_at: Optional[datetime] = None
    response_deadline: Optional[datetime] = None
    emergency_verified_at: Optional[datetime] = None


class WaitlistResponse(BaseModel):
    waitlist_id: UUID
    patient_id: UUID
    doctor_id: UUID
    session_id: int
    waitlist_date: date
    priority: int
    is_emergency: bool
    status: WaitlistStatus
    joined_at: datetime
    notified_at: Optional[datetime] = None
    response_deadline: Optional[datetime] = None
    updated_at: datetime
