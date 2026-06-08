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
    assert result.forecast[0].expense == 1_200_000
    assert result.forecast[-1].cumulative_cashflow == 7_350_000
    assert result.forecast[-1].net_worth == 427_350_000
    assert any(category.category == "전기요금" for category in result.categories)
    assert any(category.category == "연금" for category in result.categories)


def build_sample_cashflows() -> list[CashflowItem]:
    rows: list[CashflowItem] = []
    for month in range(1, 13):
        rows.extend(
            [
                CashflowItem(date=date(2025, month, 1), amount=3_000_000, type=CashflowType.income, category="월급"),
                CashflowItem(date=date(2025, month, 10), amount=650_000, type=CashflowType.income, category="연금"),
                CashflowItem(
                    date=date(2025, month, 5),
                    amount=950_000 + (month - 1) * 15_000,
                    type=CashflowType.expense,
                    category="생활비",
                ),
                CashflowItem(
                    date=date(2025, month, 18),
                    amount=130_000 + ((month - 1) % 4) * 25_000,
                    type=CashflowType.expense,
                    category="전기요금",
                    description="계절성 공과금",
                ),
            ]
        )
    return rows
