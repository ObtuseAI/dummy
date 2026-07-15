"""Unsupported-confidence guard."""

from __future__ import annotations

import math

from dummy.protocols import MessageType

from ._shared import evidence_ids, family, forecast_messages
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


def review_confidence(context: GuardContext) -> GuardFinding:
    forecasts = forecast_messages(context)
    for message in forecasts:
        uncertainty = message.payload.get("uncertainty")
        if (
            not isinstance(uncertainty, (int, float))
            or isinstance(uncertainty, bool)
            or not math.isfinite(float(uncertainty))
            or not 0.0 <= float(uncertainty) <= 0.5
        ):
            return GuardFinding(
                guard=GuardKind.CONFIDENCE,
                action=GuardAction.VETO,
                reason=f"unsupported_uncertainty:{message.sender}",
                severity=1.0,
                influence_cap=0.0,
                affected_families=(family(message),) if family(message) else (),
                affected_agent_ids=(message.sender,),
                evidence_ids=evidence_ids(context),
            )
    calibration = tuple(
        message
        for message in context.messages
        if message.message_type is MessageType.CALIBRATION_UPDATE
    )
    if len(calibration) != 1 or calibration[0].payload.get("verified_map") is not True:
        specialists = tuple(
            message
            for message in forecasts
            if message.payload.get("organism_role") == "specialist"
        )
        affected = tuple(family(message) for message in specialists if family(message))
        return GuardFinding(
            guard=GuardKind.CONFIDENCE,
            action=GuardAction.DOWNGRADE,
            reason="specialist_calibration_map_unverified",
            severity=0.5,
            influence_cap=0.75,
            affected_families=affected,
            affected_agent_ids=tuple(message.sender for message in specialists),
            evidence_ids=evidence_ids(context),
        )
    return GuardFinding(
        guard=GuardKind.CONFIDENCE,
        action=GuardAction.OBSERVE,
        reason="forecast_uncertainty_typed_and_calibration_verified",
        severity=0.0,
        evidence_ids=evidence_ids(context),
    )
