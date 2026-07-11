"""Official MLB StatsAPI adapter (statsapi.mlb.com; no key). Read-only.

Produces a point-in-time MlbGameContext with confirmed lineups, platoon
splits, bullpen fatigue, park factors, pitcher rate stats, and wind/temp.
Every field is nullable and its presence is tracked, so downstream model
heads degrade gracefully and the validation harness can attribute misses to
missing inputs. Nothing here forecasts, trades, or touches credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from datetime import date
from typing import Any, Literal, Callable

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
    vs_lhb: PitcherRates | None = None
    vs_rhb: PitcherRates | None = None


@dataclass(frozen=True)
class BatterRates:
    player_id: int
    name: str | None = None
    bats: str | None = None  # "L" | "R" | "S"
    plate_appearances: int | None = None
    k_pct: float | None = None
    bb_pct: float | None = None
    obp: float | None = None
    slg: float | None = None
    iso: float | None = None
    vs_lhp: BatterRates | None = None
    vs_rhp: BatterRates | None = None


def batter_rates_vs(batter: BatterRates | None, pitcher_throws: str | None) -> BatterRates | None:
    """Return the batter's split rates vs the pitcher's hand, or overall if unavailable."""
    if batter is None:
        return None
    if pitcher_throws == "L" and batter.vs_lhp is not None:
        return batter.vs_lhp
    if pitcher_throws == "R" and batter.vs_rhp is not None:
        return batter.vs_rhp
    return batter


def pitcher_rates_vs(pitcher: PitcherRates | None, batter_bats: str | None) -> PitcherRates | None:
    """Return the pitcher's split rates vs the batter's hand, or overall if unavailable.

    Switch-hitter ('S') batters receive the pitcher's overall rates (no split).
    """
    if pitcher is None:
        return None
    if batter_bats == "L" and pitcher.vs_lhb is not None:
        return pitcher.vs_lhb
    if batter_bats == "R" and pitcher.vs_rhb is not None:
        return pitcher.vs_rhb
    return pitcher


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
    batter_rates: dict[int, BatterRates] = field(default_factory=dict)
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
    boxscore: dict[str, Any],
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


def _pitcher_rates_from_stat(
    pid: Any, person: dict[str, Any], stat: dict[str, Any],
) -> PitcherRates:
    return PitcherRates(
        player_id=int(pid),
        name=person.get("fullName"),
        throws=((person.get("pitchHand", {}) or {}).get("code")),
        era=_float(stat.get("era")),
        k_pct=_rate(stat.get("strikeOuts"), stat.get("battersFaced")),
        bb_pct=_rate(stat.get("baseOnBalls"), stat.get("battersFaced")),
        hr9=_float(stat.get("homeRunsPer9")),
    )


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
    return _pitcher_rates_from_stat(pid, person, stat)


def parse_pitcher_splits(
    people_payload: dict[str, Any],
) -> tuple[PitcherRates | None, PitcherRates | None]:
    """Return (vs-LHB, vs-RHB) PitcherRates from a statSplits payload.

    Reads people[0].stats[0].splits, keyed by split.code ("vl" = vs
    left-handed batters, "vr" = vs right-handed batters). Missing/empty/
    malformed payloads resolve to (None, None); this never raises.
    """
    try:
        people = people_payload.get("people") or []
        if not people:
            return None, None
        person = people[0] or {}
        pid = person.get("id")
        if pid is None:
            return None, None
        stats = person.get("stats") or []
        if not stats:
            return None, None
        splits = (stats[0] or {}).get("splits") or []
        vs_lhb: PitcherRates | None = None
        vs_rhb: PitcherRates | None = None
        for entry in splits:
            entry = entry or {}
            code = ((entry.get("split") or {}) or {}).get("code")
            stat = (entry.get("stat") or {}) or {}
            if code == "vl":
                vs_lhb = _pitcher_rates_from_stat(pid, person, stat)
            elif code == "vr":
                vs_rhb = _pitcher_rates_from_stat(pid, person, stat)
        return vs_lhb, vs_rhb
    except Exception:
        return None, None


def _batter_rates_from_stat(
    pid: Any, person: dict[str, Any], stat: dict[str, Any],
) -> BatterRates:
    pa = stat.get("plateAppearances")
    slg = _float(stat.get("slg"))
    avg = _float(stat.get("avg"))
    iso = round(slg - avg, 4) if slg is not None and avg is not None else None
    return BatterRates(
        player_id=int(pid),
        name=person.get("fullName"),
        bats=((person.get("batSide", {}) or {}).get("code")),
        plate_appearances=int(pa) if pa is not None else None,
        k_pct=_rate(stat.get("strikeOuts"), pa),
        bb_pct=_rate(stat.get("baseOnBalls"), pa),
        obp=_float(stat.get("obp")),
        slg=slg,
        iso=iso,
    )


def parse_batter_rates(people_payload: dict[str, Any]) -> BatterRates | None:
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
    return _batter_rates_from_stat(pid, person, stat)


def parse_batter_splits(
    people_payload: dict[str, Any],
) -> tuple[BatterRates | None, BatterRates | None]:
    """Return (vs-LHP, vs-RHP) BatterRates from a statSplits payload.

    Reads people[0].stats[0].splits, keyed by split.code ("vl" = vs
    left-handed pitchers, "vr" = vs right-handed pitchers). Missing/empty/
    malformed payloads resolve to (None, None); this never raises.
    """
    try:
        people = people_payload.get("people") or []
        if not people:
            return None, None
        person = people[0] or {}
        pid = person.get("id")
        if pid is None:
            return None, None
        stats = person.get("stats") or []
        if not stats:
            return None, None
        splits = (stats[0] or {}).get("splits") or []
        vs_lhp: BatterRates | None = None
        vs_rhp: BatterRates | None = None
        for entry in splits:
            entry = entry or {}
            code = ((entry.get("split") or {}) or {}).get("code")
            stat = (entry.get("stat") or {}) or {}
            if code == "vl":
                vs_lhp = _batter_rates_from_stat(pid, person, stat)
            elif code == "vr":
                vs_rhp = _batter_rates_from_stat(pid, person, stat)
        return vs_lhp, vs_rhp
    except Exception:
        return None, None


# Seed table from public league-average park indices; neutral = 1.0. The
# feature-discovery loop (S5) refines these from residuals later.
PARK_FACTORS: dict[str, tuple[float, float]] = {
    "Coors Field": (1.15, 1.18),
    "Fenway Park": (1.05, 1.03),
    "Dodger Stadium": (0.98, 1.06),
    "Oracle Park": (0.94, 0.90),
    "Great American Ball Park": (1.03, 1.16),
    "Petco Park": (0.96, 0.95),
    "Yankee Stadium": (1.01, 1.10),
}


def park_factors(venue: str | None) -> tuple[float | None, float | None]:
    if venue is None:
        return None, None
    return PARK_FACTORS.get(venue, (1.0, 1.0))


def bullpen_fatigue(
    recent_appearances: dict[int, list[str]], *, as_of: str,
) -> dict[int, float]:
    """Fatigue in [0,1]: weighted count of appearances in the trailing 3 days.

    Yesterday weighs most (back-to-back), then two- and three-days-ago. The
    weights sum to 1.0 so a reliever who pitched all three trailing days
    saturates at 1.0.
    """
    reference = date.fromisoformat(str(as_of)[:10])
    day_weight = {1: 0.5, 2: 0.3, 3: 0.2}
    fatigue: dict[int, float] = {}
    for player_id, dates in recent_appearances.items():
        score = 0.0
        for stamp in dates:
            try:
                delta = (reference - date.fromisoformat(stamp)).days
            except ValueError:
                continue
            score += day_weight.get(delta, 0.0)
        fatigue[int(player_id)] = round(min(1.0, score), 4)
    return fatigue


_BASE = "https://statsapi.mlb.com/api/v1"


def default_fetch_schedule(date_iso: str) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/schedule",
        params={
            "sportId": 1, "date": date_iso,
            # "team" is required to hydrate team.abbreviation — without it the
            # schedule payload only carries team.id/name/link and parse_schedule
            # (which reads team.abbreviation) drops every game as unidentified.
            "hydrate": "team,probablePitcher,weather,venue",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def default_fetch_boxscore(game_pk: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(f"{_BASE}/game/{game_pk}/boxscore", timeout=20)
    response.raise_for_status()
    return response.json()


def default_fetch_people(player_id: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/people/{player_id}",
        params={"hydrate": "stats(group=[pitching],type=[season])"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def default_fetch_batter_people(player_id: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/people/{player_id}",
        params={"hydrate": "stats(group=[hitting],type=[season])"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def default_fetch_batter_splits(player_id: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/people/{player_id}",
        params={"hydrate": "stats(group=[hitting],type=[statSplits],sitCodes=[vl,vr])"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def default_fetch_pitcher_splits(player_id: int) -> dict[str, Any]:
    import httpx
    response = httpx.get(
        f"{_BASE}/people/{player_id}",
        params={"hydrate": "stats(group=[pitching],type=[statSplits],sitCodes=[vl,vr])"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


class StatsApiClient:
    """Assembles point-in-time MlbGameContexts from injectable StatsAPI fetchers."""

    def __init__(
        self,
        fetch_schedule: Callable[[str], dict[str, Any]] | None = None,
        fetch_boxscore: Callable[[int], dict[str, Any]] | None = None,
        fetch_people: Callable[[int], dict[str, Any]] | None = None,
        fetch_batter_people: Callable[[int], dict[str, Any]] | None = None,
        fetch_batter_splits: Callable[[int], dict[str, Any]] | None = None,
        fetch_pitcher_splits: Callable[[int], dict[str, Any]] | None = None,
    ) -> None:
        self.fetch_schedule = fetch_schedule or default_fetch_schedule
        self.fetch_boxscore = fetch_boxscore or default_fetch_boxscore
        self.fetch_people = fetch_people or default_fetch_people
        self.fetch_batter_people = fetch_batter_people or default_fetch_batter_people
        self.fetch_batter_splits = fetch_batter_splits or default_fetch_batter_splits
        self.fetch_pitcher_splits = fetch_pitcher_splits or default_fetch_pitcher_splits
        self._pitcher_cache: dict[int, PitcherRates | None] = {}
        self._batter_cache: dict[int, BatterRates | None] = {}

    def clear_cache(self) -> None:
        """Drop cached pitcher AND batter lookups (splits are baked into these
        same cached rates objects) so a reused client refetches season rates."""
        self._pitcher_cache.clear()
        self._batter_cache.clear()

    def _pitcher(self, player_id: int | None) -> PitcherRates | None:
        if player_id is None:
            return None
        if player_id not in self._pitcher_cache:
            try:
                rates = parse_pitcher_rates(self.fetch_people(player_id))
            except Exception:
                rates = None
            if rates is not None:
                try:
                    vs_lhb, vs_rhb = parse_pitcher_splits(
                        self.fetch_pitcher_splits(player_id)
                    )
                    rates = replace(rates, vs_lhb=vs_lhb, vs_rhb=vs_rhb)
                except Exception:
                    pass  # splits fetch failure must not crash hydration; vs_* stay None
            self._pitcher_cache[player_id] = rates
        return self._pitcher_cache[player_id]

    def _batter(self, player_id: int) -> BatterRates | None:
        if player_id not in self._batter_cache:
            try:
                rates = parse_batter_rates(self.fetch_batter_people(player_id))
            except Exception:
                rates = None
            if rates is not None:
                try:
                    vs_lhp, vs_rhp = parse_batter_splits(
                        self.fetch_batter_splits(player_id)
                    )
                    rates = replace(rates, vs_lhp=vs_lhp, vs_rhp=vs_rhp)
                except Exception:
                    pass  # splits fetch failure must not crash hydration; vs_* stay None
            self._batter_cache[player_id] = rates
        return self._batter_cache[player_id]

    def projected_contexts(
        self, date_iso: str, *, captured_at: str,
    ) -> list[MlbGameContext]:
        contexts = parse_schedule(
            self.fetch_schedule(date_iso), captured_at=captured_at,
        )
        hydrated: list[MlbGameContext] = []
        for ctx in contexts:
            run_factor, hr_factor = park_factors(ctx.venue)
            hydrated.append(replace(
                ctx,
                home_pitcher=self._pitcher(ctx.home_probable_pitcher_id),
                away_pitcher=self._pitcher(ctx.away_probable_pitcher_id),
                park_run_factor=run_factor,
                park_hr_factor=hr_factor,
            ))
        return hydrated

    def confirm_lineups(
        self, ctx: MlbGameContext, *, captured_at: str,
    ) -> MlbGameContext:
        home, away = parse_boxscore_lineups(self.fetch_boxscore(ctx.game_pk))
        return apply_confirmed_lineups(ctx, home, away, captured_at=captured_at)

    def hydrate_batter_rates(self, ctx: MlbGameContext) -> MlbGameContext:
        """Attach season offensive rates for every batter in both lineups."""
        rates: dict[int, BatterRates] = {}
        for slot in (*ctx.home_lineup, *ctx.away_lineup):
            batter = self._batter(slot.player_id)
            if batter is not None:
                rates[slot.player_id] = batter
        return replace(ctx, batter_rates=rates)
