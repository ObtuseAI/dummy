"""Live sportsbook odds from the ESPN game-summary endpoint.

The scoreboard's embedded moneyline is a pre-game snapshot; ESPN's per-game
``summary`` endpoint carries a ``pickcenter`` block whose books update through
the game. De-vigging its two-way moneyline, point-spread, and total markets
gives the sharp-book leg of the triangulated mispricing engine for in-progress
games, keyless and already-whitelisted (same source as the scoreboard).

Fail-closed: no summary, no pickcenter, or no complete two-way prices -> None.
Exact line matches use the observed de-vigged price directly. Because ESPN's
public feed exposes only one current main spread/total, unmatched alternate
strikes use an explicit league-width normal curve anchored to that de-vigged
main price; the projection is challenger evidence, never execution authority.

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

import math
import re
from statistics import NormalDist
from typing import Any, Callable

from autonomy.signals.sportsbook import devig_two_way
from autonomy.sports.baseball import base_state_key
from autonomy.sports.espn import LEAGUE_TO_ESPN, _american


_EJECTION_PATTERN = re.compile(r"\b(?:eject(?:ed|ion|ions)?|disqualified)\b", re.IGNORECASE)

# Main-line-to-alternate translation widths. ESPN exposes only the current
# main spread/total in its public summary/core odds resources (verified again
# 2026-07-14). Alternate coverage therefore de-vigs that observed main line,
# locates a league-specific normal distribution at the market-implied
# quantile, and evaluates the requested strike on the same curve. These are
# challenger calibration targets; exact ESPN lines always take precedence.
ALT_LINE_SIGMAS: dict[str, dict[str, float]] = {
    "mlb": {"spread": 4.0, "total": 3.1},
    "nba": {"spread": 12.0, "total": 18.0},
    "nfl": {"spread": 13.5, "total": 14.0},
    "ncaaf": {"spread": 16.0, "total": 17.0},
    "nhl": {"spread": 2.2, "total": 2.4},
    "ncaamb": {"spread": 12.5, "total": 15.0},
}
_STANDARD_NORMAL = NormalDist()


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


def _number(value: Any) -> float | None:
    """Finite numeric value, accepting ESPN's ``o8.5``/``u8.5`` strings."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().lower()
    if text.startswith(("o", "u")):
        text = text[1:]
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _same_line(left: float | None, right: float | None) -> bool:
    return left is not None and right is not None and abs(left - right) <= 1e-6


def _project_probability(main_probability: float, main_line: float, target: float, sigma: float) -> float:
    probability = min(0.999, max(0.001, float(main_probability)))
    implied_mean = float(main_line) + float(sigma) * _STANDARD_NORMAL.inv_cdf(probability)
    return min(0.999, max(0.001, _STANDARD_NORMAL.cdf((implied_mean - float(target)) / float(sigma))))


def project_summary_total_probability(
    summary: dict[str, Any] | None, threshold: float, *, sigma: float,
) -> float | None:
    """Translate complete de-vigged ESPN main totals to an alternate strike."""
    wanted = _number(threshold)
    if wanted is None or sigma <= 0.0:
        return None
    probabilities: list[float] = []
    for book in (summary or {}).get("pickcenter", []) or []:
        if not isinstance(book, dict):
            continue
        line = _number(book.get("overUnder"))
        devigged = devig_two_way(_american(book.get("overOdds")), _american(book.get("underOdds")))
        if line is not None and devigged is not None:
            probabilities.append(_project_probability(devigged, line, wanted, sigma))
    return sum(probabilities) / len(probabilities) if probabilities else None


def project_summary_spread_probability(
    summary: dict[str, Any] | None,
    *,
    subject_is_home: bool,
    threshold: float,
    sigma: float,
) -> float | None:
    """Translate complete de-vigged ESPN main spreads to an alternate rung."""
    wanted = _number(threshold)
    if wanted is None or sigma <= 0.0:
        return None
    subject_key = "home" if subject_is_home else "away"
    opponent_key = "away" if subject_is_home else "home"
    probabilities: list[float] = []
    for book in (summary or {}).get("pickcenter", []) or []:
        spread = book.get("pointSpread") if isinstance(book, dict) else None
        if not isinstance(spread, dict):
            continue
        subject = (spread.get(subject_key) or {}).get("close") or {}
        opponent = (spread.get(opponent_key) or {}).get("close") or {}
        subject_line = _number(subject.get("line"))
        opponent_line = _number(opponent.get("line"))
        if subject_line is None or opponent_line is None or abs(subject_line + opponent_line) > 1e-6:
            continue
        devigged = devig_two_way(_american(subject.get("odds")), _american(opponent.get("odds")))
        if devigged is None:
            continue
        # ESPN handicap -x corresponds to Kalshi "wins by > x".
        probabilities.append(_project_probability(devigged, -subject_line, wanted, sigma))
    return sum(probabilities) / len(probabilities) if probabilities else None


def devig_summary_total_probability(
    summary: dict[str, Any] | None, threshold: float,
) -> float | None:
    """Average de-vigged P(final total > ``threshold``) at an exact line.

    ESPN exposes one current main total per book. Kalshi exposes an alternate
    ladder, so line equality is mandatory: odds at 8.5 say nothing directly
    about a 9.5 contract without an independently calibrated distribution.
    """
    wanted = _number(threshold)
    if wanted is None:
        return None
    probabilities: list[float] = []
    for book in (summary or {}).get("pickcenter", []) or []:
        if not isinstance(book, dict):
            continue
        line = _number(book.get("overUnder"))
        over_odds = _american(book.get("overOdds"))
        under_odds = _american(book.get("underOdds"))
        if not _same_line(line, wanted):
            continue
        devigged = devig_two_way(over_odds, under_odds)
        if devigged is not None:
            probabilities.append(devigged)
    return (sum(probabilities) / len(probabilities)) if probabilities else None


def devig_summary_spread_probability(
    summary: dict[str, Any] | None,
    *,
    subject_is_home: bool,
    threshold: float,
) -> float | None:
    """Average de-vigged P(subject wins by more than ``threshold``).

    Kalshi's contract threshold is a winning-margin expression. ESPN's
    ``pointSpread`` line is the handicap applied to that side, so a Kalshi
    ``wins by > 1.5`` contract matches an ESPN side at ``-1.5``. Both sides'
    lines and prices must be present and complementary; malformed or stale
    one-sided rows abstain.
    """
    wanted = _number(threshold)
    if wanted is None:
        return None
    probabilities: list[float] = []
    subject_key = "home" if subject_is_home else "away"
    opponent_key = "away" if subject_is_home else "home"
    for book in (summary or {}).get("pickcenter", []) or []:
        if not isinstance(book, dict):
            continue
        spread = book.get("pointSpread") or {}
        if not isinstance(spread, dict):
            continue
        subject = (spread.get(subject_key) or {}).get("close") or {}
        opponent = (spread.get(opponent_key) or {}).get("close") or {}
        if not isinstance(subject, dict) or not isinstance(opponent, dict):
            continue
        subject_line = _number(subject.get("line"))
        opponent_line = _number(opponent.get("line"))
        if not _same_line(subject_line, -wanted):
            continue
        if subject_line is None or opponent_line is None or abs(subject_line + opponent_line) > 1e-6:
            continue
        devigged = devig_two_way(
            _american(subject.get("odds")), _american(opponent.get("odds")),
        )
        if devigged is not None:
            probabilities.append(devigged)
    return (sum(probabilities) / len(probabilities)) if probabilities else None


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

    def total_over_probability(
        self, event_id: str | None, threshold: float,
    ) -> float | None:
        """De-vigged live P(total > threshold), exact line then alt projection."""
        if not event_id:
            return None
        summary = self._summary(event_id)
        exact = devig_summary_total_probability(summary, threshold)
        if exact is not None:
            return exact
        sigma = ALT_LINE_SIGMAS.get(self.league, {}).get("total")
        return project_summary_total_probability(summary, threshold, sigma=sigma) if sigma else None

    def spread_cover_probability(
        self,
        event_id: str | None,
        *,
        subject_is_home: bool,
        threshold: float,
    ) -> float | None:
        """De-vigged live P(cover), exact line then main-implied alt curve."""
        if not event_id:
            return None
        summary = self._summary(event_id)
        exact = devig_summary_spread_probability(
            summary,
            subject_is_home=subject_is_home,
            threshold=threshold,
        )
        if exact is not None:
            return exact
        sigma = ALT_LINE_SIGMAS.get(self.league, {}).get("spread")
        return project_summary_spread_probability(
            summary, subject_is_home=subject_is_home,
            threshold=threshold, sigma=sigma,
        ) if sigma else None

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
