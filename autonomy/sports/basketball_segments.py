"""Segment + team-market kernel (Wave-13 basketball half, generalized Wave-18).

Splits a full-game ``TeamScorePrediction`` into segment quantities for ANY
sport with a share table (``autonomy.sports.segment_shares``): a segment
carrying share ``s`` of expected scoring gets ``s`` of the mean and
``sqrt(s)`` of the sigma (independent-increments variance). Verified market
shape (WNBA slate, 2026-07-17): segment winners are THREE-WAY -- a half ends
level often enough that Kalshi lists an explicit TIE leg
(``KXWNBA1HWINNER-...-TIE``) -- and segment totals/spreads quote half-point
strikes exactly like their full-game counterparts. The tie leg comes from
the DISCRETE margin: P(tie) is the continuity-corrected normal mass on
(-0.5, +0.5), which a continuous margin read would miss entirely.

Also prices full-game TEAM TOTALS off the same prediction: a team's score is
``(total + margin) / 2``, so its sigma is ``sqrt(total_sigma^2 +
margin_sigma^2) / 2`` under independence of the total and margin components.

Same v1 posture as the MLB first-five model: share-based splits with widened
uncertainty, refined by possession/drive-level modeling if the evidence asks
for it. The Wave-13 ``first_half_*``/``SHARE_1H`` names remain as thin
wrappers so existing callers and grading histories are untouched.
"""
from __future__ import annotations

import math

from autonomy.sports.team_scores import TeamScorePrediction

# First-half share of expected basketball points (Wave-13 constant, kept for
# back-compat; the general tables live in segment_shares.py).
SHARE_1H = 0.49

SEGMENT_MODEL_VERSION = "segment-share-v2"


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _segment_margin_sigma(margin_sigma_full: float, share: float) -> float:
    return max(0.5, margin_sigma_full * math.sqrt(share))


def segment_outcome_probabilities(
    prediction: TeamScorePrediction, margin_sigma_full: float, share: float,
) -> tuple[float, float, float]:
    """(P(home wins segment), P(tie), P(away wins segment)), discrete margin."""
    mean = (prediction.expected_home_score - prediction.expected_away_score) * share
    sigma = _segment_margin_sigma(margin_sigma_full, share)
    p_home = 1.0 - _normal_cdf((0.5 - mean) / sigma)
    p_away = _normal_cdf((-0.5 - mean) / sigma)
    p_tie = max(0.0, 1.0 - p_home - p_away)
    return p_home, p_tie, p_away


def segment_total_probability(
    prediction: TeamScorePrediction, line: float, share: float,
) -> float:
    """P(segment combined points > line) at a half-point strike."""
    mean = prediction.expected_total * share
    sigma = max(0.5, prediction.total_sigma * math.sqrt(share))
    p = 1.0 - _normal_cdf((line - mean) / sigma)
    return min(0.995, max(0.005, p))


def segment_spread_probability(
    prediction: TeamScorePrediction,
    subject_home: bool,
    line: float,
    margin_sigma_full: float,
    share: float,
) -> float:
    """P(subject's segment margin > line) at a half-point strike."""
    home_margin = (prediction.expected_home_score - prediction.expected_away_score) * share
    mean = home_margin if subject_home else -home_margin
    sigma = _segment_margin_sigma(margin_sigma_full, share)
    p = 1.0 - _normal_cdf((line - mean) / sigma)
    return min(0.995, max(0.005, p))


def team_total_probability(
    prediction: TeamScorePrediction,
    subject_home: bool,
    line: float,
    margin_sigma_full: float,
) -> float:
    """P(subject team's full-game score > line).

    team = (total + margin) / 2 for home, (total - margin) / 2 for away, so
    sigma_team = sqrt(total_sigma^2 + margin_sigma^2) / 2 under independence
    of the total and margin components.
    """
    mean = (
        prediction.expected_home_score if subject_home
        else prediction.expected_away_score)
    sigma = max(
        0.5,
        math.sqrt(prediction.total_sigma ** 2 + margin_sigma_full ** 2) / 2.0)
    p = 1.0 - _normal_cdf((line - mean) / sigma)
    return min(0.995, max(0.005, p))


# ---- Wave-13 back-compat wrappers (basketball first half) -------------------


def first_half_outcome_probabilities(
    prediction: TeamScorePrediction, margin_sigma_full: float,
) -> tuple[float, float, float]:
    return segment_outcome_probabilities(prediction, margin_sigma_full, SHARE_1H)


def first_half_total_probability(
    prediction: TeamScorePrediction, line: float,
) -> float:
    return segment_total_probability(prediction, line, SHARE_1H)


def first_half_spread_probability(
    prediction: TeamScorePrediction,
    subject_home: bool,
    line: float,
    margin_sigma_full: float,
) -> float:
    return segment_spread_probability(
        prediction, subject_home, line, margin_sigma_full, SHARE_1H)
