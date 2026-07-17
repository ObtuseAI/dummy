"""Governed live client for The Odds API (Wave-9).

Wraps the raw v4 endpoints in the credit governor: header-aware fetches (reads
``x-requests-remaining`` so the budget tracks the plan, not just our count),
an in-season gate from the free ``/sports`` list (0 credits), and multi-market
consensus in ONE call (h2h+totals+spreads, us region = 3 credits, whole slate).

The whole module is a no-op unless the governance slot is armed
(``DUMMY_ODDS_API_KEY`` present AND ``DUMMY_ODDS_API_ENABLED=1``). Read-only:
it fetches published odds; it never trades, and its emissions are
challenger-only downstream.
"""
from __future__ import annotations

import os
from typing import Any

from autonomy.odds_api_budget import (
    ODDS_CALL_COST,
    SPORTS_LIST_TTL_SECONDS,
    OddsApiBudget,
)

ODDS_API_KEY_ENV = "DUMMY_ODDS_API_KEY"
ODDS_API_ENABLED_ENV = "DUMMY_ODDS_API_ENABLED"
BASE = "https://api.the-odds-api.com/v4"
CONSENSUS_MARKETS = "h2h,totals,spreads"


def is_armed(env: dict[str, str] | None = None) -> bool:
    e = env if env is not None else os.environ
    return bool(e.get(ODDS_API_KEY_ENV)) and e.get(ODDS_API_ENABLED_ENV) == "1"


def _http_get_json(url: str, params: dict[str, str]) -> tuple[Any, int | None]:
    import httpx

    response = httpx.get(url, params=params, timeout=20)
    response.raise_for_status()
    remaining = response.headers.get("x-requests-remaining")
    try:
        remaining_int = int(remaining) if remaining is not None else None
    except ValueError:
        remaining_int = None
    return response.json(), remaining_int


class OddsApiClient:
    """In-season-gated, budgeted access to licensed consensus odds."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        budget: OddsApiBudget | None = None,
        http_get: Any = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(ODDS_API_KEY_ENV)
        self.budget = budget or OddsApiBudget()
        self._http_get = http_get or _http_get_json

    @property
    def available(self) -> bool:
        return bool(self.api_key) and os.environ.get(ODDS_API_ENABLED_ENV) == "1"

    def active_sports(self) -> set[str]:
        """The feed's currently-active sport keys (free endpoint, 0 credits,
        cached 6h). Empty set on any failure (fail-closed)."""
        if not self.api_key:
            return set()

        def _fetch() -> tuple[Any, int | None]:
            return self._http_get(f"{BASE}/sports/", {"apiKey": self.api_key})

        # cost=0: the sports list is free, so it never touches the budget.
        payload, _ = self.budget.budgeted_fetch(
            "sports_list", _fetch, cost=0, ttl=SPORTS_LIST_TTL_SECONDS)
        if not isinstance(payload, list):
            return set()
        return {str(s.get("key")) for s in payload if s.get("active")}

    def consensus_odds(self, sport_key: str) -> tuple[list[dict[str, Any]], str]:
        """(events, source) of h2h+totals+spreads consensus for one sport.

        Skips the spend entirely when the sport is out of season, and defers
        to the governor for TTL caching and budget enforcement. ``source`` is
        the governor's disposition (cache/live/stale/budget_exhausted/
        out_of_season/inert)."""
        if not self.available:
            return [], "inert"
        if sport_key not in self.active_sports():
            return [], "out_of_season"

        def _fetch() -> tuple[Any, int | None]:
            return self._http_get(
                f"{BASE}/sports/{sport_key}/odds",
                {"apiKey": self.api_key, "regions": "us",
                 "markets": CONSENSUS_MARKETS, "oddsFormat": "american"},
            )

        payload, source = self.budget.budgeted_fetch(
            f"odds|{sport_key}|{CONSENSUS_MARKETS}|us", _fetch, cost=ODDS_CALL_COST)
        events = payload if isinstance(payload, list) else []
        return events, source
