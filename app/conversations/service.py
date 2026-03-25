from typing import Optional

from app.conversations.repository import (
    append_message,
    append_patient_search,
    clear_pending_context,
    create_conversation,
    get_active_patient,
    get_conversation_by_session_id,
    get_pending_context,
    get_patient_search_history,
    get_recent_messages,
    set_active_patient,
    set_pending_action,
    set_pending_candidates,
)

from app.conversations.schemas import ConversationMessage, ConversationSession


def get_or_create_conversation(session_id: str, user_id: str, role: str) -> dict:
    conversation = get_conversation_by_session_id(session_id)

    if conversation:
        return conversation

    new_conversation = ConversationSession(
        session_id=session_id,
        user_id=user_id,
        role=role,
    )

    return create_conversation(new_conversation)


def save_user_message(session_id: str, content: str) -> None:
    message = ConversationMessage(
        sender="user",
        content=content,
    )
    append_message(session_id, message)


def save_assistant_message(
    session_id: str,
    content: str,
    tool_name: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    message = ConversationMessage(
        sender="assistant",
        content=content,
        tool_name=tool_name,
        metadata=metadata,
    )
    append_message(session_id, message)

def fetch_recent_conversation_messages(session_id: str, limit: int = 6) -> list[dict]:
    return get_recent_messages(session_id, limit)


def fetch_conversation(session_id: str) -> Optional[dict]:
    return get_conversation_by_session_id(session_id)


def remember_pending_action(session_id: str, action_name: str, action_payload: dict) -> None:
    set_pending_action(session_id, action_name, action_payload)


def remember_pending_candidates(session_id: str, candidates: list[dict]) -> None:
    set_pending_candidates(session_id, candidates)


def fetch_pending_context(session_id: str) -> Optional[dict]:
    return get_pending_context(session_id)


def clear_pending_state(session_id: str) -> None:
    clear_pending_context(session_id)


def remember_active_patient(session_id: str, patient_id: str, full_name: str) -> None:
    set_active_patient(session_id, patient_id, full_name)
    append_patient_search(session_id, patient_id, full_name)


def fetch_active_patient(session_id: str) -> Optional[dict]:
    return get_active_patient(session_id)


def fetch_patient_search_history(session_id: str) -> list[dict]:
    return get_patient_search_history(session_id)
