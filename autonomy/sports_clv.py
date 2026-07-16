"""Sports pre-game close capture for CLV (Wave-2 workstream D1).

CLV grading (``autonomy/clv.py``) scores an entry price against the sharp
book's CLOSING line. For a crypto contract the close is unambiguous: the
market settles at its ``close_time`` and the monitor sweeps the book right up
to it, so the tape row nearest ``close_time`` IS the close. Sports are
different -- a Kalshi sports contract's ``close_time`` is the game's
END/settlement, hours after the line that actually matters. The
industry-standard sports closing line is the last price before FIRST PITCH
(scheduled game start): once the game is underway the "book" is a live in-play
number, a different animal entirely, and grading a pre-game entry against it
would be meaningless. That mismatch is exactly why ``clv_report.json`` carried
zero sports scopes.

This module re-anchors the sports close on game start (the ESPN scoreboard's
scheduled start, already fetched by the specialists) so the existing CLV tape
+ grader consume sports exactly like crypto -- with ZERO changes to the
promotion ladder:

  * While a sports game is PRE-GAME (``now < start``) the tracker records the
    latest close-candidate snapshot per sports market (its de-vigged book
    price + Kalshi mid), keyed by ticker.
  * The moment first pitch passes (``now >= start``) the candidate is FROZEN
    into a single book-tape row -- the last pre-game snapshot, carrying its
    real near-pitch timestamp and a ``close_time`` set to game start -- and no
    further rows are ever written for that ticker. Freezing the stored
    candidate (rather than leaning on the raw per-pass tape) is what makes a
    stable line gradeable: a moneyline that never moved would be deduped down
    to its earliest, hours-stale row on the raw tape and fall outside
    ``select_close``'s window, but the tracker always holds the LATEST
    pre-game ts, so the frozen close lands inside the same 30-minute window
    everything else uses.
  * Fail-closed: an unknown/unparseable start time yields NO candidate and NO
    row, so a sports market whose game we cannot locate never grades a wrong
    close rather than inventing one -- the same discipline ``select_close``
    already applies to a thin or stale tape.

Pure and I/O-free: the mispricing sweep drives ``SportsCloseTracker`` per
pass (carried across passes like the ``OpportunistEngine``) and the runner
persists the frozen rows through the same ``persist_book_tape`` path crypto
uses. The game-start resolver lives on the sports specialists
(``game_start_time``); this module only owns the close-selection semantics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from autonomy.ontology import Vertical

# Team-sports specialist labels that carry a pre-game sharp book worth grading
# CLV against. UFC/F1 are retired; crypto uses the crypto close path in
# autonomy/clv.py. Kept here (not imported from taxonomy) only for a cheap
# membership check by callers that already know a market's routed label.
SPORTS_SPECIALISTS = frozenset(
    {"mlb", "nba", "nfl", "ncaaf", "ncaamb", "nhl", "wnba"}
)


def _parse_ts(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def is_sports_market(market: Any) -> bool:
    """True when this market is a SPORTS-vertical contract (fail-closed to False)."""
    return getattr(market, "vertical", None) is Vertical.SPORTS


class SportsCloseTracker:
    """Per-ticker pre-game close capture, finalized at scheduled game start.

    Carried across monitor passes (like the ``OpportunistEngine`` and the
    book-tape last-row index). Each pass, ``observe`` records the latest
    pre-game snapshot for a sports market whose game start is known;
    ``finalize_due`` freezes any candidate whose start has passed into a
    single close row and returns the newly frozen rows for the runner to
    append to the book tape. A frozen ticker is never re-opened, so a live
    in-play observation can never overwrite the pre-game close.
    """

    def __init__(self) -> None:
        self._candidates: dict[str, dict[str, Any]] = {}
        self._finalized: set[str] = set()

    def observe(
        self,
        *,
        ticker: str | None,
        start_time_iso: str | None,
        book_prob: float | None,
        kalshi_mid: float | None,
        now_iso: str,
    ) -> None:
        """Record the latest pre-game close-candidate for one sports ticker.

        Fail-closed and a no-op when: the ticker is empty, the start time or
        ``now`` is unparseable (cannot anchor the phase), the ticker is
        already finalized, or first pitch has already passed (``now >=
        start``) -- in that last case ``finalize_due`` will freeze whatever
        pre-game candidate already exists rather than record an in-play price.
        """
        if not ticker:
            return
        start = _parse_ts(start_time_iso)
        now = _parse_ts(now_iso)
        if start is None or now is None:
            return
        if ticker in self._finalized or now >= start:
            return
        self._candidates[ticker] = {
            "ticker": ticker,
            "ts": now_iso,
            "book_prob": None if book_prob is None else round(float(book_prob), 4),
            "kalshi_mid": None if kalshi_mid is None else round(float(kalshi_mid), 4),
            "close_time": start_time_iso,
        }

    def finalize_due(self, now_iso: str) -> list[dict[str, Any]]:
        """Freeze + return every candidate whose scheduled start has passed.

        Purely time-driven over the stored candidates, so a game whose market
        drops out of the scan universe at first pitch still finalizes on the
        next pass. Each frozen row is emitted exactly once (the candidate is
        removed and the ticker marked finalized).
        """
        now = _parse_ts(now_iso)
        if now is None:
            return []
        frozen: list[dict[str, Any]] = []
        for ticker, candidate in list(self._candidates.items()):
            start = _parse_ts(candidate.get("close_time"))
            if start is not None and now >= start:
                frozen.append(dict(candidate))
                self._finalized.add(ticker)
                del self._candidates[ticker]
        return frozen

    def pending_count(self) -> int:
        """Sports markets currently holding an un-frozen pre-game candidate."""
        return len(self._candidates)

    # -- optional persistence across process restarts -----------------------
    def to_state(self) -> dict[str, Any]:
        """JSON-able snapshot so a restarted monitor keeps in-flight candidates."""
        return {
            "candidates": {k: dict(v) for k, v in self._candidates.items()},
            "finalized": sorted(self._finalized),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any] | None) -> "SportsCloseTracker":
        """Rebuild a tracker from ``to_state`` output; fail-open to empty."""
        tracker = cls()
        if isinstance(state, dict):
            candidates = state.get("candidates")
            if isinstance(candidates, dict):
                tracker._candidates = {
                    str(k): dict(v)
                    for k, v in candidates.items()
                    if isinstance(v, dict)
                }
            finalized = state.get("finalized")
            if isinstance(finalized, (list, tuple)):
                tracker._finalized = {str(x) for x in finalized}
        return tracker
