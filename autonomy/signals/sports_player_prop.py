"""Sports signal: player prop over/under from a minutes/usage projection (challenger).

Prices a player counting-stat prop from the player's own recent game log
(autonomy.sports.player_props): recency-weighted minutes x per-minute rate ->
expected count, priced over/under with a count+minutes dispersion. Self-scopes
to prop markets whose stat maps to a projectable counting stat AND whose player
has enough game history in the lake; abstains otherwise (e.g. before player
boxscores exist for the league). Challenger-only, fail-closed.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports_markets import spec_for

# Prop stat family -> canonical game-log stat key produced by the boxscore
# parser. Only families we can project from counting-stat history.
_STAT_MAP = {
    "points": "points", "rebounds": "rebounds", "assists": "assists",
    "threes": "threes", "steals": "steals", "blocks": "blocks",
    "pts": "points", "reb": "rebounds", "ast": "assists",
}


class SportsPlayerPropSignal:
    name = "sports_player_prop"

    def __init__(self, store: SportsHistoryStore | None = None, seasons: Any = None) -> None:
        self._store = store
        self._as_of: str | None = None

    def _now(self) -> str:
        from datetime import datetime, timezone

        return self._as_of or datetime.now(timezone.utc).isoformat()

    def store(self) -> SportsHistoryStore | None:
        if self._store is None:
            try:
                self._store = SportsHistoryStore()
            except Exception:  # noqa: BLE001
                return None
        return self._store

    def on_cycle_start(self, as_of: str | None = None) -> None:
        self._as_of = as_of

    def _prop(self, market: MarketView):
        try:
            spec = spec_for(market.ticker)
        except Exception:  # noqa: BLE001
            return None
        return spec if spec and spec.is_prop and spec.stat else None

    def applicable(self, market: MarketView) -> bool:
        if market.vertical is not Vertical.SPORTS:
            return False
        spec = self._prop(market)
        return bool(spec and str(spec.stat).lower() in _STAT_MAP)

    def _player_and_line(self, market: MarketView):
        from autonomy.signals.sports_intelligence import parse_sports_contract

        try:
            c = parse_sports_contract(market)
        except Exception:  # noqa: BLE001
            return None, None
        if c is None:
            return None, None
        return c.subject, c.threshold

    def generate(self, market: MarketView) -> Signal | None:
        spec = self._prop(market)
        if spec is None:
            return None
        canonical = _STAT_MAP.get(str(spec.stat).lower())
        if canonical is None:
            return None
        store = self.store()
        if store is None:
            return None
        player, line = self._player_and_line(market)
        if not player or line is None:
            return None

        from autonomy.sports.player_props import project_stat, prop_over_probability

        log = store.player_game_log(str(player), self._now(), league=spec.league, n=20)
        projection = project_stat(log, canonical)
        if projection is None:
            return None  # thin history / no minutes -> fail-closed abstain
        p_over = prop_over_probability(projection["mean"], projection["sigma"], float(line))
        if p_over is None:
            return None
        p_yes = min(0.98, max(0.02, p_over))

        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=min(0.5, max(0.09, 0.24 - 0.20 * abs(p_yes - 0.5))),
            rationale=(
                f"{spec.league.upper()} {player} {canonical} over {line}: "
                f"proj {projection['mean']} +/- {projection['sigma']} "
                f"({projection['projected_minutes']}min, {projection['games']}g)"
            ),
            features={
                "player": player,
                "stat": canonical,
                "line": float(line),
                "projected_mean": projection["mean"],
                "projected_sigma": projection["sigma"],
                "projected_minutes": projection["projected_minutes"],
                "games": projection["games"],
                "market_type": "prop",
                "challenger_only": True,
                "promotion_eligible": True,
                "public_read_only": True,
                "sport": spec.league,
            },
        )
