"""ESPN fantasy baseball (flb) ownership / ADP / projections intake.

Leg #3 of the fantasy triangulation layer (see docs/FANTASY_INTAKE.md). Reads
ESPN's public fantasy-baseball ``kona_player_info`` player universe -- the same
hidden JSON the fantasy.espn.com player table calls -- and turns each player's
CROWD signals (percentOwned / percentStarted / averageDraftPosition /
auctionValueAverage), injury/availability status, and ESPN's own season
projection into per-player facts and per-team aggregates a challenger signal can
price against. It also detects *scratch / availability deltas* between
consecutive cycles (a bat flipping OUT, a probable starter's status changing)
and exposes them as a typed feed.

Endpoint (verified keyless from this machine, 2026-07-16):
    GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/2026/players
        ?scoringPeriodId=0&view=kona_player_info
    header  x-fantasy-filter: <JSON>   (see PLAYER_FILTER below)

FILTER SEMANTICS (learned at build time, documented so it travels with the
code): this ``/players`` collection ALWAYS returns the full player universe
(~23k light rows). The ``x-fantasy-filter`` header does NOT truncate that list;
it selects which players get *enriched* with ``ownership`` / ``stats`` /
``draftRanksByRankType``. Without a well-formed filter, ZERO players are
enriched (every row is the bare light shape -- no ownership, no stats) and this
leg fail-closes to empty. The filter must request ``filterActive`` and the
season stat splits (``filterStatsForSourceIds: [0,1]`` -> actual+projected,
``filterStatsForTopScoringPeriodIds`` with the ``002026``/``102026`` external
ids). The response header ``x-fantasy-filter-player-count`` reports how many
rows matched. A light-only row (no ``ownership``) is dropped, never guessed.

statSourceId: 0 = actual, 1 = projected. statSplitTypeId 0 = full season. The
projected season line (source 1, split 0) supplies ``projected_applied_total``
plus the raw projected stat dict; the crowd signal uses it as a projection-delta
input alongside ownership.

TERMS-OF-SERVICE POSTURE (identical to the FanGraphs leg): ESPN fantasy data is
used STRICTLY as internal challenger evidence. Nothing fetched is redistributed,
republished, resold, or exposed downstream. One polite fetch per cycle, a
browser User-Agent, a bounded timeout. If ESPN signals automated reads are
unwelcome, this leg is retired rather than worked around.

Discipline mirrors the sibling keyless intakes (fangraphs.py / espn.py /
injuries.py):
  * keyless / read-only -- never authenticates, never writes upstream.
  * fail-closed -- any fetch or parse error, or a light-only (un-enriched)
    response, yields an EMPTY book, which makes every downstream signal abstain
    (byte-identical to a run without this leg).
  * unknown-team fail-closed -- a proTeamId that does not map to a canonical MLB
    abbreviation (free agents, id 0) is dropped, never guessed.
  * one fetch per cycle via ``refresh()``; an un-refreshed book is empty.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

# Reuse leg #1's canonical MLB namespace + alias fold rather than re-declaring
# it -- ESPN fantasy abbreviations flow through the SAME function the FanGraphs
# leg and the sports-contract parser use, so book keys and market competitor
# abbreviations always agree.
from autonomy.ingest.fantasy.fangraphs import canonical_mlb_team

_API_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/2026/players"
)

# ESPN fantasy proTeamId (numeric) -> ESPN team abbreviation. Fetched
# authoritatively from ESPN's own proTeamSchedules_wl settings on 2026-07-16.
# id 0 is "FA" (free agent); every abbreviation is folded to the repo-canonical
# form by ``proteam_to_canonical`` via ``canonical_mlb_team`` (e.g. "Ath"->ATH,
# "ChW"->CHW, "Wsh"->WSH, "StL"->STL, "SD"/"SF"/"TB"/"KC" pass through).
ESPN_FLB_PRO_TEAMS: dict[int, str] = {
    0: "FA", 1: "Bal", 2: "Bos", 3: "LAA", 4: "ChW", 5: "Cle", 6: "Det",
    7: "KC", 8: "Mil", 9: "Min", 10: "NYY", 11: "Ath", 12: "Sea", 13: "Tex",
    14: "Tor", 15: "Atl", 16: "ChC", 17: "Cin", 18: "Hou", 19: "LAD", 20: "Wsh",
    21: "NYM", 22: "Phi", 23: "Pit", 24: "StL", 25: "SD", 26: "SF", 27: "Col",
    28: "Mia", 29: "Ari", 30: "TB",
}

# The x-fantasy-filter payload that enriches the player rows (see module
# docstring). ``limit`` is intentionally omitted: this endpoint does not
# truncate the list, so a limit only reduces the enriched set. sortPercOwned
# keeps the most-owned (most crowd-relevant) players enriched first.
PLAYER_FILTER: dict[str, Any] = {
    "players": {
        "filterActive": {"value": True},
        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        "filterStatsForSourceIds": {"value": [0, 1]},
        "filterStatsForTopScoringPeriodIds": {
            "value": 2, "additionalValue": ["002026", "102026"],
        },
    },
}

# ESPN injuryStatus -> coarse availability class. Anything not listed (unknown
# text) is treated as "available" (fail-closed: no manufactured doubt). The
# scratch detector keys off transitions between these classes, so the exact DL
# length does not matter -- OUT is OUT.
_OUT_STATUSES = {
    "OUT", "SUSPENSION", "TEN_DAY_DL", "FIFTEEN_DAY_DL", "SIXTY_DAY_DL",
    "DL", "IL", "INJURY_RESERVE",
}
_DTD_STATUSES = {"DAY_TO_DAY", "DAY-TO-DAY", "QUESTIONABLE", "PROBABLE"}

AVAIL_AVAILABLE = "available"
AVAIL_DAY_TO_DAY = "day_to_day"
AVAIL_OUT = "out"


def proteam_to_canonical(pro_team_id: Any) -> str | None:
    """ESPN numeric proTeamId -> canonical MLB abbreviation, or None.

    Free agents (id 0 -> "FA") and any unmapped id resolve to None
    (unknown-team fail-closed): the caller treats that as "no team", never a
    guess.
    """
    try:
        espn_abbr = ESPN_FLB_PRO_TEAMS.get(int(pro_team_id))
    except (TypeError, ValueError):
        return None
    if not espn_abbr:
        return None
    return canonical_mlb_team(espn_abbr)


def availability_class(injury_status: Any) -> str:
    """Coarse availability bucket for an ESPN injuryStatus string."""
    text = str(injury_status or "").strip().upper()
    if text in _OUT_STATUSES:
        return AVAIL_OUT
    if text in _DTD_STATUSES:
        return AVAIL_DAY_TO_DAY
    return AVAIL_AVAILABLE


def _num(value: Any) -> float | None:
    """Finite float or None (bools and non-numerics reject)."""
    import math

    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


@dataclass(frozen=True)
class FantasyPlayer:
    """One ESPN fantasy player's crowd + availability + projection facts.

    ``None`` = not provided. ``team`` is a canonical MLB abbreviation; a row
    whose proTeamId does not map (free agent / unknown) is dropped upstream and
    never becomes a FantasyPlayer.
    """

    player_id: str
    name: str
    team: str  # canonical MLB abbreviation
    pro_team_id: int
    injury_status: str
    availability: str  # available | day_to_day | out
    default_position_id: int | None = None
    eligible_slots: tuple[int, ...] = ()
    percent_owned: float | None = None
    percent_started: float | None = None
    percent_owned_change: float | None = None
    average_draft_position: float | None = None
    adp_percent_change: float | None = None
    auction_value: float | None = None
    draft_rank: int | None = None  # STANDARD-format draft rank
    projected_applied_total: float | None = None
    projected_stats: dict[str, float] = field(default_factory=dict)

    @property
    def is_pitcher(self) -> bool:
        # ESPN default position ids 1 (SP) and 11 (RP) are pitchers.
        return self.default_position_id in (1, 11)


def _projected_line(raw: dict[str, Any]) -> tuple[float | None, dict[str, float]]:
    """(appliedTotal, stat-dict) for the season projected line (source 1,
    split 0); (None, {}) when absent."""
    for stat in raw.get("stats") or []:
        if not isinstance(stat, dict):
            continue
        if stat.get("statSourceId") == 1 and stat.get("statSplitTypeId") == 0:
            applied = _num(stat.get("appliedTotal"))
            values: dict[str, float] = {}
            for key, value in (stat.get("stats") or {}).items():
                parsed = _num(value)
                if parsed is not None:
                    values[str(key)] = parsed
            return applied, values
    return None, {}


def parse_player(raw: Any) -> FantasyPlayer | None:
    """One raw ESPN player row -> FantasyPlayer, or None (fail-closed).

    Drops a row lacking identity (id + fullName), one whose proTeamId does not
    map to a canonical MLB team, and -- crucially -- a LIGHT-ONLY row that was
    never enriched (no ``ownership`` block): an un-enriched universe means the
    filter did not take, and a book built from light rows would be a silent
    lie. Requiring ownership is what makes the whole book fail-closed when the
    enriched view is unavailable.
    """
    if not isinstance(raw, dict):
        return None
    player_id = str(raw.get("id") or "").strip()
    name = str(raw.get("fullName") or "").strip()
    if not player_id or not name:
        return None
    team = proteam_to_canonical(raw.get("proTeamId"))
    if team is None:
        return None
    ownership = raw.get("ownership")
    if not isinstance(ownership, dict):
        return None  # light-only (un-enriched) row -> drop, fail-closed
    try:
        pro_team_id = int(raw.get("proTeamId"))
    except (TypeError, ValueError):
        return None
    injury_status = str(raw.get("injuryStatus") or "").strip().upper() or "ACTIVE"
    eligible = tuple(
        int(slot) for slot in (raw.get("eligibleSlots") or [])
        if isinstance(slot, int) and not isinstance(slot, bool)
    )
    default_position = raw.get("defaultPositionId")
    default_position = (
        int(default_position)
        if isinstance(default_position, int) and not isinstance(default_position, bool)
        else None
    )
    standard = (raw.get("draftRanksByRankType") or {}).get("STANDARD") or {}
    rank_value = standard.get("rank")
    draft_rank = (
        int(rank_value)
        if isinstance(rank_value, int) and not isinstance(rank_value, bool)
        else None
    )
    applied, projected_stats = _projected_line(raw)
    return FantasyPlayer(
        player_id=player_id,
        name=name,
        team=team,
        pro_team_id=pro_team_id,
        injury_status=injury_status,
        availability=availability_class(injury_status),
        default_position_id=default_position,
        eligible_slots=eligible,
        percent_owned=_num(ownership.get("percentOwned")),
        percent_started=_num(ownership.get("percentStarted")),
        percent_owned_change=_num(ownership.get("percentChange")),
        average_draft_position=_num(ownership.get("averageDraftPosition")),
        adp_percent_change=_num(ownership.get("averageDraftPositionPercentChange")),
        auction_value=_num(ownership.get("auctionValueAverage")),
        draft_rank=draft_rank,
        projected_applied_total=applied,
        projected_stats=projected_stats,
    )


def parse_players(payload: Any) -> list[FantasyPlayer]:
    """Parse the full ESPN player payload (a JSON array) into FantasyPlayers.

    Tolerates the array being wrapped under a ``players`` key. Never raises: a
    malformed payload yields an empty list. Light-only (un-enriched) rows are
    dropped, so a response where the filter did not take yields [].
    """
    rows: Any = payload
    if isinstance(payload, dict):
        rows = payload.get("players") or payload.get("data") or []
    if not isinstance(rows, list):
        return []
    parsed: list[FantasyPlayer] = []
    for row in rows:
        player = parse_player(row)
        if player is not None:
            parsed.append(player)
    return parsed


def default_fetch_players() -> Any:
    """Fetch the enriched player universe (keyless, browser UA, filter header)."""
    import httpx

    response = httpx.get(
        _API_URL,
        params={"scoringPeriodId": 0, "view": "kona_player_info"},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "x-fantasy-filter": json.dumps(PLAYER_FILTER),
        },
        timeout=25,
    )
    response.raise_for_status()
    return response.json()


# Ownership floor for a player to count toward a team's crowd aggregate. Deep
# bench / un-owned players (0% owned) carry no public signal and only add noise.
MIN_OWNERSHIP_FOR_AGGREGATE = 1.0
# A ownership swing of this many points between cycles is surfaced as a scratch
# event (public sentiment moved hard on a player).
OWNERSHIP_SWING_THRESHOLD = 5.0


@dataclass(frozen=True)
class TeamFantasyAggregate:
    """Per-team crowd + projection aggregate over its owned players."""

    team: str
    public_backing: float  # sum(percentOwned/100) over owned players
    projected_strength: float  # sum(projected_applied_total) over owned players
    owned_player_count: int
    out_count: int  # owned players currently OUT (availability == out)
    day_to_day_count: int
    top_owned: tuple[str, ...] = ()  # names of the most-owned, for logging


def aggregate_team_fantasy(
    players: list[FantasyPlayer],
) -> dict[str, TeamFantasyAggregate]:
    """Team abbr -> TeamFantasyAggregate over its meaningfully-owned players."""
    backing: dict[str, float] = {}
    strength: dict[str, float] = {}
    counts: dict[str, int] = {}
    out_counts: dict[str, int] = {}
    dtd_counts: dict[str, int] = {}
    owned: dict[str, list[tuple[float, str]]] = {}
    for player in players:
        owned_pct = player.percent_owned
        if owned_pct is None or owned_pct < MIN_OWNERSHIP_FOR_AGGREGATE:
            continue
        team = player.team
        backing[team] = backing.get(team, 0.0) + owned_pct / 100.0
        if player.projected_applied_total is not None:
            strength[team] = strength.get(team, 0.0) + player.projected_applied_total
        counts[team] = counts.get(team, 0) + 1
        if player.availability == AVAIL_OUT:
            out_counts[team] = out_counts.get(team, 0) + 1
        elif player.availability == AVAIL_DAY_TO_DAY:
            dtd_counts[team] = dtd_counts.get(team, 0) + 1
        owned.setdefault(team, []).append((owned_pct, player.name))

    result: dict[str, TeamFantasyAggregate] = {}
    for team in counts:
        top = tuple(
            name for _, name in sorted(owned[team], key=lambda item: -item[0])[:5]
        )
        result[team] = TeamFantasyAggregate(
            team=team,
            public_backing=backing.get(team, 0.0),
            projected_strength=strength.get(team, 0.0),
            owned_player_count=counts.get(team, 0),
            out_count=out_counts.get(team, 0),
            day_to_day_count=dtd_counts.get(team, 0),
            top_owned=top,
        )
    return result


@dataclass(frozen=True)
class ScratchEvent:
    """One player's between-cycle availability / sentiment change.

    Evidence-only, typed to mirror the opportunist's existing evidence-only
    ``ejection_events`` shape (raw ESPN observations, never a trigger predicate
    or a probability adjustment). ``kind`` is one of "availability_change" or
    "ownership_swing".
    """

    kind: str
    player_id: str
    name: str
    team: str
    injury_status: str
    previous: str  # previous availability class OR prior percentOwned as text
    current: str  # current availability class OR current percentOwned as text
    detail: str = ""


def _snapshot(players: list[FantasyPlayer]) -> dict[str, dict[str, Any]]:
    """player_id -> the minimal fields the delta detector compares."""
    return {
        p.player_id: {
            "name": p.name,
            "team": p.team,
            "injury_status": p.injury_status,
            "availability": p.availability,
            "percent_owned": p.percent_owned,
        }
        for p in players
    }


def detect_scratch_events(
    previous: dict[str, dict[str, Any]] | None,
    current: dict[str, dict[str, Any]],
) -> list[ScratchEvent]:
    """Availability flips + hard ownership swings between two snapshots.

    A missing previous snapshot (first cycle / after a restart) yields NO
    events -- fail-closed: a change is only real relative to a prior read.
    """
    if not previous:
        return []
    events: list[ScratchEvent] = []
    for player_id, now in current.items():
        before = previous.get(player_id)
        if before is None:
            continue  # newly-enriched player: no prior state to diff against
        if before.get("availability") != now.get("availability"):
            events.append(ScratchEvent(
                kind="availability_change",
                player_id=player_id,
                name=str(now.get("name") or ""),
                team=str(now.get("team") or ""),
                injury_status=str(now.get("injury_status") or ""),
                previous=str(before.get("availability") or ""),
                current=str(now.get("availability") or ""),
                detail=(
                    f"{before.get('injury_status')} -> {now.get('injury_status')}"
                ),
            ))
            continue  # an availability flip supersedes an ownership swing note
        prev_owned = before.get("percent_owned")
        now_owned = now.get("percent_owned")
        if (
            isinstance(prev_owned, (int, float))
            and isinstance(now_owned, (int, float))
            and abs(now_owned - prev_owned) >= OWNERSHIP_SWING_THRESHOLD
        ):
            events.append(ScratchEvent(
                kind="ownership_swing",
                player_id=player_id,
                name=str(now.get("name") or ""),
                team=str(now.get("team") or ""),
                injury_status=str(now.get("injury_status") or ""),
                previous=f"{prev_owned:.1f}",
                current=f"{now_owned:.1f}",
                detail=f"percentOwned {prev_owned:.1f} -> {now_owned:.1f}",
            ))
    return events


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FantasyBook:
    """Per-cycle cache of ESPN fantasy players, team aggregates, and the
    between-cycle scratch feed.

    ``refresh()`` performs the single per-cycle fetch and, when a ledger is
    attached, records every player snapshot (and any scratch event) as a
    point-in-time external observation. Any failure -- or a light-only,
    un-enriched response -- leaves an EMPTY book (fail-closed).

    Scratch persistence: the previous snapshot is held IN MEMORY on this
    long-lived book instance (registered once, refreshed each cycle), matching
    the in-memory-only discipline of the sibling injury books
    (autonomy/sports/injuries.py::InjuryBook,
    autonomy/sports/players.py::LeagueInjuryBook) and ProjectionBook. Ledger
    read-back is available (snapshots ARE recorded) but heavier and unnecessary
    for a consecutive-cycle diff; runtime-state disk persistence was rejected
    to avoid touching runtime/ and to stay consistent with those books. After a
    restart the first cycle simply emits no events (no prior) -- fail-closed.
    """

    source_name = "espn_flb"
    scratch_source_name = "espn_flb_scratch"

    def __init__(
        self,
        fetch_fn: Callable[[], Any] | None = None,
        ledger: Any = None,
    ) -> None:
        self.fetch_fn = fetch_fn or default_fetch_players
        self.ledger = ledger
        self._players: list[FantasyPlayer] = []
        self._teams: dict[str, TeamFantasyAggregate] | None = None
        self._prev_snapshot: dict[str, dict[str, Any]] | None = None
        self._scratch_events: tuple[ScratchEvent, ...] = ()

    def reset(self) -> None:
        """Drop the cached book (used when MLB is dormant). The previous
        snapshot is cleared too, so the wake-up cycle re-baselines rather than
        diffing across a dormant gap."""
        self._players = []
        self._teams = None
        self._prev_snapshot = None
        self._scratch_events = ()

    def refresh(self) -> None:
        """Reload the player universe once (best-effort); an error or an
        un-enriched response empties the book."""
        try:
            players = parse_players(self.fetch_fn())
        except Exception:
            self._players = []
            self._teams = {}
            self._scratch_events = ()
            return
        if not players:
            # Un-enriched / empty response: fail-closed, and do NOT overwrite a
            # good prior snapshot with emptiness (that would manufacture a wave
            # of "everyone scratched" events on the next good cycle).
            self._players = []
            self._teams = {}
            self._scratch_events = ()
            return
        current_snapshot = _snapshot(players)
        self._scratch_events = tuple(
            detect_scratch_events(self._prev_snapshot, current_snapshot)
        )
        self._players = players
        self._teams = aggregate_team_fantasy(players)
        self._record_snapshot()
        self._record_scratch()
        self._prev_snapshot = current_snapshot

    def _record_snapshot(self) -> None:
        """Persist each player as a raw external observation (best-effort)."""
        if self.ledger is None:
            return
        recorder = getattr(self.ledger, "record_external_observation", None)
        if not callable(recorder):
            return
        observed_at = _now_iso()
        for player in self._players:
            if player.percent_owned is None:
                continue
            series_id = f"{player.team}:{player.player_id}:flb"
            try:
                recorder(
                    source=self.source_name,
                    series_id=series_id,
                    observed_at=observed_at,
                    value=float(player.percent_owned),
                    unit="percent_owned",
                    features={
                        "name": player.name,
                        "team": player.team,
                        "injury_status": player.injury_status,
                        "availability": player.availability,
                        "percent_started": player.percent_started,
                        "average_draft_position": player.average_draft_position,
                        "auction_value": player.auction_value,
                        "draft_rank": player.draft_rank,
                        "percent_owned_change": player.percent_owned_change,
                        "projected_applied_total": player.projected_applied_total,
                        "default_position_id": player.default_position_id,
                    },
                )
            except Exception:
                continue  # one bad row never sinks the snapshot

    def _record_scratch(self) -> None:
        """Persist each scratch event as a raw external observation (best-effort)."""
        if self.ledger is None or not self._scratch_events:
            return
        recorder = getattr(self.ledger, "record_external_observation", None)
        if not callable(recorder):
            return
        observed_at = _now_iso()
        for event in self._scratch_events:
            try:
                recorder(
                    source=self.scratch_source_name,
                    series_id=f"{event.team}:{event.player_id}:{event.kind}",
                    observed_at=observed_at,
                    value=1.0,
                    unit="event",
                    features={
                        "kind": event.kind,
                        "name": event.name,
                        "team": event.team,
                        "injury_status": event.injury_status,
                        "previous": event.previous,
                        "current": event.current,
                        "detail": event.detail,
                    },
                )
            except Exception:
                continue

    def _ensure(self) -> dict[str, TeamFantasyAggregate]:
        return self._teams or {}

    def is_empty(self) -> bool:
        return not self._ensure()

    def teams(self) -> dict[str, TeamFantasyAggregate]:
        return dict(self._ensure())

    def players(self) -> list[FantasyPlayer]:
        return list(self._players)

    def team(self, abbr: Any) -> TeamFantasyAggregate | None:
        """Canonical-team lookup; None for an empty book or unmapped team."""
        canonical = canonical_mlb_team(abbr)
        if canonical is None:
            return None
        return self._ensure().get(canonical)

    def scratch_events(self) -> tuple[ScratchEvent, ...]:
        """This cycle's availability / sentiment change feed (evidence-only)."""
        return self._scratch_events
