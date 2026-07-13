"""NFL margin kernel: key-number-aware pricing of winner + spread ladders.

NFL final margins are NOT normal. Field goals (3) and touchdowns (7) make
the margin distribution spike hard on specific numbers -- roughly 10% of
all games land exactly on 3, ~7% on 7, with real mass on 10, 6, 14 and 4.
A normal margin model spreads that mass smoothly and therefore misprices
every spread near a key number (the exact strikes Kalshi lists).

Model: an auditable BASE probability mass function over absolute margins
(long-run NFL frequencies, static and reviewable below), turned into a
signed distribution and **exponentially tilted** so its mean equals the
matchup's expected margin:

    P_mu(m) proportional to base(m) * exp(lambda * m),  lambda solved so
    E[m] = mu (bisection; monotone in lambda).

Tilting preserves the key-number spikes exactly where they are while
shifting probability between the two sides -- the classic failure of
"shift the histogram by mu" (which drags the spike at 3 onto 3+mu) never
happens. Winner and every spread rung then come from ONE distribution:

    P(win)        = P(m > 0) + 0.5 * P(m = 0)   (ties ~0.4%, split)
    P(cover k.5)  = P(m >= k+1)

so the winner cell and the whole spread ladder of the 3x3 conviction
lattice are internally coherent by construction. Totals use a normal over
the matchup's expected total (totals cluster far more weakly than margins;
an empirical total kernel is a later refinement).

Static table + deterministic math = unit-testable to the cell; constants
are candidates for the propose-then-promote tuner, never silently self-fit.
"""
from __future__ import annotations

import math

# Approximate long-run frequencies of NFL FINAL ABSOLUTE margins (curated
# from public historical shapes; the tail beyond 45 folded into 45). The
# table sums to ~0.84 and is renormalized in _signed_base, so the model's
# absolute key-number probabilities run ~19% above these raw entries while
# the RELATIVE spike structure -- where the edge lives -- is preserved
# exactly. Absolute calibration is a propose-then-promote tuning target.
BASE_ABS_MARGIN_PMF: dict[int, float] = {
    1: 0.029, 2: 0.023, 3: 0.098, 4: 0.035, 5: 0.023, 6: 0.044, 7: 0.073,
    8: 0.030, 9: 0.014, 10: 0.053, 11: 0.022, 12: 0.016, 13: 0.022,
    14: 0.044, 15: 0.014, 16: 0.019, 17: 0.028, 18: 0.019, 19: 0.014,
    20: 0.020, 21: 0.027, 22: 0.014, 23: 0.014, 24: 0.016, 25: 0.012,
    26: 0.010, 27: 0.011, 28: 0.012, 29: 0.007, 30: 0.008, 31: 0.008,
    32: 0.006, 33: 0.005, 34: 0.006, 35: 0.006, 36: 0.004, 37: 0.004,
    38: 0.005, 39: 0.003, 40: 0.003, 41: 0.003, 42: 0.003, 43: 0.002,
    44: 0.002, 45: 0.006,
}
TIE_MASS = 0.004  # modern-era tie rate (~0.4% of games)
MAX_MARGIN = 45
# |lambda| = 0.40 corresponds to an expected margin near +/-43 points --
# far beyond any real matchup (EWMAs cap out around +/-25), so the clamp is
# a pure numerical guard rather than a modeling boundary.
LAMBDA_BOUND = 0.40


def _signed_base(base_pmf: dict[int, float]) -> dict[int, float]:
    """Zero-mean signed base PMF: split each |m| across +/-m, tie at 0."""
    signed: dict[int, float] = {0: TIE_MASS}
    for magnitude, mass in base_pmf.items():
        signed[magnitude] = mass / 2.0
        signed[-magnitude] = mass / 2.0
    total = sum(signed.values())
    return {margin: mass / total for margin, mass in signed.items()}


_SIGNED_BASE = _signed_base(BASE_ABS_MARGIN_PMF)
_MARGINS = sorted(_SIGNED_BASE)


def _tilted(lam: float, signed_base: dict[int, float] | None = None) -> dict[int, float]:
    base = signed_base if signed_base is not None else _SIGNED_BASE
    margins = sorted(base) if signed_base is not None else _MARGINS
    weights = {m: base[m] * math.exp(lam * m) for m in margins}
    total = sum(weights.values())
    return {m: w / total for m, w in weights.items()}


def _tilted_mean(lam: float, signed_base: dict[int, float] | None = None) -> float:
    dist = _tilted(lam, signed_base)
    return sum(m * p for m, p in dist.items())


def margin_distribution(
    expected_margin: float, base_pmf: dict[int, float] | None = None,
) -> dict[int, float]:
    """Signed margin PMF whose mean equals ``expected_margin`` (clamped).

    Solved by bisection on the tilt parameter -- the tilted mean is strictly
    increasing in lambda, so the root is unique.

    ``base_pmf`` defaults to ``BASE_ABS_MARGIN_PMF`` (NFL) -- passing a
    different auditable |margin| table (e.g. NCAAF's shallower
    ``BASE_ABS_MARGIN_PMF_COLLEGE`` in autonomy/sports/college.py) reuses
    this exact tilt/bisection machinery unchanged rather than forking it;
    see that module for why this is the DRY-correct reuse path.
    """
    signed_base = _SIGNED_BASE if base_pmf is None else _signed_base(base_pmf)
    target = float(expected_margin)
    low_mean = _tilted_mean(-LAMBDA_BOUND, signed_base)
    high_mean = _tilted_mean(LAMBDA_BOUND, signed_base)
    if target <= low_mean:
        return _tilted(-LAMBDA_BOUND, signed_base)
    if target >= high_mean:
        return _tilted(LAMBDA_BOUND, signed_base)
    low, high = -LAMBDA_BOUND, LAMBDA_BOUND
    for _ in range(60):  # ~1e-18 interval; overkill but cheap and exact
        mid = (low + high) / 2.0
        if _tilted_mean(mid, signed_base) < target:
            low = mid
        else:
            high = mid
    return _tilted((low + high) / 2.0, signed_base)


def win_probability(distribution: dict[int, float]) -> float:
    """P(subject wins) with the tie mass split evenly (OT resolves almost
    all of it in reality; the residual is priced as a coin)."""
    positive = sum(p for m, p in distribution.items() if m > 0)
    return positive + 0.5 * distribution.get(0, 0.0)


def spread_cover_probability(distribution: dict[int, float], line: float) -> float:
    """P(margin > line) -- Kalshi spread strikes are half-points (k.5)."""
    return sum(p for m, p in distribution.items() if m > line)


def normal_over_probability(mean: float, sigma: float, threshold: float) -> float:
    z = (threshold - mean) / max(0.25, sigma)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return min(0.995, max(0.005, 1.0 - cdf))


class NflMarginModel:
    """Joint winner/spread/total pricing for one NFL matchup.

    Consumes the generic team-score EWMAs (expected home/away points) and
    replaces ONLY the distributional shape: margins from the tilted
    key-number kernel, totals from a normal. The winner probability and the
    whole spread ladder come from the same distribution -- lattice-coherent
    by construction.
    """

    TOTAL_SIGMA = 13.5  # NFL total-points dispersion

    def __init__(self, expected_home_score: float, expected_away_score: float):
        self.expected_home_score = float(expected_home_score)
        self.expected_away_score = float(expected_away_score)
        self.expected_margin = self.expected_home_score - self.expected_away_score
        self.expected_total = self.expected_home_score + self.expected_away_score
        self.distribution = margin_distribution(self.expected_margin)

    def home_win_probability(self) -> float:
        # Same clamp band as the cover probabilities: winner >= cover(0.5)
        # must survive clamping too (asymmetric bands could invert them at
        # absurd margins), keeping the lattice coherent everywhere.
        return min(0.995, max(0.005, win_probability(self.distribution)))

    def home_cover_probability(self, line: float) -> float:
        """P(home margin > line); use a negative line for home underdogs."""
        return min(0.995, max(0.005, spread_cover_probability(self.distribution, line)))

    def away_cover_probability(self, line: float) -> float:
        """P(away margin > line) == P(home margin < -line)."""
        return min(0.995, max(0.005, spread_cover_probability(
            {-m: p for m, p in self.distribution.items()}, line)))

    def total_over_probability(self, threshold: float) -> float:
        return normal_over_probability(self.expected_total, self.TOTAL_SIGMA, threshold)
