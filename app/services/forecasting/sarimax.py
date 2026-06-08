from app.schemas.analysis import CategoryForecast


def forecast_seasonal_category(category: CategoryForecast) -> float:
    """Placeholder for SARIMAX. Keeps the service callable before model training data exists."""
    return category.monthly_amount
