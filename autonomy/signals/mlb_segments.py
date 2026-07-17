"""MLB segment & team markets: team totals and first-five innings (Wave-10).

The moneyline / full-game total / run-line / YRFI are priced by
``BaseballIntelligenceSignal``. This adds the rest of the MLB game-line surface
the app exposes:

  * TEAM TOTAL  (KXMLBTEAMTOTAL)  -- one team's runs over a line. Exact under the
    run model: a team's run count is Poisson at its expected runs.
  * FIRST FIVE  (KXMLBF5 / KXMLBF5TOTAL / KXMLBF5SPREAD) -- winner (3-way; a
    five-inning tie is a real leg), total, and run line for innings 1-5.

First-five is the sharper of the two ideas: it is pitched almost entirely by the
starter (no bullpen, TTO penalty still building), so it strips the bullpen
variance that muddies a full-game line -- a cleaner starter-vs-lineup read. v1
prices F5 off the run model's 5/9 innings share with widened uncertainty; the
queued refinement is the PA-sim's starter-dominant ``runs_through_5`` (see
``baseball.F5_RUN_SHARE``).

Pre-game only and challenger-only: reuses the same learned ``BaseballRunModel``
and ESPN matchup resolution as the full-game signal, fails closed on any
ambiguity, and reaches execution solely through the promotion ladder. Each
market type emits its own source string, so each earns its own grading scope.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_intelligence import (
    MODEL_DIR,
    _date_and_remainder,
    _split_mlb_teams,
    _strip_start_time,
)
from autonomy.sports.baseball import BaseballPrediction, BaseballRunModel
from autonomy.sports.espn import EspnClient, canonical_team
from autonomy.sports_markets import SPREAD, TEAM_TOTAL, TOTAL, WINNER, classify


def _teams_from_ticker(ticker: str) -> tuple[str, str] | None:
    """Recover the two team abbreviations from the game token, the same way the
    full-game MLB parser does (date+time strip, then the two-team split)."""
    parts = ticker.upper().split("-")
    if len(parts) < 2:
        return None
    dated = _date_and_remainder(parts[1])
    if dated is None:
        return None
    return _split_mlb_teams(_strip_start_time(dated[1]))


class MlbSegmentSignal:
    name = "mlb_segments"

    def __init__(
        self,
        espn: EspnClient | None = None,
        model: BaseballRunModel | None = None,
        model_path: Path | None = None,
    ) -> None:
        self.espn = espn or EspnClient()
        self.model = model or BaseballRunModel.load(model_path or MODEL_DIR / "mlb_runs_model.json")
        # Per-cycle memo: one matchup is priced once even though a game exposes
        # several segment markets (team total, F5 winner x3 legs, F5 total, ...).
        self._pred: dict[str, tuple[Any, BaseballPrediction]] = {}

    def on_cycle_start(self) -> None:
        self.espn.clear_cache()
        self._pred.clear()

    @staticmethod
    def _handles(info: Any) -> bool:
        if info is None or info.league != "mlb":
            return False
        if info.market_type == TEAM_TOTAL and info.segment == "full":
            return True
        return info.segment == "f5" and info.market_type in (WINNER, TOTAL, SPREAD)

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and self._handles(classify(market))

    def _resolve(self, market: MarketView, info: Any):
        key = info.event_ticker
        if key in self._pred:
            return self._pred[key]
        teams = _teams_from_ticker(market.ticker)
        if teams is None:
            return None
        game = self.espn.find_matchup("mlb", teams[0], teams[1], info.date_yyyymmdd)
        # Pre-game only: a first-five line is stale once the fifth is underway,
        # and team totals need a live model mid-game. Fail closed otherwise.
        if game is None or game.status != "pre":
            return None
        prediction = self.model.predict(game)
        self._pred[key] = (game, prediction)
        return self._pred[key]

    def generate(self, market: MarketView) -> Signal | None:
        info = classify(market)
        if not self._handles(info):
            return None
        resolved = self._resolve(market, info)
        if resolved is None:
            return None
        game, prediction = resolved
        home = canonical_team("mlb", game.home)
        away = canonical_team("mlb", game.away)

        probability: float
        if info.market_type == TEAM_TOTAL:
            if info.threshold is None or not info.subject:
                return None
            subject = canonical_team("mlb", info.subject)
            if subject not in (home, away):
                return None
            probability = self.model.team_total_probability(
                prediction, subject == home, info.threshold)
            source = "mlb_team_total"
            detail = f"{subject} team over {info.threshold:g}"
            uncertainty = min(0.45, prediction.total_uncertainty + 0.04)
        elif info.segment == "f5" and info.market_type == TOTAL:
            if info.threshold is None:
                return None
            probability = self.model.f5_total_probability(prediction, info.threshold)
            source = "mlb_f5_total"
            detail = f"first-5 over {info.threshold:g}"
            uncertainty = min(0.48, prediction.total_uncertainty + 0.09)
        elif info.segment == "f5" and info.market_type == SPREAD:
            if info.threshold is None or not info.subject:
                return None
            subject = canonical_team("mlb", info.subject)
            if subject not in (home, away):
                return None
            probability = self.model.f5_spread_probability(
                prediction, subject == home, info.threshold)
            source = "mlb_f5_spread"
            detail = f"{subject} first-5 by >{info.threshold:g}"
            uncertainty = min(0.48, prediction.winner_uncertainty + 0.10)
        elif info.segment == "f5" and info.market_type == WINNER:
            p_home, p_tie, p_away = self.model.f5_outcome_probabilities(prediction)
            if info.is_tie:
                probability = p_tie
                label = "tie"
            else:
                if not info.subject:
                    return None
                subject = canonical_team("mlb", info.subject)
                if subject not in (home, away):
                    return None
                probability = p_home if subject == home else p_away
                label = subject
            source = "mlb_f5_winner"
            detail = f"first-5 {label}"
            uncertainty = min(0.48, prediction.winner_uncertainty + 0.10)
        else:
            return None

        return Signal(
            source=source,
            market_ticker=market.ticker,
            probability_yes=min(0.99, max(0.01, probability)),
            uncertainty=uncertainty,
            rationale=(
                f"MLB {detail}: {game.away}@{game.home}; expected runs "
                f"{prediction.expected_away_runs:.2f}+{prediction.expected_home_runs:.2f}="
                f"{prediction.expected_total_runs:.2f}"
            ),
            features={
                "challenger_only": True,
                "market_type": info.market_type,
                "segment": info.segment,
                "subject_home": info.subject is not None
                and canonical_team("mlb", info.subject) == home,
            },
        )
