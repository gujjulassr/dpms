from typing import Optional

from pymongo import MongoClient

from app.conversations.config import (
    MONGODB_CONVERSATIONS_COLLECTION,
    MONGODB_DATABASE,
    MONGODB_URL,
)
from app.conversations.schemas import ConversationMessage, ConversationSession


client = MongoClient(MONGODB_URL)
database = client[MONGODB_DATABASE]
collection = database[MONGODB_CONVERSATIONS_COLLECTION]


def get_recent_messages(session_id: str, limit: int = 6) -> list[dict]:
    conversation = collection.find_one({"session_id": session_id}, {"_id": 0, "messages": 1})

    if not conversation:
        return []

    messages = conversation.get("messages", [])
    return messages[-limit:]




def get_conversation_by_session_id(session_id: str) -> Optional[dict]:
    return collection.find_one({"session_id": session_id}, {"_id": 0})


def create_conversation(session: ConversationSession) -> Optional[dict]:
    document = session.model_dump()
    collection.insert_one(document)
    return document


def append_message(session_id: str, message: ConversationMessage) -> None:
    collection.update_one(
        {"session_id": session_id},
        {
            "$push": {"messages": message.model_dump()},
            "$set": {"updated_at": message.created_at},
        },
    )
def set_pending_action(session_id: str, action_name: str, action_payload: dict) -> None:
    collection.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "linked_entities.pending_action": {
                    "action_name": action_name,
                    "action_payload": action_payload,
                }
            }
        },
    )


def set_pending_candidates(session_id: str, candidates: list[dict]) -> None:
    collection.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "linked_entities.pending_candidates": candidates,
            }
        },
    )


def get_pending_context(session_id: str) -> Optional[dict]:
    conversation = collection.find_one(
        {"session_id": session_id},
        {"_id": 0, "linked_entities": 1},
    )

    if not conversation:
        return None

    linked_entities = conversation.get("linked_entities", {})
    pending_action = linked_entities.get("pending_action")
    pending_candidates = linked_entities.get("pending_candidates")

    if not pending_action and not pending_candidates:
        return None

    return {
        "pending_action": pending_action,
        "pending_candidates": pending_candidates,
    }


def clear_pending_context(session_id: str) -> None:
    collection.update_one(
        {"session_id": session_id},
        {
            "$unset": {
                "linked_entities.pending_action": "",
                "linked_entities.pending_candidates": "",
            }
        },
    )


def set_active_patient(session_id: str, patient_id: str, full_name: str) -> None:
    collection.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "linked_entities.active_patient_id": patient_id,
                "linked_entities.active_patient_name": full_name,
            }
        },
    )


def get_active_patient(session_id: str) -> Optional[dict]:
    conversation = collection.find_one(
        {"session_id": session_id},
        {"_id": 0, "linked_entities": 1},
    )

    if not conversation:
        return None

    linked_entities = conversation.get("linked_entities", {})
    patient_id = linked_entities.get("active_patient_id")
    full_name = linked_entities.get("active_patient_name")

    if not patient_id:
        return None

    return {
        "patient_id": patient_id,
        "full_name": full_name,
    }


def append_patient_search(session_id: str, patient_id: str, full_name: str) -> None:
    collection.update_one(
        {"session_id": session_id},
        {
            "$push": {
                "linked_entities.patient_search_history": {
                    "patient_id": patient_id,
                    "full_name": full_name,
                }
            }
        },
    )


def get_patient_search_history(session_id: str) -> list[dict]:
    conversation = collection.find_one(
        {"session_id": session_id},
        {"_id": 0, "linked_entities.patient_search_history": 1},
    )

    if not conversation:
        return []

    linked_entities = conversation.get("linked_entities", {})
    return linked_entities.get("patient_search_history", [])
