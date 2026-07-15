"""Explicit non-skippable component lifecycle for vNext promotion."""

from __future__ import annotations

from enum import Enum


class PromotionState(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    QUARANTINED = "QUARANTINED"
    SHADOW_ONLY = "SHADOW_ONLY"
    REPLAY_VALIDATED = "REPLAY_VALIDATED"
    FORWARD_PAPER = "FORWARD_PAPER"
    CONTESTED_VALIDATED = "CONTESTED_VALIDATED"
    FILL_VALIDATED = "FILL_VALIDATED"
    CANARY_ELIGIBLE = "CANARY_ELIGIBLE"
    PROMOTED = "PROMOTED"
    DEGRADED = "DEGRADED"
    RETIRED = "RETIRED"


_ALLOWED_TRANSITIONS: dict[PromotionState, frozenset[PromotionState]] = {
    PromotionState.EXPERIMENTAL: frozenset(
        {PromotionState.QUARANTINED, PromotionState.SHADOW_ONLY}
    ),
    PromotionState.QUARANTINED: frozenset(
        {PromotionState.EXPERIMENTAL, PromotionState.RETIRED}
    ),
    PromotionState.SHADOW_ONLY: frozenset(
        {PromotionState.QUARANTINED, PromotionState.REPLAY_VALIDATED}
    ),
    PromotionState.REPLAY_VALIDATED: frozenset(
        {PromotionState.QUARANTINED, PromotionState.FORWARD_PAPER}
    ),
    PromotionState.FORWARD_PAPER: frozenset(
        {PromotionState.QUARANTINED, PromotionState.CONTESTED_VALIDATED}
    ),
    PromotionState.CONTESTED_VALIDATED: frozenset(
        {PromotionState.DEGRADED, PromotionState.FILL_VALIDATED}
    ),
    PromotionState.FILL_VALIDATED: frozenset(
        {PromotionState.DEGRADED, PromotionState.CANARY_ELIGIBLE}
    ),
    PromotionState.CANARY_ELIGIBLE: frozenset(
        {PromotionState.DEGRADED, PromotionState.PROMOTED}
    ),
    PromotionState.PROMOTED: frozenset(
        {PromotionState.DEGRADED, PromotionState.RETIRED}
    ),
    PromotionState.DEGRADED: frozenset(
        {PromotionState.QUARANTINED, PromotionState.RETIRED}
    ),
    PromotionState.RETIRED: frozenset(),
}


def transition_allowed(current: PromotionState, requested: PromotionState) -> bool:
    return requested in _ALLOWED_TRANSITIONS[current]


def require_valid_transition(current: PromotionState, requested: PromotionState) -> None:
    if not transition_allowed(current, requested):
        raise ValueError(f"promotion lifecycle transition would skip a gate: {current.value}->{requested.value}")


__all__ = ["PromotionState", "require_valid_transition", "transition_allowed"]
