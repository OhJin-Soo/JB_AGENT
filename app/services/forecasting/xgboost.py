from __future__ import annotations

import numpy as np


def forecast_irregular_category(
    values: list[float],
    horizon: int,
    observed_external_features: list[list[float]],
    future_external_features: list[list[float]],
) -> list[float]:
    if len(values) < 18:
        return _average_forecast(values, horizon)

    rows: list[list[float]] = []
    targets: list[float] = []
    for index in range(2, len(values)):
        rows.append(_feature_row(index, values, observed_external_features[index]))
        targets.append(values[index])

    try:
        from xgboost import XGBRegressor

        model = XGBRegressor(
            n_estimators=80,
            max_depth=3,
            learning_rate=0.08,
            objective="reg:squarederror",
            random_state=42,
        )
        model.fit(np.asarray(rows, dtype=float), np.asarray(targets, dtype=float))

        history = list(values)
        predictions: list[float] = []
        for step in range(horizon):
            feature_row = _feature_row(len(history), history, future_external_features[step])
            prediction = max(float(model.predict(np.asarray([feature_row], dtype=float))[0]), 0)
            rounded = round(prediction, 2)
            predictions.append(rounded)
            history.append(rounded)
        return predictions
    except Exception:
        return _average_forecast(values, horizon)


def _feature_row(index: int, values: list[float], external_features: list[float]) -> list[float]:
    lag_1 = values[index - 1]
    lag_2 = values[index - 2]
    rolling_3 = sum(values[max(0, index - 3) : index]) / min(3, index)
    trend = float(index)
    return [trend, lag_1, lag_2, rolling_3, *external_features]


def _average_forecast(values: list[float], horizon: int) -> list[float]:
    average = sum(values) / len(values) if values else 0.0
    return [round(average, 2)] * horizon
