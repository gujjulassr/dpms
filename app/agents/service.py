"""
agents/service.py

Orchestrates the chatbot loop only.
All tool logic (schemas + execution) lives in tools/*.py.
Adding a new module = add a tools file, import it here, done.
"""

import json
import re
from datetime import date
from typing import Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from app.agents.config import OPENAI_API_KEY, OPENAI_MODEL
from app.agents.role_guard import is_action_allowed
from app.agents.schemas import AgentChatRequest, AgentChatResponse
from app.agents.tools import (
    appointment_tools,
    doctor_tools,
    patient_tools,
    session_tools,
    staff_tools,
    waitlist_tools,
)
from app.conversations.service import (
    fetch_recent_conversation_messages,
    get_or_create_conversation,
    save_assistant_message,
    save_user_message,
)
from app.modules.auth.repository import get_user_by_id
from app.modules.doctors.service import get_doctors_by_name_service
from app.modules.sessions.service import get_sessions_by_doctor_service

client = OpenAI(api_key=OPENAI_API_KEY)

MAX_TOOL_ROUNDS = 8


# All tool modules — each owns its own SCHEMAS and execute()
TOOL_MODULES = [patient_tools, doctor_tools, staff_tools, session_tools, appointment_tools, waitlist_tools]
ALL_SCHEMAS = [schema for m in TOOL_MODULES for schema in m.SCHEMAS]


def _run_tool(name: str, args: dict, db: Session):
    for module in TOOL_MODULES:
        if any(s["function"]["name"] == name for s in module.SCHEMAS):
            return module.execute(name, args, db)
    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_id(payload: AgentChatRequest) -> str:
    return payload.session_id or payload.user_id


def _build_history(session_id: str) -> list[dict]:
    raw = fetch_recent_conversation_messages(session_id=session_id, limit=10)
    history = []
    for m in raw:
        role = "user" if m.get("sender") == "user" else "assistant"
        content = m.get("content", "")
        if role == "assistant":
            metadata = m.get("metadata") or {}
            tool_result = metadata.get("tool_result")
            if tool_result is not None:
                tool_result_json = json.dumps(tool_result, default=str)
                if len(tool_result_json) > 3000:
                    tool_result_json = tool_result_json[:3000] + "...(truncated)"
                tool_name = m.get("tool_name") or "tool"
                content = (
                    f"{content}\n\n"
                    f"Relevant tool context from the previous turn ({tool_name}): "
                    f"{tool_result_json}"
                )
        history.append({"role": role, "content": content})
    return history


def _system_prompt(role: str) -> str:
    return (
        f"You are a helpful hospital management assistant. The current user role is {role}.\n"
        "You help with patient records, appointments, and hospital operations.\n\n"
        "CRITICAL RULES:\n"
        "1. Respond to what the user is asking in their CURRENT message.\n"
        "   Use recent conversation context only when the current message is a clear follow-up,\n"
        "   clarification, or reference such as 'that appointment', 'that patient', 'that one', 'yes', or 'no'.\n"
        "2. If the user says something casual like 'hi', 'ok', 'thanks' — just reply conversationally. "
        "   Do NOT call any tools.\n"
        "3. Only call tools when the current message explicitly asks for an action or data.\n"
        "4. When you need data to complete a task, call tools in sequence as needed.\n"
        "   Example: to update a patient by name → search by name first → then update.\n"
        "   Example: if the user says 'just that appointment' after a clarification, use the recent appointment context.\n"
        "5. After tools are done, report ONLY what was actually done. "
        "   Never pre-announce what you are about to do.\n"
        "6. Never make up patient data — only use what the tools return.\n"
        f"7. Today's date is {date.today().isoformat()}.\n"
        "8. If the user asks for active appointments, treat active as upcoming confirmed appointments only, not past appointments.\n"
        "9. If the user asks for today's active appointments, use the specific tool for today's upcoming active appointments instead of broad status-only queries.\n"
        "10. If the user asks for active appointments without a date, use the tool for upcoming active appointments.\n"
        "11. A session is different from an appointment. If the user asks to cancel or close a session, use session tools such as cancel_session or update_session, not cancel_appointment.\n"
        "12. If more than one session matches the user's request, ask a clarification question such as morning or afternoon, or which date.\n"
        "13. BOOKING FLOW — when a patient asks to book at a specific time and date:\n"
        "    a. Call suggest_available_slot with doctor_id, date, and preferred_time.\n"
        "    b. If exact slot is available (same_session=True, exact not None) → book it directly, no questions.\n"
        "    c. If same_session=True but exact is None → slot taken but another slot is free in the same session. Ask if they want to book that nearby slot.\n"
        "    d. If same_session=False → the entire requested session is fully booked. In ONE message offer both:\n"
        "       - Waitlist for the session they originally wanted (use session_name e.g. MORNING, not session_id). Always add: 'Note: waitlist only confirms if someone cancels at least 2 hours before their slot.'\n"
        "       - The earliest available slot found (suggested) as a direct booking option.\n"
        "       Patient can choose one, both, or neither. Never auto-book or auto-waitlist.\n"
        "    e. If suggested is None → no slots available for that doctor on that date at all. Just say so.\n"
        "14. BOOKING WITHOUT A TIME — if the patient asks for earliest available with no specific time or asks for the soonest/next/earliest appointment without a date, use get_earliest_available_slot_by_doctor.\n"
        "15. Do NOT offer waitlist for the suggested/alternative session — it already has available slots so there is nothing to wait for.\n"
        "16. For PATIENT users, doctor discovery is public but contact details are not. Only present doctor name and specialization to patients unless the system explicitly allows more.\n"
        "17. If the user asks for all available slots, open slots, active slots, or free times for a doctor on a date, use get_available_slots_by_doctor_and_date. Use suggest_available_slot only for booking one requested date/time.\n"
        "18. If the user asks whether a doctor or specialization is available today, first identify the doctor, then check sessions or available slots for today.\n"
        "19. If the user mentions a specialist term like cardiologist, dermatologist, or pediatrician, prefer get_doctors_by_specialization over name search.\n"
        "20. PATIENT IDENTITY RULE — when the role is PATIENT, the logged-in patient's patient_id is "
        "automatically injected into every booking, cancellation, and lookup tool. "
        "NEVER ask a PATIENT for their name, patient ID, date of birth, or phone number to identify themselves. "
        "Just proceed directly — their identity is already known. "
        "If a tool returns 'provide a valid patient_id', the system will supply it; do not ask the user.\n"
        "21. When a PATIENT asks to book and no session exists on the requested date, do NOT say 'no sessions scheduled'. "
        "Instead, immediately call get_earliest_available_slot_by_doctor to find the next available date and offer it.\n"
        "22. ADMIN DELETE RULE — when an ADMIN says 'remove', 'delete', 'erase', or 'permanently remove' a patient, "
        "ALWAYS use the delete_patient tool. NEVER rename, anonymize, or set the name to '[REDACTED]'. "
        "First look up the patient by name or ID to confirm, then call delete_patient with their patient_id. "
        "Update/rename is ONLY for legitimate data corrections — never for deletion requests.\n"
    )


DOCTOR_DISCOVERY_TOOLS = {
    "list_doctors",
    "get_doctor_by_id",
    "get_doctor_by_email",
    "get_doctors_by_name",
    "get_doctors_by_specialization",
}


def _sanitize_doctor_record_for_patient(record: dict) -> dict:
    allowed = {}

    if "doctor_id" in record:
        allowed["doctor_id"] = record["doctor_id"]
    if "full_name" in record:
        allowed["full_name"] = record["full_name"]
    if "specialization" in record:
        allowed["specialization"] = record["specialization"]
    if "slot_duration_mins" in record:
        allowed["slot_duration_mins"] = record["slot_duration_mins"]
    if "max_patients_per_day" in record:
        allowed["max_patients_per_day"] = record["max_patients_per_day"]
    if "is_active" in record:
        allowed["is_active"] = record["is_active"]

    return allowed


def _sanitize_tool_result_for_role(role: str, action_name: str, tool_result):
    if role != "PATIENT":
        return tool_result

    if action_name not in DOCTOR_DISCOVERY_TOOLS:
        return tool_result

    if isinstance(tool_result, list):
        return [_sanitize_doctor_record_for_patient(item) for item in tool_result]

    if isinstance(tool_result, dict):
        return _sanitize_doctor_record_for_patient(tool_result)

    return tool_result


def _get_authenticated_user(db: Session, user_id: str) -> Optional[dict]:
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


def _inject_role_scoped_ids(role: str, action_name: str, action_args: dict, auth_user: Optional[dict]) -> dict:
    if not auth_user:
        return action_args

    scoped_args = dict(action_args)

    if role == "PATIENT":
        patient_id = auth_user.get("patient_id")
        # Inject patient_id for every tool a patient uses that touches their own data
        PATIENT_SCOPED_TOOLS = {
            "create_appointment",
            "cancel_appointment",
            "get_appointments_by_patient",
            "get_appointment_by_id",
            "get_upcoming_active_appointments",
            "get_active_appointments_today",
            "join_waitlist",
            "leave_waitlist",
            "get_waitlist_by_patient",
        }
        if patient_id and action_name in PATIENT_SCOPED_TOOLS:
            scoped_args["patient_id"] = str(patient_id)

    if role == "DOCTOR":
        doctor_id = auth_user.get("doctor_id")
        if doctor_id and action_name in {"get_appointments_by_doctor", "get_sessions_by_doctor"}:
            scoped_args["doctor_id"] = str(doctor_id)

    return scoped_args


def _extract_doctor_name_query(message: str) -> Optional[str]:
    match = re.search(r"\bfor\b\s+(.+)$", message, re.IGNORECASE)
    if not match:
        return None

    query = match.group(1)
    query = re.sub(r"\b(dr|dr\.|doctor|session|sessions|please|also)\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" .?")
    return query or None


def _mentioned_session_name(message: str) -> Optional[str]:
    lowered = message.lower()
    if "morning" in lowered:
        return "MORNING"
    if "afternoon" in lowered:
        return "AFTERNOON"
    return None


def _mentioned_session_date(message: str) -> Optional[str]:
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    return match.group(0) if match else None


def _maybe_handle_ambiguous_session_cancel(db: Session, payload: AgentChatRequest, session_id: str) -> Optional[AgentChatResponse]:
    lowered = payload.message.lower()

    if "session" not in lowered:
        return None
    if not any(word in lowered for word in ("cancel", "close")):
        return None
    if "all" in lowered:
        return None

    doctor_query = _extract_doctor_name_query(payload.message)
    if not doctor_query:
        return None

    doctors = get_doctors_by_name_service(db, doctor_query)
    if len(doctors) != 1:
        return None

    doctor = doctors[0]
    sessions = get_sessions_by_doctor_service(db, UUID(doctor["doctor_id"]))
    sessions = [session for session in sessions if session["status"] != "CLOSED"]

    session_name = _mentioned_session_name(payload.message)
    if session_name:
        sessions = [session for session in sessions if session["session_name"] == session_name]

    session_date = _mentioned_session_date(payload.message)
    if session_date:
        sessions = [session for session in sessions if session["session_date"] == session_date]

    if len(sessions) <= 1:
        return None

    options = ", ".join(
        f'{session["session_name"].lower()} on {session["session_date"]}'
        for session in sessions
    )
    reply = (
        f'I found multiple active sessions for Dr. {doctor["full_name"]}: {options}. '
        "Please tell me which one to cancel."
    )
    save_assistant_message(session_id, reply)
    return AgentChatResponse(
        role=payload.role,
        message=reply,
        allowed=True,
        tool_name=None,
        data=sessions,
    )


# ---------------------------------------------------------------------------
# Main entry point — called by router.py
# ---------------------------------------------------------------------------

def process_agent_chat(db: Session, payload: AgentChatRequest) -> AgentChatResponse:
    session_id = _session_id(payload)
    last_tool_name: Optional[str] = None
    last_tool_result = None
    auth_user = _get_authenticated_user(db, payload.user_id)

    # Guard: PATIENT must have a valid linked patient record
    if payload.role == "PATIENT":
        if not auth_user:
            msg = "Your session has expired or your account was not found. Please log out and sign in again."
            return AgentChatResponse(role=payload.role, message=msg, allowed=False, tool_name=None, data=None)
        if not auth_user.get("patient_id"):
            msg = "Your patient profile is not set up yet. Please sign out and sign back in with Google to complete your registration."
            return AgentChatResponse(role=payload.role, message=msg, allowed=False, tool_name=None, data=None)

    try:
        get_or_create_conversation(session_id, payload.user_id, payload.role)
        save_user_message(session_id, payload.message)

        ambiguous_session_cancel = _maybe_handle_ambiguous_session_cancel(db, payload, session_id)
        if ambiguous_session_cancel is not None:
            return ambiguous_session_cancel

        history = _build_history(session_id)

        if history and history[-1]["role"] == "user" and history[-1]["content"] == payload.message:
            history = history[:-1]

        messages: list[dict] = [
            {"role": "system", "content": _system_prompt(payload.role)},
            *history,
            {"role": "user", "content": payload.message},
        ]

        for _round in range(MAX_TOOL_ROUNDS):

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=ALL_SCHEMAS,
                tool_choice="auto",
            )
            choice = response.choices[0]

            # No tool needed — return the conversational reply
            if choice.finish_reason != "tool_calls":
                final_text = choice.message.content or "How can I help you?"
                metadata = {"tool_result": last_tool_result} if last_tool_result is not None else None
                save_assistant_message(
                    session_id,
                    final_text,
                    tool_name=last_tool_name,
                    metadata=metadata,
                )
                return AgentChatResponse(
                    role=payload.role,
                    message=final_text,
                    allowed=True,
                    tool_name=last_tool_name,
                    data=last_tool_result,
                )

            # Append assistant tool-call message to thread
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ],
            })

            # Execute each tool and append its result
            for tc in choice.message.tool_calls:
                action_name = tc.function.name
                action_args = json.loads(tc.function.arguments)
                action_args = _inject_role_scoped_ids(payload.role, action_name, action_args, auth_user)

                if not is_action_allowed(payload.role, action_name):
                    msg = (
                        f"Sorry — your role ({payload.role}) does not have permission "
                        f"to perform '{action_name}'."
                    )
                    save_assistant_message(session_id, msg)
                    return AgentChatResponse(
                        role=payload.role,
                        message=msg,
                        allowed=False,
                        tool_name=action_name,
                        data=None,
                    )

                try:
                    tool_result = _run_tool(action_name, action_args, db)
                except Exception as tool_exc:
                    tool_result = {"error": str(tool_exc)}
                visible_tool_result = _sanitize_tool_result_for_role(payload.role, action_name, tool_result)
                last_tool_name = action_name
                last_tool_result = visible_tool_result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(visible_tool_result, default=str),
                })

        fallback = "I completed the available steps but couldn't fully finish the request."
        metadata = {"tool_result": last_tool_result} if last_tool_result is not None else None
        save_assistant_message(session_id, fallback, tool_name=last_tool_name, metadata=metadata)
        return AgentChatResponse(
            role=payload.role,
            message=fallback,
            allowed=True,
            tool_name=last_tool_name,
            data=last_tool_result,
        )

    except Exception as exc:
        error_msg = f"Something went wrong: {exc}"
        save_assistant_message(session_id, error_msg)
        return AgentChatResponse(
            role=payload.role,
            message=error_msg,
            allowed=False,
            tool_name=None,
            data=None,
        )
