from app.schemas.analysis import CategoryForecast


def forecast_irregular_category(category: CategoryForecast) -> float:
    """Placeholder for XGBoost. Keeps the service callable before model training data exists."""
    return category.monthly_amount
