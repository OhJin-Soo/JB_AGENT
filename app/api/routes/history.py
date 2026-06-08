from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analysis import AnalysisResponse
from app.services.analysis import list_analyses

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[AnalysisResponse])
def list_history_endpoint(db: Session = Depends(get_db)) -> list[AnalysisResponse]:
    return list_analyses(db)
