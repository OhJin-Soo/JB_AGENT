from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis import create_analysis, get_analysis

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse)
def create_analysis_endpoint(request: AnalysisRequest, db: Session = Depends(get_db)) -> AnalysisResponse:
    return create_analysis(request, db)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis_endpoint(analysis_id: int, db: Session = Depends(get_db)) -> AnalysisResponse:
    analysis = get_analysis(analysis_id, db)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis
