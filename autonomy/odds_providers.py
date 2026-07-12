"""Sportsbook odds providers behind the mispricing engine's ``book_fn``.

The mispricing engine (``autonomy.mispricing``) triangulates our model against a
de-vigged sportsbook consensus. That consensus can come from more than one
source; each is a provider exposing a de-vigged P(home win):

  1. ESPN's embedded moneyline (``autonomy.signals.sportsbook``) — keyless,
     already-whitelisted, the default; covers pre-game and (via the summary
     endpoint) live.
  2. A LICENSED odds aggregator (this module) — a key-based, ToS-compliant API
     such as The Odds API, giving a sharper multi-book consensus.

GOVERNANCE + TERMS (important): the licensed provider is a DISABLED slot. It
returns nothing unless BOTH an API key is present AND it is explicitly enabled,
and enabling it for real is an operator decision gated on the repo's
source-universe review plus acceptance of the provider's terms of service. This
module never scrapes sites that forbid automated access and never attempts to
evade anti-bot controls; it speaks only to an API the operator has licensed.
Fail-closed everywhere: not-available, a fetch error, or an unmatched game all
yield None, and the engine simply falls back to the ESPN default.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from autonomy.signals.sportsbook import devig_two_way
from autonomy.sports.espn import _american

# Environment switches for the licensed provider. Both must be set for it to do
# anything; the default (unset) leaves it inert.
ODDS_API_KEY_ENV = "DUMMY_ODDS_API_KEY"
ODDS_API_ENABLED_ENV = "DUMMY_ODDS_API_ENABLED"  # "1" to arm (after governance)


def _norm(text: str | None) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def _match_event(events: list[dict[str, Any]], home_team: str, away_team: str) -> dict[str, Any] | None:
    """Find the event whose home/away names contain the given team tokens.

    Matching is normalized substring both ways (a Kalshi "Astros"/"HOU" token vs
    the API's "Houston Astros"), so either a nickname or a full name resolves.
    """
    home_key, away_key = _norm(home_team), _norm(away_team)
    if not home_key or not away_key:
        return None
    for event in events:
        api_home = _norm(event.get("home_team"))
        api_away = _norm(event.get("away_team"))
        home_ok = home_key in api_home or api_home in home_key
        away_ok = away_key in api_away or api_away in away_key
        if api_home and api_away and home_ok and away_ok:
            return event
    return None


def devigged_home_probability(
    events: list[dict[str, Any]], home_team: str, away_team: str
) -> float | None:
    """Average de-vigged P(home win) across books for the matching event.

    ``events`` is a licensed odds payload (The Odds API v4 shape,
    ``oddsFormat=american``): a list of games, each with ``home_team``,
    ``away_team``, and ``bookmakers[].markets[key=="h2h"].outcomes[{name,price}]``.
    Returns None when the game is not found or no book prices a two-way h2h.
    """
    event = _match_event(events or [], home_team, away_team)
    if event is None:
        return None
    api_home = event.get("home_team")
    api_away = event.get("away_team")
    probabilities: list[float] = []
    for bookmaker in event.get("bookmakers", []) or []:
        market = next(
            (m for m in bookmaker.get("markets", []) or [] if m.get("key") == "h2h"),
            None,
        )
        if not market:
            continue
        home_odds = away_odds = None
        for outcome in market.get("outcomes", []) or []:
            name = _norm(outcome.get("name"))
            if name and (name in _norm(api_home) or _norm(api_home) in name):
                home_odds = _american(outcome.get("price"))
            elif name and (name in _norm(api_away) or _norm(api_away) in name):
                away_odds = _american(outcome.get("price"))
        devigged = devig_two_way(home_odds, away_odds)
        if devigged is not None:
            probabilities.append(devigged)
    if not probabilities:
        return None
    return sum(probabilities) / len(probabilities)


def default_odds_api_fetch(sport_key: str, api_key: str) -> list[dict[str, Any]]:
    """Fetch h2h odds from The Odds API v4 (only called when armed)."""
    import httpx

    response = httpx.get(
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


class LicensedOddsProvider:
    """Governance-gated licensed-odds provider. Inert unless armed."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        enabled: bool | None = None,
        sport_key: str = "baseball_mlb",
        fetch_fn: Callable[[str, str], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(ODDS_API_KEY_ENV)
        if enabled is None:
            enabled = os.environ.get(ODDS_API_ENABLED_ENV) == "1"
        self.enabled = bool(enabled)
        self.sport_key = sport_key
        self.fetch_fn = fetch_fn or default_odds_api_fetch
        self._cache: list[dict[str, Any]] | None = None

    @property
    def available(self) -> bool:
        """True only when armed: enabled AND a key present (governance-gated)."""
        return self.enabled and bool(self.api_key)

    def clear(self) -> None:
        self._cache = None

    def _events(self) -> list[dict[str, Any]]:
        if self._cache is None:
            try:
                self._cache = list(self.fetch_fn(self.sport_key, self.api_key) or [])
            except Exception:
                self._cache = []
        return self._cache

    def home_win_probability(self, home_team: str, away_team: str) -> float | None:
        """De-vigged licensed-book P(home win), or None if inert/unmatched."""
        if not self.available:
            return None
        return devigged_home_probability(self._events(), home_team, away_team)


def make_book_fn(
    provider: LicensedOddsProvider,
    resolve_teams: Callable[[Any], tuple[str, str, bool] | None],
) -> Callable[[Any], float | None]:
    """Adapt a provider to the engine's ``book_fn(market) -> P(YES)``.

    ``resolve_teams(market)`` returns ``(home_team, away_team, yes_is_home)`` for
    a winner market, or None to abstain. The provider gives P(home win); the
    result is flipped to P(YES) when the market's YES side is the away team.
    """
    def book_fn(market: Any) -> float | None:
        resolved = resolve_teams(market)
        if resolved is None:
            return None
        home_team, away_team, yes_is_home = resolved
        home_prob = provider.home_win_probability(home_team, away_team)
        if home_prob is None:
            return None
        return home_prob if yes_is_home else 1.0 - home_prob

    return book_fn
