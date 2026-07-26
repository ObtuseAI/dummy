"""Shared confidence intervals and dependency-cluster sign tests."""
from __future__ import annotations

import math
from typing import Any, Sequence

_MAX_EXACT_SIGN_TEST_CLUSTERS = 1_024


def mean_ci95(
    values: Sequence[float], *, collapse_single: bool = False
) -> dict[str, Any] | None:
    """Mean with a 95% normal CI.

    A single sample has no dispersion estimate: bounds are ``None`` unless
    ``collapse_single`` is set, in which case they collapse to the mean.
    """
    if not values:
        return None
    numbers = [float(value) for value in values]
    mean = sum(numbers) / len(numbers)
    if len(numbers) < 2:
        bound = round(mean, 6) if collapse_single else None
        return {
            "mean": round(mean, 6),
            "lower": bound,
            "upper": bound,
            "n": len(numbers),
            "method": "normal_mean_95",
        }
    variance = sum((value - mean) ** 2 for value in numbers) / (len(numbers) - 1)
    half = 1.96 * math.sqrt(variance / len(numbers))
    return {
        "mean": round(mean, 6),
        "lower": round(mean - half, 6),
        "upper": round(mean + half, 6),
        "n": len(numbers),
        "method": "normal_mean_95",
    }


def one_sided_sign_test(
    values: Sequence[float],
    *,
    alternative: str = "greater",
    zero_tolerance: float = 1e-15,
) -> dict[str, Any]:
    """Exact one-sided sign test over independent dependency-cluster values.

    Repeated emissions from one event must be reduced to one value before this
    helper is called. Under the null, a non-zero cluster is equally likely to
    have either sign. Ties are removed, and the exact ``Binomial(n, 0.5)``
    upper tail is evaluated with integer arithmetic.
    """
    if alternative not in {"greater", "less"}:
        raise ValueError("alternative must be 'greater' or 'less'")
    tolerance = float(zero_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("zero_tolerance must be finite and non-negative")
    parsed = [float(value) for value in values]
    if any(not math.isfinite(value) for value in parsed):
        raise ValueError("sign-test values must be finite")
    nonzero = [value for value in parsed if abs(value) > tolerance]
    n = len(nonzero)
    if n == 0:
        return {
            "p_value": 1.0,
            "successes": 0,
            "nonzero_clusters": 0,
            "ties": len(parsed),
            "alternative": alternative,
            "method": "exact_one_sided_dependency_cluster_sign_test",
        }
    successes = sum(
        value > 0.0 if alternative == "greater" else value < 0.0
        for value in nonzero
    )
    if n <= _MAX_EXACT_SIGN_TEST_CLUSTERS:
        denominator = 1 << n
        if successes <= n // 2:
            # The requested upper tail is large. Its strict lower complement
            # has fewer terms than the requested tail.
            lower = sum(math.comb(n, count) for count in range(successes))
            p_value = 1.0 - lower / denominator
        else:
            upper = sum(
                math.comb(n, count) for count in range(successes, n + 1)
            )
            p_value = upper / denominator
        method = "exact_one_sided_dependency_cluster_sign_test"
    else:
        # Exact integer tails become super-linear at production-scale cluster
        # counts. The continuity-corrected normal limit is conservative enough
        # for the large-n regime and keeps the nightly backtest bounded.
        z_score = (
            successes - 0.5 - 0.5 * n
        ) / math.sqrt(0.25 * n)
        p_value = 0.5 * math.erfc(z_score / math.sqrt(2.0))
        method = (
            "continuity_corrected_normal_one_sided_dependency_cluster_sign_test"
        )
    if p_value == 0.0:
        p_value = math.ulp(0.0)
    return {
        "p_value": min(1.0, max(0.0, float(p_value))),
        "successes": successes,
        "nonzero_clusters": n,
        "ties": len(parsed) - n,
        "alternative": alternative,
        "method": method,
    }


__all__ = ["mean_ci95", "one_sided_sign_test"]
