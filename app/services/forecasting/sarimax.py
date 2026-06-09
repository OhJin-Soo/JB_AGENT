from __future__ import annotations

import warnings

import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX


def forecast_seasonal_category(
    values: list[float],
    horizon: int,
    observed_external_features: list[list[float]],
    future_external_features: list[list[float]],
) -> list[float]:
    if len(values) < 12:
        return _average_forecast(values, horizon)

    order = (1, 0, 0)
    seasonal_order = (0, 1, 1, 12) if len(values) >= 24 else (0, 0, 0, 0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SARIMAX(
                values,
                exog=np.asarray(observed_external_features, dtype=float),
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fitted = model.fit(disp=False, maxiter=100)
            forecast = fitted.forecast(steps=horizon, exog=np.asarray(future_external_features, dtype=float))
        return [round(max(float(value), 0), 2) for value in forecast]
    except Exception:
        return _average_forecast(values, horizon)


def _average_forecast(values: list[float], horizon: int) -> list[float]:
    average = sum(values) / len(values) if values else 0.0
    return [round(average, 2)] * horizon
