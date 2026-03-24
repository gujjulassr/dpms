from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DoctorCreate(BaseModel):
    full_name: str
    specialization: str
    email: str
    phone: str
    slot_duration_mins: Optional[int] = 15
    max_patients_per_day: Optional[int] = 40


class DoctorUpdate(BaseModel):
    full_name: Optional[str] = None
    specialization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    slot_duration_mins: Optional[int] = None
    max_patients_per_day: Optional[int] = None
    is_active: Optional[bool] = None


class DoctorResponse(BaseModel):
    doctor_id: UUID
    full_name: str
    specialization: str
    email: str
    phone: str
    slot_duration_mins: int
    max_patients_per_day: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
