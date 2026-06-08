from datetime import date

from app.schemas.analysis import AnalysisRequest, CashflowItem, CashflowType
from app.services.forecasting.rules import run_rule_based_forecast


def test_rule_based_forecast_returns_monthly_points() -> None:
    request = AnalysisRequest(
        title="test",
        forecast_months=3,
        save=False,
        cashflows=[
            CashflowItem(date=date(2026, 1, 1), amount=3_000_000, type=CashflowType.income, category="월급"),
            CashflowItem(date=date(2026, 2, 1), amount=3_000_000, type=CashflowType.income, category="월급"),
            CashflowItem(date=date(2026, 3, 1), amount=3_000_000, type=CashflowType.income, category="월급"),
            CashflowItem(date=date(2026, 1, 3), amount=900_000, type=CashflowType.expense, category="생활비"),
            CashflowItem(date=date(2026, 2, 3), amount=1_000_000, type=CashflowType.expense, category="생활비"),
            CashflowItem(date=date(2026, 3, 3), amount=1_100_000, type=CashflowType.expense, category="생활비"),
        ],
    )

    result = run_rule_based_forecast(request)

    assert len(result.forecast) == 3
    assert result.forecast[0].month == "2026-04"
    assert result.forecast[0].income == 3_000_000
    assert result.forecast[0].expense == 1_000_000
    assert result.forecast[-1].cumulative_cashflow == 6_000_000
