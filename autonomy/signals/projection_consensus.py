"""FanGraphs projection-consensus signal: team projections -> MLB fair value.

Fantasy triangulation leg #1. Turns FanGraphs per-player projections, aggregated
to per-team scoring/prevention rates (autonomy.ingest.fantasy.fangraphs), into
fair-value probabilities for MLB winner and total-runs markets. It reuses the
existing MLB run-model plumbing rather than forking it: the two teams' expected
runs are fed straight into ``poisson_win_probability`` / ``poisson_over_probability``
from autonomy.sports.baseball -- the exact functions the incumbent
BaseballRunModel prices with -- so a projection view and a results-EWMA view are
directly comparable on the same scale.

v1 SIMPLIFICATION (documented, deliberate): the projection rates are
lineup-agnostic, rest-of-season TEAM rates. There is no game-day lineup, no
announced-starter ERA on top, no park/weather adjustment here -- those already
live in BaseballIntelligenceSignal. This leg contributes the orthogonal thing
projections add: a talent-based, results-independent prior on how good each
lineup and staff actually are. Expected runs blend a team's own offense with the
opponent's projected run prevention, mirroring BaseballRunModel.predict's
structure.

Discipline:
  * challenger_only=True -- logged as point-in-time evidence, admitted to the
    live ensemble ONLY through a settlement-backed WS-14 promotion. Breadth
    never silently moves live risk.
  * promotion_eligible is left to the evidence: this signal does NOT stamp it
    False. Eligibility is decided by the promotion engine from the settled
    contested record, not hardcoded here.
  * fail-closed abstain -- empty book (no feed / offseason), an unmapped team,
    or a missing projection for either side => return None, and the MLB forecast
    is byte-identical to a run without this leg.
"""
from __future__ import annotations

from typing import Any

from autonomy.ingest.fantasy.fangraphs import (
    DEFAULT_SYSTEM,
    MAX_RUNS_PER_GAME,
    MIN_RUNS_PER_GAME,
    ProjectionBook,
    TeamProjection,
)
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_intelligence import parse_sports_contract
from autonomy.sports.baseball import (
    poisson_over_probability,
    poisson_win_probability,
)

# Market types this leg prices. Spread/YRFI are out of scope for v1 -- team
# rest-of-season rates carry no first-inning or run-margin-shape information
# beyond what the two means already imply.
_SUPPORTED_MARKETS = {"winner", "total_runs"}

# Season-long, lineup-agnostic projections deserve a wide error bar: they are a
# slow talent prior, not a game-day model. The ensemble weights them lightly
# until a contested-Brier record earns more.
_WINNER_UNCERTAINTY = 0.17
_TOTAL_UNCERTAINTY = 0.22
# Widen further when a side's run prevention fell back to league average
# (no usable pitching projection for that team).
_DEFENSE_FALLBACK_WIDEN = 0.04


def _expected_runs(offense: TeamProjection, defense: TeamProjection) -> float:
    """Expected runs for ``offense`` vs ``defense`` (own bats + their arms)."""
    blended = 0.5 * (offense.runs_per_game + defense.runs_allowed_per_game)
    return max(MIN_RUNS_PER_GAME, min(MAX_RUNS_PER_GAME, blended))


class ProjectionConsensusSignal:
    """MLB winner/total fair value from FanGraphs projection consensus."""

    name = "fangraphs_projection_consensus"

    def __init__(
        self,
        book: ProjectionBook | None = None,
        system: str = DEFAULT_SYSTEM,
        seasons: Any = None,
        ledger: Any = None,
    ) -> None:
        self.system = system
        self.book = book or ProjectionBook(system=system, ledger=ledger)
        # Season gate shared with the other MLB signals when injected; None means
        # "no gate" (the book itself still fail-closes to empty off-season).
        self.seasons = seasons

    def on_cycle_start(self) -> None:
        # MLB sleeps Nov-Feb: when the shared monitor reports the league dormant,
        # drop the book (abstain everywhere) and skip the per-cycle fetch.
        if self.seasons is not None:
            try:
                if not self.seasons.active("mlb"):
                    self.book.reset()
                    return
            except Exception:
                # A flaky gate must never suppress the leg; fall through to the
                # book's own fail-closed refresh.
                pass
        self.book.refresh()

    def applicable(self, market: MarketView) -> bool:
        if market.vertical is not Vertical.SPORTS:
            return False
        contract = parse_sports_contract(market)
        return (
            contract is not None
            and contract.sport == "mlb"
            and contract.market_type in _SUPPORTED_MARKETS
        )

    def generate(self, market: MarketView) -> Signal | None:
        contract = parse_sports_contract(market)
        if contract is None or contract.sport != "mlb":
            return None
        if contract.market_type not in _SUPPORTED_MARKETS:
            return None
        if contract.competitors is None:
            return None
        first, second = contract.competitors
        team_first = self.book.team(first)
        team_second = self.book.team(second)
        if team_first is None or team_second is None:
            return None  # empty book or unmapped team -> abstain (fail-closed)

        expected_first = _expected_runs(team_first, team_second)
        expected_second = _expected_runs(team_second, team_first)
        defense_fallback = not (
            team_first.defense_is_projected and team_second.defense_is_projected
        )

        common_features: dict[str, Any] = {
            "challenger_only": True,
            "projection_system": self.system,
            "model": "fangraphs_projection_consensus_v1",
            "lineup_agnostic": True,
            "first_team": team_first.team,
            "second_team": team_second.team,
            "expected_first_runs": expected_first,
            "expected_second_runs": expected_second,
            "first_runs_per_game": team_first.runs_per_game,
            "second_runs_per_game": team_second.runs_per_game,
            "first_runs_allowed_per_game": team_first.runs_allowed_per_game,
            "second_runs_allowed_per_game": team_second.runs_allowed_per_game,
            "first_defense_projected": team_first.defense_is_projected,
            "second_defense_projected": team_second.defense_is_projected,
            "first_batter_count": team_first.batter_count,
            "second_batter_count": team_second.batter_count,
            "first_pitcher_count": team_first.pitcher_count,
            "second_pitcher_count": team_second.pitcher_count,
        }

        if contract.market_type == "total_runs":
            threshold = contract.threshold
            if threshold is None:
                return None
            probability = poisson_over_probability(
                expected_first + expected_second, float(threshold),
            )
            uncertainty = _TOTAL_UNCERTAINTY + (
                _DEFENSE_FALLBACK_WIDEN if defense_fallback else 0.0
            )
            rationale = (
                f"{self.system}: proj total {expected_first + expected_second:.2f} "
                f"({team_first.team} {expected_first:.2f} + {team_second.team} "
                f"{expected_second:.2f}) vs line {float(threshold):.1f} "
                f"-> P(over)={probability:.3f}; challenger-only"
            )
            features = {**common_features, "market_type": "total_runs",
                       "threshold": float(threshold),
                       "expected_total_runs": expected_first + expected_second}
            return Signal(
                source=self.name, market_ticker=market.ticker,
                probability_yes=probability, uncertainty=uncertainty,
                rationale=rationale, features=features,
            )

        # winner: resolve which competitor the YES side is, and price P(subject wins)
        subject = contract.subject
        if subject is None:
            return None
        if subject == team_first.team:
            subject_mean, opponent_mean, opponent = expected_first, expected_second, team_second.team
        elif subject == team_second.team:
            subject_mean, opponent_mean, opponent = expected_second, expected_first, team_first.team
        else:
            return None  # subject not one of the resolved competitors -> abstain
        probability = poisson_win_probability(subject_mean, opponent_mean)
        uncertainty = _WINNER_UNCERTAINTY + (
            _DEFENSE_FALLBACK_WIDEN if defense_fallback else 0.0
        )
        rationale = (
            f"{self.system}: {subject} proj {subject_mean:.2f} runs vs {opponent} "
            f"{opponent_mean:.2f} -> P({subject} win)={probability:.3f}; challenger-only"
        )
        features = {**common_features, "market_type": "winner", "subject": subject,
                    "subject_expected_runs": subject_mean,
                    "opponent_expected_runs": opponent_mean}
        return Signal(
            source=self.name, market_ticker=market.ticker,
            probability_yes=probability, uncertainty=uncertainty,
            rationale=rationale, features=features,
        )
