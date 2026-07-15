"""Provenance and explicit-missing-state guard."""

from __future__ import annotations

from collections.abc import Mapping

from ._shared import evidence_ids, non_market_families
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def review_provenance(context: GuardContext) -> GuardFinding:
    values = context.world_state.get("values")
    schema = context.world_state.get("schema", {})
    fields = schema.get("fields", ()) if isinstance(schema, Mapping) else ()
    if not isinstance(values, tuple) or not isinstance(fields, tuple):
        return GuardFinding(
            guard=GuardKind.PROVENANCE,
            action=GuardAction.VETO,
            reason="world_state_values_or_schema_malformed",
            severity=1.0,
            influence_cap=0.0,
            evidence_ids=evidence_ids(context),
        )
    critical = {
        str(field.get("key"))
        for field in fields
        if isinstance(field, Mapping) and field.get("critical") is True
    }
    missing = []
    for value in values:
        if not isinstance(value, Mapping):
            return GuardFinding(
                guard=GuardKind.PROVENANCE,
                action=GuardAction.VETO,
                reason="world_state_value_malformed",
                severity=1.0,
                influence_cap=0.0,
                evidence_ids=evidence_ids(context),
            )
        status = str(value.get("status", ""))
        key = str(value.get("field_key", ""))
        provenance = value.get("provenance", ())
        if status == "present" and not provenance:
            return GuardFinding(
                guard=GuardKind.PROVENANCE,
                action=GuardAction.VETO,
                reason=f"present_state_lacks_provenance:{key}",
                severity=1.0,
                influence_cap=0.0,
                evidence_ids=evidence_ids(context),
            )
        if status != "present":
            if key in critical:
                return GuardFinding(
                    guard=GuardKind.PROVENANCE,
                    action=GuardAction.REQUIRE_ABSTENTION,
                    reason=f"critical_state_unavailable:{key}",
                    severity=1.0,
                    influence_cap=0.0,
                    evidence_ids=evidence_ids(context),
                )
            missing.append(key)
    if missing:
        severity = min(1.0, len(missing) / max(1, len(values)))
        return GuardFinding(
            guard=GuardKind.PROVENANCE,
            action=GuardAction.REQUEST_EVIDENCE,
            reason=f"optional_state_unavailable:{len(missing)}",
            severity=round(severity, 12),
            influence_cap=0.9,
            affected_families=non_market_families(context),
            evidence_ids=evidence_ids(context),
        )
    return GuardFinding(
        guard=GuardKind.PROVENANCE,
        action=GuardAction.OBSERVE,
        reason="provenance_complete",
        severity=0.0,
        evidence_ids=evidence_ids(context),
    )
