"""FanGraphs projection-consensus intake (keyless, read-only, fail-closed).

Leg #1 of the fantasy triangulation layer. Reads FanGraphs' public projections
JSON API -- the same endpoint the site's own projections table calls -- and
turns per-player, rest-of-season projections into per-team scoring/prevention
rates the MLB run model can price against. Both the batting and pitching cuts
are pulled for one configurable projection system (default ``steamer``).

Endpoint (verified keyless, 2026-07-16):
    https://www.fangraphs.com/api/projections?type=steamer&stats=bat&pos=all&team=0
    (also stats=pit; type in {steamer, zips, thebat, thebatx, atc})

Batter rows carry PlayerName/Team/R/HR/RBI/SB/wOBA/wRC+/WAR plus q10..q90
wOBA-percentile bands and ADP; pitcher rows carry ERA/FIP/SO/IP/WAR plus q10..q90
ERA-percentile bands and ADP.

TERMS-OF-SERVICE POSTURE: FanGraphs projections are used here strictly as
INTERNAL CHALLENGER EVIDENCE. Nothing fetched is redistributed, republished, or
resold, and no derived table is exposed downstream. A single polite fetch per
cycle (bat + pit), a browser User-Agent, and a bounded timeout keep the read
courteous. If FanGraphs signals that automated reads are unwelcome, this leg is
retired rather than worked around.

Discipline mirrors the other keyless intake adapters (espn.py / injuries.py):
  * keyless / read-only -- never authenticates, never writes upstream.
  * fail-closed -- any fetch or parse error yields an EMPTY book, which makes
    every downstream signal abstain (byte-identical to a run without this leg).
  * unknown-team fail-closed -- a row whose team does not map to a canonical MLB
    abbreviation is dropped, never guessed.
  * circuit-breaker friendly -- one fetch per cycle via ``refresh()``; an
    un-refreshed book is simply empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

_API_URL = "https://www.fangraphs.com/api/projections"

# Projection systems FanGraphs exposes on this endpoint. An unrecognized request
# falls back to the default rather than fetching a garbage cut.
PROJECTION_SYSTEMS: tuple[str, ...] = ("steamer", "zips", "thebat", "thebatx", "atc")
DEFAULT_SYSTEM = "steamer"

# A projected full-season counting stat (R, IP) is divided by this to reach a
# per-game rate. MLB plays a 162-game schedule; using the season length keeps
# the RELATIVE ordering across teams intact even if a given cut is rest-of-season
# rather than full-season (the v1 simplification -- see ProjectionBook).
GAMES_PER_SEASON = 162.0

# ERA is earned runs per 9 innings; team runs allowed per game runs a little
# higher because ~8% of runs are unearned. A fixed, documented multiplier keeps
# the defense rate honest without a second model.
UNEARNED_RUN_FACTOR = 1.08

# League-average team runs per game -- the defense fallback when a team has no
# usable pitching projection, and the sanity clamp bounds for every rate.
LEAGUE_AVG_RUNS_PER_GAME = 4.30
MIN_RUNS_PER_GAME = 2.5
MAX_RUNS_PER_GAME = 6.5

# Canonical MLB abbreviations = the namespace the sports-contract parser emits
# (autonomy.sports.espn.canonical_team output). The Athletics collapse to "ATH".
CANONICAL_MLB_TEAMS: frozenset[str] = frozenset({
    "ARI", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN", "CLE", "COL", "DET",
    "HOU", "KC", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "ATH",
    "PHI", "PIT", "SD", "SEA", "SF", "STL", "TB", "TEX", "TOR", "WSH",
})

# Non-canonical inputs -> canonical. Covers FanGraphs' 3-letter abbreviations
# (KCR/SDP/SFG/TBR/WSN), the ESPN aliases the contract parser also honors
# (AZ->ARI, CWS->CHW), and the OAK->ATH relocation fold. Anything not resolvable
# to a canonical team is dropped (unknown-team fail-closed).
_TEAM_ALIASES: dict[str, str] = {
    "KCR": "KC", "SDP": "SD", "SFG": "SF", "TBR": "TB", "WSN": "WSH",
    "AZ": "ARI", "ARZ": "ARI", "CWS": "CHW", "OAK": "ATH", "WAS": "WSH",
    "KCA": "KC", "SDN": "SD", "SFN": "SF", "TBA": "TB", "CHA": "CHW",
    "CHN": "CHC", "LAN": "LAD", "NYA": "NYY", "NYN": "NYM", "SLN": "STL",
}


def canonical_mlb_team(abbr: Any) -> str | None:
    """Map any FanGraphs/ESPN/Kalshi MLB abbreviation to the canonical form.

    Returns ``None`` for a blank, unknown, or unmappable team (fail-closed): the
    caller must treat that as "no projection for this team", never a guess.
    """
    text = str(abbr or "").strip().upper()
    if not text:
        return None
    text = _TEAM_ALIASES.get(text, text)
    return text if text in CANONICAL_MLB_TEAMS else None


def _num(row: dict[str, Any], *keys: str) -> float | None:
    """First finite float among ``keys`` in ``row``; None if none parse."""
    import math

    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is None or isinstance(value, bool):
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            return parsed
    return None


def _percentiles(row: dict[str, Any]) -> dict[str, float]:
    """q10..q90 band (wOBA for batters, ERA for pitchers) present in the row."""
    bands: dict[str, float] = {}
    for pct in (10, 20, 30, 40, 50, 60, 70, 80, 90):
        value = _num(row, f"q{pct}")
        if value is not None:
            bands[f"q{pct}"] = value
    return bands


@dataclass(frozen=True)
class PlayerProjection:
    """One player's projected line, team-canonicalized. ``None`` = not provided."""

    player_id: str
    name: str
    team: str  # canonical MLB abbreviation (rows with an unknown team are dropped)
    system: str  # projection system, e.g. "steamer"
    stat_group: str  # "bat" | "pit"
    games: float | None = None
    plate_appearances: float | None = None
    runs: float | None = None
    home_runs: float | None = None
    rbi: float | None = None
    stolen_bases: float | None = None
    woba: float | None = None
    wrc_plus: float | None = None
    innings_pitched: float | None = None
    era: float | None = None
    fip: float | None = None
    strikeouts: float | None = None
    war: float | None = None
    adp: float | None = None
    percentiles: dict[str, float] = field(default_factory=dict)


def parse_projection_row(
    row: dict[str, Any], system: str, stat_group: str,
) -> PlayerProjection | None:
    """One raw FanGraphs row -> PlayerProjection, or None (fail-closed).

    Drops rows lacking an identity (name + id) or an unmappable team so no
    guessed team ever enters the book.
    """
    if not isinstance(row, dict):
        return None
    name = str(row.get("PlayerName") or "").strip()
    player_id = str(row.get("playerid") or row.get("playerids") or "").strip()
    if not name or not player_id:
        return None
    team = canonical_mlb_team(row.get("Team"))
    if team is None:
        return None
    return PlayerProjection(
        player_id=player_id,
        name=name,
        team=team,
        system=system,
        stat_group=stat_group,
        games=_num(row, "G"),
        plate_appearances=_num(row, "PA"),
        runs=_num(row, "R"),
        home_runs=_num(row, "HR"),
        rbi=_num(row, "RBI"),
        stolen_bases=_num(row, "SB"),
        woba=_num(row, "wOBA"),
        wrc_plus=_num(row, "wRC+"),
        innings_pitched=_num(row, "IP"),
        era=_num(row, "ERA"),
        fip=_num(row, "FIP"),
        strikeouts=_num(row, "SO"),
        war=_num(row, "WAR"),
        adp=_num(row, "ADP"),
        percentiles=_percentiles(row),
    )


def parse_projections(
    payload: Any, system: str, stat_group: str,
) -> list[PlayerProjection]:
    """Parse a full projections payload (a JSON array) into PlayerProjections.

    Tolerates the array being wrapped under a ``data``/``projections`` key.
    Never raises: a malformed payload yields an empty list.
    """
    rows: Any = payload
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("projections") or []
    if not isinstance(rows, list):
        return []
    parsed: list[PlayerProjection] = []
    for row in rows:
        projection = parse_projection_row(row, system, stat_group)
        if projection is not None:
            parsed.append(projection)
    return parsed


def default_fetch_projections(system: str, stat_group: str) -> Any:
    """Fetch one projections cut (keyless, browser UA, bounded timeout)."""
    import httpx

    response = httpx.get(
        _API_URL,
        params={"type": system, "stats": stat_group, "pos": "all", "team": "0"},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.fangraphs.com/projections",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _clamp_runs(value: float) -> float:
    return max(MIN_RUNS_PER_GAME, min(MAX_RUNS_PER_GAME, value))


@dataclass(frozen=True)
class TeamProjection:
    """Projection-derived per-game scoring / prevention rates for one team."""

    team: str
    runs_per_game: float  # offense: sum(projected R) / GAMES_PER_SEASON, clamped
    runs_allowed_per_game: float  # defense: IP-weighted ERA * unearned, clamped
    defense_is_projected: bool  # False => league-average fallback (no pitching)
    batter_count: int
    pitcher_count: int
    top_woba: float | None = None
    team_era: float | None = None


def aggregate_team_projections(
    batters: list[PlayerProjection], pitchers: list[PlayerProjection],
) -> dict[str, TeamProjection]:
    """Team abbr -> TeamProjection from the batter + pitcher projection lists.

    Offense: a team's season runs equal the sum of its batters' projected R
    (each run is credited to exactly one scorer), so ``sum(R) / 162`` is a clean
    lineup-agnostic runs-per-game rate. Defense: the IP-weighted mean ERA of the
    team's pitchers, scaled to total runs allowed. A team with batters but no
    usable pitching keeps a league-average defense (flagged), so it can still be
    priced; a team with neither is simply absent from the book.
    """
    runs_for: dict[str, float] = {}
    batter_count: dict[str, int] = {}
    top_woba: dict[str, float] = {}
    for batter in batters:
        if batter.runs is None:
            continue
        runs_for[batter.team] = runs_for.get(batter.team, 0.0) + batter.runs
        batter_count[batter.team] = batter_count.get(batter.team, 0) + 1
        if batter.woba is not None:
            top_woba[batter.team] = max(top_woba.get(batter.team, 0.0), batter.woba)

    era_weighted: dict[str, float] = {}
    ip_total: dict[str, float] = {}
    pitcher_count: dict[str, int] = {}
    for pitcher in pitchers:
        if pitcher.era is None or pitcher.innings_pitched is None:
            continue
        if pitcher.innings_pitched <= 0:
            continue
        era_weighted[pitcher.team] = (
            era_weighted.get(pitcher.team, 0.0) + pitcher.era * pitcher.innings_pitched
        )
        ip_total[pitcher.team] = ip_total.get(pitcher.team, 0.0) + pitcher.innings_pitched
        pitcher_count[pitcher.team] = pitcher_count.get(pitcher.team, 0) + 1

    teams: dict[str, TeamProjection] = {}
    for team in runs_for:  # an offense rate is required to price either side
        team_era = era_weighted[team] / ip_total[team] if ip_total.get(team) else None
        defense_projected = team_era is not None
        runs_allowed = (
            _clamp_runs(team_era * UNEARNED_RUN_FACTOR)
            if defense_projected
            else LEAGUE_AVG_RUNS_PER_GAME
        )
        teams[team] = TeamProjection(
            team=team,
            runs_per_game=_clamp_runs(runs_for[team] / GAMES_PER_SEASON),
            runs_allowed_per_game=runs_allowed,
            defense_is_projected=defense_projected,
            batter_count=batter_count.get(team, 0),
            pitcher_count=pitcher_count.get(team, 0),
            top_woba=top_woba.get(team),
            team_era=team_era,
        )
    return teams


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectionBook:
    """Per-cycle cache of FanGraphs projections aggregated to team rates.

    ``refresh()`` performs the single per-cycle fetch (bat + pit) and, when a
    ledger is attached, records every player snapshot as a point-in-time
    external observation. Any failure leaves an EMPTY book (fail-closed).
    """

    def __init__(
        self,
        system: str = DEFAULT_SYSTEM,
        fetch_fn: Callable[[str, str], Any] | None = None,
        ledger: Any = None,
    ) -> None:
        self.system = system if system in PROJECTION_SYSTEMS else DEFAULT_SYSTEM
        self.fetch_fn = fetch_fn or default_fetch_projections
        self.ledger = ledger
        self._teams: dict[str, TeamProjection] | None = None
        self._players: list[PlayerProjection] = []

    @property
    def source_name(self) -> str:
        return f"fangraphs_{self.system}"

    def reset(self) -> None:
        """Drop the cached book (used when MLB is dormant)."""
        self._teams = None
        self._players = []

    def refresh(self) -> None:
        """Reload both cuts once (best-effort); an error empties the book."""
        try:
            batters = parse_projections(self.fetch_fn(self.system, "bat"), self.system, "bat")
            pitchers = parse_projections(self.fetch_fn(self.system, "pit"), self.system, "pit")
        except Exception:
            self._teams = {}
            self._players = []
            return
        self._players = [*batters, *pitchers]
        self._teams = aggregate_team_projections(batters, pitchers)
        self._record_snapshot()

    def _record_snapshot(self) -> None:
        """Persist each player projection as a raw external observation.

        Best-effort and non-load-bearing: a ledger error never disturbs the
        book. Each refresh is a new point-in-time vintage (observed_at is part
        of the ledger's content-addressed row key); rows within one snapshot
        dedup automatically.
        """
        if self.ledger is None:
            return
        recorder = getattr(self.ledger, "record_external_observation", None)
        if not callable(recorder):
            return
        observed_at = _now_iso()
        for player in self._players:
            # Primary value: wOBA for batters, ERA for pitchers -- the stat the
            # q10..q90 band describes. Skip a player with no primary value.
            if player.stat_group == "bat":
                value, unit = player.woba, "woba"
            else:
                value, unit = player.era, "era"
            if value is None:
                continue
            series_id = f"{player.team}:{player.player_id or player.name}:{self.system}"
            try:
                recorder(
                    source=self.source_name,
                    series_id=series_id,
                    observed_at=observed_at,
                    value=float(value),
                    unit=unit,
                    features={
                        "name": player.name,
                        "team": player.team,
                        "stat_group": player.stat_group,
                        "system": self.system,
                        "percentiles": player.percentiles,
                        "war": player.war,
                        "adp": player.adp,
                        "runs": player.runs,
                        "home_runs": player.home_runs,
                        "rbi": player.rbi,
                        "wrc_plus": player.wrc_plus,
                        "innings_pitched": player.innings_pitched,
                        "fip": player.fip,
                        "strikeouts": player.strikeouts,
                    },
                )
            except Exception:
                continue  # one bad row never sinks the snapshot

    def _ensure(self) -> dict[str, TeamProjection]:
        return self._teams or {}

    def is_empty(self) -> bool:
        return not self._ensure()

    def teams(self) -> dict[str, TeamProjection]:
        return dict(self._ensure())

    def players(self) -> list[PlayerProjection]:
        return list(self._players)

    def team(self, abbr: Any) -> TeamProjection | None:
        """Canonical-team lookup; None for an empty book or unmapped team."""
        canonical = canonical_mlb_team(abbr)
        if canonical is None:
            return None
        return self._ensure().get(canonical)
