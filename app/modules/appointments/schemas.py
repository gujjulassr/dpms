from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

AppointmentStatus = Literal["CONFIRMED", "CANCELLED", "COMPLETED", "NO_SHOW"]


class AppointmentCreate(BaseModel):
    slot_id: UUID
    patient_id: UUID
    doctor_id: UUID


class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    reminder_24hr_sent: Optional[bool] = None
    reminder_2hr_sent: Optional[bool] = None
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class AppointmentResponse(BaseModel):
    appointment_id: UUID
    slot_id: UUID
    patient_id: UUID
    doctor_id: UUID
    booked_at: datetime
    status: AppointmentStatus
    reminder_24hr_sent: bool
    reminder_2hr_sent: bool
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    updated_at: datetime


class AppointmentFilters(BaseModel):
    patient_id: Optional[UUID] = None
    doctor_id: Optional[UUID] = None
    status: Optional[AppointmentStatus] = None
    appointment_date: Optional[date] = None
