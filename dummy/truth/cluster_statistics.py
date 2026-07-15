"""Deterministic event-cluster statistics for causal forecast comparisons."""

from __future__ import annotations

import hashlib
import itertools
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from dummy.world_model.models import canonical_json


class TruthValidationError(ValueError):
    """Causal truth evidence is malformed or statistically incoherent."""


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise TruthValidationError("quantile requires observations")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


@dataclass(frozen=True, slots=True)
class ClusterStatistic:
    row_count: int
    event_cluster_count: int
    observed_mean: float | None
    confidence_interval: tuple[float, float] | None
    one_sided_p_value: float | None
    bootstrap_simulations: int
    permutation_draws: int
    method: str = "event_cluster_mean_bootstrap_and_sign_flip"

    @property
    def positive_interval(self) -> bool:
        return bool(
            self.confidence_interval is not None
            and self.confidence_interval[0] > 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "event_cluster_count": self.event_cluster_count,
            "observed_mean": self.observed_mean,
            "confidence_interval": (
                list(self.confidence_interval)
                if self.confidence_interval is not None
                else None
            ),
            "one_sided_p_value": self.one_sided_p_value,
            "bootstrap_simulations": self.bootstrap_simulations,
            "permutation_draws": self.permutation_draws,
            "method": self.method,
            "positive_interval": self.positive_interval,
        }


def clustered_mean_test(
    rows: tuple[tuple[str, float], ...],
    *,
    bootstrap_simulations: int = 4_000,
    permutation_draws: int = 8_000,
) -> ClusterStatistic:
    if bootstrap_simulations < 1_000 or permutation_draws < 1_000:
        raise TruthValidationError("cluster inference requires at least 1,000 draws")
    grouped: dict[str, list[float]] = defaultdict(list)
    for cluster, value in rows:
        cluster = str(cluster).strip()
        parsed = float(value)
        if not cluster or not math.isfinite(parsed):
            raise TruthValidationError("cluster rows require finite identified values")
        grouped[cluster].append(parsed)
    cluster_means = tuple(
        sum(grouped[key]) / len(grouped[key]) for key in sorted(grouped)
    )
    if not cluster_means:
        return ClusterStatistic(
            row_count=0,
            event_cluster_count=0,
            observed_mean=None,
            confidence_interval=None,
            one_sided_p_value=None,
            bootstrap_simulations=bootstrap_simulations,
            permutation_draws=permutation_draws,
        )
    observed = sum(cluster_means) / len(cluster_means)
    seed_payload = {
        "clusters": [
            {"cluster": key, "values": grouped[key]} for key in sorted(grouped)
        ],
        "bootstrap_simulations": bootstrap_simulations,
        "permutation_draws": permutation_draws,
    }
    seed = int(
        hashlib.sha256(canonical_json(seed_payload).encode("utf-8")).hexdigest()[:16],
        16,
    )
    generator = random.Random(seed)
    n = len(cluster_means)
    bootstrap = [
        sum(generator.choice(cluster_means) for _ in range(n)) / n
        for _ in range(bootstrap_simulations)
    ]
    interval = (
        round(_quantile(bootstrap, 0.025), 12),
        round(_quantile(bootstrap, 0.975), 12),
    )
    if n <= 16:
        null_means = (
            sum(value * sign for value, sign in zip(cluster_means, signs, strict=True))
            / n
            for signs in itertools.product((-1.0, 1.0), repeat=n)
        )
        exceedances = 0
        draws = 0
        for null_mean in null_means:
            draws += 1
            exceedances += null_mean >= observed - 1e-15
        p_value = exceedances / draws
    else:
        exceedances = 0
        draws = permutation_draws
        for _ in range(draws):
            null_mean = sum(
                value * (-1.0 if generator.random() < 0.5 else 1.0)
                for value in cluster_means
            ) / n
            exceedances += null_mean >= observed - 1e-15
        p_value = (exceedances + 1) / (draws + 1)
    return ClusterStatistic(
        row_count=len(rows),
        event_cluster_count=n,
        observed_mean=round(observed, 12),
        confidence_interval=interval,
        one_sided_p_value=round(p_value, 12),
        bootstrap_simulations=bootstrap_simulations,
        permutation_draws=draws,
    )


__all__ = ["ClusterStatistic", "TruthValidationError", "clustered_mean_test"]
