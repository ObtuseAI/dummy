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

TEAM_LEAGUES = ("nba", "nfl", "ncaaf", "nhl", "ncaamb")


def _source_by_name(sources: list[Any], name: str) -> Any:
    return next((s for s in sources if getattr(s, "name", "") == name), None)


def build_specialist_registry(source_registry: Any) -> SpecialistRegistry:
    """Assemble the council from an existing ``SourceRegistry``."""
    sources = list(source_registry.sources())
    mlb_signal = _source_by_name(sources, "mlb_intelligence")
    team_signal = _source_by_name(sources, "team_sports_intelligence")
    sportsbook = _source_by_name(sources, "sportsbook_consensus")
    crypto_champion = _source_by_name(sources, "crypto_spot_vol")

    registry = SpecialistRegistry()
    registry.register(MlbSpecialist(intelligence=mlb_signal, sportsbook=sportsbook))
    for league in TEAM_LEAGUES:
        registry.register(TeamLeagueSpecialist(
            league=league, intelligence=team_signal, sportsbook=sportsbook,
        ))
    registry.register(CryptoSpecialist(champion=crypto_champion))
    return registry
