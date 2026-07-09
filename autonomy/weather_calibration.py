"""Weather calibration backfill: pre-train per-city forecast error.

Open-Meteo exposes both the *historical forecast* (what each model predicted
for a past day) and the *archive* (ERA5 reanalysis actuals). Comparing them
over a trailing window yields, per city, the ensemble's real error
distribution — a bias (systematic offset) and a sigma (RMSE). Seeding the
weather signal with these means its very first live forecast is calibrated to
that station instead of starting from a hand-guessed prior.

Read-only; writes one JSON calibration artifact the signal loads at startup.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from autonomy.signals.weather_openmeteo import CITY_TABLE

CALIBRATION_PATH = Path("runtime/autonomy/weather_calibration.json")
_HIST_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_MODELS = "gfs_seamless,ecmwf_ifs025,icon_seamless"
MIN_SAMPLES = 10
SIGMA_FLOOR_F = 0.8


def _daily_variable(kind: str) -> str:
    return "temperature_2m_max" if kind == "HIGH" else "temperature_2m_min"


def default_fetch_historical_forecast(lat: float, lon: float, start: str, end: str, kind: str) -> dict[str, list]:
    import httpx

    variable = _daily_variable(kind)
    response = httpx.get(
        _HIST_FORECAST_URL,
        params={
            "latitude": lat, "longitude": lon, "daily": variable,
            "temperature_unit": "fahrenheit", "timezone": "America/New_York",
            "start_date": start, "end_date": end, "models": _MODELS,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("daily", {})


def default_fetch_archive_actuals(lat: float, lon: float, start: str, end: str, kind: str) -> dict[str, list]:
    import httpx

    variable = _daily_variable(kind)
    response = httpx.get(
        _ARCHIVE_URL,
        params={
            "latitude": lat, "longitude": lon, "daily": variable,
            "temperature_unit": "fahrenheit", "timezone": "America/New_York",
            "start_date": start, "end_date": end,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("daily", {})


def _ensemble_mean_by_date(daily: dict[str, list], variable: str) -> dict[str, float]:
    """Average all model columns for `variable` per date."""
    times = daily.get("time", [])
    columns = [v for k, v in daily.items() if k.startswith(variable) and isinstance(v, list)]
    out: dict[str, float] = {}
    for i, date in enumerate(times):
        vals = [col[i] for col in columns if i < len(col) and col[i] is not None]
        if vals:
            out[date] = sum(vals) / len(vals)
    return out


def _actuals_by_date(daily: dict[str, list], variable: str) -> dict[str, float]:
    times = daily.get("time", [])
    series = daily.get(variable, [])
    return {date: series[i] for i, date in enumerate(times)
            if i < len(series) and series[i] is not None}


def calibrate_city(
    city_code: str,
    kind: str = "HIGH",
    lookback_days: int = 120,
    today_iso: str | None = None,
    fetch_forecast: Callable[..., dict[str, list]] | None = None,
    fetch_actuals: Callable[..., dict[str, list]] | None = None,
) -> dict[str, Any] | None:
    """Compute bias + sigma for one city from the trailing window."""
    city = CITY_TABLE.get(city_code)
    if city is None:
        return None
    fetch_forecast = fetch_forecast or default_fetch_historical_forecast
    fetch_actuals = fetch_actuals or default_fetch_archive_actuals
    # Archive reanalysis lags a few days; end the window before it.
    end_dt = (datetime.fromisoformat(today_iso) if today_iso else datetime.now(timezone.utc)) - timedelta(days=5)
    start_dt = end_dt - timedelta(days=lookback_days)
    start, end = start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")
    variable = _daily_variable(kind)

    try:
        forecast_mean = _ensemble_mean_by_date(fetch_forecast(city["lat"], city["lon"], start, end, kind), variable)
        actuals = _actuals_by_date(fetch_actuals(city["lat"], city["lon"], start, end, kind), variable)
    except Exception as exc:
        return {"city": city_code, "kind": kind, "error": f"{type(exc).__name__}", "usable": False}

    residuals = [forecast_mean[d] - actuals[d] for d in forecast_mean if d in actuals]
    if len(residuals) < MIN_SAMPLES:
        return {"city": city_code, "kind": kind, "samples": len(residuals), "usable": False}

    n = len(residuals)
    bias = sum(residuals) / n
    variance = sum((r - bias) ** 2 for r in residuals) / max(1, n - 1)
    sigma = max(SIGMA_FLOOR_F, math.sqrt(variance))
    mae = sum(abs(r) for r in residuals) / n
    return {
        "city": city_code, "kind": kind, "samples": n,
        "bias_f": round(bias, 3), "sigma_f": round(sigma, 3), "mae_f": round(mae, 3),
        "usable": True, "window": [start, end],
    }


def run_backfill(
    city_codes: list[str] | None = None,
    kind: str = "HIGH",
    lookback_days: int = 120,
    out_path: Path | None = None,
    today_iso: str | None = None,
    fetch_forecast: Callable[..., dict[str, list]] | None = None,
    fetch_actuals: Callable[..., dict[str, list]] | None = None,
) -> dict[str, Any]:
    city_codes = city_codes or list(CITY_TABLE.keys())
    out_path = out_path or CALIBRATION_PATH
    cities: dict[str, Any] = {}
    for code in city_codes:
        result = calibrate_city(code, kind, lookback_days, today_iso, fetch_forecast, fetch_actuals)
        if result is not None:
            cities[code] = result
    report = {
        "report_name": "WEATHER_CALIBRATION_BACKFILL",
        "kind": kind,
        "lookback_days": lookback_days,
        "cities": cities,
        "usable_count": sum(1 for c in cities.values() if c.get("usable")),
        "created_at": (today_iso or datetime.now(timezone.utc).isoformat()),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def load_sigma_overrides(path: Path | None = None) -> dict[str, float]:
    path = path or CALIBRATION_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {code: float(c["sigma_f"]) for code, c in data.get("cities", {}).items()
            if c.get("usable") and "sigma_f" in c}


def load_bias_corrections(path: Path | None = None) -> dict[str, float]:
    path = path or CALIBRATION_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {code: float(c["bias_f"]) for code, c in data.get("cities", {}).items()
            if c.get("usable") and "bias_f" in c}
