"""Conservative resource-cost model that refuses to impute missing compute."""

from __future__ import annotations

from .models import CostEstimate, ResourceBudget, ResourceUsage


def estimate_costs(
    usage: ResourceUsage,
    budget: ResourceBudget,
    *,
    duplication_fraction: float,
    execution_relevance: float,
) -> CostEstimate:
    if not 0.0 <= duplication_fraction <= 1.0:
        raise ValueError("duplication_fraction must be in [0, 1]")
    if not 0.0 <= execution_relevance <= 1.0:
        raise ValueError("execution_relevance must be in [0, 1]")
    critical_unknown = tuple(
        name
        for name in ("cpu_ms", "peak_memory_bytes", "wall_clock_ms")
        if getattr(usage, name) is None
    )
    compute_cost = None
    latency_cost = None
    if not critical_unknown:
        compute_cost = min(
            1.0,
            (
                usage.agent_count / budget.max_agent_count
                + usage.payload_bytes / budget.max_payload_bytes
                + usage.cpu_ms / budget.max_cpu_ms
                + usage.peak_memory_bytes / budget.max_peak_memory_bytes
            )
            / 4.0,
        )
        latency_cost = min(
            1.0,
            float(usage.wall_clock_ms) / budget.max_wall_clock_ms,
        )
    normalized = (
        None
        if compute_cost is None or latency_cost is None
        else round(
            0.5 * compute_cost
            + 0.2 * latency_cost
            + 0.2 * duplication_fraction
            + 0.1 * (1.0 - execution_relevance),
            12,
        )
    )
    return CostEstimate(
        normalized_cost=normalized,
        compute_cost=compute_cost,
        latency_cost=latency_cost,
        duplication_cost=round(duplication_fraction, 12),
        execution_irrelevance_cost=round(1.0 - execution_relevance, 12),
        unmeasured=critical_unknown,
    )
