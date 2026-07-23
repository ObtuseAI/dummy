"""NHL-API team identities -> ESPN abbreviations.

fastRhockey's NHL feed keys on NHL-API team ids/full names, not ESPN
abbreviations, which is why the deep-history backfill deliberately excluded
NHL (rows would neither dedup with ESPN games nor match live signals).
This static map is step one of the October onboarding: adapters translate
before upsert, and anything unmapped is skipped fail-closed rather than
polluting the lake with an unjoinable key.
"""
from __future__ import annotations

# NHL-API full name -> ESPN abbreviation (32 franchises, 2025-26 season).
NHL_NAME_TO_ESPN: dict[str, str] = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LA",
    "Minnesota Wild": "MIN", "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL", "Nashville Predators": "NSH",
    "New Jersey Devils": "NJ", "New York Islanders": "NYI",
    "New York Rangers": "NYR", "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJ", "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL", "Tampa Bay Lightning": "TB",
    "Toronto Maple Leafs": "TOR", "Utah Hockey Club": "UTAH",
    "Utah Mammoth": "UTAH", "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


def espn_abbreviation(nhl_name: str | None) -> str | None:
    """ESPN abbreviation for an NHL-API team name; None when unmapped."""
    if not nhl_name:
        return None
    return NHL_NAME_TO_ESPN.get(str(nhl_name).strip())
