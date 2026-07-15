"""Source-family duplication and alias-influence guard."""

from __future__ import annotations

from collections import defaultdict

from ._shared import evidence_ids, family, forecast_messages
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def review_duplication(context: GuardContext) -> GuardFinding:
    by_family: dict[str, list[str]] = defaultdict(list)
    for message in forecast_messages(context):
        source_family = family(message)
        if not source_family:
            return GuardFinding(
                guard=GuardKind.DUPLICATION,
                action=GuardAction.VETO,
                reason=f"forecast_source_family_missing:{message.sender}",
                severity=1.0,
                influence_cap=0.0,
                affected_agent_ids=(message.sender,),
                evidence_ids=evidence_ids(context),
            )
        by_family[source_family].append(message.sender)
    duplicated = {key: value for key, value in by_family.items() if len(value) > 1}
    if duplicated:
        return GuardFinding(
            guard=GuardKind.DUPLICATION,
            action=GuardAction.DOWNGRADE,
            reason="duplicated_source_family_influence",
            severity=min(1.0, max(len(value) for value in duplicated.values()) / 4.0),
            influence_cap=0.5,
            affected_families=tuple(duplicated),
            affected_agent_ids=tuple(
                agent for agents in duplicated.values() for agent in agents
            ),
            evidence_ids=evidence_ids(context),
        )
    return GuardFinding(
        guard=GuardKind.DUPLICATION,
        action=GuardAction.OBSERVE,
        reason="source_families_are_unique",
        severity=0.0,
        evidence_ids=evidence_ids(context),
    )
