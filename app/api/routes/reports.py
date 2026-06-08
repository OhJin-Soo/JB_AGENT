from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.analysis import get_analysis
from app.services.report import build_pdf_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/analyses/{analysis_id}.pdf")
def download_report_endpoint(analysis_id: int, db: Session = Depends(get_db)) -> Response:
    analysis = get_analysis(analysis_id, db)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    pdf_bytes = build_pdf_report(analysis)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=analysis-{analysis_id}.pdf"},
    )
