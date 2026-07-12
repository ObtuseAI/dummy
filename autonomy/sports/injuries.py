"""MLB injury / availability awareness from the keyless ESPN injuries feed.

A banged-up roster is genuinely harder to forecast: a game-time-decision bat or
a late scratch adds availability uncertainty the season EWMA hasn't absorbed
yet. This reads ESPN's league injuries endpoint and turns each team's
*currently questionable* count into a bounded burden the MLB model uses to
WIDEN its uncertainty -- deliberately not to shift the mean, since which player
and how much they matter is unknown. Long-term IL players are excluded: they
are already reflected in the team's recent results.

Keyless, read-only, fail-closed: no feed -> zero burden -> byte-identical
forecasts.
"""
from __future__ import annotations

from typing import Any, Callable

# Statuses that represent same-day availability doubt (not long-term IL, which
# the season EWMA already reflects).
_QUESTIONABLE_STATUSES = {"day-to-day", "out", "questionable", "game-time-decision"}
# Significant-injury count that saturates the burden at 1.0.
_BURDEN_SATURATION = 6.0


def _norm(text: str | None) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def parse_team_injuries(payload: dict[str, Any] | None) -> dict[str, int]:
    """Normalized-team-name -> count of currently-questionable players.

    Long-term IL statuses (e.g. "60-Day-IL") are ignored on purpose.
    """
    counts: dict[str, int] = {}
    for team in (payload or {}).get("injuries", []) or []:
        name = _norm(team.get("displayName"))
        if not name:
            continue
        questionable = 0
        for injury in team.get("injuries", []) or []:
            status = str(injury.get("status") or "").strip().lower()
            if status in _QUESTIONABLE_STATUSES:
                questionable += 1
        counts[name] = questionable
    return counts


def injury_burden(questionable_count: int) -> float:
    """Bounded 0..1 availability burden from a questionable-player count."""
    return min(1.0, max(0, int(questionable_count)) / _BURDEN_SATURATION)


def default_fetch_injuries() -> dict[str, Any]:
    """Fetch the ESPN MLB league injuries payload (keyless, read-only)."""
    import httpx

    response = httpx.get(
        "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


class InjuryBook:
    """Cached per-team availability burden from the ESPN injuries feed."""

    def __init__(self, fetch_fn: Callable[[], dict[str, Any]] | None = None) -> None:
        self.fetch_fn = fetch_fn or default_fetch_injuries
        self._counts: dict[str, int] | None = None

    def refresh(self) -> None:
        """Reload the feed once (best-effort); an error leaves an empty book."""
        try:
            self._counts = parse_team_injuries(self.fetch_fn())
        except Exception:
            self._counts = {}

    def _ensure(self) -> dict[str, int]:
        # No implicit fetch: refresh() (called once per cycle) is the only
        # network trigger, so an un-refreshed book is simply empty (burden 0).
        return self._counts or {}

    def questionable_for(self, team_name: str | None) -> int:
        return self._ensure().get(_norm(team_name), 0)

    def burden_for(self, team_name: str | None) -> float:
        """Availability burden (0..1) for a team; 0 when unknown (fail-closed)."""
        return injury_burden(self.questionable_for(team_name))
