from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.graph import run_agent
from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return await run_agent(request, db)
