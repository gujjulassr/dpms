from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel

AppointmentStatus = Literal["CONFIRMED", "CANCELLED", "COMPLETED", "NO_SHOW"]


class AppointmentCreate(BaseModel):
    """
    Create an appointment by specifying doctor, patient, session, and time.
    No more slot_id — time is stored directly on the appointment.
    """
    patient_id: int
    doctor_id: int
    session_id: int
    appointment_date: date
    start_time: time


class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    reminder_24hr_sent: Optional[bool] = None
    reminder_2hr_sent: Optional[bool] = None
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class AppointmentResponse(BaseModel):
    appointment_id: int
    patient_id: int
    doctor_id: int
    session_id: int
    appointment_date: date
    start_time: time
    end_time: time
    booked_at: datetime
    status: AppointmentStatus
    reminder_24hr_sent: bool
    reminder_2hr_sent: bool
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    updated_at: datetime


class AppointmentFilters(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: Optional[AppointmentStatus] = None
    appointment_date: Optional[date] = None
