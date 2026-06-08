from collections import defaultdict
from datetime import date

from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    CashflowType,
    CategoryForecast,
    ForecastPoint,
)
from app.services.forecasting.selector import select_model


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def run_rule_based_forecast(request: AnalysisRequest) -> AnalysisResult:
    grouped: dict[tuple[str, CashflowType], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    observed_months = sorted({_month_key(item.date) for item in request.cashflows})

    for item in request.cashflows:
        grouped[(item.category, item.type)][_month_key(item.date)] += item.amount

    categories: list[CategoryForecast] = []
    monthly_income = 0.0
    monthly_expense = 0.0

    for (category, flow_type), monthly_values in sorted(grouped.items()):
        average_amount = sum(monthly_values.values()) / len(observed_months)
        sample_item = next(
            item for item in request.cashflows if item.category == category and item.type == flow_type
        )
        model = select_model(sample_item)
        categories.append(
            CategoryForecast(
                category=category,
                type=flow_type,
                model=model,
                monthly_amount=round(average_amount, 2),
            )
        )
        if flow_type == CashflowType.income:
            monthly_income += average_amount
        else:
            monthly_expense += average_amount

    start_month = max(date(item.date.year, item.date.month, 1) for item in request.cashflows)
    starting_net_worth = sum(asset.current_value for asset in request.assets)
    cumulative_cashflow = 0.0
    forecast: list[ForecastPoint] = []

    for offset in range(1, request.forecast_months + 1):
        month_date = _add_months(start_month, offset)
        net_cashflow = monthly_income - monthly_expense
        cumulative_cashflow += net_cashflow
        forecast.append(
            ForecastPoint(
                month=_month_key(month_date),
                income=round(monthly_income, 2),
                expense=round(monthly_expense, 2),
                net_cashflow=round(net_cashflow, 2),
                cumulative_cashflow=round(cumulative_cashflow, 2),
                net_worth=round(starting_net_worth + cumulative_cashflow, 2),
            )
        )

    summary = build_summary(monthly_income, monthly_expense, forecast, len(observed_months))
    return AnalysisResult(
        forecast=forecast,
        categories=categories,
        summary=summary,
        chart={
            "labels": [point.month for point in forecast],
            "income": [point.income for point in forecast],
            "expense": [point.expense for point in forecast],
            "net_worth": [point.net_worth for point in forecast],
        },
        data_quality={
            "observed_months": len(observed_months),
            "forecast_months": request.forecast_months,
            "method": "rule_based_average_with_model_selection_placeholders",
        },
    )


def build_summary(
    monthly_income: float,
    monthly_expense: float,
    forecast: list[ForecastPoint],
    observed_month_count: int,
) -> str:
    net = monthly_income - monthly_expense
    direction = "증가" if net >= 0 else "감소"
    last = forecast[-1]
    return (
        f"최근 {observed_month_count}개월 데이터를 기준으로 월 평균 수입은 "
        f"{monthly_income:,.0f}원, 월 평균 지출은 {monthly_expense:,.0f}원입니다. "
        f"예상 월 순현금흐름은 {net:,.0f}원이며, 예측 종료 시점의 누적 현금흐름은 "
        f"{last.cumulative_cashflow:,.0f}원으로 {direction}할 것으로 예상됩니다."
    )
