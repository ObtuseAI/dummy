"""Authority, promotion, and execution-boundary guard."""

from __future__ import annotations

from dummy.constitution import RESEARCH_AUTHORITY_CEILING

from ._shared import evidence_ids
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def review_authority(context: GuardContext) -> GuardFinding:
    for message in (context.state, *context.messages):
        payload = message.payload
        expansion = (
            message.authority > RESEARCH_AUTHORITY_CEILING
            or payload.get("execution_authority") is True
            or payload.get("order_submitted") is True
            or payload.get("broker_contacted") is True
            or payload.get("incumbent_substitution_allowed") is True
            or payload.get("automatic_promotion") is True
            or payload.get("promotion_authority", "HUMAN_ONLY") != "HUMAN_ONLY"
        )
        if expansion:
            return GuardFinding(
                guard=GuardKind.AUTHORITY,
                action=GuardAction.TERMINATE,
                reason=f"authority_expansion_detected:{message.message_id}",
                severity=1.0,
                influence_cap=0.0,
                affected_agent_ids=(message.sender,),
                evidence_ids=evidence_ids(context),
            )
    return GuardFinding(
        guard=GuardKind.AUTHORITY,
        action=GuardAction.OBSERVE,
        reason="research_authority_boundary_intact",
        severity=0.0,
        evidence_ids=evidence_ids(context),
    )
