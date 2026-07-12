"""Live sportsbook odds from the ESPN game-summary endpoint.

The scoreboard's embedded moneyline is a pre-game snapshot; ESPN's per-game
``summary`` endpoint carries a ``pickcenter`` block whose books update through
the game. De-vigging those live moneylines gives a live P(home win) — the
sharp-book leg of the triangulated mispricing engine for in-progress games,
keyless and already-whitelisted (same source as the scoreboard).

Fail-closed: no summary, no pickcenter, or no two-way moneyline -> None, and the
engine falls back to the pre-game book or abstains.
"""
from __future__ import annotations

from typing import Any, Callable

from autonomy.signals.sportsbook import devig_two_way
from autonomy.sports.espn import LEAGUE_TO_ESPN, _american


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

    def home_win_probability(self, event_id: str | None) -> float | None:
        """De-vigged live P(home win) for the event, or None (fail-closed)."""
        if not event_id:
            return None
        key = str(event_id)
        if key not in self._cache:
            try:
                self._cache[key] = self.fetch_summary(self.league, key) or {}
            except Exception:
                self._cache[key] = {}
        return devig_summary_home_probability(self._cache[key])
