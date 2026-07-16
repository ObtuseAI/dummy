"""ESPN fantasy crowd-lean signal: ownership / ADP + projections -> MLB lean.

Fantasy triangulation leg #3. Turns ESPN's public fantasy-baseball CROWD signals
-- percentOwned / averageDraftPosition / auctionValueAverage -- plus ESPN's own
season projections into a per-team "public backing + projected strength" index,
and prices MLB **winner** markets from the differential between the two teams'
indices via a bounded logistic. This is deliberately the ORTHOGONAL thing crowd
data adds on top of the FanGraphs run model (leg #1): where a projection is a
talent estimate, ownership is a measure of where the *public* has piled in, and
the differential is a coarse "which roster does the crowd + the projections
back harder" prior. It is a lean, not a precise win model -- hence a wide error
bar and challenger-only status.

Why winner-only: fantasy ownership/ADP carry NO first-inning, run-margin-shape,
or total-runs information beyond the crude team-strength ordering the two
indices already imply, so spread / total / YRFI are out of scope for v1
(exactly the boundary leg #1 drew for the same reason).

Discipline (base-branch convention, identical to ProjectionConsensusSignal):
  * challenger_only=True -- logged as point-in-time evidence, admitted to the
    live ensemble ONLY through a settlement-backed promotion. Breadth never
    silently moves live risk.
  * promotion_eligible is left to the evidence -- this signal does NOT stamp it.
  * fail-closed abstain -- empty book (no feed / offseason / un-enriched
    response), an unmapped team, or a team with too little owned data => return
    None, and the MLB forecast is byte-identical to a run without this leg.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.ingest.fantasy.espn_fantasy import (
    FantasyBook,
    TeamFantasyAggregate,
)
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_intelligence import parse_sports_contract

# Winner markets only (see module docstring).
_SUPPORTED_MARKETS = {"winner"}

# A team needs at least this many meaningfully-owned players in the book for its
# crowd index to be trustworthy; fewer -> abstain (fail-closed).
_MIN_OWNED_PLAYERS = 3

# Logistic scale converting the (subject - opponent) combined-index differential
# into a probability. Deliberately conservative: a large index gap moves the
# lean only modestly off 0.5, because ownership is a coarse public prior, not a
# calibrated win model. Tuned so a full-roster backing gap (~a few "index"
# units) lands inside a sane 0.35..0.65 band rather than saturating.
_LOGISTIC_SCALE = 6.0

# Ownership-backing and projected-strength are combined into one index after
# each is normalized to a comparable scale. Backing is already ~O(sum of
# fractions); projected strength (sum of fantasy points) is divided down to the
# same order of magnitude before blending.
_STRENGTH_NORMALIZER = 200.0
_BACKING_WEIGHT = 0.6
_STRENGTH_WEIGHT = 0.4

# Crowd leans are a slow, coarse public prior: a wide error bar, weighted
# lightly by the ensemble until a contested-Brier record earns more.
_WINNER_UNCERTAINTY = 0.20
# Widen further when either side is carrying OUT players among its owned core
# (roster availability the crowd index does not fully price).
_OUT_WIDEN_PER_SIDE = 0.02


def _combined_index(team: TeamFantasyAggregate) -> float:
    """Blend public backing and projected strength into one comparable index."""
    strength = team.projected_strength / _STRENGTH_NORMALIZER
    return _BACKING_WEIGHT * team.public_backing + _STRENGTH_WEIGHT * strength


def _win_probability(subject: TeamFantasyAggregate, opponent: TeamFantasyAggregate) -> float:
    """Bounded logistic on the two teams' combined-index differential."""
    delta = _combined_index(subject) - _combined_index(opponent)
    probability = 1.0 / (1.0 + math.exp(-delta / _LOGISTIC_SCALE))
    return min(0.95, max(0.05, probability))


class EspnFantasyCrowdSignal:
    """MLB winner lean from ESPN fantasy ownership/ADP + projection consensus."""

    name = "espn_fantasy_crowd"

    def __init__(
        self,
        book: FantasyBook | None = None,
        seasons: Any = None,
        ledger: Any = None,
    ) -> None:
        self.book = book or FantasyBook(ledger=ledger)
        # Season gate shared with the other MLB signals when injected; None
        # means "no gate" (the book still fail-closes to empty off-season).
        self.seasons = seasons

    def on_cycle_start(self) -> None:
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
        if contract.competitors is None or contract.subject is None:
            return None
        first, second = contract.competitors
        team_first = self.book.team(first)
        team_second = self.book.team(second)
        if team_first is None or team_second is None:
            return None  # empty book or unmapped team -> abstain (fail-closed)
        if (
            team_first.owned_player_count < _MIN_OWNED_PLAYERS
            or team_second.owned_player_count < _MIN_OWNED_PLAYERS
        ):
            return None  # too little crowd data to lean on -> abstain

        subject = contract.subject
        if subject == team_first.team:
            subject_team, opponent_team = team_first, team_second
        elif subject == team_second.team:
            subject_team, opponent_team = team_second, team_first
        else:
            return None  # subject not one of the resolved competitors -> abstain

        probability = _win_probability(subject_team, opponent_team)
        out_sides = int(team_first.out_count > 0) + int(team_second.out_count > 0)
        uncertainty = _WINNER_UNCERTAINTY + _OUT_WIDEN_PER_SIDE * out_sides

        rationale = (
            f"espn-flb crowd: {subject_team.team} backing "
            f"{subject_team.public_backing:.2f}/proj {subject_team.projected_strength:.0f} "
            f"vs {opponent_team.team} backing {opponent_team.public_backing:.2f}/proj "
            f"{opponent_team.projected_strength:.0f} -> P({subject_team.team} win)="
            f"{probability:.3f}; challenger-only"
        )
        features: dict[str, Any] = {
            "challenger_only": True,
            "model": "espn_fantasy_crowd_v1",
            "market_type": "winner",
            "subject": subject_team.team,
            "opponent": opponent_team.team,
            "public_lean": True,
            "subject_public_backing": subject_team.public_backing,
            "opponent_public_backing": opponent_team.public_backing,
            "subject_projected_strength": subject_team.projected_strength,
            "opponent_projected_strength": opponent_team.projected_strength,
            "subject_combined_index": _combined_index(subject_team),
            "opponent_combined_index": _combined_index(opponent_team),
            "subject_owned_players": subject_team.owned_player_count,
            "opponent_owned_players": opponent_team.owned_player_count,
            "subject_out_count": subject_team.out_count,
            "opponent_out_count": opponent_team.out_count,
            "subject_day_to_day_count": subject_team.day_to_day_count,
            "opponent_day_to_day_count": opponent_team.day_to_day_count,
            "scratch_events_this_cycle": len(self.book.scratch_events()),
        }
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=probability,
            uncertainty=uncertainty,
            rationale=rationale,
            features=features,
        )
