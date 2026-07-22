"""Weather-data helpers retained for contextual sports features.

Direct weather-contract prediction is retired. Open-Meteo parsing and station
metadata remain available as data plumbing, while the compatibility signal
class is permanently non-applicable and emits no forecast.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal

# Station coordinates for Kalshi temperature series (city code -> lat/lon and
# a conservative model-error prior in deg F, tightened by the learner later).
CITY_TABLE: dict[str, dict[str, Any]] = {
    "NY": {"lat": 40.7794, "lon": -73.9692, "sigma_prior_f": 2.6, "name": "New York Central Park"},
    "CHI": {"lat": 41.9602, "lon": -87.9316, "sigma_prior_f": 2.8, "name": "Chicago Midway/OHare"},
    "MIA": {"lat": 25.7906, "lon": -80.3164, "sigma_prior_f": 1.9, "name": "Miami Intl"},
    "AUS": {"lat": 30.1975, "lon": -97.6664, "sigma_prior_f": 2.7, "name": "Austin Bergstrom"},
    "DEN": {"lat": 39.8467, "lon": -104.6564, "sigma_prior_f": 3.4, "name": "Denver Intl"},
    "PHIL": {"lat": 39.8683, "lon": -75.2311, "sigma_prior_f": 2.6, "name": "Philadelphia Intl"},
    "LAX": {"lat": 33.9382, "lon": -118.3866, "sigma_prior_f": 2.2, "name": "Los Angeles Intl"},
    # Kalshi's Seattle series ticker is KXHIGHTSEA (city token "TSEA").
    "TSEA": {"lat": 47.4444, "lon": -122.3139, "sigma_prior_f": 2.3, "name": "Seattle Tacoma"},
}

_MODELS = "gfs_seamless,ecmwf_ifs025,icon_seamless"

# Ticker shapes: KXHIGHNY-26JUL09-B78.5 (between) / -T80 (threshold >=)
_SERIES_RE = re.compile(r"^KX(HIGH|LOW)([A-Z]+)-(\d{2}[A-Z]{3}\d{2})-([BT])([\d.]+)$")


def _normal_cdf(x: float, mean: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0 if x >= mean else 0.0
    return 0.5 * (1.0 + math.erf((x - mean) / (sigma * math.sqrt(2.0))))


def default_fetch_daily_temps(lat: float, lon: float, date_iso: str, kind: str) -> list[float]:
    """Fetch per-model daily max/min temperature (F) from Open-Meteo."""
    import httpx

    variable = "temperature_2m_max" if kind == "HIGH" else "temperature_2m_min"
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": variable,
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "start_date": date_iso,
            "end_date": date_iso,
            "models": _MODELS,
        },
        timeout=15,
    )
    response.raise_for_status()
    daily = response.json().get("daily", {})
    values: list[float] = []
    for key, series in daily.items():
        if key.startswith(variable) and isinstance(series, list) and series and series[0] is not None:
            values.append(float(series[0]))
    return values


def parse_temp_ticker(ticker: str) -> dict[str, Any] | None:
    match = _SERIES_RE.match(ticker)
    if not match:
        return None
    kind, city, date_token, style, threshold = match.groups()
    if city not in CITY_TABLE:
        return None
    months = {m: i for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
    year = 2000 + int(date_token[:2])
    month = months.get(date_token[2:5])
    day = int(date_token[5:7])
    if not month:
        return None
    return {
        "kind": kind,
        "city": city,
        "date_iso": f"{year:04d}-{month:02d}-{day:02d}",
        "style": style,  # B = between bucket midpoint threshold, T = >= threshold
        "threshold": float(threshold),
    }


class OpenMeteoWeatherSignal:
    """Retired compatibility shell; weather is contextual sports data only."""

    name = "weather_openmeteo"
    data_only = True
    prediction_authority = False

    def __init__(
        self,
        fetch_daily_temps: Callable[[float, float, str, str], list[float]] | None = None,
        sigma_overrides: dict[str, float] | None = None,
        bias_corrections: dict[str, float] | None = None,
    ) -> None:
        self.fetch_daily_temps = fetch_daily_temps or default_fetch_daily_temps
        # Per-city sigma + bias from the historical backfill (weather_calibration).
        # sigma_overrides tightens/loosens the CDF; bias_corrections subtracts a
        # systematic offset from the ensemble mean. Production wiring loads these
        # from the calibration artifact via from_calibration(); default is priors.
        self.sigma_overrides = sigma_overrides or {}
        self.bias_corrections = bias_corrections or {}

    @classmethod
    def from_calibration(cls, fetch_daily_temps: Callable[..., list[float]] | None = None):
        """Construct with sigma/bias loaded from the backfill artifact."""
        from autonomy.weather_calibration import load_bias_corrections, load_sigma_overrides

        return cls(
            fetch_daily_temps=fetch_daily_temps,
            sigma_overrides=load_sigma_overrides(),
            bias_corrections=load_bias_corrections(),
        )

    def applicable(self, market: MarketView) -> bool:
        return False

    def generate(self, market: MarketView) -> Signal | None:
        return None
