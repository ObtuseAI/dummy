"""WS-10: NFL/NCAAF outdoor-weather adjustment to game TOTALS only.

Same keyless-Open-Meteo shape as `autonomy/sports/ballpark_weather.py`
(MLB, shipped, NOT modified here), but football needs one extra hourly
field ballpark_weather.py never requests: precipitation intensity (as a
WMO `weathercode`), so a heavy-precip reading can dock points the way the
brief specifies. That is the entire reason this module owns its own fetch
function instead of importing ballpark_weather's -- the URL/pattern
(httpx GET, `temperature_unit=fahrenheit`, `wind_speed_unit=mph`,
single-day `start_date==end_date` window, hour_utc indexing straight into
the 0..23 hourly arrays) is otherwise identical.

Adjustment hits the TOTALS mean ONLY. Wind/cold/precip suppress both
offenses roughly symmetrically -- there is no directional read here, so
this module never touches winner or spread pricing; the hook in
autonomy/signals/sports_intelligence.py applies the returned delta to
`expected_total` inside the "total" market branch exclusively, before that
branch's over/under ladder is priced. See that module for the wiring.

Fail-closed at every step: an unmapped team, a domed/retractable-roof
stadium, an unparseable kickoff timestamp, a raised fetch exception, or a
defensively-parsed-away reading (missing/short hourly arrays, non-numeric
values) all resolve to a ZERO adjustment with an EMPTY features dict --
byte-identical to this whole feature being disabled. Never silently
default to a "neutral" non-zero reading.

COVERAGE (intentionally partial, not a bug):
  - NFL: all 32 current stadiums.
  - College: the top-40 programs only (see COLLEGE_STADIUMS below). Every
    other FBS/FCS program returns (0.0, {}) via the same fail-closed path
    as a fetch failure -- "uncovered" and "zero effect measured" are
    indistinguishable on purpose (honest partial coverage beats a
    fabricated coordinate). Do not read a college total's absent weather
    features as "calm conditions confirmed" -- it may just mean the team
    is outside the top-40 table.

Coordinates below are approximate stadium/campus locations (public
geodata), accurate enough for a same-city Open-Meteo hourly lookup --
same standard ballpark_weather.py already uses for MLB parks. None are
fabricated placeholders.

BUILD-TIME PROBE (2026-07-13, network confirmed reachable): fetched
Arrowhead Stadium's coordinates (39.0489, -94.4839) with
`hourly=temperature_2m,wind_speed_10m,weathercode,precipitation`. Response
included all four series (24 hourly entries, `weathercode` as WMO integer
codes, `precipitation` in mm) -- confirms the extra fields this module
needs beyond ballpark_weather's request actually exist on the endpoint. A
5-hour trimmed slice of that real response is committed at
tests/fixtures/open_meteo_football_weather_kc_probe.json and exercised by
tests/test_autonomy_football_weather.py's parse test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable


@dataclass(frozen=True)
class StadiumSite:
    name: str
    lat: float
    lon: float
    is_dome: bool  # fixed dome or retractable/fixed roof normally closed


@dataclass(frozen=True)
class FootballWeatherReading:
    temperature_f: float
    wind_speed_mph: float
    weather_code: float  # WMO code, see HEAVY_PRECIP_CODES below
    source: str = "open_meteo"


# ---------------------------------------------------------------- NFL table
# Team abbreviation -> StadiumSite, ESPN's own convention (upper-case, no
# alias table needed -- unlike MLB's AZ/CWS quirks, NFL abbreviations here
# match ESPN's scoreboard directly: see autonomy/sports/espn.py's
# canonical_team, a no-op for any league other than "mlb").
#
# Domes/retractable-or-fixed-roof-closed stadiums (NO adjustment, ever):
# ARI, ATL, DAL, DET, HOU, IND, LV, MIN, NO -- plus BOTH Los Angeles teams
# (LAC and LAR), since they share the same building, SoFi Stadium. The
# brief's own enumeration named only "LAR/SoFi"; LAC is added here for
# physical correctness (weather cannot tell the two tenants apart -- see
# the WS-10 report for the full rationale) rather than followed literally
# at the cost of an inconsistent same-building reading.
NFL_STADIUMS: dict[str, StadiumSite] = {
    "ARI": StadiumSite("State Farm Stadium", 33.5276, -112.2626, is_dome=True),
    "ATL": StadiumSite("Mercedes-Benz Stadium", 33.7554, -84.4008, is_dome=True),
    "BAL": StadiumSite("M&T Bank Stadium", 39.2780, -76.6227, is_dome=False),
    "BUF": StadiumSite("Highmark Stadium", 42.7738, -78.7870, is_dome=False),
    "CAR": StadiumSite("Bank of America Stadium", 35.2258, -80.8528, is_dome=False),
    "CHI": StadiumSite("Soldier Field", 41.8623, -87.6167, is_dome=False),
    "CIN": StadiumSite("Paycor Stadium", 39.0954, -84.5160, is_dome=False),
    "CLE": StadiumSite("Cleveland Browns Stadium", 41.5061, -81.6995, is_dome=False),
    "DAL": StadiumSite("AT&T Stadium", 32.7473, -97.0945, is_dome=True),
    "DEN": StadiumSite("Empower Field at Mile High", 39.7439, -105.0201, is_dome=False),
    "DET": StadiumSite("Ford Field", 42.3400, -83.0456, is_dome=True),
    "GB": StadiumSite("Lambeau Field", 44.5013, -88.0622, is_dome=False),
    "HOU": StadiumSite("NRG Stadium", 29.6847, -95.4107, is_dome=True),
    "IND": StadiumSite("Lucas Oil Stadium", 39.7601, -86.1639, is_dome=True),
    "JAX": StadiumSite("EverBank Stadium", 30.3239, -81.6373, is_dome=False),
    "KC": StadiumSite("Arrowhead Stadium", 39.0489, -94.4839, is_dome=False),
    "LAC": StadiumSite("SoFi Stadium", 33.9535, -118.3392, is_dome=True),  # shares building w/ LAR
    "LAR": StadiumSite("SoFi Stadium", 33.9535, -118.3392, is_dome=True),
    "LV": StadiumSite("Allegiant Stadium", 36.0909, -115.1833, is_dome=True),
    "MIA": StadiumSite("Hard Rock Stadium", 25.9580, -80.2389, is_dome=False),
    "MIN": StadiumSite("U.S. Bank Stadium", 44.9736, -93.2575, is_dome=True),
    "NE": StadiumSite("Gillette Stadium", 42.0909, -71.2643, is_dome=False),
    "NO": StadiumSite("Caesars Superdome", 29.9511, -90.0812, is_dome=True),
    "NYG": StadiumSite("MetLife Stadium", 40.8135, -74.0745, is_dome=False),  # shares building w/ NYJ
    "NYJ": StadiumSite("MetLife Stadium", 40.8135, -74.0745, is_dome=False),
    "PHI": StadiumSite("Lincoln Financial Field", 39.9008, -75.1675, is_dome=False),
    "PIT": StadiumSite("Acrisure Stadium", 40.4468, -80.0158, is_dome=False),
    "SEA": StadiumSite("Lumen Field", 47.5952, -122.3316, is_dome=False),
    "SF": StadiumSite("Levi's Stadium", 37.4033, -121.9694, is_dome=False),
    "TB": StadiumSite("Raymond James Stadium", 27.9759, -82.5033, is_dome=False),
    "TEN": StadiumSite("Nissan Stadium", 36.1665, -86.7713, is_dome=False),
    "WSH": StadiumSite("Northwest Stadium", 38.9078, -76.8645, is_dome=False),
}

# ------------------------------------------------------------ college table
# Top-40 programs only (2020s-era national relevance, spanning the major
# conferences) -- see the module docstring's COVERAGE note. Keys follow the
# same conventional abbreviations already exercised elsewhere in this repo
# (e.g. tests/test_autonomy_nfl_margin.py and college.py's own tests use
# "TEX"/"OU"). None of these 40 stadiums are domed, so `is_dome` is False
# throughout, but the field is kept for a uniform StadiumSite shape shared
# with NFL_STADIUMS (and in case a future expansion adds a domed program).
COLLEGE_STADIUMS: dict[str, StadiumSite] = {
    "ALA": StadiumSite("Bryant-Denny Stadium", 33.2083, -87.5504, is_dome=False),
    "UGA": StadiumSite("Sanford Stadium", 33.9497, -83.3733, is_dome=False),
    "OSU": StadiumSite("Ohio Stadium", 40.0017, -83.0197, is_dome=False),
    "MICH": StadiumSite("Michigan Stadium", 42.2658, -83.7487, is_dome=False),
    "TEX": StadiumSite("DKR-Texas Memorial Stadium", 30.2839, -97.7325, is_dome=False),
    "OU": StadiumSite("Gaylord Family Oklahoma Memorial Stadium", 35.2058, -97.4425, is_dome=False),
    "CLEM": StadiumSite("Memorial Stadium", 34.6834, -82.8433, is_dome=False),
    "LSU": StadiumSite("Tiger Stadium", 30.4118, -91.1837, is_dome=False),
    "PSU": StadiumSite("Beaver Stadium", 40.8122, -77.8563, is_dome=False),
    "ND": StadiumSite("Notre Dame Stadium", 41.6983, -86.2331, is_dome=False),
    "FLA": StadiumSite("Ben Hill Griffin Stadium", 29.6499, -82.3486, is_dome=False),
    "FSU": StadiumSite("Doak Campbell Stadium", 30.4380, -84.3040, is_dome=False),
    "AUB": StadiumSite("Jordan-Hare Stadium", 32.6023, -85.4903, is_dome=False),
    "TENN": StadiumSite("Neyland Stadium", 35.9550, -83.9250, is_dome=False),
    "WIS": StadiumSite("Camp Randall Stadium", 43.0699, -89.4123, is_dome=False),
    "ORE": StadiumSite("Autzen Stadium", 44.0582, -123.0684, is_dome=False),
    "USC": StadiumSite("LA Memorial Coliseum", 34.0141, -118.2879, is_dome=False),
    "WASH": StadiumSite("Husky Stadium", 47.6503, -122.3017, is_dome=False),
    "MSU": StadiumSite("Spartan Stadium", 42.7284, -84.4839, is_dome=False),
    "TAMU": StadiumSite("Kyle Field", 30.6100, -96.3400, is_dome=False),
    "MIA": StadiumSite("Hard Rock Stadium", 25.9580, -80.2389, is_dome=False),
    "NEB": StadiumSite("Memorial Stadium", 40.8206, -96.7056, is_dome=False),
    "IOWA": StadiumSite("Kinnick Stadium", 41.6584, -91.5511, is_dome=False),
    "OKST": StadiumSite("Boone Pickens Stadium", 36.1258, -97.0664, is_dome=False),
    "UTAH": StadiumSite("Rice-Eccles Stadium", 40.7599, -111.8485, is_dome=False),
    "BAY": StadiumSite("McLane Stadium", 31.5586, -97.1156, is_dome=False),
    "TCU": StadiumSite("Amon G. Carter Stadium", 32.7095, -97.3688, is_dome=False),
    "MISS": StadiumSite("Vaught-Hemingway Stadium", 34.3623, -89.5348, is_dome=False),
    "MSST": StadiumSite("Davis Wade Stadium", 33.4553, -88.7892, is_dome=False),
    "UNC": StadiumSite("Kenan Stadium", 35.9049, -79.0469, is_dome=False),
    "NCST": StadiumSite("Carter-Finley Stadium", 35.8010, -78.7195, is_dome=False),
    "VT": StadiumSite("Lane Stadium", 37.2199, -80.4183, is_dome=False),
    "LOU": StadiumSite("L&N Federal Credit Union Stadium", 38.2058, -85.7585, is_dome=False),
    "KSU": StadiumSite("Bill Snyder Family Stadium", 39.2027, -96.5847, is_dome=False),
    "ISU": StadiumSite("Jack Trice Stadium", 42.0140, -93.6359, is_dome=False),
    "WVU": StadiumSite("Milan Puskar Stadium", 39.6486, -79.9540, is_dome=False),
    "PITT": StadiumSite("Acrisure Stadium", 40.4468, -80.0158, is_dome=False),
    "STAN": StadiumSite("Stanford Stadium", 37.4347, -122.1611, is_dome=False),
    "UCLA": StadiumSite("Rose Bowl", 34.1613, -118.1676, is_dome=False),
    "ASU": StadiumSite("Mountain America Stadium", 33.4260, -111.9326, is_dome=False),
}

# ------------------------------------------------------------- adjustments
# Exact values from the WS-10 brief, TOTALS mean only.
WIND_HIGH_MPH = 20.0
WIND_HIGH_ADJ = -2.5
WIND_MED_MPH = 15.0
WIND_MED_ADJ = -1.5
TEMP_LOW_F = 15.0
TEMP_LOW_ADJ = -1.5
PRECIP_ADJ = -1.0
STACK_CAP = -4.0  # summed adjustment never more negative than this

# WMO weather codes (Open-Meteo's `weathercode` series) denoting at least
# moderate-to-heavy precipitation: heavy rain/freezing rain (65/67), heavy
# snowfall (75), violent rain showers (82), heavy snow showers (86), and
# every thunderstorm variant (95/96/99). Light/moderate codes (drizzle
# 51-55, light-to-moderate rain 61/63, light-to-moderate snow 71/73, light
# showers 80/81) deliberately do NOT trigger the adjustment -- the brief
# specifies "heavy precip", not any measurable precipitation.
HEAVY_PRECIP_CODES: frozenset[float] = frozenset({65.0, 67.0, 75.0, 82.0, 86.0, 95.0, 96.0, 99.0})


def stadium_for(league: str, team_abbr: str) -> StadiumSite | None:
    """Look up a team's stadium. None for an unmapped team or league."""
    if league == "nfl":
        table = NFL_STADIUMS
    elif league == "ncaaf":
        table = COLLEGE_STADIUMS
    else:
        return None
    return table.get(team_abbr.upper())


def default_fetch_football_weather(lat: float, lon: float, date_iso: str, hour_utc: int) -> dict[str, Any]:
    """Keyless Open-Meteo hourly forecast, temperature+wind+weathercode+precip.

    Same URL/pattern as `ballpark_weather.default_fetch_hourly_weather`
    (that module is shipped MLB code and is not edited here); the only
    difference is the `hourly` params string, which adds `weathercode` and
    `precipitation` -- fields the MLB fetch never requests. `hour_utc`
    (0-23) indexes straight into the returned single-day hourly arrays,
    same convention as ballpark_weather's own hour_utc contract.
    """
    import httpx

    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m,weathercode,precipitation",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "start_date": date_iso,
            "end_date": date_iso,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def parse_football_weather(payload: dict[str, Any], hour_index: int) -> FootballWeatherReading | None:
    """Extract the reading at `hour_index`. Defensive like ballpark_weather's
    `parse_hourly_weather`: any missing/short/non-numeric field -> None."""
    hourly = payload.get("hourly") if isinstance(payload, dict) else None
    if not isinstance(hourly, dict):
        return None

    temps = hourly.get("temperature_2m")
    winds = hourly.get("wind_speed_10m")
    codes = hourly.get("weathercode")
    if not isinstance(temps, list) or not isinstance(winds, list) or not isinstance(codes, list):
        return None

    if hour_index < 0 or hour_index >= len(temps) or hour_index >= len(winds) or hour_index >= len(codes):
        return None

    try:
        temperature_f = float(temps[hour_index])
        wind_speed_mph = float(winds[hour_index])
        weather_code = float(codes[hour_index])
    except (TypeError, ValueError):
        return None

    return FootballWeatherReading(
        temperature_f=temperature_f,
        wind_speed_mph=wind_speed_mph,
        weather_code=weather_code,
    )


def total_points_adjustment(
    weather: FootballWeatherReading | None, *, is_dome: bool = False,
) -> tuple[float, dict[str, Any]]:
    """Bounded mean adjustment to the expected TOTAL only.

    Returns (adjustment, features). Dome or no reading -> (0.0, {}),
    byte-identical to the feature being disabled outright -- callers must
    NOT merge an empty features dict differently from a populated one with
    adjustment==0.0 (that latter case is a genuine "measured calm
    conditions", the former is "no measurement at all").
    """
    if is_dome or weather is None:
        return 0.0, {}

    adjustment = 0.0
    if weather.wind_speed_mph >= WIND_HIGH_MPH:
        adjustment += WIND_HIGH_ADJ
    elif weather.wind_speed_mph >= WIND_MED_MPH:
        adjustment += WIND_MED_ADJ

    if weather.temperature_f <= TEMP_LOW_F:
        adjustment += TEMP_LOW_ADJ

    if weather.weather_code in HEAVY_PRECIP_CODES:
        adjustment += PRECIP_ADJ

    adjustment = max(STACK_CAP, adjustment)  # stack cap: never more negative than -4.0

    features = {
        "weather_wind_mph": weather.wind_speed_mph,
        "weather_temp_f": weather.temperature_f,
        "weather_code": weather.weather_code,
        "weather_total_adjustment": adjustment,
    }
    return adjustment, features


def _parse_kickoff_hour(event_start: str | None) -> tuple[str, int] | None:
    """Split an ESPN-style event timestamp ("YYYY-MM-DDTHH:MMZ" or with
    seconds) into (date_iso, hour_utc). None on anything unparseable --
    fail-closed, same discipline as every other extraction in this module.
    """
    if not event_start or len(event_start) < 13 or event_start[10] != "T":
        return None
    date_part = event_start[:10]
    hour_part = event_start[11:13]
    try:
        year, month, day = (int(part) for part in date_part.split("-"))
        hour = int(hour_part)
    except ValueError:
        return None
    if not (0 <= hour <= 23):
        return None
    try:
        date(year, month, day)  # validates a real calendar date
    except ValueError:
        return None
    return date_part, hour


def football_weather_adjustment(
    league: str,
    home_team: str,
    event_start: str | None,
    *,
    fetch_fn: Callable[[float, float, str, int], dict[str, Any]] | None = None,
) -> tuple[float, dict[str, Any]]:
    """End-to-end: stadium lookup -> kickoff-hour parse -> fetch -> adjustment.

    Fail-closed at every step: an unmapped team (or a stadium marked
    `is_dome`), an unparseable `event_start`, a raised fetch exception, or a
    defensively-parsed-away reading all resolve to (0.0, {}) -- byte-
    identical to the feature disabled. Never raises.
    """
    stadium = stadium_for(league, home_team)
    if stadium is None or stadium.is_dome:
        return 0.0, {}

    kickoff = _parse_kickoff_hour(event_start)
    if kickoff is None:
        return 0.0, {}
    date_iso, hour_utc = kickoff

    fetch = fetch_fn or default_fetch_football_weather
    try:
        payload = fetch(stadium.lat, stadium.lon, date_iso, hour_utc)
    except Exception:
        return 0.0, {}

    weather = parse_football_weather(payload, hour_utc)
    return total_points_adjustment(weather, is_dome=False)
