"""Official MLB StatsAPI adapter (statsapi.mlb.com; no key). Read-only.

Produces a point-in-time MlbGameContext with confirmed lineups, platoon
splits, bullpen fatigue, park factors, pitcher rate stats, and wind/temp.
Every field is nullable and its presence is tracked, so downstream model
heads degrade gracefully and the validation harness can attribute misses to
missing inputs. Nothing here forecasts, trades, or touches credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Literal

SnapshotKind = Literal["projected", "confirmed"]


@dataclass(frozen=True)
class LineupSlot:
    batting_order: int
    player_id: int
    name: str | None = None
    bats: str | None = None  # "L" | "R" | "S"


@dataclass(frozen=True)
class PitcherRates:
    player_id: int
    name: str | None = None
    throws: str | None = None  # "L" | "R"
    era: float | None = None
    k_pct: float | None = None
    bb_pct: float | None = None
    hr9: float | None = None


@dataclass(frozen=True)
class MlbGameContext:
    game_pk: int
    snapshot: SnapshotKind
    captured_at: str  # ISO-8601 UTC receipt time (provenance)
    home: str
    away: str
    venue: str | None = None
    home_probable_pitcher_id: int | None = None
    away_probable_pitcher_id: int | None = None
    home_pitcher: PitcherRates | None = None
    away_pitcher: PitcherRates | None = None
    home_lineup: tuple[LineupSlot, ...] = ()
    away_lineup: tuple[LineupSlot, ...] = ()
    home_bullpen_fatigue: dict[int, float] = field(default_factory=dict)
    away_bullpen_fatigue: dict[int, float] = field(default_factory=dict)
    park_run_factor: float | None = None
    park_hr_factor: float | None = None
    wind_speed_mph: float | None = None
    wind_direction: str | None = None
    temperature_f: float | None = None

    def field_provenance(self) -> dict[str, bool]:
        """Presence map: True when a field carries real data, False when absent.

        A scalar zero (calm wind, a 0.00 rate) is a real reading, not missing;
        only None or an empty collection counts as absent.
        """
        identity = {"game_pk", "snapshot", "captured_at", "home", "away"}
        present: dict[str, bool] = {}
        for f in fields(self):
            if f.name in identity:
                continue
            value = getattr(self, f.name)
            if value is None:
                present[f.name] = False
            elif isinstance(value, (tuple, list, dict)) and len(value) == 0:
                present[f.name] = False
            else:
                present[f.name] = True
        return present


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_wind(wind: Any) -> tuple[float | None, str | None]:
    """StatsAPI wind is a string like '8 mph, Out To CF' or '' — split it."""
    if not isinstance(wind, str) or not wind.strip():
        return None, None
    speed: float | None = None
    direction: str | None = None
    parts = [p.strip() for p in wind.split(",", 1)]
    head = parts[0]
    if "mph" in head:
        speed = _float(head.replace("mph", "").strip())
        direction = parts[1] if len(parts) > 1 else None
    else:
        direction = wind.strip()
    return speed, (direction or None)


def parse_schedule(
    payload: dict[str, Any],
    *,
    captured_at: str,
    snapshot: SnapshotKind = "projected",
) -> list[MlbGameContext]:
    """Point-in-time contexts from the hydrated schedule endpoint."""
    contexts: list[MlbGameContext] = []
    for date_block in payload.get("dates", []) or []:
        for game in date_block.get("games", []) or []:
            teams = game.get("teams", {}) or {}
            home = ((teams.get("home", {}) or {}).get("team", {}) or {}).get("abbreviation")
            away = ((teams.get("away", {}) or {}).get("team", {}) or {}).get("abbreviation")
            game_pk = game.get("gamePk")
            if not home or not away or game_pk is None:
                continue
            home_prob = ((teams.get("home", {}) or {}).get("probablePitcher", {}) or {}).get("id")
            away_prob = ((teams.get("away", {}) or {}).get("probablePitcher", {}) or {}).get("id")
            weather = game.get("weather", {}) or {}
            wind_speed, wind_direction = _parse_wind(weather.get("wind"))
            contexts.append(MlbGameContext(
                game_pk=int(game_pk),
                snapshot=snapshot,
                captured_at=captured_at,
                home=str(home),
                away=str(away),
                venue=((game.get("venue", {}) or {}).get("name")),
                home_probable_pitcher_id=int(home_prob) if home_prob is not None else None,
                away_probable_pitcher_id=int(away_prob) if away_prob is not None else None,
                wind_speed_mph=wind_speed,
                wind_direction=wind_direction,
                temperature_f=_float(weather.get("temp")),
            ))
    return contexts


from dataclasses import replace


def _team_lineup(team_box: dict[str, Any]) -> tuple[LineupSlot, ...]:
    order = team_box.get("battingOrder") or []
    players = team_box.get("players", {}) or {}
    slots: list[LineupSlot] = []
    for index, player_id in enumerate(order, start=1):
        person = (players.get(f"ID{player_id}", {}) or {}).get("person", {}) or {}
        slots.append(LineupSlot(
            batting_order=index,
            player_id=int(player_id),
            name=person.get("fullName"),
            bats=((person.get("batSide", {}) or {}).get("code")),
        ))
    return tuple(slots)


def parse_boxscore_lineups(
    boxscore: dict[str, Any], roster_bats: dict[int, str] | None = None,
) -> tuple[tuple[LineupSlot, ...], tuple[LineupSlot, ...]]:
    teams = boxscore.get("teams", {}) or {}
    home = _team_lineup(teams.get("home", {}) or {})
    away = _team_lineup(teams.get("away", {}) or {})
    return home, away


def apply_confirmed_lineups(
    ctx: MlbGameContext,
    home_lineup: tuple[LineupSlot, ...],
    away_lineup: tuple[LineupSlot, ...],
    *,
    captured_at: str,
) -> MlbGameContext:
    """Return a confirmed-snapshot copy carrying the real lineups."""
    return replace(
        ctx,
        snapshot="confirmed",
        captured_at=captured_at,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
    )


def _rate(numerator: Any, denominator: Any) -> float | None:
    n, d = _float(numerator), _float(denominator)
    if n is None or not d:
        return None
    return round(n / d, 4)


def parse_pitcher_rates(people_payload: dict[str, Any]) -> PitcherRates | None:
    people = people_payload.get("people") or []
    if not people:
        return None
    person = people[0] or {}
    pid = person.get("id")
    if pid is None:
        return None
    stat: dict[str, Any] = {}
    stats = person.get("stats") or []
    if stats:
        splits = (stats[0] or {}).get("splits") or []
        if splits:
            stat = (splits[0] or {}).get("stat", {}) or {}
    return PitcherRates(
        player_id=int(pid),
        name=person.get("fullName"),
        throws=((person.get("pitchHand", {}) or {}).get("code")),
        era=_float(stat.get("era")),
        k_pct=_rate(stat.get("strikeOuts"), stat.get("battersFaced")),
        bb_pct=_rate(stat.get("baseOnBalls"), stat.get("battersFaced")),
        hr9=_float(stat.get("homeRunsPer9")),
    )
