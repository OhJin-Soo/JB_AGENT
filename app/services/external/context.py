from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
import re

from app.services.external.real_estate import RealEstateClient
from app.services.external.weather import WeatherClient


@dataclass(frozen=True)
class ExternalFeatureContext:
    weather_monthly_avg_temp: dict[str, float] = field(default_factory=dict)
    weather_monthly_climatology: dict[int, float] = field(default_factory=dict)
    real_estate_monthly_growth: dict[str, float] = field(default_factory=dict)
    real_estate_recent_growth_avg: float = 0.0015
    weather_source: str = "proxy"
    real_estate_source: str = "proxy"


async def collect_external_feature_context(today: date | None = None) -> ExternalFeatureContext:
    current = today or date.today()
    start_date = date(current.year - 5, current.month, 1)

    weather_raw, real_estate_data = await asyncio.gather(
        _fetch_weather_payload(start_date, current),
        _fetch_real_estate_payload(start_date, current),
    )

    weather_monthly_avg_temp: dict[str, float] = {}
    weather_monthly_climatology: dict[int, float] = {}
    weather_source = "proxy"
    if isinstance(weather_raw, str) and weather_raw.strip():
        weather_context = parse_weather_monthly_context(weather_raw)
        weather_monthly_avg_temp = weather_context["monthly_avg_temp"]
        weather_monthly_climatology = weather_context["monthly_climatology"]
        if weather_monthly_avg_temp or weather_monthly_climatology:
            weather_source = "kma_sfcdd3.php"

    real_estate_monthly_growth: dict[str, float] = {}
    real_estate_recent_growth_avg = 0.0015
    real_estate_source = "proxy"
    if isinstance(real_estate_data, dict) and real_estate_data:
        real_estate_context = parse_real_estate_monthly_growth_context(real_estate_data)
        real_estate_monthly_growth = real_estate_context["monthly_growth"]
        real_estate_recent_growth_avg = real_estate_context["recent_growth_avg"]
        if real_estate_monthly_growth:
            real_estate_source = "reb_openapi"

    return ExternalFeatureContext(
        weather_monthly_avg_temp=weather_monthly_avg_temp,
        weather_monthly_climatology=weather_monthly_climatology,
        real_estate_monthly_growth=real_estate_monthly_growth,
        real_estate_recent_growth_avg=real_estate_recent_growth_avg,
        weather_source=weather_source,
        real_estate_source=real_estate_source,
    )


async def _fetch_weather_payload(start_date: date, current: date) -> str:
    try:
        return await WeatherClient().fetch_daily_weather(start_date=start_date, end_date=current)
    except Exception:
        return ""


async def _fetch_real_estate_payload(start_date: date, current: date) -> dict:
    try:
        return await RealEstateClient().fetch_land_price_changes(start_date=start_date, end_date=current)
    except Exception:
        return {}


def parse_weather_monthly_context(raw_text: str) -> dict[str, dict]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    header_index = next((index for index, line in enumerate(lines) if _looks_like_weather_header(line)), None)
    if header_index is None:
        return {"monthly_avg_temp": {}, "monthly_climatology": {}}

    header_tokens = _split_tokens(lines[header_index])
    tm_index = _find_token_index(header_tokens, {"TM"})
    temp_index = _find_token_index(header_tokens, {"TA_AVG", "TA"})
    if tm_index is None or temp_index is None:
        return {"monthly_avg_temp": {}, "monthly_climatology": {}}

    daily_temp_by_month: dict[str, list[float]] = defaultdict(list)
    monthly_temp_by_year_month: dict[str, list[float]] = defaultdict(list)

    for line in lines[header_index + 1 :]:
        tokens = _split_tokens(line)
        if len(tokens) <= max(tm_index, temp_index):
            continue
        tm_value = tokens[tm_index]
        temp_value = _parse_float(tokens[temp_index])
        if temp_value is None:
            continue
        month_key = _normalize_ymd_to_month_key(tm_value)
        if month_key is None:
            continue
        monthly_temp_by_year_month[month_key].append(temp_value)
        daily_temp_by_month[month_key[:7]].append(temp_value)

    monthly_avg_temp = {
        month_key: round(sum(values) / len(values), 4)
        for month_key, values in sorted(daily_temp_by_month.items())
        if values
    }
    climatology_by_month: dict[int, list[float]] = defaultdict(list)
    for month_key, values in monthly_temp_by_year_month.items():
        month_number = int(month_key[-2:])
        climatology_by_month[month_number].extend(values)

    monthly_climatology = {
        month_number: round(sum(values) / len(values), 4)
        for month_number, values in sorted(climatology_by_month.items())
        if values
    }
    return {"monthly_avg_temp": monthly_avg_temp, "monthly_climatology": monthly_climatology}


def parse_real_estate_monthly_growth_context(data: dict) -> dict[str, dict | float]:
    monthly_growth: dict[str, float] = {}
    values: list[float] = []
    for row in _iter_dicts(data):
        if "WRTTIME_IDTFR_ID" not in row or "DTA_VAL" not in row:
            continue
        month_key = _normalize_year_month_key(str(row.get("WRTTIME_IDTFR_ID", "")))
        growth = _parse_float(row.get("DTA_VAL"))
        if month_key is None or growth is None:
            continue
        monthly_growth[month_key] = growth / 100.0
        values.append(growth / 100.0)
    recent_window = values[-12:] if len(values) >= 12 else values
    recent_growth_avg = round(sum(recent_window) / len(recent_window), 6) if recent_window else 0.0015
    return {"monthly_growth": monthly_growth, "recent_growth_avg": recent_growth_avg}


def _looks_like_weather_header(line: str) -> bool:
    tokens = _split_tokens(line)
    return "TM" in tokens and any(token in tokens for token in ("TA_AVG", "TA"))


def _split_tokens(line: str) -> list[str]:
    return [token for token in re.split(r"\s+", line.strip()) if token]


def _find_token_index(tokens: list[str], candidates: set[str]) -> int | None:
    for index, token in enumerate(tokens):
        if token in candidates:
            return index
    return None


def _normalize_ymd_to_month_key(value: str) -> str | None:
    cleaned = re.sub(r"[^0-9]", "", value)
    if len(cleaned) < 6:
        return None
    if len(cleaned) >= 8:
        return f"{cleaned[:4]}-{cleaned[4:6]}"
    return f"{cleaned[:4]}-{cleaned[4:6]}"


def _normalize_year_month_key(value: str) -> str | None:
    cleaned = re.sub(r"[^0-9]", "", value)
    if len(cleaned) < 6:
        return None
    return f"{cleaned[:4]}-{cleaned[4:6]}"


def _iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _parse_float(value) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
