"""Sports signal: EPA/play win probability from the lake (challenger).

The NFL gold standard as a live challenger: net EPA/play (offense minus defense
allowed) aggregated point-in-time from the nflfastR play-by-play in the lake.
Self-scopes to leagues with EPA data (NFL today) -- abstains elsewhere.
Challenger-only + fail-closed; earns weight only through the contested-Brier gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.epa import LakeEpa
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.history_store import SportsHistoryStore


class SportsEpaSignal:
    name = "sports_epa"

    def __init__(self, espn: EspnClient | None = None,
                 store: SportsHistoryStore | None = None, seasons: Any = None) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._store = store
        self._as_of: str | None = None
        self.seasons = seasons or SeasonMonitor(espn=self.espn)

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
        self.espn.clear_cache()
        self._as_of = as_of

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and parse_game_ticker(market.ticker) is not None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None or parsed["league"] not in LEAGUE_TO_ESPN:
            return None
        league, subject, opponent = parsed["league"], parsed["subject"], parsed["opponent"]
        store = self.store()
        if store is None:
            return None
        try:
            game = self.espn.find_matchup(league, subject, opponent, dates=parsed["date_yyyymmdd"])
        except Exception:  # noqa: BLE001
            game = None
        if game is not None and game.status != "pre":
            return None
        subject_home = None if game is None else (game.home.upper() == subject)

        model = LakeEpa(store, league=league)
        as_of = self._now()
        try:
            if subject_home is True:
                p = model.matchup_prob(subject, opponent, as_of)
            elif subject_home is False:
                q = model.matchup_prob(opponent, subject, as_of)
                p = None if q is None else 1.0 - q
            else:
                p = model.matchup_prob(subject, opponent, as_of, home_advantage=0.0)
        except Exception:  # noqa: BLE001
            p = None
        if p is None:                                    # no EPA data for this scope
            return None
        p_yes = min(0.98, max(0.02, p))
        seen = min(model.games_seen(subject, as_of), model.games_seen(opponent, as_of))
        site = 0.06 if subject_home is None else 0.0
        cold = 0.16 if seen < 4 else 0.05
        uncertainty = min(0.5, max(0.05, 0.18 - 0.28 * abs(p_yes - 0.5) + cold + site))
        return Signal(
            source=self.name, market_ticker=market.ticker, probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=f"{league.upper()} EPA {subject} vs {opponent} home={subject_home} n={seen}",
            features={"subject_home": subject_home, "min_games": seen},
        )
