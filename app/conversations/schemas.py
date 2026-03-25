from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


SenderType = Literal["user", "assistant"]
RoleType = Literal["ADMIN", "RECEPTIONIST", "DOCTOR", "PATIENT"]


"""

What this file defines:

ConversationMessage
one message in the chat
ConversationSession
one full chat session with many messages

"""


class ConversationMessage(BaseModel):
    sender: SenderType
    content: str
    tool_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationSession(BaseModel):
    session_id: str
    user_id: int
    role: RoleType
    summary: Optional[str] = None
    messages: List[ConversationMessage] = Field(default_factory=list)
    linked_entities: Dict[str, List[str]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
