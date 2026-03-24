"""
 Purpose: define the shape of incoming and outgoing patient data.


"""




from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


#PatientCreate is for POST

class PatientCreate(BaseModel):
    full_name: str
    email: str
    phone: str
    date_of_birth: Optional[date] = None



"""

    PatientUpdate is for PATCH

    PATCH is an HTTP method used for partial updates to an existing resource. Unlike PUT (which replaces the entire resource), PATCH lets you change only specific fields while leaving others untouched.


"""



class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None


#PatientResponse is what we send back to the client

class PatientResponse(BaseModel):
    patient_id: UUID
    full_name: str
    email: str
    phone: str
    date_of_birth: Optional[date] = None
    cancellation_count: int
    late_cancellation_count: int
    no_show_count: int
    risk_score: float
    created_at: datetime
    updated_at: datetime
