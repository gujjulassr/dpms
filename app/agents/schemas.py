from typing import Any, Literal, Optional

from pydantic import BaseModel

RoleType = Literal["ADMIN", "RECEPTIONIST", "DOCTOR", "PATIENT"]


class AgentChatRequest(BaseModel):
    role: RoleType
    user_id: str
    message: str
    session_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    role: RoleType
    message: str
    allowed: bool = True
    tool_name: Optional[str] = None
    data: Optional[Any] = None
