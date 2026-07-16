"""Event-driven live-game poller (Wave-3).

Watches in-progress games and reacts to material state CHANGES only, so the
forecasting/execution stack re-prices on real events (a run scores, an inning
flips, bases turn over, a game goes final) instead of on a fixed wall clock.

Two layers, mirroring ``live_book.py``'s split:

  * A pure, synchronous CORE. ``parse_game_state`` turns one ESPN summary into
    a :class:`GameState`; ``diff_states`` turns two consecutive states into a
    list of typed :class:`ChangeEvent`. No I/O -- fully testable from committed
    fixtures. Identical consecutive states emit nothing (delta-driven).

  * A thin I/O SHELL. :class:`LiveGamePoller` discovers live events from the
    ESPN scoreboard, fetches each watched event's summary (reusing
    ``EspnSummaryBook``'s keyless read-only fetch + base-out parse), diffs
    against the last stored state, ledgers each change through an injected sink
    and invokes an injected re-evaluation hook. It self-paces: a fast cadence
    while any game is live, exponential backoff (to a cap) when none is.

Read/observe only: never submits an order, never mutates an unrelated book.
Gated OFF by default -- the constructor ``enabled`` flag AND the
``DUMMY_LIVE_POLLER`` env flag must BOTH be truthy, so the capability is opt-in
and fail-closed. The re-eval hook and ledger sink are injected (default no-op),
so wiring to the real forecaster/ledger is a one-liner and the core stays pure.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from autonomy.live_odds import EspnSummaryBook, parse_base_out_state
from autonomy.sports.espn import Game, default_fetch_scoreboard, parse_scoreboard

# Change kinds. Stable strings -- ledgered and matched by downstream consumers.
STATUS_IN = "status_in"
STATUS_POST = "status_post"
SCORE = "score"
LEAD_CHANGE = "lead_change"
PERIOD = "period"
BASE_OUT = "base_out"

_ENV_FLAG = "DUMMY_LIVE_POLLER"


def _env_enabled() -> bool:
    return str(os.environ.get(_ENV_FLAG, "")).strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed


def _period_number(play: dict[str, Any]) -> int | None:
    """ESPN carries a play's period as ``{"number": N}`` or occasionally a bare
    int; tolerate both, fail-closed to None."""
    period = play.get("period")
    if isinstance(period, dict):
        return _int(period.get("number"))
    return _int(period)


def _summary_status(summary: dict[str, Any]) -> str | None:
    """"pre"/"in"/"post" from the summary header, or None (fail-closed)."""
    header = summary.get("header") if isinstance(summary, dict) else None
    if not isinstance(header, dict):
        return None
    competitions = header.get("competitions") or []
    if not competitions or not isinstance(competitions[0], dict):
        return None
    status = (competitions[0].get("status") or {}).get("type") or {}
    state = status.get("state") if isinstance(status, dict) else None
    return str(state) if state else None


def _header_scores(summary: dict[str, Any]) -> tuple[int | None, int | None]:
    header = summary.get("header") if isinstance(summary, dict) else None
    if not isinstance(header, dict):
        return None, None
    competitions = header.get("competitions") or []
    if not competitions or not isinstance(competitions[0], dict):
        return None, None
    home = away = None
    for competitor in competitions[0].get("competitors") or []:
        if not isinstance(competitor, dict):
            continue
        side = competitor.get("homeAway")
        score = _int(competitor.get("score"))
        if side == "home":
            home = score
        elif side == "away":
            away = score
    return home, away


@dataclass(frozen=True)
class GameState:
    """Parsed point-in-time state of one game (fail-closed: unknown -> None)."""

    event_id: str
    league: str
    status: str  # "pre" | "in" | "post" | "unknown"
    home_score: int | None = None
    away_score: int | None = None
    period: int | None = None
    base_state: str | None = None
    outs: int | None = None

    @property
    def lead(self) -> int | None:
        if self.home_score is None or self.away_score is None:
            return None
        return self.home_score - self.away_score


@dataclass(frozen=True)
class ChangeEvent:
    """One material change between two consecutive states."""

    event_id: str
    league: str
    kind: str
    detail: dict[str, Any] = field(default_factory=dict)


def parse_game_state(
    summary: dict[str, Any] | None,
    *,
    event_id: str,
    league: str,
    status: str | None = None,
) -> GameState:
    """Turn one ESPN summary into a :class:`GameState`.

    Scores/period are read from the LAST ``plays`` entry (the most recent
    recorded state -- the same anchor ``parse_base_out_state`` uses), falling
    back to the header competitors. ``status`` may be supplied by the caller
    (the scoreboard discovery already knows it); otherwise it is read from the
    summary header, defaulting to ``"unknown"`` fail-closed.
    """
    summary = summary or {}
    plays = summary.get("plays") or []
    last = plays[-1] if plays and isinstance(plays[-1], dict) else {}

    home_score = _int(last.get("homeScore"))
    away_score = _int(last.get("awayScore"))
    if home_score is None or away_score is None:
        header_home, header_away = _header_scores(summary)
        home_score = home_score if home_score is not None else header_home
        away_score = away_score if away_score is not None else header_away

    period = _period_number(last)
    state = status or _summary_status(summary) or "unknown"

    base_state = outs = None
    base_out = parse_base_out_state(summary)
    if base_out is not None:
        base_state, outs = base_out

    return GameState(
        event_id=str(event_id),
        league=league,
        status=state,
        home_score=home_score,
        away_score=away_score,
        period=period,
        base_state=base_state,
        outs=outs,
    )


def _lead_sign(lead: int | None) -> int | None:
    if lead is None:
        return None
    return (lead > 0) - (lead < 0)


def diff_states(prev: GameState | None, curr: GameState) -> list[ChangeEvent]:
    """Material change-events between two consecutive states (pure).

    First observation (``prev is None``): emit a single ``status_in`` iff the
    game is already live, so a freshly-watched in-progress game triggers an
    initial re-evaluation; a pre/post first sight emits nothing.
    """
    def _event(kind: str, detail: dict[str, Any]) -> ChangeEvent:
        return ChangeEvent(event_id=curr.event_id, league=curr.league, kind=kind, detail=detail)

    if prev is None:
        if curr.status == "in":
            return [_event(STATUS_IN, {"status": "in"})]
        return []

    events: list[ChangeEvent] = []

    if prev.status != "in" and curr.status == "in":
        events.append(_event(STATUS_IN, {"from": prev.status, "to": "in"}))
    if prev.status != "post" and curr.status == "post":
        events.append(_event(STATUS_POST, {"from": prev.status, "to": "post"}))

    if (
        curr.home_score is not None
        and curr.away_score is not None
        and (curr.home_score != prev.home_score or curr.away_score != prev.away_score)
    ):
        events.append(_event(SCORE, {
            "home_score": curr.home_score,
            "away_score": curr.away_score,
            "prev_home_score": prev.home_score,
            "prev_away_score": prev.away_score,
            "lead": curr.lead,
        }))

    prev_sign, curr_sign = _lead_sign(prev.lead), _lead_sign(curr.lead)
    if prev_sign is not None and curr_sign is not None and prev_sign != curr_sign:
        events.append(_event(LEAD_CHANGE, {
            "prev_lead": prev.lead,
            "lead": curr.lead,
        }))

    if curr.period is not None and curr.period != prev.period:
        events.append(_event(PERIOD, {"from": prev.period, "to": curr.period}))

    if (
        (curr.base_state is not None or curr.outs is not None)
        and (curr.base_state != prev.base_state or curr.outs != prev.outs)
    ):
        events.append(_event(BASE_OUT, {
            "base_state": curr.base_state,
            "outs": curr.outs,
            "prev_base_state": prev.base_state,
            "prev_outs": prev.outs,
        }))

    return events


def change_record(event: ChangeEvent, state: GameState) -> dict[str, Any]:
    """A ledgerable typed record for one change (mirrors live_odds' ejection
    observation shape so the existing typed-feed wiring accepts it verbatim)."""
    return {
        "event_type": "live_game_change",
        "source": "espn_live_poller",
        "kind": event.kind,
        "event_id": event.event_id,
        "league": event.league,
        "status": state.status,
        "home_score": state.home_score,
        "away_score": state.away_score,
        "period": state.period,
        "base_state": state.base_state,
        "outs": state.outs,
        "detail": dict(event.detail),
    }


@dataclass(frozen=True)
class PollResult:
    """Outcome of one poll cycle."""

    events: tuple[ChangeEvent, ...]
    next_interval: float
    live_event_ids: tuple[str, ...]


class LiveGamePoller:
    """Discovers live games and emits change-events, self-pacing by activity.

    Everything network-facing is injected so the whole object is testable
    offline: ``fetch_scoreboard(league, dates)`` and the summary ``book``.
    ``on_change(event, state)`` is the re-evaluation hook; ``record_event(rec)``
    is the ledger sink. Both default to no-ops and both are called best-effort
    (a raising hook is swallowed per-event so one bad callback cannot drop the
    rest of the cycle).
    """

    def __init__(
        self,
        leagues: tuple[str, ...] = ("mlb",),
        *,
        book: EspnSummaryBook | None = None,
        fetch_scoreboard: Callable[[str, str | None], dict[str, Any]] | None = None,
        on_change: Callable[[ChangeEvent, GameState], None] | None = None,
        record_event: Callable[[dict[str, Any]], None] | None = None,
        enabled: bool = False,
        fast_interval: float = 20.0,
        idle_interval: float = 60.0,
        max_idle_interval: float = 900.0,
    ) -> None:
        self.leagues = tuple(leagues)
        self._book = book
        self._fetch_scoreboard = fetch_scoreboard or default_fetch_scoreboard
        self._on_change = on_change
        self._record_event = record_event
        # Opt-in AND env-gated: both must be true, else the poller is inert.
        self.enabled = bool(enabled) and _env_enabled()
        self.fast_interval = float(fast_interval)
        self.idle_interval = float(idle_interval)
        self.max_idle_interval = float(max_idle_interval)
        self._states: dict[str, GameState] = {}
        self._watched: set[str] = set()
        self._idle_streak = 0

    def _summary_book(self, league: str) -> EspnSummaryBook:
        # One book per league; a fresh book per cycle so its per-event cache
        # never serves a stale summary across cycles.
        return EspnSummaryBook(league=league)

    def discover_live(self, league: str) -> list[str]:
        """game_ids of in-progress games for a league (fail-closed -> [])."""
        try:
            payload = self._fetch_scoreboard(league, None)
            games = parse_scoreboard(league, payload)
        except Exception:
            return []
        return [g.game_id for g in games if isinstance(g, Game) and g.status == "in"]

    def _idle_next_interval(self) -> float:
        interval = self.idle_interval * (2 ** self._idle_streak)
        return min(self.max_idle_interval, interval)

    def poll_once(self) -> PollResult:
        """One event-driven poll cycle across all configured leagues.

        Returns the change-events emitted this cycle, the recommended delay
        until the next cycle, and the currently-live event ids. When disabled
        it is fully inert (no network, no events).
        """
        if not self.enabled:
            return PollResult(events=(), next_interval=self._idle_next_interval(), live_event_ids=())

        # Discover live events and keep polling already-watched ones until they
        # reach "post" -- so the final-state transition is never missed.
        live_by_event: dict[str, str] = {}
        for league in self.leagues:
            for event_id in self.discover_live(league):
                live_by_event[str(event_id)] = league
        for event_id in self._watched:
            live_by_event.setdefault(event_id, self._states.get(event_id, GameState(event_id, self.leagues[0], "unknown")).league)

        emitted: list[ChangeEvent] = []
        any_live = False
        book_cache: dict[str, EspnSummaryBook] = {}

        for event_id, league in live_by_event.items():
            book = book_cache.get(league)
            if book is None:
                book = self._book if self._book is not None else self._summary_book(league)
                book_cache[league] = book
            try:
                summary = book.fetch_summary(league, event_id)
            except Exception:
                summary = None
            curr = parse_game_state(summary, event_id=event_id, league=league)

            for event in diff_states(self._states.get(event_id), curr):
                emitted.append(event)
                self._emit(event, curr)

            self._states[event_id] = curr
            if curr.status == "in":
                any_live = True
                self._watched.add(event_id)
            elif curr.status == "post":
                self._watched.discard(event_id)

        if any_live:
            self._idle_streak = 0
            next_interval = self.fast_interval
        else:
            next_interval = self._idle_next_interval()
            self._idle_streak += 1

        live_ids = tuple(eid for eid, s in self._states.items() if s.status == "in")
        return PollResult(events=tuple(emitted), next_interval=next_interval, live_event_ids=live_ids)

    def _emit(self, event: ChangeEvent, state: GameState) -> None:
        if self._record_event is not None:
            try:
                self._record_event(change_record(event, state))
            except Exception:
                pass
        if self._on_change is not None:
            try:
                self._on_change(event, state)
            except Exception:
                pass
