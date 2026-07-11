"""MLB divisional / rivalry matchup awareness (Task 5).

Divisional and marquee rivalry games are historically closer and
higher-variance than a random pairing of teams: familiarity, geographic
proximity, and playoff stakes compress the talent gap that shows up on paper.
This module supplies the lookup tables and pure predicates the plate-
appearance simulator (`autonomy.sports.mlb_pa_sim`) uses to apply a modest,
deterministic variance bump when a game is divisional. Pure, offline,
deterministic; no network calls.
"""
from __future__ import annotations

# Team abbreviation -> division name. Keys follow the same ESPN/StatsAPI
# convention used elsewhere in this repo (see autonomy/sports/espn.py's
# canonical_team, which maps "CWS" -> "CHW", and
# autonomy/sports/ballpark_weather.py's BALLPARKS table, which the keys here
# match exactly). The Athletics play as "ATH" (Sutter Health Park), not
# "OAK", per the same convention.
DIVISIONS: dict[str, str] = {
    # AL East
    "NYY": "AL East",
    "BOS": "AL East",
    "TB": "AL East",
    "TOR": "AL East",
    "BAL": "AL East",
    # AL Central
    "CLE": "AL Central",
    "MIN": "AL Central",
    "DET": "AL Central",
    "KC": "AL Central",
    "CHW": "AL Central",
    # AL West
    "HOU": "AL West",
    "SEA": "AL West",
    "TEX": "AL West",
    "LAA": "AL West",
    "ATH": "AL West",
    # NL East
    "ATL": "NL East",
    "NYM": "NL East",
    "PHI": "NL East",
    "MIA": "NL East",
    "WSH": "NL East",
    # NL Central
    "MIL": "NL Central",
    "CHC": "NL Central",
    "STL": "NL Central",
    "CIN": "NL Central",
    "PIT": "NL Central",
    # NL West
    "LAD": "NL West",
    "SD": "NL West",
    "SF": "NL West",
    "ARI": "NL West",
    "COL": "NL West",
}

# Well-known rivalry pairs, independent of division (some divisional, some
# cross-league/cross-division "civic" rivalries). Order-independent by
# construction: each pair is a frozenset of the two team abbreviations.
RIVALRIES: frozenset[frozenset[str]] = frozenset({
    frozenset({"NYY", "BOS"}),   # Yankees-Red Sox
    frozenset({"LAD", "SF"}),    # Dodgers-Giants
    frozenset({"CHC", "STL"}),   # Cubs-Cardinals
    frozenset({"NYM", "PHI"}),   # Mets-Phillies
    frozenset({"LAD", "SD"}),    # Dodgers-Padres
    frozenset({"CLE", "CHW"}),   # Guardians-White Sox
    frozenset({"HOU", "TEX"}),   # Astros-Rangers ("Silver Boot")
    frozenset({"NYY", "NYM"}),   # Subway Series
    frozenset({"CHC", "CHW"}),   # Crosstown Classic
    frozenset({"SF", "ATH"}),    # Bay Bridge Series
    frozenset({"BAL", "WSH"}),   # Beltway Series
    frozenset({"STL", "KC"}),    # I-70 Series
})


def is_divisional(home: str, away: str) -> bool:
    """True when both teams are in the same division. Unknown team -> False.

    Order-independent: is_divisional(a, b) == is_divisional(b, a).
    """
    home_division = DIVISIONS.get(home)
    away_division = DIVISIONS.get(away)
    if home_division is None or away_division is None:
        return False
    return home_division == away_division


def is_rivalry(home: str, away: str) -> bool:
    """True when (home, away) is a known rivalry pair. Unknown team -> False.

    Order-independent: is_rivalry(a, b) == is_rivalry(b, a).
    """
    return frozenset({home, away}) in RIVALRIES
