"""Deterministic resource-budget guard."""

from __future__ import annotations

from ._shared import evidence_ids, non_market_families
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def review_resources(context: GuardContext) -> GuardFinding:
    ratios: list[float] = []
    unmeasured: list[str] = []
    for key, budget in context.resource_budget.items():
        usage = context.resource_usage.get(key)
        if usage is None:
            unmeasured.append(key)
            continue
        ratio = float(usage) / float(budget)
        ratios.append(ratio)
        if ratio > 1.0:
            return GuardFinding(
                guard=GuardKind.RESOURCE,
                action=GuardAction.TERMINATE,
                reason=f"resource_budget_exceeded:{key}",
                severity=1.0,
                influence_cap=0.0,
                affected_families=non_market_families(context),
                evidence_ids=evidence_ids(context),
            )
    if unmeasured:
        return GuardFinding(
            guard=GuardKind.RESOURCE,
            action=GuardAction.REQUEST_EVIDENCE,
            reason=f"critical_resource_unmeasured:{','.join(sorted(unmeasured))}",
            severity=0.5,
            influence_cap=0.8,
            affected_families=non_market_families(context),
            evidence_ids=evidence_ids(context),
        )
    peak = max(ratios, default=0.0)
    if peak >= 0.8:
        return GuardFinding(
            guard=GuardKind.RESOURCE,
            action=GuardAction.DOWNGRADE,
            reason="resource_budget_near_limit",
            severity=round(peak, 12),
            influence_cap=0.8,
            affected_families=non_market_families(context),
            evidence_ids=evidence_ids(context),
        )
    return GuardFinding(
        guard=GuardKind.RESOURCE,
        action=GuardAction.OBSERVE,
        reason="measured_resources_within_budget",
        severity=round(peak, 12),
        evidence_ids=evidence_ids(context),
    )
