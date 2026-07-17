"""Player-prop line plumbing (Wave-3, fixtures-first, governance-gated).

Parses player-prop markets (player over/under lines -- hits, total bases, etc.)
from a licensed odds payload shaped like The Odds API v4 event-odds response
(``events[].bookmakers[].markets[key="player_*"].outcomes[{name:"Over"/"Under",
description:<player>, price:<american>, point:<line>}]``), pairs each book's
Over/Under for the same (player, point), de-vigs it to a fair P(over), and
averages across books. Every ambiguity fails closed: a one-sided quote, a
point that doesn't match between Over and Under, or a malformed row is dropped,
never guessed.

GOVERNANCE SLOT (important). Player-prop data comes from the SAME licensed,
key-based aggregator as ``autonomy.odds_providers`` (The Odds API), so it reuses
that module's DISABLED-by-default slot and its two env switches:

  * ``DUMMY_ODDS_API_KEY``     -- the licensed API key (absent by default).
  * ``DUMMY_ODDS_API_ENABLED`` -- ``"1"`` to arm, only after the operator's
    source-universe review AND acceptance of the provider's terms of service.

:class:`LicensedPropProvider` is inert unless BOTH are set: no key or not
enabled -> ``available`` is False -> it never touches the network and returns
nothing. There is NO live fallback path that bypasses the key. The offline
:class:`FixturePropProvider` reads only committed sample fixtures and contacts
no provider, so the parser/de-vig are fully testable with the slot closed.

Nothing here scrapes a site that forbids automated access or evades anti-bot
controls; it speaks only to an API the operator has licensed. Emitted prop
probabilities are CHALLENGER evidence only and cannot reach execution: the live
provider stays disabled until the governance slot is opened, so the challenger
is dormant-but-ready (the same posture as the Wave-2 cross-venue econ source).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from autonomy.odds_providers import ODDS_API_ENABLED_ENV, ODDS_API_KEY_ENV, _match_event, _norm
from autonomy.signals.sportsbook import devig_two_way
from autonomy.sports.espn import _american

# Prop markets in the licensed feed. The provider's real MLB keys are
# ``batter_*`` / ``pitcher_*`` (verified live 2026-07-17, e.g. batter_home_runs,
# pitcher_strikeouts); older fixtures used a generic ``player_*`` namespace.
# Accept all three so the de-vig runs against real payloads AND the committed
# fixtures. h2h / spreads / totals are handled elsewhere (odds_providers).
_PROP_MARKET_PREFIXES = ("player_", "batter_", "pitcher_")


@dataclass(frozen=True)
class PropQuote:
    """A de-vigged fair P(over) for one (market, player, line), cross-book."""

    market_key: str
    player: str
    point: float
    prob_over: float
    n_books: int


@dataclass(frozen=True)
class EventProps:
    event_id: str | None
    home_team: str | None
    away_team: str | None
    quotes: tuple[PropQuote, ...] = field(default_factory=tuple)


def _point(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _book_prop_pairs(market: dict[str, Any]) -> dict[tuple[str, float], dict[str, int]]:
    """One book's (player, point) -> {"over": american, "under": american}.

    Only sides with a parseable american price and a numeric point are kept;
    Over and Under must share the SAME point to become a pair later.
    """
    pairs: dict[tuple[str, float], dict[str, int]] = {}
    for outcome in market.get("outcomes", []) or []:
        if not isinstance(outcome, dict):
            continue
        side = str(outcome.get("name") or "").strip().lower()
        if side not in {"over", "under"}:
            continue
        player = str(outcome.get("description") or "").strip()
        point = _point(outcome.get("point"))
        price = _american(outcome.get("price"))
        if not player or point is None or price is None:
            continue
        pairs.setdefault((player, point), {})[side] = price
    return pairs


def parse_event_props(event: dict[str, Any]) -> list[PropQuote]:
    """De-vigged prop quotes for one event (fail-closed -> [] on anything odd)."""
    if not isinstance(event, dict):
        return []
    # market_key -> (player, point) -> list of per-book P(over)
    collected: dict[tuple[str, str, float], list[float]] = {}
    for bookmaker in event.get("bookmakers", []) or []:
        if not isinstance(bookmaker, dict):
            continue
        for market in bookmaker.get("markets", []) or []:
            if not isinstance(market, dict):
                continue
            market_key = str(market.get("key") or "")
            if not market_key.startswith(_PROP_MARKET_PREFIXES):
                continue
            for (player, point), sides in _book_prop_pairs(market).items():
                over, under = sides.get("over"), sides.get("under")
                if over is None or under is None:
                    continue  # one-sided -> abstain
                devigged = devig_two_way(over, under)
                if devigged is None:
                    continue
                collected.setdefault((market_key, player, point), []).append(devigged)

    quotes: list[PropQuote] = []
    for (market_key, player, point), probs in sorted(collected.items()):
        if not probs:
            continue
        quotes.append(PropQuote(
            market_key=market_key,
            player=player,
            point=point,
            prob_over=sum(probs) / len(probs),
            n_books=len(probs),
        ))
    return quotes


def parse_player_props(payload: dict[str, Any] | None) -> list[EventProps]:
    """All events' de-vigged prop quotes from a licensed payload (fail-closed)."""
    events = (payload or {}).get("events") if isinstance(payload, dict) else None
    result: list[EventProps] = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        result.append(EventProps(
            event_id=str(event.get("id")) if event.get("id") is not None else None,
            home_team=event.get("home_team"),
            away_team=event.get("away_team"),
            quotes=tuple(parse_event_props(event)),
        ))
    return result


class FixturePropProvider:
    """Offline provider over a committed sample payload (contacts no network)."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        path: str | Path | None = None,
    ) -> None:
        if payload is None and path is not None:
            try:
                payload = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                payload = {}
        self._payload = payload or {}

    @property
    def available(self) -> bool:
        return bool(self._payload.get("events"))

    def event_props(self) -> list[EventProps]:
        return parse_player_props(self._payload)

    def props_for(self, home_team: str, away_team: str) -> list[PropQuote]:
        event = _match_event(self._payload.get("events") or [], home_team, away_team)
        return parse_event_props(event) if event else []


def default_prop_api_fetch(sport_key: str, api_key: str, markets: str) -> dict[str, Any]:
    """Fetch player-prop odds from The Odds API v4 (only called when armed)."""
    import httpx

    response = httpx.get(
        f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": markets,
            "oddsFormat": "american",
        },
        timeout=15,
    )
    response.raise_for_status()
    return {"sport_key": sport_key, "events": response.json()}


class LicensedPropProvider:
    """Governance-gated licensed player-prop provider. Inert unless armed.

    Reuses ``odds_providers``' env switches (same licensed aggregator). It is
    ``available`` -- and only then will it fetch -- when BOTH a key is present
    AND it is explicitly enabled. Default construction in this repo is inert.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        enabled: bool | None = None,
        sport_key: str = "baseball_mlb",
        markets: str = "player_hits,player_total_bases",
        fetch_fn: Callable[[str, str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(ODDS_API_KEY_ENV)
        if enabled is None:
            enabled = os.environ.get(ODDS_API_ENABLED_ENV) == "1"
        self.enabled = bool(enabled)
        self.sport_key = sport_key
        self.markets = markets
        self.fetch_fn = fetch_fn or default_prop_api_fetch
        self._cache: dict[str, Any] | None = None

    @property
    def available(self) -> bool:
        """True only when armed: enabled AND a key present (governance-gated)."""
        return self.enabled and bool(self.api_key)

    def clear(self) -> None:
        self._cache = None

    def _payload(self) -> dict[str, Any]:
        if self._cache is None:
            try:
                self._cache = self.fetch_fn(self.sport_key, self.api_key, self.markets) or {}
            except Exception:
                self._cache = {}
        return self._cache

    def event_props(self) -> list[EventProps]:
        if not self.available:
            return []
        return parse_player_props(self._payload())

    def props_for(self, home_team: str, away_team: str) -> list[PropQuote]:
        if not self.available:
            return []
        event = _match_event(self._payload().get("events") or [], home_team, away_team)
        return parse_event_props(event) if event else []


def prop_over_probability(
    provider: FixturePropProvider | LicensedPropProvider,
    *,
    home_team: str,
    away_team: str,
    market_key: str,
    player: str,
    point: float,
) -> float | None:
    """Challenger P(over) for a specific prop, or None (fail-closed).

    The hook a future Kalshi player-prop matcher calls. With the licensed
    provider unarmed it always returns None, so the challenger stays dormant
    until the governance slot is opened.
    """
    player_key = _norm(player)
    wanted = _point(point)
    if not player_key or wanted is None:
        return None
    for quote in provider.props_for(home_team, away_team):
        if quote.market_key == market_key and _norm(quote.player) == player_key and abs(quote.point - wanted) <= 1e-9:
            return quote.prob_over
    return None
