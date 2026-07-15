"""Regime familiarity and transfer-risk guard."""

from __future__ import annotations

from collections.abc import Mapping

from ._shared import evidence_ids, non_market_families
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def review_regime(context: GuardContext) -> GuardFinding:
    regime_values = tuple(
        value
        for value in context.world_state.get("values", ())
        if isinstance(value, Mapping) and "regime" in str(value.get("field_key", ""))
    )
    present = tuple(value for value in regime_values if value.get("status") == "present")
    if not present:
        return GuardFinding(
            guard=GuardKind.REGIME,
            action=GuardAction.REQUEST_EVIDENCE,
            reason="regime_familiarity_unobserved",
            severity=0.5,
            influence_cap=0.9,
            affected_families=non_market_families(context),
            evidence_ids=evidence_ids(context),
        )
    if any(float(value.get("uncertainty", 1.0)) > 0.5 for value in present):
        return GuardFinding(
            guard=GuardKind.REGIME,
            action=GuardAction.DOWNGRADE,
            reason="regime_state_high_uncertainty",
            severity=0.6,
            influence_cap=0.75,
            affected_families=non_market_families(context),
            evidence_ids=evidence_ids(context),
        )
    return GuardFinding(
        guard=GuardKind.REGIME,
        action=GuardAction.OBSERVE,
        reason="regime_state_present",
        severity=0.0,
        evidence_ids=evidence_ids(context),
    )
