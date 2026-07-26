"""Correlation-aware parlay / combo fair-value engine (Wave-10).

A combo (parlay) pays only if EVERY leg hits. The tempting way to price it is the
independence product ``prod(p_i)`` -- and that is roughly how sportsbooks and
Kalshi's combo builder quote same-game combos. But the legs fans actually stack
are the correlated ones: "Yankees win" + "Yankees team total over" + "Yankees
win the first five" all move together with one latent thing -- did the Yankees
dominate? When legs are positively correlated the model's joint probability is
higher than the product, so an independence-priced combo can look underpriced.
That is an uncalibrated challenger observation, never evidence or authority to
buy it.

Model: a one-factor Gaussian copula, per game. Each leg i has fair probability
``p_i`` and a signed loading ``a_i`` on a shared per-game "home dominance" factor
F ~ N(0,1): latent ``X_i = a_i F + sqrt(1 - a_i^2) eps_i`` and the leg hits when
``X_i <= z_i`` with ``z_i = Phi^{-1}(p_i)`` (so the marginal stays exactly p_i).
Legs on the SAME game share F (pairwise corr a_i a_j); legs on DIFFERENT games
get independent factors, so cross-game combos price at the product. The joint is
the 1-D integral ``\\int phi(f) prod_i Phi((z_i - a_i f)/sqrt(1-a_i^2)) df``,
evaluated on a fixed standard-normal grid -- no SciPy.

Everything here is descriptive fair value. Parlays are challenger-only evidence
and NEVER auto-staked: combos multiply both edge and variance, so committing
capital to one stays a human-gated action exactly like every other execution
decision in this system.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from autonomy.sports_markets import SPREAD, TEAM_TOTAL, TOTAL, WINNER

# Loadings sit strictly inside (-1, 1); this cap keeps sqrt(1 - a^2) well away
# from zero (numerical safety) and reflects that no single leg is a perfect
# proxy for the whole game script.
_MAX_LOADING = 0.9
# Fixed standard-normal integration grid (scipy-free). +-6 sigma at 0.05 covers
# the mass to ~1e-9; the joint integrand is smooth so this is ample.
_GRID_LIMIT = 6.0
_GRID_STEP = 0.05


def _phi(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation, scipy-free).
    Accurate to ~1e-9 on (0,1); clamps the open interval so callers never pass 0/1."""
    p = min(1 - 1e-12, max(1e-12, p))
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


@dataclass(frozen=True)
class ParlayLeg:
    """One combo leg plus optional, explicit settlement semantics.

    ``identity`` names the selected proposition (``ticker`` is the legacy
    fallback). ``outcome`` names its member inside ``exclusivity_group``.
    Different explicit outcomes in the same group cannot both settle true.
    Fields are appended to preserve every existing positional constructor.
    Free-text ``description`` is never parsed for safety decisions.
    """

    description: str
    fair_prob: float
    loading: float = 0.0        # signed loading on the same-game dominance factor
    game_id: str | None = None  # legs sharing a game_id share the latent factor
    ticker: str | None = None
    identity: str | None = None
    outcome: str | None = None
    exclusivity_group: str | None = None


@dataclass(frozen=True)
class ParlayPricing:
    fair_prob: float            # correlation-aware joint P(all legs hit)
    naive_prob: float           # independence product prod(p_i)
    correlation_premium: float  # fair - naive (positive => legs reinforce)
    n_legs: int
    edge: float | None = None   # fair - combo_price, when a market price is given
    combo_price: float | None = None
    features: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _SemanticAnalysis:
    legs: tuple[ParlayLeg, ...]
    duplicate_legs_collapsed: int
    duplicate_conflicts: int
    contradiction_reasons: tuple[str, ...]
    explicit_identities: int
    explicit_outcomes: int
    explicit_exclusivity_groups: int

    @property
    def contradictory(self) -> bool:
        return bool(self.contradiction_reasons)


def _semantic_text(value: str | None) -> str | None:
    parsed = str(value or "").strip().casefold()
    return parsed or None


def _semantic_identity(leg: ParlayLeg) -> tuple[str, str] | None:
    """Stable proposition key, scoped by game when one is available."""
    identity = _semantic_text(leg.identity) or _semantic_text(leg.ticker)
    if identity is None:
        return None
    return (_semantic_text(leg.game_id) or "", identity)


def _exclusive_group(leg: ParlayLeg) -> tuple[str, str] | None:
    group = _semantic_text(leg.exclusivity_group)
    if group is None:
        return None
    return (_semantic_text(leg.game_id) or "", group)


def _merge_duplicate(held: ParlayLeg, incoming: ParlayLeg) -> tuple[ParlayLeg, bool]:
    """Collapse one proposition conservatively when duplicate estimates differ.

    Exact copies return unchanged. Conflicting marginal estimates keep the
    lower fair probability, and conflicting loadings are neutralized rather
    than inventing correlation. ``price_parlay`` discloses the conflict.
    """
    held_group = _semantic_text(held.exclusivity_group)
    incoming_group = _semantic_text(incoming.exclusivity_group)
    conflict = (
        held.fair_prob != incoming.fair_prob
        or held.loading != incoming.loading
        or held_group != incoming_group
    )
    if not conflict:
        return held, False
    return (
        ParlayLeg(
            description=held.description,
            fair_prob=min(held.fair_prob, incoming.fair_prob),
            loading=held.loading if held.loading == incoming.loading else 0.0,
            game_id=held.game_id,
            ticker=held.ticker or incoming.ticker,
            identity=held.identity or incoming.identity,
            outcome=held.outcome or incoming.outcome,
            exclusivity_group=(
                held.exclusivity_group if held_group == incoming_group else None
            ),
        ),
        True,
    )


def _analyze_semantics(legs: list[ParlayLeg]) -> _SemanticAnalysis:
    """Normalize provable semantics without guessing from descriptions."""
    identity_outcomes: dict[tuple[str, str], set[str]] = {}
    exclusive_outcomes: dict[tuple[str, str], set[str]] = {}
    explicit_identities = explicit_outcomes = explicit_groups = 0

    for leg in legs:
        identity = _semantic_identity(leg)
        outcome = _semantic_text(leg.outcome)
        group = _exclusive_group(leg)
        if identity is not None:
            explicit_identities += 1
        if outcome is not None:
            explicit_outcomes += 1
        if group is not None:
            explicit_groups += 1
        if identity is not None and outcome is not None:
            identity_outcomes.setdefault(identity, set()).add(outcome)
        if group is not None and outcome is not None:
            exclusive_outcomes.setdefault(group, set()).add(outcome)

    reasons = {
        f"identity:{game_id}:{identity}"
        for (game_id, identity), outcomes in identity_outcomes.items()
        if len(outcomes) > 1
    }
    reasons.update(
        f"exclusivity_group:{game_id}:{group}"
        for (game_id, group), outcomes in exclusive_outcomes.items()
        if len(outcomes) > 1
    )

    effective: list[ParlayLeg] = []
    seen: dict[tuple[tuple[str, str], str], int] = {}
    duplicate_count = duplicate_conflicts = 0
    for leg in legs:
        identity = _semantic_identity(leg)
        if identity is None:
            effective.append(leg)
            continue
        # Missing outcomes still describe the legacy selected proposition.
        predicate = (identity, _semantic_text(leg.outcome) or "__selected__")
        held_index = seen.get(predicate)
        if held_index is None:
            seen[predicate] = len(effective)
            effective.append(leg)
            continue
        duplicate_count += 1
        merged, conflict = _merge_duplicate(effective[held_index], leg)
        effective[held_index] = merged
        duplicate_conflicts += int(conflict)

    return _SemanticAnalysis(
        legs=tuple(effective),
        duplicate_legs_collapsed=duplicate_count,
        duplicate_conflicts=duplicate_conflicts,
        contradiction_reasons=tuple(sorted(reasons)),
        explicit_identities=explicit_identities,
        explicit_outcomes=explicit_outcomes,
        explicit_exclusivity_groups=explicit_groups,
    )


def alignment_loading(market_type: str, segment: str, subject_is_home: bool | None) -> float:
    """Signed loading of a leg on its game's "home dominates" factor.

    Margin-family legs (who wins / by how much / a team's own scoring) load
    strongly and with a clear sign: backing the home side is +, the away side -.
    Combined-total legs (game or first-five over/under) are only weakly tied to
    WHO wins -- they track the scoring environment, a mostly separate axis -- so
    they get a small loading. Capturing total<->total correlation precisely is
    the queued two-factor refinement; under-loading them here is the honest,
    conservative choice (it never invents correlation that is not there)."""
    if market_type in (WINNER, SPREAD, TEAM_TOTAL):
        if subject_is_home is None:
            return 0.0
        base = 0.72 if segment == "full" else 0.6   # first-five is noisier
        return base if subject_is_home else -base
    if market_type == TOTAL:
        return 0.15   # weak, sign-agnostic tie to scoring; near-independent of margin
    return 0.0


def _clamp_loading(a: float) -> float:
    return max(-_MAX_LOADING, min(_MAX_LOADING, a))


def _one_factor_joint(legs: list[ParlayLeg]) -> float:
    """P(all same-game legs hit) under the shared one-factor copula."""
    if not legs:
        return 1.0
    if len(legs) == 1:
        return min(1.0, max(0.0, legs[0].fair_prob))
    zs = [normal_ppf(leg.fair_prob) for leg in legs]
    loadings = [_clamp_loading(leg.loading) for leg in legs]
    roots = [math.sqrt(1.0 - a * a) for a in loadings]
    total = 0.0
    weight_sum = 0.0
    f = -_GRID_LIMIT
    while f <= _GRID_LIMIT + 1e-9:
        w = _phi(f)
        prod = 1.0
        for z, a, root in zip(zs, loadings, roots):
            prod *= normal_cdf((z - a * f) / root)
        total += w * prod
        weight_sum += w
        f += _GRID_STEP
    # Normalise by the grid's captured mass so truncation at +-6 sigma is unbiased.
    return min(1.0, max(0.0, total / weight_sum))


def _joint_probability_effective(legs: tuple[ParlayLeg, ...]) -> float:
    if not legs:
        return 1.0
    groups: dict[str, list[ParlayLeg]] = {}
    solo = 0
    for leg in legs:
        # A leg with no game_id is treated as its own independent group.
        key = leg.game_id if leg.game_id is not None else f"__solo_{solo}"
        if leg.game_id is None:
            solo += 1
        groups.setdefault(key, []).append(leg)
    joint = 1.0
    for group in groups.values():
        joint *= _one_factor_joint(group)
    return min(1.0, max(0.0, joint))


def joint_probability(legs: list[ParlayLeg]) -> float:
    """Correlation-aware P(every leg hits), after semantic feasibility checks.

    Only explicit identity/outcome/group metadata can force a zero. Legacy
    legs retain the prior copula behavior; descriptions are never guessed.
    """
    analysis = _analyze_semantics(legs)
    if analysis.contradictory:
        return 0.0
    return _joint_probability_effective(analysis.legs)


def _naive_independent_effective(legs: tuple[ParlayLeg, ...]) -> float:
    prob = 1.0
    for leg in legs:
        prob *= min(1.0, max(0.0, leg.fair_prob))
    return prob


def naive_independent(legs: list[ParlayLeg]) -> float:
    """Independence baseline after duplicate and feasibility normalization."""
    analysis = _analyze_semantics(legs)
    if analysis.contradictory:
        return 0.0
    return _naive_independent_effective(analysis.legs)


def price_parlay(legs: list[ParlayLeg], combo_price: float | None = None) -> ParlayPricing:
    """Full fair-value view of a combo: correlation-aware joint, the independence
    baseline, their gap, and -- when a combo price is supplied -- the edge.

    A positive edge remains uncalibrated challenger evidence only; never an
    instruction or authority to stake."""
    analysis = _analyze_semantics(legs)
    effective_legs = analysis.legs
    if analysis.contradictory:
        fair = naive = 0.0
    else:
        fair = _joint_probability_effective(effective_legs)
        naive = _naive_independent_effective(effective_legs)
    edge = None if combo_price is None else fair - combo_price
    if analysis.contradictory:
        semantic_status = "MUTUALLY_EXCLUSIVE"
        pricing_status = "IMPOSSIBLE_MUTUALLY_EXCLUSIVE"
    elif (
        analysis.explicit_identities == len(legs)
        and analysis.explicit_outcomes == len(legs)
        and analysis.explicit_exclusivity_groups == len(legs)
    ):
        semantic_status = "EXPLICIT_CHECKED"
        pricing_status = "UNCALIBRATED"
    elif analysis.explicit_identities or analysis.explicit_outcomes:
        semantic_status = "EXPLICIT_PARTIAL"
        pricing_status = "UNCALIBRATED"
    else:
        semantic_status = "LEGACY_UNCHECKED"
        pricing_status = "UNCALIBRATED"
    return ParlayPricing(
        fair_prob=fair,
        naive_prob=naive,
        correlation_premium=fair - naive,
        n_legs=len(effective_legs),
        edge=edge,
        combo_price=combo_price,
        features={
            "challenger_only": True,
            "calibration_status": "UNCALIBRATED",
            "pricing_status": pricing_status,
            "semantic_status": semantic_status,
            "execution_authority": False,
            "promotion_authority": False,
            "same_game": len({
                leg.game_id for leg in effective_legs if leg.game_id is not None
            }) == 1 and all(leg.game_id is not None for leg in effective_legs),
            "n_legs": len(effective_legs),
            "input_legs": len(legs),
            "effective_legs": len(effective_legs),
            "duplicate_legs_collapsed": analysis.duplicate_legs_collapsed,
            "duplicate_conflicts": analysis.duplicate_conflicts,
            "contradiction_reasons": list(analysis.contradiction_reasons),
            "explicit_identities": analysis.explicit_identities,
            "explicit_outcomes": analysis.explicit_outcomes,
            "explicit_exclusivity_groups": analysis.explicit_exclusivity_groups,
        },
    )
