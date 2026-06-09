import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisRecord
from app.schemas.analysis import AnalysisRequest, AnalysisResponse, AnalysisResult
from app.services.forecasting.rules import run_rule_based_forecast


def create_analysis(request: AnalysisRequest, db: Session) -> AnalysisResponse:
    result = run_rule_based_forecast(request)
    created_at = datetime.utcnow()
    record_id: int | None = None

    if request.save:
        record = AnalysisRecord(
            title=request.title,
            request_json=request.model_dump_json(),
            result_json=result.model_dump_json(),
            summary=result.summary,
            created_at=created_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        record_id = record.id
        created_at = record.created_at

    return AnalysisResponse(id=record_id, title=request.title, created_at=created_at, result=result)


def get_analysis(record_id: int, db: Session) -> AnalysisResponse | None:
    record = db.get(AnalysisRecord, record_id)
    if record is None:
        return None
    return _to_response(record)


def list_analyses(db: Session) -> list[AnalysisResponse]:
    records = db.query(AnalysisRecord).order_by(AnalysisRecord.created_at.desc()).all()
    return [_to_response(record) for record in records]


def _to_response(record: AnalysisRecord) -> AnalysisResponse:
    result = AnalysisResult.model_validate(json.loads(record.result_json))
    _hydrate_result_metadata(result, record.request_json)
    return AnalysisResponse(
        id=record.id,
        title=record.title,
        created_at=record.created_at,
        result=result,
    )


def _hydrate_result_metadata(result: AnalysisResult, request_json: str) -> None:
    try:
        request_data = json.loads(request_json)
    except json.JSONDecodeError:
        return
    if "real_estate_initial_value" not in result.data_quality:
        real_estate_value = sum(
            float(asset.get("current_value", 0) or 0)
            for asset in request_data.get("assets", [])
            if asset.get("type") == "real_estate"
        )
        result.data_quality["real_estate_initial_value"] = round(real_estate_value, 2)
        result.data_quality["real_estate_monthly_growth_proxy"] = 0.0015 if real_estate_value else 0.0
    if any(not category.forecast for category in result.categories):
        try:
            refreshed = run_rule_based_forecast(AnalysisRequest.model_validate(request_data))
        except Exception:
            return
        forecast_by_key = {(category.category, category.type): category.forecast for category in refreshed.categories}
        for category in result.categories:
            category.forecast = forecast_by_key.get((category.category, category.type), category.forecast)
