from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CashflowType(StrEnum):
    income = "income"
    expense = "expense"


class CashflowItem(BaseModel):
    date: date
    amount: float = Field(gt=0)
    type: CashflowType
    category: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)


class AssetType(StrEnum):
    cash = "cash"
    pension = "pension"
    real_estate = "real_estate"
    other = "other"


class AssetInput(BaseModel):
    type: AssetType
    name: str = Field(min_length=1, max_length=120)
    current_value: float = Field(ge=0)
    region_code: str | None = None


class AnalysisRequest(BaseModel):
    title: str = Field(default="Cashflow analysis", max_length=120)
    cashflows: list[CashflowItem] = Field(min_length=1)
    assets: list[AssetInput] = Field(default_factory=list)
    forecast_months: int = Field(ge=1, le=120)
    save: bool = True

    @model_validator(mode="after")
    def validate_history_length(self) -> "AnalysisRequest":
        months = {(item.date.year, item.date.month) for item in self.cashflows}
        if len(months) < 3:
            raise ValueError("At least 3 months of cashflow data is required for a useful forecast.")
        return self


class ForecastPoint(BaseModel):
    month: str
    income: float
    expense: float
    net_cashflow: float
    cumulative_cashflow: float
    net_worth: float


class CategoryForecast(BaseModel):
    category: str
    type: CashflowType
    model: str
    monthly_amount: float
    forecast: dict[str, float] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    forecast: list[ForecastPoint]
    categories: list[CategoryForecast]
    summary: str
    chart: dict[str, list[float] | list[str]]
    data_quality: dict[str, str | int | float]


class AnalysisResponse(BaseModel):
    id: int | None
    title: str
    created_at: datetime
    result: AnalysisResult
