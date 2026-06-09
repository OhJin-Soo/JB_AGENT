from collections import defaultdict
from datetime import date

from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    AssetType,
    CashflowType,
    CategoryForecast,
    ForecastPoint,
)
from app.services.external.context import ExternalFeatureContext
from app.services.forecasting.features import build_external_feature_rows
from app.services.forecasting.sarimax import forecast_seasonal_category
from app.services.forecasting.selector import select_model
from app.services.forecasting.xgboost import forecast_irregular_category


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def run_rule_based_forecast(
    request: AnalysisRequest,
    external_context: ExternalFeatureContext | None = None,
) -> AnalysisResult:
    grouped: dict[tuple[str, CashflowType], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    first_month = min(date(item.date.year, item.date.month, 1) for item in request.cashflows)
    last_month = max(date(item.date.year, item.date.month, 1) for item in request.cashflows)
    observed_month_dates = _continuous_months(first_month, last_month)
    observed_months = [_month_key(month) for month in observed_month_dates]
    future_month_dates = [_add_months(last_month, offset) for offset in range(1, request.forecast_months + 1)]
    real_estate_asset_count = sum(1 for asset in request.assets if asset.type == AssetType.real_estate)
    observed_external_features = build_external_feature_rows(
        observed_month_dates,
        real_estate_asset_count,
        external_context,
    )
    future_external_features = build_external_feature_rows(
        future_month_dates,
        real_estate_asset_count,
        external_context,
    )

    for item in request.cashflows:
        grouped[(item.category, item.type)][_month_key(item.date)] += item.amount

    categories: list[CategoryForecast] = []
    income_forecasts = [0.0] * request.forecast_months
    expense_forecasts = [0.0] * request.forecast_months
    model_counts: dict[str, int] = defaultdict(int)

    for (category, flow_type), monthly_values in sorted(grouped.items()):
        values = [monthly_values.get(month, 0.0) for month in observed_months]
        sample_item = next(
            item for item in request.cashflows if item.category == category and item.type == flow_type
        )
        model = select_model(sample_item)
        forecast_values = _forecast_category_values(
            values,
            request.forecast_months,
            model,
            observed_external_features,
            future_external_features,
        )
        model_counts[model] += 1
        categories.append(
            CategoryForecast(
                category=category,
                type=flow_type,
                model=model,
                monthly_amount=round(sum(forecast_values) / len(forecast_values), 2),
                observed={month: round(value, 2) for month, value in zip(observed_months, values, strict=True)},
                forecast={
                    _month_key(future_month_dates[index]): round(value, 2)
                    for index, value in enumerate(forecast_values)
                },
            )
        )
        target = income_forecasts if flow_type == CashflowType.income else expense_forecasts
        for index, forecast_value in enumerate(forecast_values):
            target[index] += forecast_value

    real_estate_value = sum(asset.current_value for asset in request.assets if asset.type == AssetType.real_estate)
    other_asset_value = sum(asset.current_value for asset in request.assets if asset.type != AssetType.real_estate)
    real_estate_monthly_growth = 0.0015 if real_estate_asset_count else 0.0
    cumulative_cashflow = 0.0
    forecast: list[ForecastPoint] = []

    for index, month_date in enumerate(future_month_dates):
        monthly_income = income_forecasts[index]
        monthly_expense = expense_forecasts[index]
        net_cashflow = monthly_income - monthly_expense
        cumulative_cashflow += net_cashflow
        projected_real_estate_value = real_estate_value * ((1 + real_estate_monthly_growth) ** (index + 1))
        forecast.append(
            ForecastPoint(
                month=_month_key(month_date),
                income=round(monthly_income, 2),
                expense=round(monthly_expense, 2),
                net_cashflow=round(net_cashflow, 2),
                cumulative_cashflow=round(cumulative_cashflow, 2),
                net_worth=round(other_asset_value + projected_real_estate_value + cumulative_cashflow, 2),
            )
        )

    average_income = sum(income_forecasts) / len(income_forecasts) if income_forecasts else 0.0
    average_expense = sum(expense_forecasts) / len(expense_forecasts) if expense_forecasts else 0.0
    summary = build_summary(average_income, average_expense, forecast, len(observed_months))
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
            "real_estate_initial_value": round(real_estate_value, 2),
            "real_estate_monthly_growth_proxy": real_estate_monthly_growth,
            "method": "model_selected_forecast_with_external_features",
            "model_counts": ", ".join(f"{model}:{count}" for model, count in sorted(model_counts.items())),
            "external_features": (
                "month, temperature_or_climatology, cooling_degree_proxy, "
                "heating_degree_proxy, real_estate_growth_rate"
            ),
            "external_data_sources": (
                f"weather={external_context.weather_source if external_context else 'proxy'}, "
                f"real_estate={external_context.real_estate_source if external_context else 'proxy'}"
            ),
        },
    )


def _forecast_category_values(
    values: list[float],
    horizon: int,
    model: str,
    observed_external_features: list[list[float]],
    future_external_features: list[list[float]],
) -> list[float]:
    if model == "sarimax":
        return forecast_seasonal_category(values, horizon, observed_external_features, future_external_features)
    if model == "xgboost":
        return forecast_irregular_category(values, horizon, observed_external_features, future_external_features)
    average_amount = sum(values) / len(values) if values else 0.0
    return [round(average_amount, 2)] * horizon


def _continuous_months(start_month: date, end_month: date) -> list[date]:
    months: list[date] = []
    current = start_month
    while current <= end_month:
        months.append(current)
        current = _add_months(current, 1)
    return months


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
