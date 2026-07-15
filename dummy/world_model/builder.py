"""Causal, fail-closed hydration of immutable world-state snapshots."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .models import (
    ContradictionSeverity,
    ValueStatus,
    WorldContradiction,
    WorldHydrationError,
    WorldModelValidationError,
    WorldObservation,
    WorldStateSchema,
    WorldStateSnapshot,
    WorldStateValue,
    digest_json,
    thaw_json,
    utc,
)


def _contradiction(
    *,
    fields: tuple[str, ...],
    severity: ContradictionSeverity,
    reason: str,
    evidence_ids: tuple[str, ...],
) -> WorldContradiction:
    semantic = {
        "fields": sorted(fields),
        "severity": severity.value,
        "reason": reason,
        "evidence_ids": sorted(evidence_ids),
    }
    return WorldContradiction(
        contradiction_id=digest_json(semantic),
        field_keys=fields,
        severity=severity,
        reason=reason,
        evidence_ids=evidence_ids,
    )


def _resolve_group(
    observations: tuple[WorldObservation, ...],
) -> tuple[tuple[WorldObservation, ...], bool]:
    """Return causally ordered observations and whether they conflict."""

    ordered = tuple(
        sorted(observations, key=lambda item: (item.received_at, item.revision_id))
    )
    if len(ordered) == 1:
        return ordered, False
    values = {digest_json({"value": thaw_json(item.value)}) for item in ordered}
    semantics = {
        (
            item.layer,
            item.transform_version,
            item.probability,
            item.calibration_identity,
            item.mapping_evidence_ids,
        )
        for item in ordered
    }
    if len(values) == 1 and len(semantics) == 1:
        return ordered, False
    revision_ids = {item.revision_id for item in ordered}
    roots = tuple(item for item in ordered if item.supersedes_revision_id is None)
    if len(roots) != 1:
        return ordered, True
    by_parent: dict[str, list[WorldObservation]] = defaultdict(list)
    for item in ordered:
        if item.supersedes_revision_id is not None:
            if item.supersedes_revision_id not in revision_ids:
                return ordered, True
            by_parent[item.supersedes_revision_id].append(item)
    if any(len(children) != 1 for children in by_parent.values()):
        return ordered, True
    walked = [roots[0]]
    while walked[-1].revision_id in by_parent:
        walked.append(by_parent[walked[-1].revision_id][0])
    if len(walked) != len(ordered):
        return ordered, True
    if any(
        child.received_at < parent.received_at
        for parent, child in zip(walked, walked[1:], strict=False)
    ):
        return ordered, True
    return tuple(walked), False


def _present(values: dict[str, WorldStateValue], key: str) -> Any | None:
    item = values[key]
    return thaw_json(item.value) if item.status is ValueStatus.PRESENT else None


def _book_contradictions(
    values: dict[str, WorldStateValue],
) -> tuple[WorldContradiction, ...]:
    keys = (
        "market.yes_bid_cents",
        "market.yes_ask_cents",
        "market.no_bid_cents",
        "market.no_ask_cents",
    )
    if any(_present(values, key) is None for key in keys):
        return ()
    yes_bid, yes_ask, no_bid, no_ask = (int(_present(values, key)) for key in keys)
    evidence_ids = tuple(
        provenance.evidence_id
        for key in keys
        for provenance in values[key].provenance
    )
    contradictions: list[WorldContradiction] = []
    if not (
        1 <= yes_bid <= yes_ask <= 99
        and 1 <= no_bid <= no_ask <= 99
    ):
        contradictions.append(
            _contradiction(
                fields=keys,
                severity=ContradictionSeverity.BLOCKING,
                reason="crossed_or_out_of_bounds_two_sided_book",
                evidence_ids=evidence_ids,
            )
        )
    if yes_ask + no_bid != 100 or yes_bid + no_ask != 100:
        contradictions.append(
            _contradiction(
                fields=keys,
                severity=ContradictionSeverity.BLOCKING,
                reason="yes_no_quotes_are_not_complementary",
                evidence_ids=evidence_ids,
            )
        )
    return tuple(contradictions)


def build_world_snapshot(
    *,
    schema: WorldStateSchema,
    market_id: str,
    as_of: datetime,
    policy_version: str,
    observations: tuple[WorldObservation, ...],
) -> WorldStateSnapshot:
    """Freeze one exact schema version using only evidence received by ``as_of``."""

    decision_time = utc(as_of)
    ordered = tuple(
        sorted(
            observations,
            key=lambda item: (item.field_key, item.received_at, item.revision_id),
        )
    )
    if not ordered:
        raise WorldHydrationError("world snapshot requires observations")
    revision_ids = tuple(item.revision_id for item in ordered)
    if len(set(revision_ids)) != len(revision_ids):
        raise WorldModelValidationError("world observation revision_ids must be unique")
    grouped: dict[str, list[WorldObservation]] = defaultdict(list)
    for item in ordered:
        try:
            spec = schema.field(item.field_key)
        except WorldModelValidationError as exc:
            raise WorldHydrationError(
                f"observation is outside resolved schema: {item.field_key}"
            ) from exc
        if item.received_at > decision_time:
            raise WorldHydrationError(
                f"future-received observation entered hydration: {item.evidence_id}"
            )
        if item.unit != spec.unit:
            raise WorldHydrationError(
                f"observation unit differs from schema for {item.field_key}"
            )
        if item.layer not in spec.allowed_layers:
            raise WorldHydrationError(
                f"observation layer is not allowed for {item.field_key}"
            )
        grouped[item.field_key].append(item)

    values: dict[str, WorldStateValue] = {}
    contradictions: list[WorldContradiction] = []
    for spec in schema.fields:
        candidates = tuple(grouped.get(spec.key, ()))
        if not candidates:
            values[spec.key] = WorldStateValue.missing(
                spec,
                status=ValueStatus.MISSING,
                reason="no_verified_point_in_time_observation",
                limitations=("value_not_imputed",),
            )
            continue
        resolved, conflicted = _resolve_group(candidates)
        if conflicted:
            severity = (
                ContradictionSeverity.BLOCKING
                if spec.critical
                else ContradictionSeverity.WARNING
            )
            contradictions.append(
                _contradiction(
                    fields=(spec.key,),
                    severity=severity,
                    reason="unlinked_observations_disagree",
                    evidence_ids=tuple(item.evidence_id for item in candidates),
                )
            )
            values[spec.key] = WorldStateValue.missing(
                spec,
                status=ValueStatus.CONTRADICTED,
                reason="unresolved_observation_conflict",
                limitations=("conflicting_values_not_arbitrarily_selected",),
            )
            continue
        candidate = WorldStateValue.from_observations(spec, resolved)
        if candidate.valid_until is None or candidate.valid_until < decision_time:
            values[spec.key] = WorldStateValue.missing(
                spec,
                status=ValueStatus.STALE,
                reason="observation_lease_expired_before_decision",
                limitations=("stale_value_not_carried_forward",),
            )
        else:
            values[spec.key] = candidate

    status = _present(values, "market.status")
    if status is not None and str(status).lower() not in {"open", "active"}:
        contradictions.append(
            _contradiction(
                fields=("market.status",),
                severity=ContradictionSeverity.BLOCKING,
                reason="market_is_not_open_at_decision",
                evidence_ids=tuple(
                    item.evidence_id
                    for item in values["market.status"].provenance
                ),
            )
        )
    contradictions.extend(_book_contradictions(values))
    source_digest = digest_json(
        {"observations": [item.to_dict() for item in ordered]}
    )
    frozen_values = tuple(values[item.key] for item in schema.fields)
    frozen_contradictions = tuple(contradictions)
    snapshot_id = WorldStateSnapshot.identity_for(
        schema=schema,
        market_id=market_id,
        as_of=decision_time,
        policy_version=policy_version,
        values=frozen_values,
        contradictions=frozen_contradictions,
        source_observation_digest=source_digest,
    )
    snapshot = WorldStateSnapshot(
        snapshot_id=snapshot_id,
        schema=schema,
        market_id=market_id,
        as_of=decision_time,
        policy_version=policy_version,
        values=frozen_values,
        contradictions=frozen_contradictions,
        source_observation_digest=source_digest,
    )
    snapshot.assert_usable(decision_time)
    return snapshot
