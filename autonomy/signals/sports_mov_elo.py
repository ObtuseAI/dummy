"""Sports signal: margin-of-victory Elo win probability from the lake (challenger).

The MOV-Elo sibling of :mod:`autonomy.signals.sports_glicko`: same ticker parse
+ ESPN home/away resolution, matchup probability from
:class:`autonomy.sports.mov_elo.LakeMovElo` -- ratings that weight recent games
by how much a team won by. On the lake it is the sharpest of the three rating
analytics (NFL 63.6%, WNBA 66.2% straight-up in walk-forward), so it carries a
tighter uncertainty than the W/L-only Glicko.

Challenger-only + fail-closed; earns weight only through the contested-Brier gate.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker
from autonomy.signals.sports_glicko import _HOME_ADVANTAGE
from autonomy.sports.espn import LEAGUE_TO_ESPN, EspnClient
from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.mov_elo import LakeMovElo

_BASE = 1500.0


class SportsMovEloSignal:
    name = "sports_mov_elo"

    def __init__(self, espn: EspnClient | None = None,
                 store: SportsHistoryStore | None = None, seasons: Any = None) -> None:
        from autonomy.specialists.seasons import SeasonMonitor

        self.espn = espn or EspnClient()
        self._store = store
        self._models: dict[str, LakeMovElo] = {}
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

    def _model_for(self, league: str) -> LakeMovElo | None:
        if league in self._models:
            return self._models[league]
        store = self.store()
        if store is None:
            return None
        try:
            model = LakeMovElo(store, league=league,
                               home_advantage=_HOME_ADVANTAGE.get(league, 35.0)).warm(self._now())
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
        if subject_home is True:
            p_yes = model.matchup_prob(subject, opponent)
        elif subject_home is False:
            p_yes = 1.0 - model.matchup_prob(opponent, subject)
        else:
            p_yes = model.matchup_prob(subject, opponent, home_advantage=0.0)
        p_yes = min(0.98, max(0.02, p_yes))

        r_s, r_o = model.rating(subject), model.rating(opponent)
        cold = abs(r_s - _BASE) < 1e-6 or abs(r_o - _BASE) < 1e-6
        site_penalty = 0.06 if subject_home is None else 0.0
        coldness = 0.16 if cold else 0.04
        uncertainty = min(0.5, max(0.05, 0.18 - 0.28 * abs(p_yes - 0.5) + coldness + site_penalty))

        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=uncertainty,
            rationale=f"{league.upper()} MOV-Elo {subject}({r_s:.0f}) vs {opponent}({r_o:.0f}) home={subject_home}",
            features={"subject_rating": round(r_s, 1), "opponent_rating": round(r_o, 1),
                      "subject_home": subject_home},
        )
