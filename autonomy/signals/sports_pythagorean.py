"""Sports signal: Pythagenpat win probability from the lake (challenger).

The Pythagorean sibling of :mod:`autonomy.signals.sports_glicko`: same ticker
parse + ESPN home/away resolution, but the matchup probability comes from
:class:`autonomy.sports.pythagorean.LakePythagorean` -- team strength inferred
from scoring margin rather than W/L. Independent of Glicko, so it diversifies
the ensemble (a team that wins ugly but loses big is rated honestly).

Challenger-only + fail-closed: abstains when the lake is empty, the game has
started, or anything raises; earns weight only through the contested-Brier gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.pythagorean import LakePythagorean

# Home advantage as a probability bump per league (Pythagenpat works in prob
# space, unlike Glicko's rating-point bump).
_HOME_ADVANTAGE_PROB = {
    "nfl": 0.055, "ncaaf": 0.075, "nba": 0.05, "wnba": 0.05,
    "ncaamb": 0.065, "nhl": 0.045, "mlb": 0.033,
}


class SportsPythagoreanSignal:
    name = "sports_pythagorean"

    def __init__(self, espn: EspnClient | None = None,
                 store: SportsHistoryStore | None = None, seasons: Any = None) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._store = store
        self._models: dict[str, LakePythagorean] = {}
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

    def _model_for(self, league: str) -> LakePythagorean | None:
        if league in self._models:
            return self._models[league]
        store = self.store()
        if store is None:
            return None
        try:
            model = LakePythagorean(store, league=league).warm(self._now())
        except Exception:  # noqa: BLE001
            return None
        self._models[league] = model
        return model

    def on_cycle_start(self, as_of: str | None = None) -> None:
        self.espn.clear_cache()
        self._as_of = as_of
        self._models.clear()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and parse_game_ticker(market.ticker) is not None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None or parsed["league"] not in LEAGUE_TO_ESPN:
            return None
        league, subject, opponent = parsed["league"], parsed["subject"], parsed["opponent"]

        try:
            game = self.espn.find_matchup(league, subject, opponent, dates=parsed["date_yyyymmdd"])
        except Exception:  # noqa: BLE001
            game = None
        if game is not None and game.status != "pre":
            return None
        subject_home = None if game is None else (game.home.upper() == subject)

        model = self._model_for(league)
        if model is None:
            return None
        from autonomy.sports.tuner import load_tuned
        hadv = load_tuned(league, 'pythagenpat', 'home_advantage_prob', _HOME_ADVANTAGE_PROB.get(league, 0.05))
        if subject_home is True:
            p_yes = model.matchup_prob(subject, opponent, home_advantage_prob=hadv)
        elif subject_home is False:
            p_yes = 1.0 - model.matchup_prob(opponent, subject, home_advantage_prob=hadv)
        else:
            p_yes = model.matchup_prob(subject, opponent, home_advantage_prob=0.0)
        p_yes = min(0.98, max(0.02, p_yes))

        seen = min(model.games_seen(subject), model.games_seen(opponent))
        coldness = 0.20 if seen < 3 else (0.10 if seen < 8 else 0.05)
        site_penalty = 0.06 if subject_home is None else 0.0
        uncertainty = min(0.5, max(0.06, 0.20 - 0.26 * abs(p_yes - 0.5) + coldness + site_penalty))

        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=(
                f"{league.upper()} Pythagenpat {subject}({model.strength(subject):.2f}) "
                f"vs {opponent}({model.strength(opponent):.2f}) home={subject_home} n={seen}"
            ),
            features={
                "subject_strength": round(model.strength(subject), 3),
                "opponent_strength": round(model.strength(opponent), 3),
                "subject_home": subject_home, "min_games": seen,
            },
        )
