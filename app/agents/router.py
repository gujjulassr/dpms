from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.agents.schemas import AgentChatRequest, AgentChatResponse
from app.agents.service import process_agent_chat
from app.database.connection.database import get_db
from app.modules.auth.service import decode_token


router = APIRouter(prefix="/agents", tags=["Agents"])


def _extract_token_payload(request: Request) -> Optional[dict]:
    """
    Optionally pull decoded JWT payload from Bearer token.
    Returns None if no token or token is invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    return decode_token(token)


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    status_code=status.HTTP_200_OK,
    name="agent_chat",
)
def agent_chat_endpoint(
    payload: AgentChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    # If a valid JWT is present, trusted token identity takes precedence over body values.
    token_payload = _extract_token_payload(request)
    if token_payload:
        payload = payload.model_copy(
            update={
                "role": token_payload.get("role", payload.role),
                "user_id": token_payload.get("user_id", payload.user_id),
            }
        )

    try:
        return process_agent_chat(db, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
