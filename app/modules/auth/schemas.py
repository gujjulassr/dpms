from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    user_id: str
    display_name: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str                        # ADMIN | RECEPTIONIST | DOCTOR | PATIENT
    display_name: str
    staff_id:   Optional[str] = None
    patient_id: Optional[str] = None
    doctor_id:  Optional[str] = None


class GoogleRegisterRequest(BaseModel):
    """Sent from Streamlit registration form after first Google login."""
    reg_token:    str            # signed temp JWT from the callback redirect
    phone:        str            # collected from the form, must be ≤15 chars
    date_of_birth: Optional[str] = None   # YYYY-MM-DD, optional


class UserInfo(BaseModel):
    user_id:      str
    username:     str
    role:         str
    display_name: str
    staff_id:     Optional[str] = None
    patient_id:   Optional[str] = None
    doctor_id:    Optional[str] = None
    is_active:    bool
