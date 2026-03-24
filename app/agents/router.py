from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session


from app.agents.schemas import AgentChatRequest, AgentChatResponse
from app.agents.service import process_agent_chat
from app.database.connection.database import get_db


router = APIRouter(prefix="/agents", tags=["Agents"])
@router.post(
    "/chat",
    response_model=AgentChatResponse,
    status_code=status.HTTP_200_OK,
    name="agent_chat",
)
def agent_chat_endpoint(payload: AgentChatRequest, db: Session = Depends(get_db)):
    try:
        return process_agent_chat(db, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc