"""Future-information and causal-clock leakage guard."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from ._shared import evidence_ids
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def _received_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def review_leakage(context: GuardContext) -> GuardFinding:
    for message in (context.state, *context.messages):
        if message.received_at > context.decision_at or message.issued_at > context.decision_at:
            return GuardFinding(
                guard=GuardKind.LEAKAGE,
                action=GuardAction.REQUIRE_ABSTENTION,
                reason=f"future_message_clock:{message.message_id}",
                severity=1.0,
                influence_cap=0.0,
                evidence_ids=evidence_ids(context),
            )
    for value in context.world_state.get("values", ()):
        if not isinstance(value, Mapping):
            continue
        for provenance in value.get("provenance", ()):
            if not isinstance(provenance, Mapping):
                continue
            received = _received_at(provenance.get("received_at"))
            if received is None:
                return GuardFinding(
                    guard=GuardKind.LEAKAGE,
                    action=GuardAction.REQUIRE_ABSTENTION,
                    reason=f"invalid_world_state_clock:{value.get('field_key')}",
                    severity=1.0,
                    influence_cap=0.0,
                    evidence_ids=evidence_ids(context),
                )
            if received > context.decision_at:
                return GuardFinding(
                    guard=GuardKind.LEAKAGE,
                    action=GuardAction.REQUIRE_ABSTENTION,
                    reason=f"future_world_state_provenance:{value.get('field_key')}",
                    severity=1.0,
                    influence_cap=0.0,
                    evidence_ids=evidence_ids(context),
                )
    return GuardFinding(
        guard=GuardKind.LEAKAGE,
        action=GuardAction.OBSERVE,
        reason="no_future_information_detected",
        severity=0.0,
        evidence_ids=evidence_ids(context),
    )
