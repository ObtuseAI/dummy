"""Council assembly: build the specialist registry from a brain's sources.

Specialists share the brain's registered signal instances (model state,
caches, health records) instead of constructing their own -- the council is
a routing layer over the shipped stack, not a second copy of it. A missing
signal leaves that specialist cold (it abstains), never raises.
"""
from __future__ import annotations

from typing import Any

from autonomy.specialists.base import SpecialistRegistry
from autonomy.specialists.crypto import CryptoSpecialist
from autonomy.specialists.mlb import MlbSpecialist
from autonomy.specialists.team_leagues import TeamLeagueSpecialist

TEAM_LEAGUES = ("nba", "nfl", "ncaaf", "nhl", "ncaamb", "wnba")


def _source_by_name(sources: list[Any], name: str) -> Any:
    return next((s for s in sources if getattr(s, "name", "") == name), None)


def build_specialist_registry(source_registry: Any) -> SpecialistRegistry:
    """Assemble the council from an existing ``SourceRegistry``."""
    sources = list(source_registry.sources())
    mlb_signal = _source_by_name(sources, "mlb_intelligence")
    team_signal = _source_by_name(sources, "team_sports_intelligence")
    sportsbook = _source_by_name(sources, "sportsbook_consensus")
    crypto_champion = _source_by_name(sources, "crypto_spot_vol")

    # The Deribit DVOL implied book rides the SAME shared CryptoDataHub the
    # registered indicator signals use (one multi-venue fetch per asset per
    # cycle) -- recovered via any hub-backed signal's fetch_state. No hub
    # signal registered means no crypto book (fail-closed, model_only).
    implied_book = None
    dvol_signal = _source_by_name(sources, "crypto_dvol_implied")
    fetch_state = getattr(dvol_signal, "fetch_state", None)
    if callable(fetch_state):
        from autonomy.crypto_implied_book import CryptoImpliedBook

        implied_book = CryptoImpliedBook(fetch_state)

    # One shared season monitor for council health truth ("dormant" vs
    # "ok"); the warmup-gating monitors live inside the signals themselves
    # and share the same persisted state file, so verdicts agree.
    from autonomy.specialists.seasons import SeasonMonitor

    seasons = getattr(team_signal, "seasons", None) or SeasonMonitor()

    registry = SpecialistRegistry()
    registry.register(MlbSpecialist(intelligence=mlb_signal, sportsbook=sportsbook))
    for league in TEAM_LEAGUES:
        registry.register(TeamLeagueSpecialist(
            league=league, intelligence=team_signal, sportsbook=sportsbook,
            seasons=seasons, espn=getattr(team_signal, "espn", None),
        ))
    registry.register(CryptoSpecialist(
        champion=crypto_champion, implied_book=implied_book,
    ))
    return registry
