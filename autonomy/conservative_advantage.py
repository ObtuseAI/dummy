"""Conservative-advantage haircut stack (Wave-7).

Ascendancy delta #5. Raw measured edge is the OPTIMISTIC quantity; the number
a decision should key on is what survives after every honest deduction:

    conservative = raw_edge
                   - cost
                   - statistical uncertainty        (CI half-width)
                   - selection-bias haircut          (family-size z-inflation)
                   - correlation haircut             (duplicated-thesis shrink)

Selection haircut: when the reported edge was picked from a family of K
candidates, the honest confidence interval is the one a Sidak-corrected
z-score implies -- the half-width scales by z(1 - alpha/(2K)) / z(1 - alpha/2).

Correlation haircut: N opportunities sharing one underlying thesis carry
roughly one thesis's worth of independent evidence; the effective half-width
scales by sqrt(N_group).

Pure math, evidence-only. Consumers attach the breakdown to readiness /
no-edge artifacts; nothing here gates or trades by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

_NORMAL = NormalDist()
DEFAULT_ALPHA = 0.05


def _z(alpha_two_sided: float) -> float:
    return _NORMAL.inv_cdf(1.0 - alpha_two_sided / 2.0)


def selection_z_inflation(family_size: int, alpha: float = DEFAULT_ALPHA) -> float:
    """How much wider the CI must be because the winner was picked from K."""
    k = max(1, int(family_size))
    if k == 1:
        return 1.0
    # Sidak: per-comparison alpha that keeps family-wise alpha at `alpha`.
    per_comparison = 1.0 - (1.0 - alpha) ** (1.0 / k)
    return _z(per_comparison) / _z(alpha)


@dataclass(frozen=True, slots=True)
class ConservativeAdvantage:
    raw_edge: float
    cost: float
    ci_halfwidth: float
    selection_inflation: float
    correlation_inflation: float
    conservative: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_edge": round(self.raw_edge, 6),
            "cost": round(self.cost, 6),
            "ci_halfwidth": round(self.ci_halfwidth, 6),
            "selection_inflation": round(self.selection_inflation, 4),
            "correlation_inflation": round(self.correlation_inflation, 4),
            "conservative_advantage": round(self.conservative, 6),
            "positive": self.conservative > 0,
        }


def conservative_advantage(
    raw_edge: float,
    *,
    ci_halfwidth: float,
    cost: float = 0.0,
    family_size: int = 1,
    correlation_group_n: int = 1,
    alpha: float = DEFAULT_ALPHA,
) -> ConservativeAdvantage:
    """The decision-grade advantage after every honest haircut.

    Units are the caller's (Brier edge, cents per contract, ...); every
    deduction is applied in the same units. ``ci_halfwidth`` is the measured
    95% half-width BEFORE any correction; selection and correlation inflate
    it multiplicatively.
    """
    selection = selection_z_inflation(family_size, alpha)
    correlation = max(1, int(correlation_group_n)) ** 0.5
    effective_halfwidth = max(0.0, float(ci_halfwidth)) * selection * correlation
    conservative = float(raw_edge) - float(cost) - effective_halfwidth
    return ConservativeAdvantage(
        raw_edge=float(raw_edge),
        cost=float(cost),
        ci_halfwidth=float(ci_halfwidth),
        selection_inflation=selection,
        correlation_inflation=correlation,
        conservative=conservative,
    )


def scope_conservative_advantage(
    scope_stats: dict[str, Any],
    *,
    family_size: int = 1,
    correlation_group_n: int = 1,
) -> dict[str, Any] | None:
    """Attach the haircut stack to one backtest scope-stats dict, or None
    when the scope carries no contested CI."""
    ci = scope_stats.get("contested_mean_brier_edge_ci95") or {}
    mean, lower, upper = ci.get("mean"), ci.get("lower"), ci.get("upper")
    if mean is None or lower is None or upper is None:
        return None
    halfwidth = (float(upper) - float(lower)) / 2.0
    return conservative_advantage(
        float(mean), ci_halfwidth=halfwidth,
        family_size=family_size, correlation_group_n=correlation_group_n,
    ).to_dict()
