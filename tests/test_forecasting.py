from datetime import date

from app.schemas.analysis import AnalysisRequest, AssetInput, AssetType, CashflowItem, CashflowType
from app.services.forecasting.rules import run_rule_based_forecast


def test_rule_based_forecast_returns_monthly_points() -> None:
    request = AnalysisRequest(
        title="test",
        forecast_months=3,
        save=False,
        cashflows=build_sample_cashflows(),
        assets=[
            AssetInput(type=AssetType.real_estate, name="아파트", current_value=420_000_000),
        ],
    )

    result = run_rule_based_forecast(request)

    assert len(result.forecast) == 3
    assert result.forecast[0].month == "2026-01"
    assert result.forecast[0].income == 3_650_000
    assert result.forecast[0].expense > 0
    assert result.forecast[-1].cumulative_cashflow > 0
    assert result.forecast[-1].net_worth > 420_000_000
    assert any(category.category == "전기요금" and category.model == "sarimax" for category in result.categories)
    assert any(category.category == "생활비" and category.model == "xgboost" for category in result.categories)
    electricity = next(category for category in result.categories if category.category == "전기요금")
    assert electricity.forecast
    assert set(electricity.forecast) == {point.month for point in result.forecast}
    assert any(category.category == "연금" and category.model == "rule_based" for category in result.categories)
    assert result.data_quality["observed_months"] == 24
    assert result.data_quality["method"] == "model_selected_forecast_with_external_features"


def build_sample_cashflows() -> list[CashflowItem]:
    rows: list[CashflowItem] = []
    for index in range(24):
        year = 2024 if index < 12 else 2025
        month = (index % 12) + 1
        rows.extend(
            [
                CashflowItem(date=date(year, month, 1), amount=3_000_000, type=CashflowType.income, category="월급"),
                CashflowItem(date=date(year, month, 10), amount=650_000, type=CashflowType.income, category="연금"),
                CashflowItem(
                    date=date(year, month, 5),
                    amount=950_000 + index * 15_000,
                    type=CashflowType.expense,
                    category="생활비",
                ),
                CashflowItem(
                    date=date(year, month, 18),
                    amount=electricity_sample_amount(month, index),
                    type=CashflowType.expense,
                    category="전기요금",
                    description="계절성 공과금",
                ),
            ]
        )
    return rows


def electricity_sample_amount(month: int, index: int) -> int:
    if month in {1, 2, 7, 8, 12}:
        return 260_000 + (index % 3) * 18_000
    if month in {6, 9}:
        return 190_000 + (index % 2) * 12_000
    return 125_000 + (index % 2) * 9_000
