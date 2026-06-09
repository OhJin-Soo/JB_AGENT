from datetime import date
from math import cos, pi


def build_external_feature_rows(months: list[date], real_estate_asset_count: int = 0) -> list[list[float]]:
    return [_feature_row(month, real_estate_asset_count) for month in months]


def _feature_row(month: date, real_estate_asset_count: int) -> list[float]:
    month_number = month.month
    avg_temp_proxy = 13 + 13 * cos((month_number - 7) * pi / 6)
    cooling_degree_proxy = max(avg_temp_proxy - 22, 0)
    heating_degree_proxy = max(18 - avg_temp_proxy, 0)
    real_estate_growth_proxy = 0.0015 if real_estate_asset_count else 0.0
    return [
        float(month_number),
        round(avg_temp_proxy, 4),
        round(cooling_degree_proxy, 4),
        round(heating_degree_proxy, 4),
        real_estate_growth_proxy,
    ]
