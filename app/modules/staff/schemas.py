from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

StaffRole = Literal["RECEPTIONIST", "DOCTOR", "ADMIN"]


class StaffCreate(BaseModel):
    full_name: str
    email: str
    phone: str
    role: StaffRole


class StaffUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[StaffRole] = None
    is_active: Optional[bool] = None


class StaffResponse(BaseModel):
    staff_id: int
    full_name: str
    email: str
    phone: str
    role: StaffRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
