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


def _half_point(line: float | None) -> bool:
    """True for X.5 lines. Book quotes at integer lines can PUSH; a de-vig of
    the two sides then prices P(cover | no push), which is not the Kalshi
    binary P(margin/total beyond X). Only half-point quotes translate exactly,
    so everything else is refused rather than approximated."""
    if line is None:
        return False
    doubled = line * 2
    return abs(doubled - round(doubled)) < 1e-9 and round(doubled) % 2 != 0


def _points_equal(a: Any, b: float) -> bool:
    try:
        return abs(float(a) - b) < 1e-9
    except (TypeError, ValueError):
        return False


def devigged_total_probability(
    events: list[dict[str, Any]], team_a: str, team_b: str, line: float
) -> tuple[float, int] | None:
    """(avg de-vigged P(over ``line``), book count) across books quoting EXACTLY
    that half-point line for the matching event; None when no book does.

    Order-agnostic on the teams (a total does not care which side is home).
    Books quoting a different line are skipped -- no derivative adjustment,
    no false precision.
    """
    if not _half_point(line):
        return None
    event = _match_event(events or [], team_a, team_b) or _match_event(
        events or [], team_b, team_a)
    if event is None:
        return None
    probabilities: list[float] = []
    for bookmaker in event.get("bookmakers", []) or []:
        market = next(
            (m for m in bookmaker.get("markets", []) or [] if m.get("key") == "totals"),
            None,
        )
        if not market:
            continue
        over_odds = under_odds = None
        for outcome in market.get("outcomes", []) or []:
            if not _points_equal(outcome.get("point"), line):
                continue
            name = _norm(outcome.get("name"))
            if name == "over":
                over_odds = _american(outcome.get("price"))
            elif name == "under":
                under_odds = _american(outcome.get("price"))
        devigged = devig_two_way(over_odds, under_odds)
        if devigged is not None:
            probabilities.append(devigged)
    if not probabilities:
        return None
    return sum(probabilities) / len(probabilities), len(probabilities)


def devigged_spread_probability(
    events: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    subject_team: str,
    line: float,
) -> tuple[float, int] | None:
    """(avg de-vigged P(``subject_team`` margin > ``line``), book count).

    The Kalshi spread leg is "subject wins by more than ``line``" (Wave-10
    convention; a negative line is the underdog side, margin > -1.5). The book
    quotes the same event as ``subject_team`` at point == -line and the
    opponent at +line; only exact half-point matches are used (see
    ``_half_point``). None when unmatched or no book quotes that line.
    """
    if not _half_point(line):
        return None
    event = _match_event(events or [], home_team, away_team)
    if event is None:
        return None
    subject_key = _norm(subject_team)
    if not subject_key:
        return None
    probabilities: list[float] = []
    for bookmaker in event.get("bookmakers", []) or []:
        market = next(
            (m for m in bookmaker.get("markets", []) or [] if m.get("key") == "spreads"),
            None,
        )
        if not market:
            continue
        subject_odds = other_odds = None
        for outcome in market.get("outcomes", []) or []:
            name = _norm(outcome.get("name"))
            if not name:
                continue
            is_subject = subject_key in name or name in subject_key
            if is_subject and _points_equal(outcome.get("point"), -line):
                subject_odds = _american(outcome.get("price"))
            elif not is_subject and _points_equal(outcome.get("point"), line):
                other_odds = _american(outcome.get("price"))
        devigged = devig_two_way(subject_odds, other_odds)
        if devigged is not None:
            probabilities.append(devigged)
    if not probabilities:
        return None
    return sum(probabilities) / len(probabilities), len(probabilities)


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
