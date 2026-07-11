# scripts/verify_ballpark_weather_live.py
"""One-shot live check of the ballpark-weather pipeline against a real slate.

Read-only, keyless. Fetches tonight's ~first-pitch-hour Open-Meteo forecast
for a handful of real MLB parks and prints the observed temp/wind plus the
derived (hr_factor, run_factor), proving `autonomy/sports/ballpark_weather.py`
works end to end against the live public API (not a mock). A dome (TB) must
print (1.0, 1.0) regardless of the weather reading. Not part of the hermetic
pytest suite.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.sports.ballpark_weather import (
    BALLPARKS,
    Ballpark,
    default_fetch_hourly_weather,
    parse_hourly_weather,
    weather_factors,
)
from autonomy.sports.espn import MLB_TEAM_ALIASES

# BALLPARKS keys the Athletics as "ATH" (their temporary Sutter Health Park
# home), but the rest of this repo's ESPN adapter still emits "OAK" for the
# franchise (autonomy.sports.espn.canonical_team does not alias OAK->ATH).
# Route any park lookup through this alias map so an "OAK" code still finds
# Oakland/Athletics, alongside the existing AZ->ARI, CWS->CHW aliases ESPN
# already knows about.
PARK_ALIASES: dict[str, str] = {"OAK": "ATH", **MLB_TEAM_ALIASES}


def resolve_park(team_code: str) -> tuple[str, Ballpark]:
    """Resolve a team code to its (canonical BALLPARKS key, Ballpark), alias-aware."""
    code = team_code.upper()
    if code in BALLPARKS:
        return code, BALLPARKS[code]
    aliased = PARK_ALIASES.get(code)
    if aliased and aliased in BALLPARKS:
        return aliased, BALLPARKS[aliased]
    raise KeyError(f"no ballpark found for team code {team_code!r}")


# Demo slate: a few real parks spanning time zones, a dome, and the OAK->ATH
# alias. (team_code, first-pitch UTC hour, day offset from "today" in UTC).
# Evening first pitch is ~19:00 local; in July (DST in effect for all of
# these US zones) that lands at:
#   Eastern (NYY, BOS, TB):      19:00 EDT -> 23:00 UTC same day
#   Mountain (COL):               19:00 MDT -> 01:00 UTC next day
#   Pacific (OAK/ATH):            19:00 PDT -> 02:00 UTC next day
DEMO_SLATE: list[tuple[str, int, int]] = [
    ("COL", 1, 1),   # Coors Field - mile-high, thin air -> expect hr_factor boost
    ("NYY", 23, 0),  # Yankee Stadium
    ("BOS", 23, 0),  # Fenway Park - known ~45deg CF bearing
    ("TB", 23, 0),   # Tropicana Field - the one always-dome park
    ("OAK", 2, 1),   # Resolves via alias -> ATH (Sutter Health Park)
]


def main() -> int:
    today_utc = datetime.now(timezone.utc).date()
    print(f"Live ballpark-weather verification (Open-Meteo, keyless) - run at {datetime.now(timezone.utc).isoformat()}")
    print(f"'Tonight' anchor date (UTC): {today_utc.isoformat()}")
    print()

    ok = 0
    for team_code, hour_utc, day_offset in DEMO_SLATE:
        try:
            park_key, park = resolve_park(team_code)
        except KeyError as exc:
            print(f"{team_code:4} -> lookup failed: {exc}")
            continue

        date_iso = (today_utc + timedelta(days=day_offset)).isoformat()
        label = f"{team_code:4} -> {park_key:4} {park.name}"
        if team_code != park_key:
            label += f" (alias {team_code}->{park_key})"

        try:
            payload = default_fetch_hourly_weather(park.lat, park.lon, date_iso, hour_utc)
        except Exception as exc:  # keyless public API: report honestly, never fabricate
            print(f"{label}")
            print(f"     fetch FAILED for {date_iso} hour {hour_utc:02d}:00 UTC - {exc!r}")
            print()
            continue

        weather = parse_hourly_weather(payload, hour_utc)
        hr_factor, run_factor = weather_factors(weather, park.cf_bearing_deg, is_dome=park.is_dome)

        print(label)
        print(f"     forecast: {date_iso} {hour_utc:02d}:00 UTC  dome={park.is_dome}")
        if weather is None:
            print("     weather: no reading parsed (payload missing/short) -> neutral factors")
        else:
            print(
                f"     weather: {weather.temperature_f:.1f}F, "
                f"wind {weather.wind_speed_mph:.1f}mph @ {weather.wind_direction_deg:.0f}deg (from)"
            )
        print(f"     factors: hr_factor={hr_factor:.4f}  run_factor={run_factor:.4f}")
        if park.is_dome and (hr_factor, run_factor) != (1.0, 1.0):
            print("     !! WARNING: dome park did not resolve to neutral (1.0, 1.0)")
        print()
        ok += 1

    print(f"{ok}/{len(DEMO_SLATE)} parks fetched successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
