"""Per-game team boxscore stat pipeline (keyless ESPN summary endpoint).

Foundation for the NBA pace model, NHL special-teams model, and NFL
unit-mismatch finder: those engines need per-game team stats (shooting
splits, rebounding, special teams, yardage) the scoreboard endpoint doesn't
carry. This module fetches, parses, and persists that one layer once.

Fail-closed throughout: a missing feed, a missing boxscore section, or an
unsupported league returns ``[]``/empty state -- never raises past the fetch
call itself, so an outage leaves history byte-identical to before.

PROBE (build-time, 2026-07-12, network confirmed reachable): one completed
("status.type.state" == "post") game's summary was fetched per league via
``https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary``
and the exact ``boxscore.teams[].statistics[].name`` keys recorded below.

- NBA: event 401810960 (PHI @ WSH, 2026-04-01), found via the
  basketball/nba scoreboard for dates=20260112 (a "post" game one date
  bucket later, per ESPN's UTC date bucketing).
  Observed keys include: fieldGoalsMade-fieldGoalsAttempted, fieldGoalPct,
  threePointFieldGoalsMade-threePointFieldGoalsAttempted,
  threePointFieldGoalPct, freeThrowsMade-freeThrowsAttempted, freeThrowPct,
  totalRebounds, offensiveRebounds, defensiveRebounds, assists, steals,
  blocks, turnovers, teamTurnovers, totalTurnovers, technicalFouls,
  totalTechnicalFouls, flagrantFouls, turnoverPoints, fastBreakPoints,
  pointsInPaint, fouls, largestLead, leadChanges, leadPercentage.
  DISCREPANCIES vs the brief's expected keys:
    * `fieldGoalsAttempted` and `freeThrowsAttempted` do NOT exist as
      standalone keys. ESPN packs made+attempted into one composite
      "made-attempted" displayValue (e.g. "61-99"); split on "-" to recover
      both (see _NBA_SPLIT_KEYS below).
    * `points` is NOT present anywhere in boxscore.teams[].statistics. Final
      score lives on header.competitions[].competitors[].score instead, a
      different part of the payload this module doesn't touch (it's already
      carried by autonomy/sports/espn.py's Game.home_score/away_score, so
      there's no need to duplicate it here -- YAGNI).
- NHL: event 401803067 (FLA @ BUF, 2026-01-12), found via the
  hockey/nhl scoreboard for dates=20260112.
  Observed keys: blockedShots, hits, takeaways, shotsTotal, powerPlayGoals,
  powerPlayOpportunities, powerPlayPct, shortHandedGoals, shootoutGoals,
  faceoffsWon, faceoffPercent, giveaways, penalties, penaltyMinutes.
  Matches the brief's expectations exactly (powerPlayGoals,
  powerPlayOpportunities, shotsTotal all present, plain numeric strings).
- NFL: event 401772977 (BUF @ JAX, 2026-01-11), found via the
  football/nfl scoreboard for dates=20260111.
  Observed keys include: firstDowns, firstDownsPassing, firstDownsRushing,
  firstDownsPenalty, thirdDownEff, fourthDownEff, totalOffensivePlays,
  totalYards, yardsPerPlay, totalDrives, netPassingYards,
  completionAttempts, yardsPerPass, interceptions, sacksYardsLost,
  rushingYards, rushingAttempts, yardsPerRushAttempt, redZoneAttempts,
  totalPenaltiesYards, turnovers, fumblesLost, defensiveTouchdowns,
  possessionTime.
  Matches the brief's expectations exactly (netPassingYards, rushingYards,
  totalYards, turnovers all present as plain numeric strings; "plays if
  present" -> totalOffensivePlays is present).

Trimmed real fixtures captured from these three probes live under
tests/fixtures/boxscore_{league}_{event_id}.json.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from autonomy.sports.espn import LEAGUE_TO_ESPN

DEFAULT_DIR = Path("runtime/autonomy")
RETENTION_CAP = 30  # per-team history cap (deque semantics on ingest)

# Per-league whitelist of raw ESPN `statistics[].name` values to keep, as
# verified by the build-time probe above. Anything else in the statistics
# row is dropped (YAGNI: only stats the WS-2/WS-3/WS-4 formulas need).
_STAT_KEYS: dict[str, tuple[str, ...]] = {
    "nba": ("offensiveRebounds", "turnovers"),  # + fieldGoals/freeThrows split below
    "nhl": ("powerPlayGoals", "powerPlayOpportunities", "shotsTotal"),
    "nfl": ("netPassingYards", "rushingYards", "totalYards", "turnovers", "totalOffensivePlays"),
    # WS-4 PROBE (2026-07-13, event 401825552, PUR @ OSU, mens-college-basketball
    # summary): boxscore.teams[].statistics[].name keys are IDENTICAL to NBA's
    # (same composite fieldGoalsMade-fieldGoalsAttempted / freeThrowsMade-
    # freeThrowsAttempted displayValues, same offensiveRebounds/turnovers) --
    # ESPN's basketball schema is shared across leagues, so ncaamb reuses the
    # NBA whitelist + split-key handling verbatim (see _parse_stat_row below).
    "ncaamb": ("offensiveRebounds", "turnovers"),
    # WNBA shares ESPN's basketball schema (same composites + ORB/TO keys), so
    # it reuses the NBA whitelist + split-key handling verbatim. Added Wave-56
    # for the four-factors analytic (in-season league).
    "wnba": ("offensiveRebounds", "turnovers"),
}

# Basketball: ESPN reports made+attempted as one composite displayValue
# ("61-99"). Split each into two float stats under the names the possessions
# formula (FGA - ORB + TO + 0.44*FTA) and eFG% (needs 3PM) expect.
_NBA_SPLIT_KEYS: dict[str, tuple[str, str]] = {
    "fieldGoalsMade-fieldGoalsAttempted": ("fieldGoalsMade", "fieldGoalsAttempted"),
    "freeThrowsMade-freeThrowsAttempted": ("freeThrowsMade", "freeThrowsAttempted"),
    # Wave-56: 3-pointers, so eFG% = (FGM + 0.5*3PM)/FGA is exact.
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted":
        ("threePointFieldGoalsMade", "threePointFieldGoalsAttempted"),
}


@dataclass(frozen=True)
class TeamBoxscore:
    game_id: str
    league: str
    team: str
    opponent: str
    is_home: bool
    stats: dict[str, float]  # flat, per-league keys per _STAT_KEYS/_NBA_SPLIT_KEYS


def fetch_summary(league: str, event_id: str) -> dict[str, Any]:
    """Fetch the ESPN game summary for one event (keyless, read-only).

    Raises on failure (network error or non-2xx) -- callers that loop over
    many events must wrap each call in try/except-continue themselves (the
    fetch budget in the WS-1 brief), mirroring autonomy/live_odds.py's
    default_fetch_summary shape.
    """
    import httpx

    sport, esp = LEAGUE_TO_ESPN[league]
    response = httpx.get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{esp}/summary",
        params={"event": event_id},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _parse_stat_row(league: str, name: str, display_value: Any, out: dict[str, float]) -> None:
    if name in _STAT_KEYS.get(league, ()):
        try:
            out[name] = float(display_value)
        except (TypeError, ValueError):
            pass
        return
    if league in ("nba", "ncaamb", "wnba") and name in _NBA_SPLIT_KEYS:
        made_key, attempted_key = _NBA_SPLIT_KEYS[name]
        parts = str(display_value).split("-")
        if len(parts) == 2:
            try:
                out[made_key] = float(parts[0])
                out[attempted_key] = float(parts[1])
            except ValueError:
                pass


# Player counting-stat labels we keep, mapped from ESPN's boxscore column
# labels to canonical prop stat names. Basketball leagues share this schema.
_PLAYER_STAT_LABELS = {
    "MIN": "minutes", "PTS": "points", "REB": "rebounds", "AST": "assists",
    "STL": "steals", "BLK": "blocks", "3PT": "threes", "TO": "turnovers",
}


def parse_player_boxscores(
    league: str, summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Per-player counting stats from a summary's ``boxscore.players``.

    Returns rows shaped for the lake boxscores table
    ({game_id, team, player, stat, value}). Basketball only (the label schema
    is NBA/WNBA/NCAAMB); other leagues return []. ``3PT`` is recorded as made
    threes (the ``M-A`` string's made count). Fail-closed on odd payloads.
    """
    payload = summary or {}
    game_id = str((payload.get("header") or {}).get("id") or "")
    if not game_id or str(league).lower() not in {"nba", "wnba", "ncaamb"}:
        return []
    rows: list[dict[str, Any]] = []
    for block in ((payload.get("boxscore") or {}).get("players")) or []:
        team = ((block or {}).get("team") or {}).get("abbreviation")
        stat_groups = (block or {}).get("statistics") or []
        if not team or not stat_groups:
            continue
        group = stat_groups[0]
        labels = group.get("labels") or []
        index = {label: i for i, label in enumerate(labels)}
        for athlete in group.get("athletes") or []:
            name = (athlete.get("athlete") or {}).get("displayName")
            values = athlete.get("stats") or []
            if not name or not values:
                continue
            for label, canonical in _PLAYER_STAT_LABELS.items():
                pos = index.get(label)
                if pos is None or pos >= len(values):
                    continue
                raw = str(values[pos]).strip()
                if canonical == "threes" and "-" in raw:
                    raw = raw.split("-", 1)[0]  # made count from "M-A"
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "game_id": game_id, "team": team, "player": name,
                    "stat": canonical, "value": value,
                })
    return rows


def parse_team_boxscores(league: str, summary: dict[str, Any] | None) -> list[TeamBoxscore]:
    """Parse both teams' boxscores from a summary payload; [] when absent.

    Fail-closed: an unsupported league, a missing/empty boxscore section, a
    missing game id, or anything other than exactly two teams returns [].
    """
    if league not in _STAT_KEYS:
        return []
    payload = summary or {}
    game_id = str((payload.get("header") or {}).get("id") or "")
    if not game_id:
        return []
    teams = ((payload.get("boxscore") or {}).get("teams")) or []
    if len(teams) != 2:
        return []

    parsed: list[tuple[str, bool, dict[str, float]]] = []
    for entry in teams:
        abbreviation = (entry.get("team") or {}).get("abbreviation")
        if not abbreviation:
            return []
        is_home = entry.get("homeAway") == "home"
        stats: dict[str, float] = {}
        for row in entry.get("statistics") or []:
            name = row.get("name")
            display_value = row.get("displayValue")
            if name is None or display_value is None:
                continue
            _parse_stat_row(league, name, display_value, stats)
        parsed.append((abbreviation, is_home, stats))

    return [
        TeamBoxscore(
            game_id=game_id,
            league=league,
            team=abbreviation,
            opponent=parsed[1 - index][0],
            is_home=is_home,
            stats=stats,
        )
        for index, (abbreviation, is_home, stats) in enumerate(parsed)
    ]


class BoxscoreStore:
    """JSON-persisted per-league boxscore history, idempotent by game_id.

    Retention: caps each team's history at RETENTION_CAP entries, dropping
    the oldest on overflow (deque semantics) so history stays bounded even
    across a full season of warmup ingests.
    """

    def __init__(self, league: str, path: Path | None = None) -> None:
        self.league = league
        self.path = path or DEFAULT_DIR / f"boxscores_{league}.json"
        self._teams: dict[str, list[TeamBoxscore]] = {}
        self._seen: set[tuple[str, str]] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return
        for team, rows in (data.get("teams") or {}).items():
            history: list[TeamBoxscore] = []
            for row in rows:
                try:
                    boxscore = TeamBoxscore(**row)
                except (TypeError, KeyError):
                    continue
                history.append(boxscore)
                self._seen.add((boxscore.team, boxscore.game_id))
            self._teams[team] = history

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "league": self.league,
            "teams": {
                team: [asdict(boxscore) for boxscore in history]
                for team, history in self._teams.items()
            },
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

    def ingest(self, boxscores: list[TeamBoxscore]) -> int:
        """Idempotently add boxscores (by (team, game_id)); returns count added."""
        added = 0
        for boxscore in boxscores:
            key = (boxscore.team, boxscore.game_id)
            if key in self._seen:
                continue
            self._seen.add(key)
            history = self._teams.setdefault(boxscore.team, [])
            history.append(boxscore)
            if len(history) > RETENTION_CAP:
                del history[0]
            added += 1
        if added:
            self._save()
        return added

    def recent(self, team: str, n: int = 20) -> list[TeamBoxscore]:
        """Up to `n` most recent boxscores for `team`, newest first."""
        history = self._teams.get(team, [])
        return list(reversed(history[-n:])) if n > 0 else []
