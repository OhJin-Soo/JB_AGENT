from datetime import date
from math import cos, pi
from app.services.external.context import ExternalFeatureContext


def build_external_feature_rows(
    months: list[date],
    real_estate_asset_count: int = 0,
    context: ExternalFeatureContext | None = None,
) -> list[list[float]]:
    return [_feature_row(month, real_estate_asset_count, context) for month in months]


def _feature_row(month: date, real_estate_asset_count: int, context: ExternalFeatureContext | None) -> list[float]:
    month_number = month.month
    month_key = f"{month.year:04d}-{month.month:02d}"
    avg_temp_proxy = 13 + 13 * cos((month_number - 7) * pi / 6)
    avg_temp = avg_temp_proxy
    if context is not None:
        avg_temp = context.weather_monthly_avg_temp.get(
            month_key,
            context.weather_monthly_climatology.get(month_number, avg_temp_proxy),
        )
    real_estate_growth_proxy = 0.0015 if real_estate_asset_count else 0.0
    if context is not None:
        real_estate_growth_proxy = context.real_estate_monthly_growth.get(
            month_key,
            context.real_estate_recent_growth_avg if real_estate_asset_count else 0.0,
        )
    return [
        float(month_number),
        round(avg_temp, 4),
        round(max(avg_temp - 22, 0), 4),
        round(max(18 - avg_temp, 0), 4),
        real_estate_growth_proxy,
    ]
