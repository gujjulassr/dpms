"""
agents/service.py

Orchestrates the chatbot loop only.
All tool logic (schemas + execution) lives in tools/*.py.
Adding a new module = add a tools file, import it here, done.
"""

import json
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.agents.config import OPENAI_API_KEY, OPENAI_MODEL
from app.agents.role_guard import is_action_allowed
from app.agents.schemas import AgentChatRequest, AgentChatResponse
from app.agents.tools import doctor_tools, patient_tools, staff_tools
from app.conversations.service import (
    fetch_recent_conversation_messages,
    get_or_create_conversation,
    save_assistant_message,
    save_user_message,
)

client = OpenAI(api_key=OPENAI_API_KEY)

MAX_TOOL_ROUNDS = 5


# All tool modules — each owns its own SCHEMAS and execute()
TOOL_MODULES = [patient_tools, doctor_tools, staff_tools]
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
        history.append({"role": role, "content": m.get("content", "")})
    return history


def _system_prompt(role: str) -> str:
    return (
        f"You are a helpful hospital management assistant. The current user role is {role}.\n"
        "You help with patient records, appointments, and hospital operations.\n\n"
        "CRITICAL RULES:\n"
        "1. Only respond to what the user is asking in their CURRENT message.\n"
        "   Do NOT continue, resume, or complete anything from previous messages.\n"
        "   Each message is a fresh, independent request.\n"
        "2. If the user says something casual like 'hi', 'ok', 'thanks' — just reply conversationally. "
        "   Do NOT call any tools.\n"
        "3. Only call tools when the current message explicitly asks for an action or data.\n"
        "4. When you need data to complete a task, call tools in sequence as needed.\n"
        "   Example: to update a patient by name → search by name first → then update.\n"
        "5. After tools are done, report ONLY what was actually done. "
        "   Never pre-announce what you are about to do.\n"
        "6. Never make up patient data — only use what the tools return."
    )


# ---------------------------------------------------------------------------
# Main entry point — called by router.py
# ---------------------------------------------------------------------------

def process_agent_chat(db: Session, payload: AgentChatRequest) -> AgentChatResponse:
    session_id = _session_id(payload)
    last_tool_name: Optional[str] = None
    last_tool_result = None

    try:
        get_or_create_conversation(session_id, payload.user_id, payload.role)
        save_user_message(session_id, payload.message)

        messages: list[dict] = [
            {"role": "system", "content": _system_prompt(payload.role)},
            *_build_history(session_id),
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
                save_assistant_message(session_id, final_text, tool_name=last_tool_name)
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

                tool_result = _run_tool(action_name, action_args, db)
                last_tool_name = action_name
                last_tool_result = tool_result

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, default=str),
                })

        fallback = "I completed the available steps but couldn't fully finish the request."
        save_assistant_message(session_id, fallback, tool_name=last_tool_name)
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
