"""Basketball first-half kernel (Wave-13).

Splits a full-game ``TeamScorePrediction`` into first-half quantities. The
market shape (verified live 2026-07-17 on the WNBA slate): the 1H winner is
THREE-WAY -- a half ends level often enough that Kalshi lists an explicit TIE
leg (``KXWNBA1HWINNER-...-TIE``) -- and 1H totals/spreads quote half-point
strikes exactly like their full-game counterparts.

Mechanics: scoring is treated as an approximately-stationary process, so a
half carries ``SHARE_1H`` of the expected points and HALF the variance
(independent halves: sigma scales by sqrt(share)). The first half runs
fractionally under half the points league-wide (second halves are inflated by
garbage time, late-game fouling, and bench minutes), hence 0.49 rather than
0.50. The tie leg comes from the DISCRETE margin: P(tie) is the continuity-
corrected normal mass on (-0.5, +0.5), which a continuous margin read would
miss entirely.

League-agnostic within basketball (WNBA/NBA/NCAAMB share the mechanics; only
the upstream prediction differs). Same v1 posture as the MLB first-five model:
a share-based split with widened uncertainty, refined later by possession-level
modeling if the evidence asks for it.
"""
from __future__ import annotations

import math

from autonomy.sports.team_scores import TeamScorePrediction

# First-half share of expected points. Slightly under one half: second halves
# score more (garbage time, intentional fouling, deeper rotations).
SHARE_1H = 0.49

SEGMENT_MODEL_VERSION = "basketball-half-share-v1"


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _margin_sigma_1h(margin_sigma_full: float) -> float:
    return max(1.0, margin_sigma_full * math.sqrt(SHARE_1H))


def first_half_outcome_probabilities(
    prediction: TeamScorePrediction, margin_sigma_full: float
) -> tuple[float, float, float]:
    """(P(home wins 1H), P(1H tie), P(away wins 1H)) on the discrete margin.

    P(tie) is the normal mass on (-0.5, +0.5) around the expected 1H margin
    (continuity correction: basketball margins are integers).
    """
    mean = (prediction.expected_home_score - prediction.expected_away_score) * SHARE_1H
    sigma = _margin_sigma_1h(margin_sigma_full)
    p_home = 1.0 - _normal_cdf((0.5 - mean) / sigma)
    p_away = _normal_cdf((-0.5 - mean) / sigma)
    p_tie = max(0.0, 1.0 - p_home - p_away)
    return p_home, p_tie, p_away


def first_half_total_probability(
    prediction: TeamScorePrediction, line: float
) -> float:
    """P(1H combined points > line) at a half-point strike."""
    mean = prediction.expected_total * SHARE_1H
    sigma = max(1.0, prediction.total_sigma * math.sqrt(SHARE_1H))
    p = 1.0 - _normal_cdf((line - mean) / sigma)
    return min(0.995, max(0.005, p))


def first_half_spread_probability(
    prediction: TeamScorePrediction,
    subject_home: bool,
    line: float,
    margin_sigma_full: float,
) -> float:
    """P(subject's 1H margin > line) at a half-point strike."""
    home_margin = (prediction.expected_home_score - prediction.expected_away_score) * SHARE_1H
    mean = home_margin if subject_home else -home_margin
    sigma = _margin_sigma_1h(margin_sigma_full)
    p = 1.0 - _normal_cdf((line - mean) / sigma)
    return min(0.995, max(0.005, p))
