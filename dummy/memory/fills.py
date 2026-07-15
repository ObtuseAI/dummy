"""Fill memory keeps witnessed execution truth separate from simulation."""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .schema import (
    EvidenceReality,
    MemoryKind,
    MemoryRecord,
    MemoryValidationError,
)


class FillOutcome(str, Enum):
    ORDER_UNFILLED = "ORDER_UNFILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_FILLED = "ORDER_FILLED"


def fill_memory(
    *,
    fill_id: str,
    event_cluster_id: str,
    observed_at: datetime,
    received_at: datetime,
    recorded_at: datetime,
    source: str,
    source_reference: str,
    outcome: FillOutcome,
    witnessed: bool,
    simulated: bool,
    quantity: int,
    price_cents: int | None,
    fee_cents: int,
    slippage_cents: int | None,
    evidence_ids: tuple[str, ...],
    causal_parent_ids: tuple[str, ...] = (),
    details: Mapping[str, Any] | None = None,
) -> MemoryRecord:
    if witnessed is simulated:
        raise MemoryValidationError(
            "fill memory must be exactly one of witnessed or simulated"
        )
    if isinstance(quantity, bool) or quantity < 0:
        raise MemoryValidationError("fill quantity must be non-negative")
    for name, value in (
        ("price_cents", price_cents),
        ("fee_cents", fee_cents),
        ("slippage_cents", slippage_cents),
    ):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise MemoryValidationError(f"{name} must be a non-negative integer")
    if outcome is FillOutcome.ORDER_UNFILLED:
        if quantity != 0 or price_cents is not None:
            raise MemoryValidationError("unfilled orders cannot contain fill price or size")
    elif quantity <= 0 or price_cents is None:
        raise MemoryValidationError("filled outcomes require positive size and price")
    if price_cents is not None and not 1 <= price_cents <= 99:
        raise MemoryValidationError("fill price must be in [1, 99]")
    payload = {
        "outcome": outcome.value,
        "witnessed": witnessed,
        "simulated": simulated,
        "realized_capital_pnl": witnessed,
        "quantity": quantity,
        "price_cents": price_cents,
        "fee_cents": fee_cents,
        "slippage_cents": slippage_cents,
        "details": dict(details or {}),
    }
    if any(
        isinstance(value, float) and not math.isfinite(value)
        for value in payload["details"].values()
    ):
        raise MemoryValidationError("fill details contain non-finite values")
    return MemoryRecord.create(
        kind=MemoryKind.FILL,
        entity_id=fill_id,
        event_cluster_id=event_cluster_id,
        observed_at=observed_at,
        received_at=received_at,
        recorded_at=recorded_at,
        source=source,
        source_reference=source_reference,
        evidence_reality=(
            EvidenceReality.WITNESSED_FILL
            if witnessed
            else EvidenceReality.SIMULATED
        ),
        provenance_verified=witnessed,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=evidence_ids,
        payload=payload,
    )


__all__ = ["FillOutcome", "fill_memory"]
