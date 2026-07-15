"""Constitutional market-prior identity and anchoring guard."""

from __future__ import annotations

from ._shared import evidence_ids, family, forecast_messages
from .context import GuardContext
from .models import GuardAction, GuardFinding, GuardKind


REVIEWED_MARKET_PRIOR_FLOOR = 0.50


def review_market_prior(context: GuardContext) -> GuardFinding:
    priors = tuple(
        message
        for message in forecast_messages(context)
        if message.payload.get("organism_role") == "market_prior"
    )
    if len(priors) != 1 or family(priors[0]) != "market-price":
        return GuardFinding(
            guard=GuardKind.MARKET_PRIOR,
            action=GuardAction.REQUIRE_ABSTENTION,
            reason="unique_market_price_prior_missing",
            severity=1.0,
            influence_cap=0.0,
            affected_agent_ids=tuple(message.sender for message in priors),
            evidence_ids=evidence_ids(context),
        )
    return GuardFinding(
        guard=GuardKind.MARKET_PRIOR,
        action=GuardAction.REQUIRE_MARKET_PRIOR,
        reason="reviewed_market_prior_floor_required",
        severity=0.0,
        affected_families=("market-price",),
        affected_agent_ids=(priors[0].sender,),
        evidence_ids=evidence_ids(context),
    )
