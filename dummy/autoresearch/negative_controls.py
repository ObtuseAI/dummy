"""Adversarial controls shared by every registered research plugin."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from dummy.world_model.models import digest_json, thaw_json

from .control_models import EvidenceSnapshot, ResearchDefinition


CONTROL_IDS = (
    "finite_numeric_payload",
    "future_leakage_free",
    "forced_coverage_free",
    "no_embedded_authority",
    "point_in_time_verified",
    "source_identity_unique",
)

_AUTHORITY_KEYS = frozenset(
    {
        "automatic_promotion",
        "capital_authority",
        "code_mutation_authority",
        "deployment_authority",
        "execution_authority",
        "orders_placed",
        "promotion_authority",
        "risk_write_authority",
        "runtime_application",
        "source_edit_applied",
        "weight_write_authority",
    }
)
_FUTURE_KEYS = frozenset(
    {
        "candidate_used_future_evidence",
        "future_evidence_used",
        "future_leakage",
        "lookahead",
    }
)
_FORCED_KEYS = frozenset(
    {
        "forced_coverage",
        "forced_forecast",
        "abstention_overridden",
    }
)


def _walk(value: Any):
    yield value
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _walk(item)


def _all_finite(value: Any) -> bool:
    for item in _walk(value):
        if isinstance(item, float) and not math.isfinite(item):
            return False
    return True


def _no_truthy_keys(value: Any, keys: frozenset[str]) -> bool:
    for item in _walk(value):
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and item[0].strip().lower() in keys
            and bool(item[1])
        ):
            return False
    return True


def evaluate_evidence_controls(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> dict[str, bool]:
    """Evaluate fail-closed checks over the immutable worker input."""
    payload = thaw_json(evidence.payload)
    return {
        "finite_numeric_payload": _all_finite(payload),
        "future_leakage_free": _no_truthy_keys(payload, _FUTURE_KEYS),
        "forced_coverage_free": _no_truthy_keys(payload, _FORCED_KEYS),
        "no_embedded_authority": _no_truthy_keys(payload, _AUTHORITY_KEYS),
        "point_in_time_verified": evidence.point_in_time_verified,
        "source_identity_unique": (
            len(set(evidence.source_ids)) == len(evidence.source_ids)
            and len(set(evidence.source_family_ids))
            == len(evidence.source_family_ids)
        ),
        "definition_requires_registered_controls": set(
            definition.required_control_ids
        ).issubset(CONTROL_IDS),
    }


def adversarial_canary_controls(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> dict[str, bool]:
    """Prove that the detector rejects synthetic leakage and authority canaries."""

    def canary_payload(extra: Mapping[str, Any]) -> EvidenceSnapshot:
        payload = thaw_json(evidence.payload)
        payload["__negative_control_canary__"] = dict(extra)
        return EvidenceSnapshot.create(
            domain_id=evidence.domain_id,
            captured_at=evidence.captured_at,
            source_ids=evidence.source_ids,
            source_family_ids=evidence.source_family_ids,
            payload=payload,
            point_in_time_verified=evidence.point_in_time_verified,
            settlement_verified=evidence.settlement_verified,
        )

    future = evaluate_evidence_controls(
        definition,
        canary_payload({"candidate_used_future_evidence": True}),
    )
    forced = evaluate_evidence_controls(
        definition,
        canary_payload({"forced_coverage": True}),
    )
    authority = evaluate_evidence_controls(
        definition,
        canary_payload({"execution_authority": True}),
    )
    return {
        "future_leakage_canary_detected": not future["future_leakage_free"],
        "forced_coverage_canary_detected": not forced["forced_coverage_free"],
        "authority_canary_detected": not authority["no_embedded_authority"],
        "deterministic_input_digest": (
            digest_json(evidence.semantic_dict())
            == digest_json(evidence.semantic_dict())
        ),
    }


def run_negative_control_suite(
    definition: ResearchDefinition,
    evidence: EvidenceSnapshot,
) -> dict[str, Any]:
    evidence_checks = evaluate_evidence_controls(definition, evidence)
    canary_checks = adversarial_canary_controls(definition, evidence)
    checks = {**evidence_checks, **canary_checks}
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "required_control_ids": list(definition.required_control_ids),
        "control_suite_version": "dummy-negative-controls-v1",
    }


__all__ = [
    "CONTROL_IDS",
    "adversarial_canary_controls",
    "evaluate_evidence_controls",
    "run_negative_control_suite",
]
