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
    "ncaaf": ("football", "college-football"),
    "mlb": ("baseball", "mlb"),
    "nhl": ("hockey", "nhl"),
    "ncaamb": ("basketball", "mens-college-basketball"),
}

MLB_TEAM_ALIASES = {
    "AZ": "ARI",
    "CWS": "CHW",
}


def canonical_team(league: str, team: str) -> str:
    upper = team.upper()
    return MLB_TEAM_ALIASES.get(upper, upper) if league == "mlb" else upper


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
    # Sportsbook moneylines (american odds) from the scoreboard's embedded
    # odds block: current ("close") and opening lines for both sides, so a
    # single snapshot carries the line movement since open.
    home_ml: int | None = None
    away_ml: int | None = None
    home_ml_open: int | None = None
    away_ml_open: int | None = None
    odds_provider: str | None = None
    # Final-score and first-inning facts power the isolated MLB runs model.
    # They remain None before settlement or when the public payload is incomplete.
    home_score: int | None = None
    away_score: int | None = None
    home_first_inning_runs: int | None = None
    away_first_inning_runs: int | None = None
    # Live game state (in-progress only): the current period/inning, so a live
    # model can price the remaining game. None pre-game and post-game.
    current_period: int | None = None
    venue: str | None = None
    indoor: bool | None = None
    weather_temperature_f: float | None = None
    weather_condition: str | None = None
    home_name: str | None = None
    away_name: str | None = None
    # Live clock (in-progress only), raw ESPN "status.displayClock" string
    # (e.g. "5:23"; "0.0" once a period ends). Added for WS-2's NBA live
    # Brownian diffusion -- see autonomy/sports/nba_model.py's build-time
    # probe comment for the exact field name/shape confirmed on a real
    # scoreboard payload. None pre-game and post-game, same gating as
    # current_period.
    current_clock: str | None = None
    # Completed games can end tied (rare in NFL/NCAAF).  ``home_won=None``
    # alone cannot distinguish a true tie from an unresolved/malformed
    # result, so preserve the settlement fact explicitly for tie-aware
    # ratings such as Colley while leaving winner-only models fail-closed.
    is_tie: bool = False


def _american(value: Any) -> int | None:
    """Parse an american-odds string ('+101', '-149', 'EVEN') to an int."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().upper()
    if text in ("EVEN", "EV", "PK"):
        return 100
    try:
        parsed = float(text.replace("+", ""))
    except Exception:
        return None
    return int(parsed) if parsed.is_integer() else None


def _moneylines(comp: dict[str, Any]) -> tuple[int | None, int | None, int | None, int | None, str | None]:
    """(home_ml, away_ml, home_ml_open, away_ml_open, provider) from odds[0]."""
    for odds in comp.get("odds") or []:
        ml = odds.get("moneyline") or {}
        home, away = ml.get("home") or {}, ml.get("away") or {}
        home_close = _american((home.get("close") or {}).get("odds"))
        away_close = _american((away.get("close") or {}).get("odds"))
        if home_close is None and away_close is None:
            continue
        return (
            home_close,
            away_close,
            _american((home.get("open") or {}).get("odds")),
            _american((away.get("open") or {}).get("odds")),
            (odds.get("provider") or {}).get("name"),
        )
    return None, None, None, None, None


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


def _score(competitor: dict[str, Any]) -> int | None:
    try:
        value = float(competitor.get("score"))
    except (TypeError, ValueError):
        return None
    return int(value) if value >= 0 and value.is_integer() else None


def _inning_runs(competitor: dict[str, Any], inning: int = 1) -> int | None:
    for line in competitor.get("linescores") or []:
        try:
            if int(line.get("period")) != inning:
                continue
            value = float(line.get("value"))
        except (TypeError, ValueError):
            continue
        return int(value) if value >= 0 and value.is_integer() else None
    return None


def _espn_scoreboard_url(league: str) -> str:
    sport, esp = LEAGUE_TO_ESPN[league]
    return f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{esp}/scoreboard"


def default_fetch_scoreboard(league: str, dates: str | None) -> dict[str, Any]:
    import httpx

    params: dict[str, Any] = {}
    if dates:
        params["dates"] = dates  # YYYYMMDD or YYYYMMDD-YYYYMMDD
    response = httpx.get(_espn_scoreboard_url(league), params=params, timeout=20)
    if response.is_success:
        return response.json()
    # Some college feeds reject date ranges while accepting each constituent
    # date. Fall back to daily public reads and merge events rather than
    # silently leaving a league permanently cold.
    if dates and "-" in dates:
        from datetime import datetime, timedelta

        start_text, end_text = dates.split("-", 1)
        start = datetime.strptime(start_text, "%Y%m%d").date()
        end = datetime.strptime(end_text, "%Y%m%d").date()
        if 0 <= (end - start).days <= 31:
            merged: dict[str, Any] = {"events": []}
            current = start
            seen: set[str] = set()
            while current <= end:
                daily = httpx.get(
                    _espn_scoreboard_url(league),
                    params={"dates": current.strftime("%Y%m%d")},
                    timeout=20,
                )
                daily.raise_for_status()
                for event in daily.json().get("events", []):
                    event_id = str(event.get("id") or "")
                    if event_id and event_id in seen:
                        continue
                    if event_id:
                        seen.add(event_id)
                    merged["events"].append(event)
                current += timedelta(days=1)
            return merged
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
        home_name = away_name = None
        home_competitor = away_competitor = None
        home_won = away_won = None
        home_era = away_era = None
        home_p = away_p = None
        for c in competitors:
            abbr = c.get("team", {}).get("abbreviation")
            if c.get("homeAway") == "home":
                home = abbr
                home_name = c.get("team", {}).get("displayName")
                home_competitor = c
                home_won = c.get("winner")
                home_era, home_p = _probable_era(c)
            elif c.get("homeAway") == "away":
                away = abbr
                away_name = c.get("team", {}).get("displayName")
                away_competitor = c
                away_won = c.get("winner")
                away_era, away_p = _probable_era(c)
        state = comp.get("status", {}).get("type", {}).get("state", "")
        if not home or not away:
            continue
        home_score = _score(home_competitor or {}) if state in ("post", "in") else None
        away_score = _score(away_competitor or {}) if state in ("post", "in") else None
        is_tie = (
            state == "post"
            and home_score is not None
            and away_score is not None
            and home_score == away_score
        )
        resolved: bool | None = None
        if state == "post" and not is_tie:
            if home_won is True or away_won is False:
                resolved = True
            elif home_won is False or away_won is True:
                resolved = False
        home_ml, away_ml, home_ml_open, away_ml_open, provider = _moneylines(comp)
        # Live scores + inning are exposed for in-progress games so the live
        # model can re-price; final scores remain settlement facts.
        live_or_final = state in ("post", "in")
        period_raw = comp.get("status", {}).get("period")
        try:
            current_period = int(period_raw) if state == "in" and period_raw is not None else None
        except (TypeError, ValueError):
            current_period = None
        clock_raw = comp.get("status", {}).get("displayClock")
        current_clock = str(clock_raw) if state == "in" and clock_raw is not None else None
        venue = comp.get("venue") or {}
        weather = comp.get("weather") or {}
        try:
            temperature = float(weather.get("temperature"))
        except (TypeError, ValueError):
            temperature = None
        games.append(Game(
            game_id=str(event.get("id", f"{away}@{home}:{event.get('date','')}")),
            league=league, home=home, away=away, status=state or "pre",
            home_won=resolved, date=str(event.get("date", "")),
            home_pitcher_era=home_era, away_pitcher_era=away_era,
            home_pitcher=home_p, away_pitcher=away_p,
            home_ml=home_ml, away_ml=away_ml,
            home_ml_open=home_ml_open, away_ml_open=away_ml_open,
            odds_provider=provider,
            home_score=home_score if live_or_final else None,
            away_score=away_score if live_or_final else None,
            home_first_inning_runs=(
                _inning_runs(home_competitor or {}) if state == "post" else None
            ),
            away_first_inning_runs=(
                _inning_runs(away_competitor or {}) if state == "post" else None
            ),
            current_period=current_period,
            current_clock=current_clock,
            venue=venue.get("fullName"),
            indoor=venue.get("indoor") if isinstance(venue.get("indoor"), bool) else None,
            weather_temperature_f=temperature,
            weather_condition=weather.get("displayValue"),
            home_name=home_name,
            away_name=away_name,
            is_tie=is_tie,
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
            # Deliberately NOT cached. Caching the empty result made the
            # failure sticky: the next games_or_raise for the same key
            # returned it without raising, re-hiding the outage that
            # variant exists to expose, and an in-cycle retry could never
            # recover. The swallow-to-empty contract for this call is
            # unchanged -- only its persistence is.
            return []
        games = parse_scoreboard(league, payload)
        self._cache[key] = games
        return games

    def games_or_raise(self, league: str, dates: str | None = None) -> list[Game]:
        """Like ``games`` but a fetch failure RAISES instead of returning [].

        Callers that must distinguish "no games" from "feed down" (the
        season gate: an empty scoreboard means offseason, a dead feed means
        keep the last verdict) need the exception. ``games``'s swallow-to-
        empty contract stays untouched for every forecasting path.

        Cache caveat: the two methods share the cache, so a [] cached by a
        FAILED ``games`` call would be returned here without raising. Today
        no caller shares a (league, dates) key across both paths (the gate
        uses its own -7/+21 window), and cycle starts clear the cache.
        """
        key = (league, dates)
        if key in self._cache:
            return self._cache[key]
        payload = self.fetch_scoreboard(league, dates)
        games = parse_scoreboard(league, payload)
        self._cache[key] = games
        return games

    def find_matchup(self, league: str, team_a: str, team_b: str, dates: str | None = None) -> Game | None:
        teams = {canonical_team(league, team_a), canonical_team(league, team_b)}
        for game in self.games(league, dates):
            if {
                canonical_team(league, game.home), canonical_team(league, game.away),
            } == teams:
                return game
        return None

    def find_matchup_names(
        self, league: str, team_a: str, team_b: str, dates: str | None = None,
    ) -> Game | None:
        def normalized(value: str | None) -> set[str]:
            text = "".join(char.lower() if char.isalnum() else " " for char in str(value or ""))
            return {token for token in text.split() if len(token) > 1}

        requested = (normalized(team_a), normalized(team_b))
        for game in self.games(league, dates):
            actual = (normalized(game.home_name or game.home), normalized(game.away_name or game.away))
            direct = requested[0] <= actual[0] and requested[1] <= actual[1]
            reverse = requested[0] <= actual[1] and requested[1] <= actual[0]
            if direct or reverse:
                return game
        return None
