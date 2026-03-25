from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.agents.schemas import AgentChatRequest, AgentChatResponse
from app.agents.service import process_agent_chat
from app.database.connection.database import get_db
from app.modules.auth.service import decode_token


router = APIRouter(prefix="/agents", tags=["Agents"])


def _extract_role_from_token(request: Request) -> Optional[str]:
    """
    Optionally pull role from Bearer token.
    Returns None if no token or token is invalid — caller falls back to payload.role.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        return None
    return payload.get("role")


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
    # If a valid JWT is present, its role takes precedence over the body role.
    # This ensures a patient cannot escalate their own role by editing the request.
    token_role = _extract_role_from_token(request)
    if token_role:
        # Override payload role with the one from the verified token
        payload = payload.model_copy(update={"role": token_role})

    try:
        return process_agent_chat(db, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
