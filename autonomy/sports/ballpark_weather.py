"""MLB ballpark table + keyless Open-Meteo hourly weather fetch.

Weather prediction was retired from the trading verticals (net loser vs the
sharp Kalshi weather market — see `autonomy/scanner.py`); this module
repurposes the same keyless Open-Meteo pipeline as an MLB game-time
*feature*: fetch temperature + wind at a ballpark near first pitch and
(Task 3) turn them into HR/run modifiers the plate-appearance simulator
already knows how to consume via `park_hr_factor`-style multipliers.

`cf_bearing_deg` is the compass bearing (0=N, 90=E, 180=S, 270=W) from home
plate toward center field. It lets a later step project wind direction onto
the out-to-CF axis (blowing out raises HR odds, blowing in lowers them).
Real-park bearings are well documented for only a few parks (e.g. Fenway's
famous ~45 deg "Green Monster" orientation, Wrigley's ~30 deg); the rest
below are sensible per-park estimates consistent with the general MLB
orientation convention (home plate positioned so the batter does not face
the setting sun, i.e. center field points roughly N through ESE for the
large majority of parks). Where a bearing is an estimate rather than a
confirmed survey figure, it is noted inline. Coordinates are the
approximate home-plate location for each park (public stadium geodata),
accurate enough for a same-city Open-Meteo hourly-forecast lookup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Ballpark:
    name: str
    lat: float
    lon: float
    cf_bearing_deg: float  # home-plate -> center-field compass bearing
    is_dome: bool  # True only for parks that are effectively always closed


@dataclass(frozen=True)
class GameWeather:
    temperature_f: float
    wind_speed_mph: float
    wind_direction_deg: float
    source: str = "open_meteo"  # provenance of the reading


# Team abbreviation -> Ballpark. Keys follow the ESPN/StatsAPI convention
# already used elsewhere in this repo (see autonomy/sports/espn.py's
# canonical_team: "AZ" canonicalizes to "ARI", "CWS" to "CHW"). The
# Athletics play as "ATH" (Sutter Health Park, West Sacramento, their
# temporary home before Las Vegas) as of the 2025-2027 seasons.
#
# Retractable-roof parks (ARI, HOU, MIL, SEA, TEX, TOR, MIA) are stored as
# is_dome=False (open by default) per the plan's Task 2 note — modeling
# actual roof-state per game is deferred to a later feature-discovery pass.
# Tropicana Field (TB) is the one park that is effectively always closed,
# so it is the only is_dome=True entry.
BALLPARKS: dict[str, Ballpark] = {
    "ARI": Ballpark("Chase Field", 33.4455, -112.0667, 15.0, is_dome=False),  # retractable; bearing estimate
    "ATL": Ballpark("Truist Park", 33.8907, -84.4677, 20.0, is_dome=False),  # bearing estimate
    "BAL": Ballpark("Oriole Park at Camden Yards", 39.2839, -76.6217, 30.0, is_dome=False),  # bearing estimate
    "BOS": Ballpark("Fenway Park", 42.3467, -71.0972, 45.0, is_dome=False),  # known orientation
    "CHC": Ballpark("Wrigley Field", 41.9484, -87.6553, 30.0, is_dome=False),  # known orientation
    "CHW": Ballpark("Guaranteed Rate Field", 41.8299, -87.6338, 15.0, is_dome=False),  # bearing estimate
    "CIN": Ballpark("Great American Ball Park", 39.0979, -84.5063, 5.0, is_dome=False),  # bearing estimate
    "CLE": Ballpark("Progressive Field", 41.4962, -81.6852, 5.0, is_dome=False),  # bearing estimate
    "COL": Ballpark("Coors Field", 39.7559, -104.9942, 50.0, is_dome=False),  # bearing estimate
    "DET": Ballpark("Comerica Park", 42.3390, -83.0485, 60.0, is_dome=False),  # bearing estimate
    "HOU": Ballpark("Minute Maid Park", 29.7573, -95.3555, 35.0, is_dome=False),  # retractable; bearing estimate
    "KC": Ballpark("Kauffman Stadium", 39.0517, -94.4803, 80.0, is_dome=False),  # bearing estimate (unusually easterly)
    "LAA": Ballpark("Angel Stadium", 33.8003, -117.8827, 20.0, is_dome=False),  # bearing estimate
    "LAD": Ballpark("Dodger Stadium", 34.0739, -118.2400, 20.0, is_dome=False),  # bearing estimate
    "MIA": Ballpark("loanDepot Park", 25.7781, -80.2196, 35.0, is_dome=False),  # retractable; bearing estimate
    "MIL": Ballpark("American Family Field", 43.0280, -87.9712, 20.0, is_dome=False),  # retractable; bearing estimate
    "MIN": Ballpark("Target Field", 44.9817, -93.2776, 90.0, is_dome=False),  # bearing estimate (unusually easterly)
    "NYM": Ballpark("Citi Field", 40.7571, -73.8458, 30.0, is_dome=False),  # bearing estimate
    "NYY": Ballpark("Yankee Stadium", 40.8296, -73.9262, 75.0, is_dome=False),  # bearing estimate
    "ATH": Ballpark("Sutter Health Park", 38.5802, -121.5127, 45.0, is_dome=False),  # temporary home; bearing estimate
    "PHI": Ballpark("Citizens Bank Park", 39.9061, -75.1665, 15.0, is_dome=False),  # bearing estimate
    "PIT": Ballpark("PNC Park", 40.4469, -80.0057, 65.0, is_dome=False),  # bearing estimate
    "SD": Ballpark("Petco Park", 32.7073, -117.1566, 10.0, is_dome=False),  # bearing estimate
    "SEA": Ballpark("T-Mobile Park", 47.5914, -122.3325, 45.0, is_dome=False),  # retractable; bearing estimate
    "SF": Ballpark("Oracle Park", 37.7786, -122.3893, 85.0, is_dome=False),  # bearing estimate (faces the bay)
    "STL": Ballpark("Busch Stadium", 38.6226, -90.1928, 30.0, is_dome=False),  # bearing estimate
    "TB": Ballpark("Tropicana Field", 27.7683, -82.6534, 45.0, is_dome=True),  # always closed
    "TEX": Ballpark("Globe Life Field", 32.7473, -97.0842, 40.0, is_dome=False),  # retractable; bearing estimate
    "TOR": Ballpark("Rogers Centre", 43.6414, -79.3894, 10.0, is_dome=False),  # retractable; bearing estimate
    "WSH": Ballpark("Nationals Park", 38.8730, -77.0074, 30.0, is_dome=False),  # bearing estimate
}


def default_fetch_hourly_weather(lat: float, lon: float, date_iso: str, hour_utc: int) -> dict[str, Any]:
    """Keyless Open-Meteo hourly forecast for a ballpark's game date.

    Mirrors the httpx GET + timeout=20 + raise_for_status idiom used by
    `autonomy.signals.weather_openmeteo.default_fetch_daily_temps`.

    `date_iso` is the (UTC) calendar date of the game; Open-Meteo's hourly
    endpoint defaults to UTC when no `timezone` parameter is supplied, so a
    single-day window's `hourly.time` array runs 00:00..23:00 UTC and
    `hour_utc` (0-23, the scheduled first-pitch hour in UTC) indexes
    directly into it — callers pass `hour_utc` straight through as the
    `hour_index` argument to `parse_hourly_weather`.
    """
    import httpx

    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "start_date": date_iso,
            "end_date": date_iso,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def parse_hourly_weather(payload: dict[str, Any], hour_index: int) -> GameWeather | None:
    """Extract the reading at `hour_index` from an Open-Meteo hourly payload.

    Every field is defensively parsed: a missing `hourly` block, missing or
    non-list series, an out-of-range/negative index, or a non-numeric value
    all resolve to `None` rather than raising.
    """
    hourly = payload.get("hourly") if isinstance(payload, dict) else None
    if not isinstance(hourly, dict):
        return None

    temps = hourly.get("temperature_2m")
    winds = hourly.get("wind_speed_10m")
    directions = hourly.get("wind_direction_10m")
    if not isinstance(temps, list) or not isinstance(winds, list) or not isinstance(directions, list):
        return None

    if hour_index < 0 or hour_index >= len(temps) or hour_index >= len(winds) or hour_index >= len(directions):
        return None

    try:
        temperature_f = float(temps[hour_index])
        wind_speed_mph = float(winds[hour_index])
        wind_direction_deg = float(directions[hour_index])
    except (TypeError, ValueError):
        return None

    return GameWeather(
        temperature_f=temperature_f,
        wind_speed_mph=wind_speed_mph,
        wind_direction_deg=wind_direction_deg,
    )
