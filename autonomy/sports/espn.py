"""ESPN public scoreboard adapter (no key). Read-only.

Returns a normalized list of games (teams, home/away, status, winner) for a
league across a date range — enough to both warm up Elo from completed games
and locate an upcoming game for a Kalshi market.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# Kalshi league prefix -> (ESPN sport, ESPN league)
LEAGUE_TO_ESPN: dict[str, tuple[str, str]] = {
    "nba": ("basketball", "nba"),
    "wnba": ("basketball", "wnba"),
    "nfl": ("football", "nfl"),
    "mlb": ("baseball", "mlb"),
    "nhl": ("hockey", "nhl"),
}


@dataclass(frozen=True)
class Game:
    game_id: str
    league: str
    home: str
    away: str
    status: str  # "pre" | "in" | "post"
    home_won: bool | None
    date: str
    # Probable starting-pitcher season ERA (baseball only; None when absent).
    home_pitcher_era: float | None = None
    away_pitcher_era: float | None = None
    home_pitcher: str | None = None
    away_pitcher: str | None = None


def _probable_era(competitor: dict[str, Any]) -> tuple[float | None, str | None]:
    """Extract a competitor's probable starter ERA + name, if present."""
    probs = competitor.get("probables") or []
    if not probs:
        return None, None
    p = probs[0]
    name = p.get("displayName") or (p.get("athlete") or {}).get("displayName")
    for stat in p.get("statistics") or []:
        if str(stat.get("name", "")).lower() in ("era", "earnedrunaverage"):
            try:
                return float(stat.get("displayValue")), name
            except Exception:
                return None, name
    return None, name


def _espn_scoreboard_url(league: str) -> str:
    sport, esp = LEAGUE_TO_ESPN[league]
    return f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{esp}/scoreboard"


def default_fetch_scoreboard(league: str, dates: str | None) -> dict[str, Any]:
    import httpx

    params: dict[str, Any] = {}
    if dates:
        params["dates"] = dates  # YYYYMMDD or YYYYMMDD-YYYYMMDD
    response = httpx.get(_espn_scoreboard_url(league), params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def parse_scoreboard(league: str, payload: dict[str, Any]) -> list[Game]:
    games: list[Game] = []
    for event in payload.get("events", []):
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]
        competitors = comp.get("competitors", [])
        home = away = None
        home_won = away_won = None
        home_era = away_era = None
        home_p = away_p = None
        for c in competitors:
            abbr = c.get("team", {}).get("abbreviation")
            if c.get("homeAway") == "home":
                home = abbr
                home_won = c.get("winner")
                home_era, home_p = _probable_era(c)
            elif c.get("homeAway") == "away":
                away = abbr
                away_won = c.get("winner")
                away_era, away_p = _probable_era(c)
        state = comp.get("status", {}).get("type", {}).get("state", "")
        if not home or not away:
            continue
        resolved: bool | None = None
        if state == "post":
            if home_won is True or away_won is False:
                resolved = True
            elif home_won is False or away_won is True:
                resolved = False
        games.append(Game(
            game_id=str(event.get("id", f"{away}@{home}:{event.get('date','')}")),
            league=league, home=home, away=away, status=state or "pre",
            home_won=resolved, date=str(event.get("date", "")),
            home_pitcher_era=home_era, away_pitcher_era=away_era,
            home_pitcher=home_p, away_pitcher=away_p,
        ))
    return games


class EspnClient:
    def __init__(self, fetch_scoreboard: Callable[[str, str | None], dict[str, Any]] | None = None):
        self.fetch_scoreboard = fetch_scoreboard or default_fetch_scoreboard
        self._cache: dict[tuple[str, str | None], list[Game]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def games(self, league: str, dates: str | None = None) -> list[Game]:
        key = (league, dates)
        if key in self._cache:
            return self._cache[key]
        try:
            payload = self.fetch_scoreboard(league, dates)
        except Exception:
            self._cache[key] = []
            return []
        games = parse_scoreboard(league, payload)
        self._cache[key] = games
        return games

    def find_matchup(self, league: str, team_a: str, team_b: str, dates: str | None = None) -> Game | None:
        teams = {team_a.upper(), team_b.upper()}
        for game in self.games(league, dates):
            if {game.home.upper(), game.away.upper()} == teams:
                return game
        return None
