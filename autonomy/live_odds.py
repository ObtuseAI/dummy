"""Live sportsbook odds from the ESPN game-summary endpoint.

The scoreboard's embedded moneyline is a pre-game snapshot; ESPN's per-game
``summary`` endpoint carries a ``pickcenter`` block whose books update through
the game. De-vigging those live moneylines gives a live P(home win) — the
sharp-book leg of the triangulated mispricing engine for in-progress games,
keyless and already-whitelisted (same source as the scoreboard).

Fail-closed: no summary, no pickcenter, or no two-way moneyline -> None, and the
engine falls back to the pre-game book or abstains.

WS-11 build-time PROBE (2026-07-12, network confirmed reachable): the plan
was to find a live ("in") MLB game and inspect its summary's ``situation``
block. At probe time (run in the small hours UTC) every game on the MLB
scoreboard -- today's date and the prior several days -- had already gone
"post"; no "in" game was available. The base-out keys were instead confirmed
from a COMPLETED game's ``plays`` array, which carries the identical
per-play schema a live game would (each play IS the game's state as of that
moment; the LAST play in the list is simply the final one once status
becomes "post" instead of an in-progress one):

  Event 401816130 (MIL @ PIT, 2026-07-12), fetched via
  ``https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event=401816130``.

  DISCREPANCY vs the brief's phrasing ("summary `plays`/`situation` carries
  onFirst/onSecond/onThird, outs"): there is NO top-level (or
  ``header.competitions[0]``) ``situation`` block anywhere in this payload --
  0 occurrences of the substring "situation" in the raw JSON. The base-out
  state lives ONLY on individual entries of the top-level ``plays`` array.

  Observed per-play keys (exact, verbatim): ``onFirst``, ``onSecond``,
  ``onThird`` -- each present as an object (``{"athlete": {"id": "..."}}``)
  ONLY when that base is occupied; the key is ABSENT from the play dict
  entirely when the base is empty (not ``null``/``false``). ``outs`` is a
  plain int, 0-2 during play and 3 at a half-inning-ending out. Confirmed
  both the empty-bases case (key absent on ~305 sampled plays) and the
  bases-loaded case (all three keys present, e.g. play id
  "4018161300705990057": "Lowe singled to center, Mangum to second, Davis to
  third" -- outs=0, onFirst/onSecond/onThird all populated).

  A trimmed, real fixture (5 representative plays spanning empty/1st/loaded/
  2-out/final states) is committed at
  ``tests/fixtures/mlb_summary_401816130_baseout.json``.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from autonomy.signals.sportsbook import devig_two_way
from autonomy.sports.baseball import base_state_key
from autonomy.sports.espn import LEAGUE_TO_ESPN, _american


_EJECTION_PATTERN = re.compile(r"\b(?:eject(?:ed|ion|ions)?|disqualified)\b", re.IGNORECASE)


def devig_summary_home_probability(summary: dict[str, Any] | None) -> float | None:
    """Average de-vigged P(home win) across the summary's pickcenter books."""
    pickcenter = (summary or {}).get("pickcenter") or []
    probabilities: list[float] = []
    for book in pickcenter:
        home_ml = (book.get("homeTeamOdds") or {}).get("moneyLine")
        away_ml = (book.get("awayTeamOdds") or {}).get("moneyLine")
        devigged = devig_two_way(_american(home_ml), _american(away_ml))
        if devigged is not None:
            probabilities.append(devigged)
    if not probabilities:
        return None
    return sum(probabilities) / len(probabilities)


def _base_state_from_play(play: dict[str, Any]) -> tuple[str, int] | None:
    """(base_state_key, outs) from one ESPN play dict, or None if unparseable.

    onFirst/onSecond/onThird are present as ``{"athlete": {...}}`` ONLY when
    that base is occupied -- KEY ABSENT (not null/false) when empty -- per
    the WS-11 probe recorded in this module's docstring.
    """
    outs = play.get("outs")
    if not isinstance(outs, int) or isinstance(outs, bool):
        return None
    return base_state_key("onFirst" in play, "onSecond" in play, "onThird" in play), outs


def parse_base_out_state(summary: dict[str, Any] | None) -> tuple[str, int] | None:
    """(base_state, outs) for the CURRENT game state from an ESPN summary.

    Reads the LAST entry of ``plays`` -- the most recent recorded state.
    Fail-closed: no summary, no plays, or an unparseable last play -> None,
    which leaves `BaseballRunModel.live_total_probability`'s base-out
    adjustment a no-op (byte-identical to the pre-WS11 output).
    """
    plays = (summary or {}).get("plays") or []
    if not plays:
        return None
    return _base_state_from_play(plays[-1])


def parse_ejection_events(summary: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    """Raw ejection observations from ESPN's point-in-time play feed.

    Only ``summary.plays`` is inspected. Postgame article prose is deliberately
    excluded because it may be published after the fact and cannot establish
    that an ejection was knowable during the game. Missing/malformed plays
    simply produce an empty tuple (fail closed).

    Public read-only probe (NBA event 401585677, 2024-03-27): play 50 carries
    ``type.text == \"Ejection\"``, ``text == \"Draymond Green ejected\"``, a
    source wall-clock timestamp, team/participant IDs, period, clock, and the
    score at observation time. MLB event 401814825 demonstrated the opposite
    case: its manager ejection appeared in article prose but not in ``plays``,
    so this parser correctly abstains rather than backfill postgame knowledge.
    """
    if not isinstance(summary, dict):
        return ()
    observations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for play in (summary or {}).get("plays", []) or []:
        if not isinstance(play, dict):
            continue
        play_type = play.get("type") or {}
        if not isinstance(play_type, dict):
            play_type = {}
        text = str(play.get("text") or play.get("shortDescription") or "").strip()
        type_text = str(play_type.get("text") or "").strip()
        if not _EJECTION_PATTERN.search(f"{type_text} {text}"):
            continue

        play_id = str(play.get("id") or play.get("sequenceNumber") or "").strip()
        dedupe_key = play_id or f"{type_text}|{text}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        period = play.get("period") or {}
        clock = play.get("clock") or {}
        team = play.get("team") or {}
        if not isinstance(period, dict):
            period = {}
        if not isinstance(clock, dict):
            clock = {}
        if not isinstance(team, dict):
            team = {}
        participant_ids: list[str] = []
        participants = play.get("participants") or []
        if isinstance(participants, (list, tuple)):
            for participant in participants:
                if not isinstance(participant, dict):
                    continue
                athlete = participant.get("athlete") or {}
                if isinstance(athlete, dict) and athlete.get("id") is not None:
                    participant_ids.append(str(athlete["id"]))
        observations.append({
            "event_type": "ejection",
            "source": "espn_summary_plays",
            "play_id": play_id or None,
            "sequence_number": str(play.get("sequenceNumber") or "") or None,
            "source_event_time": play.get("wallclock"),
            "text": text or type_text or "Ejection",
            "team_id": str(team.get("id")) if team.get("id") is not None else None,
            "participant_ids": tuple(participant_ids),
            "period": period.get("number"),
            "clock": clock.get("displayValue"),
            "home_score": play.get("homeScore"),
            "away_score": play.get("awayScore"),
        })
    return tuple(observations)


def default_fetch_summary(league: str, event_id: str) -> dict[str, Any]:
    """Fetch the ESPN game summary for one event (keyless, read-only)."""
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


class EspnSummaryBook:
    """Live de-vigged sportsbook consensus from the ESPN summary endpoint."""

    def __init__(
        self,
        league: str = "mlb",
        fetch_summary: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.league = league
        self.fetch_summary = fetch_summary or default_fetch_summary
        self._cache: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._cache.clear()

    def _summary(self, event_id: str) -> dict[str, Any]:
        key = str(event_id)
        if key not in self._cache:
            try:
                self._cache[key] = self.fetch_summary(self.league, key) or {}
            except Exception:
                self._cache[key] = {}
        return self._cache[key]

    def home_win_probability(self, event_id: str | None) -> float | None:
        """De-vigged live P(home win) for the event, or None (fail-closed)."""
        if not event_id:
            return None
        return devig_summary_home_probability(self._summary(event_id))

    def base_out_state(self, event_id: str | None) -> tuple[str, int] | None:
        """(base_state, outs) for the event's current game state, or None.

        WS-11: reuses the same cached summary fetch as
        ``home_win_probability`` -- one fetch per event per cycle serves
        both the sharp-book live de-vig and the base-out RE adjustment.
        """
        if not event_id:
            return None
        return parse_base_out_state(self._summary(event_id))

    def ejection_events(self, event_id: str | None) -> tuple[dict[str, Any], ...]:
        """Raw live ejection observations for an event, or an empty tuple."""
        if not event_id:
            return ()
        return parse_ejection_events(self._summary(event_id))
